"""
gRPC server implementing the TaxEngine service defined in tax_service.proto.
"""

import logging
from concurrent import futures
from pathlib import Path

import grpc
from grpc_reflection.v1alpha import reflection

from app.config import settings
from app.core.tax_engine import TaxEngine
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


class TaxEngineServicer(pb2_grpc.TaxEngineServicer):
    """gRPC service implementation for TaxEngine."""

    def __init__(self) -> None:
        self.rag_service = _init_rag_service()
        self.engine = TaxEngine(rag_service=self.rag_service)
        self.doc_processor = DocumentProcessor()

    async def ProcessMessage(self, request, context):
        """Process a user's tax-related message."""
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

            result = await self.engine.process_message(
                message=request.message,
                customer_type=customer_type,
                session_context=session_context,
            )
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
            result = {
                "reply": (
                    "Xin lỗi, hệ thống đang xử lý không thành công. "
                    "Bạn vui lòng thử lại hoặc đặt câu hỏi khác nhé."
                ),
                "actions": [],
                "references": [],
                "confidence": 0.0,
            }

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


async def serve_grpc() -> grpc.aio.Server:
    """Start the gRPC server."""
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
