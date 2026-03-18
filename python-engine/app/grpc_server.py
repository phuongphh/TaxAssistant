"""
gRPC server implementing the TaxEngine service defined in tax_service.proto.
"""

import logging
import uuid as uuid_mod
from concurrent import futures
from pathlib import Path

import grpc
from grpc_reflection.v1alpha import reflection

from app.config import settings
from app.core.tax_engine import TaxEngine
from app.core.memory import build_memory_context
from app.core.onboarding import OnboardingHandler
from app.core.case_manager import CaseManager
from app.db.database import async_session, engine as db_engine
from app.db.models import Base
from app.db.customer_repository import CustomerRepository
from app.db.case_repository import CaseRepository
from app.db.summary_repository import SummaryRepository
from app.documents.processor import DocumentProcessor

logger = logging.getLogger(__name__)

# Load generated proto stubs dynamically
PROTO_PATH = str(Path(__file__).resolve().parent.parent.parent / "proto" / "tax_service.proto")


def _load_proto():
    """Load proto using grpc_tools for dynamic stub generation."""
    from grpc_tools import protoc
    import importlib
    import sys
    import tempfile

    out_dir = tempfile.mkdtemp()
    protoc.main([
        "grpc_tools.protoc",
        f"-I{Path(PROTO_PATH).parent}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
        str(PROTO_PATH),
    ])

    sys.path.insert(0, out_dir)
    pb2 = importlib.import_module("tax_service_pb2")
    pb2_grpc = importlib.import_module("tax_service_pb2_grpc")
    return pb2, pb2_grpc


# Proto modules (loaded at import time)
pb2, pb2_grpc = _load_proto()

# Map proto CustomerType enum to string
_CUSTOMER_TYPE_MAP = {
    0: "unknown",
    1: "sme",
    2: "household",
    3: "individual",
}


def _init_rag_service():
    """Initialize RAG service (optional, graceful fallback if unavailable)."""
    try:
        from app.ai.embeddings import EmbeddingService
        from app.ai.llm_client import LLMClient
        from app.ai.rag_service import RAGService

        embedding = EmbeddingService()
        doc_count = embedding.get_document_count()
        logger.info("ChromaDB initialized: %d documents in vector store", doc_count)
        if doc_count == 0:
            logger.warning(
                "ChromaDB is EMPTY. Run seed_loader to index tax regulations: "
                "docker compose exec tax-engine python -m data.seed_loader"
            )

        llm = LLMClient()
        rag = RAGService(embedding, llm)
        logger.info("RAG service initialized successfully (LLM + ChromaDB)")
        return rag
    except Exception as e:
        logger.warning(
            "RAG service unavailable - running WITHOUT LLM/vector search. "
            "Reason: %s: %s. "
            "Ensure ANTHROPIC_API_KEY is set in environment.",
            type(e).__name__,
            e,
        )
        return None


async def _ensure_tables(max_retries: int = 3, base_delay: float = 2.0):
    """Create new tables if they don't exist (idempotent).

    Retries with exponential backoff on transient database errors.
    """
    import asyncio

    for attempt in range(1, max_retries + 1):
        try:
            async with db_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables ensured")
            return
        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Database connection failed (attempt %d/%d): %s: %s — retrying in %.1fs",
                    attempt, max_retries, type(e).__name__, e, delay,
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    "Database connection failed after %d attempts: %s: %s",
                    max_retries, type(e).__name__, e,
                )
                raise


class TaxEngineServicer(pb2_grpc.TaxEngineServicer):
    """gRPC service implementation for TaxEngine."""

    def __init__(self) -> None:
        self.rag_service = _init_rag_service()
        self.engine = TaxEngine(rag_service=self.rag_service)
        self.doc_processor = DocumentProcessor()
        self.onboarding = OnboardingHandler()

    # Maximum time (seconds) for the engine to process a single message.
    # Must be LESS than the gRPC deadline set by the gateway (180s) to
    # guarantee we always return a response instead of letting the deadline
    # fire silently.
    _ENGINE_TIMEOUT = 150.0

    async def ProcessMessage(self, request, context):
        """Process a user's tax-related message."""
        import asyncio
        import time

        start = time.monotonic()
        logger.info(
            "gRPC ProcessMessage: request_id=%s msg='%s'",
            request.request_id,
            request.message[:100],
        )

        try:
            customer_type = _CUSTOMER_TYPE_MAP.get(request.context.customer_type, "unknown")

            session_context = {
                "session_id": request.context.session_id,
                "user_id": request.context.user_id,
                "metadata": dict(request.context.metadata),
            }

            # Extract conversation history from gRPC request
            conversation_history = [
                {"role": entry.role, "content": entry.content}
                for entry in request.conversation_history
            ]

            # Extract customer profile from request (if provided by gateway)
            customer_profile = None
            if request.HasField("customer_profile") and request.customer_profile.customer_id:
                customer_profile = {
                    "customer_id": request.customer_profile.customer_id,
                    "customer_type": request.customer_profile.customer_type,
                    "business_name": request.customer_profile.business_name,
                    "tax_code": request.customer_profile.tax_code,
                    "industry": request.customer_profile.industry,
                    "province": request.customer_profile.province,
                    "annual_revenue_range": request.customer_profile.annual_revenue_range,
                    "onboarding_step": request.customer_profile.onboarding_step,
                    "tax_profile": dict(request.customer_profile.tax_profile),
                    "notes": [{"note": n} for n in request.customer_profile.recent_notes],
                }
                # Use customer_type from profile if available
                if customer_profile["customer_type"] and customer_profile["customer_type"] != "unknown":
                    customer_type = customer_profile["customer_type"]

            # Extract active cases
            active_cases = [
                {
                    "case_id": c.case_id,
                    "service_type": c.service_type,
                    "title": c.title,
                    "status": c.status,
                    "current_step": c.current_step,
                }
                for c in request.active_cases
            ]

            # Conversation summaries
            summaries = list(request.conversation_summaries)

            logger.info(
                "Context: history=%d profile=%s cases=%d summaries=%d session=%s",
                len(conversation_history),
                "yes" if customer_profile else "no",
                len(active_cases),
                len(summaries),
                request.context.session_id,
            )

            # Check if customer is in onboarding flow
            if customer_profile and customer_profile.get("onboarding_step") in ("new", "collecting_type", "collecting_info"):
                coro = self._handle_onboarding(
                    request, customer_profile, customer_type
                )
            else:
                # Build memory context for LLM
                memory_context = build_memory_context(
                    customer=customer_profile,
                    active_cases=active_cases,
                    recent_summaries=summaries,
                )

                coro = self.engine.process_message(
                    message=request.message,
                    customer_type=customer_type,
                    session_context=session_context,
                    conversation_history=conversation_history,
                    memory_context=memory_context,
                )

            # Enforce a hard timeout so we ALWAYS return a response before
            # the gRPC deadline fires.  Without this, slow LLM/DB calls
            # could exceed the 180s deadline and the client gets nothing.
            try:
                result = await asyncio.wait_for(coro, timeout=self._ENGINE_TIMEOUT)
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - start
                logger.error(
                    "ProcessMessage TIMEOUT: request_id=%s elapsed=%.2fs (limit=%.0fs)",
                    request.request_id, elapsed, self._ENGINE_TIMEOUT,
                )
                result = {
                    "reply": (
                        "Xin lỗi, hệ thống xử lý quá lâu. "
                        "Bạn vui lòng thử lại với câu hỏi ngắn gọn hơn hoặc "
                        "sử dụng tính năng tính thuế cơ bản."
                    ),
                    "actions": [
                        {"label": "Tính thuế", "action_type": "quick_reply", "payload": "tính thuế"},
                        {"label": "Hạn nộp thuế", "action_type": "quick_reply", "payload": "hạn nộp thuế"},
                    ],
                    "references": [],
                    "confidence": 0.0,
                    "intent": "timeout",
                }

            elapsed = time.monotonic() - start
            logger.info(
                "ProcessMessage OK: request_id=%s intent=%s elapsed=%.2fs",
                request.request_id,
                result.get("intent", "?"),
                elapsed,
            )
        except Exception as e:
            elapsed = time.monotonic() - start
            logger.exception(
                "ProcessMessage FAILED: request_id=%s error=%s: %s elapsed=%.2fs",
                request.request_id,
                type(e).__name__,
                e,
                elapsed,
            )
            result = self._build_error_result(e)

        # Build proto response
        actions = [
            pb2.SuggestedAction(
                label=a.get("label", ""),
                action_type=a.get("action_type", ""),
                payload=a.get("payload", ""),
            )
            for a in result.get("actions", [])
        ]

        references = [
            pb2.TaxReference(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("snippet", ""),
            )
            for r in result.get("references", [])
        ]

        return pb2.TaxResponse(
            request_id=request.request_id,
            reply=result.get("reply", ""),
            actions=actions,
            references=references,
            confidence=result.get("confidence", 0.0),
        )

    @staticmethod
    def _build_error_result(error: Exception) -> dict:
        """Build a user-facing error result with specific messaging per error type."""
        from app.ai.llm_client import LLMCreditError, LLMAuthError, LLMRateLimitError, LLMOverloadedError, LLMError

        if isinstance(error, LLMCreditError):
            reply = (
                "⚠️ Hệ thống AI tạm thời không khả dụng do hết hạn mức sử dụng API. "
                "Đội ngũ kỹ thuật đã được thông báo.\n\n"
                "Trong lúc chờ khắc phục, bạn vẫn có thể:\n"
                "• Sử dụng các tính năng tính thuế cơ bản (VD: \"tính thuế GTGT 500 triệu\")\n"
                "• Tra cứu hạn nộp thuế\n"
                "• Xem thông tin thuế tổng quát\n\n"
                "Xin lỗi vì sự bất tiện này!"
            )
        elif isinstance(error, LLMAuthError):
            reply = (
                "⚠️ Hệ thống AI gặp lỗi cấu hình. "
                "Đội ngũ kỹ thuật đã được thông báo và đang xử lý.\n\n"
                "Bạn vẫn có thể sử dụng các tính năng tính thuế cơ bản."
            )
        elif isinstance(error, LLMRateLimitError):
            reply = (
                "Hệ thống đang nhận nhiều yêu cầu cùng lúc. "
                "Vui lòng thử lại sau 1-2 phút nhé."
            )
        elif isinstance(error, LLMOverloadedError):
            reply = (
                "Hệ thống AI đang quá tải tạm thời. "
                "Vui lòng thử lại sau ít phút."
            )
        elif isinstance(error, LLMError):
            reply = (
                "Xin lỗi, hệ thống AI gặp sự cố tạm thời. "
                "Bạn vui lòng thử lại hoặc đặt câu hỏi khác nhé."
            )
        else:
            reply = (
                "Xin lỗi, hệ thống đang xử lý không thành công. "
                "Bạn vui lòng thử lại hoặc đặt câu hỏi khác nhé."
            )

        # Encode error_type in reply metadata so gateway can detect it
        error_type = getattr(error, "error_type", "unknown")

        return {
            "reply": reply,
            "actions": [],
            "references": [],
            "confidence": 0.0,
            "error_type": error_type,
        }

    async def _handle_onboarding(self, request, customer_profile: dict, customer_type: str) -> dict:
        """Handle messages during onboarding flow."""
        onboarding_result = self.onboarding.process_step(customer_profile, request.message)

        # Persist onboarding updates to DB
        update_fields = onboarding_result.get("update_fields", {})
        if update_fields:
            saved = False
            for attempt in range(3):
                try:
                    async with async_session() as session:
                        repo = CustomerRepository(session)
                        cid = uuid_mod.UUID(customer_profile["customer_id"])
                        await repo.update_profile(cid, **update_fields)
                        await session.commit()
                    saved = True
                    break
                except Exception as e:
                    logger.warning(
                        "Failed to save onboarding data (attempt %d/3): %s", attempt + 1, e
                    )
            if not saved:
                logger.error(
                    "Onboarding DB update failed after 3 attempts for customer %s, "
                    "fields=%s — user will see a stale onboarding step on next message",
                    customer_profile.get("customer_id"),
                    list(update_fields.keys()),
                )

        return {
            "reply": onboarding_result["reply"],
            "actions": onboarding_result.get("actions", []),
            "references": [],
            "confidence": 1.0,
            "intent": "onboarding",
        }

    async def ProcessMessageStream(self, request, context):
        """Stream response for long-running operations."""
        # Process message normally first
        result = await self.engine.process_message(
            message=request.message,
            customer_type=_CUSTOMER_TYPE_MAP.get(request.context.customer_type, "unknown"),
        )

        reply = result.get("reply", "")
        # Stream in chunks
        chunk_size = 100
        for i in range(0, len(reply), chunk_size):
            chunk = reply[i:i + chunk_size]
            is_final = (i + chunk_size) >= len(reply)
            yield pb2.TaxStreamChunk(
                request_id=request.request_id,
                chunk=chunk,
                is_final=is_final,
            )

    async def LookupRegulation(self, request, context):
        """Lookup tax regulation using RAG vector search."""
        logger.info("gRPC LookupRegulation: query=%s", request.query)

        if not self.rag_service:
            return pb2.RegulationResponse(
                regulations=[],
                summary="Chức năng tra cứu văn bản chưa được kích hoạt (cần cấu hình LLM/ChromaDB).",
            )

        category = request.category if request.category else None
        rag_result = await self.rag_service.query(
            question=request.query,
            tax_category=category,
            n_results=request.max_results or 5,
        )

        regulations = [
            pb2.TaxReference(
                title=s.get("title", ""),
                url=s.get("url", ""),
                snippet=s.get("snippet", ""),
            )
            for s in rag_result.sources
        ]

        return pb2.RegulationResponse(
            regulations=regulations,
            summary=rag_result.answer,
        )

    async def ProcessDocument(self, request, context):
        """Process uploaded tax document."""
        logger.info("gRPC ProcessDocument: request_id=%s, type=%s", request.request_id, request.document_type)

        result = await self.doc_processor.process(
            file_url=request.file_url,
            mime_type=request.mime_type,
            document_type=request.document_type,
        )

        return pb2.DocumentResponse(
            request_id=request.request_id,
            extracted_data=result.extracted_data,
            summary=result.summary,
            warnings=result.warnings,
        )


    # ================================================================
    # Customer Profile RPCs
    # ================================================================

    async def GetOrCreateCustomer(self, request, context):
        """Get or create a customer profile."""
        logger.info("gRPC GetOrCreateCustomer: %s/%s", request.channel, request.channel_user_id)
        async with async_session() as session:
            repo = CustomerRepository(session)
            customer, is_new = await repo.get_or_create(request.channel, request.channel_user_id)
            await session.commit()
            return self._customer_to_proto(customer)

    async def UpdateCustomerProfile(self, request, context):
        """Update customer profile fields."""
        logger.info("gRPC UpdateCustomerProfile: %s", request.customer_id)
        async with async_session() as session:
            repo = CustomerRepository(session)
            cid = uuid_mod.UUID(request.customer_id)
            fields = dict(request.fields)
            customer = await repo.update_profile(cid, **fields)
            await session.commit()
            if not customer:
                context.abort(grpc.StatusCode.NOT_FOUND, "Customer not found")
            return self._customer_to_proto(customer)

    # ================================================================
    # Support Case RPCs
    # ================================================================

    async def GetActiveCases(self, request, context):
        """Get active support cases for a customer."""
        logger.info("gRPC GetActiveCases: customer=%s", request.customer_id)
        async with async_session() as session:
            repo = CaseRepository(session)
            cid = uuid_mod.UUID(request.customer_id)
            cases = await repo.get_active_cases(cid)
            return pb2.ActiveCasesResponse(
                cases=[self._case_to_proto(c) for c in cases]
            )

    async def CreateSupportCase(self, request, context):
        """Create a new support case."""
        logger.info("gRPC CreateSupportCase: customer=%s type=%s", request.customer_id, request.service_type)
        async with async_session() as session:
            repo = CaseRepository(session)
            cid = uuid_mod.UUID(request.customer_id)
            case = await repo.create(
                customer_id=cid,
                service_type=request.service_type,
                title=request.service_type,
                context=dict(request.context) if request.context else None,
            )
            await session.commit()
            return self._case_to_proto(case)

    async def UpdateSupportCase(self, request, context):
        """Update a support case step/status."""
        logger.info("gRPC UpdateSupportCase: case=%s", request.case_id)
        async with async_session() as session:
            repo = CaseRepository(session)
            cid = uuid_mod.UUID(request.case_id)
            step_data = dict(request.step_data) if request.step_data else None
            case = await repo.update_step(
                case_id=cid,
                current_step=request.current_step,
                step_data=step_data,
                status=request.status if request.status else None,
            )
            await session.commit()
            if not case:
                context.abort(grpc.StatusCode.NOT_FOUND, "Case not found")
            return self._case_to_proto(case)

    # ================================================================
    # Proto conversion helpers
    # ================================================================

    def _customer_to_proto(self, customer):
        """Convert Customer ORM model to proto message."""
        notes = customer.notes or []
        recent_notes = [n.get("note", "") for n in notes[-5:]] if notes else []
        tax_profile = customer.tax_profile or {}
        tax_profile_str = {k: str(v) for k, v in tax_profile.items()}

        return pb2.CustomerProfileMsg(
            customer_id=str(customer.id),
            channel=customer.channel or "",
            channel_user_id=customer.channel_user_id or "",
            customer_type=customer.customer_type or "unknown",
            business_name=customer.business_name or "",
            tax_code=customer.tax_code or "",
            industry=customer.industry or "",
            province=customer.province or "",
            annual_revenue_range=customer.annual_revenue_range or "",
            employee_count_range=customer.employee_count_range or "",
            onboarding_step=customer.onboarding_step or "new",
            tax_profile=tax_profile_str,
            recent_notes=recent_notes,
        )

    def _case_to_proto(self, case):
        """Convert SupportCase ORM model to proto message."""
        ctx = case.context or {}
        ctx_str = {k: str(v) for k, v in ctx.items()}
        return pb2.SupportCaseMsg(
            case_id=str(case.id),
            customer_id=str(case.customer_id),
            service_type=case.service_type or "",
            title=case.title or "",
            status=case.status or "",
            current_step=case.current_step or "",
            context=ctx_str,
            created_at=case.created_at.isoformat() if case.created_at else "",
            updated_at=case.updated_at.isoformat() if case.updated_at else "",
        )


async def serve_grpc() -> grpc.aio.Server:
    """Start the gRPC server.

    Handles database initialization failures gracefully — if the database
    is unreachable the server still starts (DB-dependent RPCs will fail
    individually rather than preventing all message processing).
    """
    # Ensure database tables exist (retry with backoff)
    try:
        await _ensure_tables()
    except Exception:
        logger.error(
            "Could not connect to database — starting gRPC server WITHOUT "
            "database support. Customer profiles and support cases will be "
            "unavailable until the database is reachable."
        )

    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    pb2_grpc.add_TaxEngineServicer_to_server(TaxEngineServicer(), server)

    # Enable reflection for debugging tools like grpcurl
    service_names = (
        pb2.DESCRIPTOR.services_by_name["TaxEngine"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(service_names, server)

    address = f"{settings.grpc_host}:{settings.grpc_port}"
    server.add_insecure_port(address)
    await server.start()
    logger.info("gRPC server started on %s", address)
    return server
