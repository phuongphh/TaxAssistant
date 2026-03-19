"""
Tax Engine - Central orchestrator for tax-related queries.
Coordinates between intent classification, tax rules, AI/RAG, and NLP.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.intent_classifier import ClassificationResult, Intent, IntentClassifier
from app.core.onboarding import OnboardingHandler
from app.core.suggestions import format_suggestions, generate_suggestions
from app.core.tax_rules.base import CustomerType, TaxCategory, TaxContext, TaxResult
from app.core.tax_rules.cit import CITRule
from app.core.tax_rules.license_tax import LicenseTaxRule
from app.core.tax_rules.pit import PITRule
from app.core.tax_rules.vat import VATRule

if TYPE_CHECKING:
    from app.ai.rag_service import RAGService

logger = logging.getLogger(__name__)


class TaxEngine:
    """
    Main Tax Engine that processes user queries.

    Pipeline:
    1. Classify intent (keyword-based + LLM fallback)
    2. Extract entities from the message
    3. Route to appropriate handler (tax rules, RAG, etc.)
    4. Format and return response
    """

    def __init__(self, rag_service: RAGService | None = None) -> None:
        self.classifier = IntentClassifier()
        self.rag = rag_service

        # Register tax rules
        self.tax_rules = {
            TaxCategory.VAT: VATRule(),
            TaxCategory.CIT: CITRule(),
            TaxCategory.PIT: PITRule(),
            TaxCategory.LICENSE: LicenseTaxRule(),
        }

    async def process_message(
        self,
        message: str,
        customer_type: str = "unknown",
        session_context: dict | None = None,
        conversation_history: list[dict] | None = None,
        memory_context: str = "",
    ) -> dict:
        """
        Process a tax-related message and return a response.

        Args:
            conversation_history: List of {"role": "user"|"assistant", "content": str}
                from previous turns in this session.
            memory_context: Long-term memory context string to inject into LLM prompts.

        Returns:
            dict with keys: reply, actions, references, confidence, category
        """
        ct = CustomerType(customer_type) if customer_type in CustomerType.__members__.values() else CustomerType.UNKNOWN
        history = conversation_history or []

        # 0. Check for numeric service selection (from onboarding menu buttons)
        # Only match short messages (single number like "1"-"8") to avoid
        # intercepting full natural-language questions that happen to contain
        # keywords like "kê khai" or "tính thuế".
        msg_stripped = message.strip()
        if msg_stripped in ("1", "2", "3", "4", "5", "6", "7", "8"):
            service_type = OnboardingHandler.parse_service_selection(msg_stripped)
            if service_type:
                return self._route_service_selection(service_type, ct, memory_context)

        # 1. Classify intent
        classification = self.classifier.classify(message)
        logger.info(
            "Classified: intent=%s category=%s confidence=%.2f rag=%s history=%d memory=%d msg='%s'",
            classification.intent.value,
            classification.tax_category.value if classification.tax_category else "none",
            classification.confidence,
            "yes" if self.rag else "no",
            len(history),
            len(memory_context),
            message[:80],
        )

        # 2. Route to appropriate handler
        if classification.intent == Intent.GREETING:
            return self._build_response(
                reply=self._get_greeting(ct),
                classification=classification,
            )

        if classification.intent == Intent.HELP:
            return self._build_response(
                reply=self._get_help_text(ct),
                classification=classification,
            )

        # When conversation history exists, route follow-up messages through
        # LLM so the model can reference previous turns (e.g. "tôi là hộ kinh
        # doanh" from an earlier message).  Only GREETING, HELP, TAX_CALCULATE,
        # and TAX_DEADLINE are exempt because they don't need conversational
        # context.
        if history and classification.intent not in (Intent.TAX_CALCULATE, Intent.TAX_DEADLINE):
            return await self._handle_contextual_query(message, classification, ct, history, memory_context)

        if classification.intent == Intent.TAX_CALCULATE:
            return await self._handle_calculation(classification, ct, memory_context)

        if classification.intent == Intent.TAX_INFO:
            return await self._handle_tax_info(classification, ct, message, history, memory_context)

        if classification.intent == Intent.TAX_DEADLINE:
            return self._build_response(
                reply=self._get_deadline_info(classification.tax_category, ct),
                classification=classification,
            )

        if classification.intent == Intent.TAX_PROCEDURE:
            return await self._handle_procedure(classification, ct, message, history, memory_context)

        if classification.intent == Intent.REGISTRATION:
            return await self._handle_registration(classification, ct, message, history, memory_context)

        if classification.intent == Intent.DECLARATION:
            return await self._handle_declaration(classification, ct, message, history, memory_context)

        if classification.intent == Intent.PENALTY:
            return await self._handle_penalty(classification, ct, message, history, memory_context)

        # Unknown intent → use RAG/LLM for general answer
        return await self._handle_general_query(message, classification, ct, history, memory_context)

    def _route_service_selection(
        self, service_type: str, customer_type: CustomerType, memory_context: str = "",
    ) -> dict:
        """Route a numeric/keyword service selection from the onboarding menu
        into the appropriate intent handler by synthesizing a ClassificationResult."""
        from app.core.onboarding import SERVICE_TITLE_MAP

        service_intent_map = {
            "tax_calculation": (Intent.TAX_CALCULATE, None),
            "tax_declaration": (Intent.DECLARATION, None),
            "tax_registration": (Intent.REGISTRATION, None),
            "tax_consultation": (Intent.TAX_INFO, None),
            "invoice_check": (Intent.DOCUMENT_CHECK, None),
            "penalty_consultation": (Intent.PENALTY, None),
            "tax_refund": (Intent.TAX_PROCEDURE, None),
            "annual_settlement": (Intent.DECLARATION, None),
        }

        intent, category = service_intent_map.get(service_type, (Intent.UNKNOWN, None))
        title = SERVICE_TITLE_MAP.get(service_type, service_type)

        classification = ClassificationResult(
            intent=intent,
            tax_category=category,
            confidence=0.9,
            extracted_entities={},
        )

        logger.info("Service selection: type=%s → intent=%s title='%s'", service_type, intent.value, title)

        # For calculation, ask which tax type
        if intent == Intent.TAX_CALCULATE:
            return self._build_response(
                reply=(
                    "Bạn muốn tính loại thuế nào?\n"
                    "• Thuế GTGT (VAT)\n"
                    "• Thuế TNDN (CIT)\n"
                    "• Thuế TNCN (PIT)\n"
                    "• Thuế Môn bài"
                ),
                classification=classification,
                actions=[
                    {"label": "Thuế GTGT", "action_type": "quick_reply", "payload": "tính thuế GTGT"},
                    {"label": "Thuế TNDN", "action_type": "quick_reply", "payload": "tính thuế TNDN"},
                    {"label": "Thuế TNCN", "action_type": "quick_reply", "payload": "tính thuế TNCN"},
                    {"label": "Thuế Môn bài", "action_type": "quick_reply", "payload": "tính thuế môn bài"},
                ],
            )

        # For info/consultation, provide tax overview
        if intent == Intent.TAX_INFO:
            overview = self._get_tax_overview(customer_type)
            return self._build_response(reply=overview, classification=classification)

        # For declaration
        if intent == Intent.DECLARATION:
            return self._build_response(
                reply=(
                    "Về kê khai thuế:\n\n"
                    "📋 Các tờ khai phổ biến:\n"
                    "• Mẫu 01/GTGT - Tờ khai thuế GTGT (hàng tháng/quý)\n"
                    "• Mẫu 03/TNDN - Tờ khai tạm tính thuế TNDN (quý)\n"
                    "• Mẫu 02/KK-TNCN - Tờ khai thuế TNCN\n"
                    "• Mẫu 01/MBAI - Tờ khai thuế môn bài\n\n"
                    "Bạn muốn tìm hiểu về tờ khai nào?"
                ),
                classification=classification,
            )

        # For registration
        if intent == Intent.REGISTRATION:
            return self._build_response(
                reply=(
                    "Để đăng ký mã số thuế, bạn cần:\n\n"
                    "1. Tờ khai đăng ký thuế (Mẫu 01-ĐK-TCT hoặc 03-ĐK-TCT)\n"
                    "2. Bản sao CCCD/CMND\n"
                    "3. Giấy chứng nhận ĐKKD\n\n"
                    "Bạn muốn biết thêm chi tiết không?"
                ),
                classification=classification,
            )

        # For penalty
        if intent == Intent.PENALTY:
            return self._build_response(
                reply=(
                    "Về xử phạt vi phạm thuế:\n\n"
                    "⚠️ Chậm nộp tờ khai: 2-5 triệu VND\n"
                    "⚠️ Chậm nộp tiền thuế: 0.03%/ngày\n"
                    "⚠️ Khai sai: 20% số thuế khai thiếu\n\n"
                    "Bạn cần tư vấn trường hợp cụ thể nào?"
                ),
                classification=classification,
            )

        # For document check
        if intent == Intent.DOCUMENT_CHECK:
            return self._build_response(
                reply=(
                    "Tôi có thể giúp kiểm tra hóa đơn, chứng từ.\n\n"
                    "Bạn hãy gửi hình ảnh hóa đơn hoặc mô tả thông tin cần kiểm tra."
                ),
                classification=classification,
            )

        # For procedure (tax refund, etc.)
        if intent == Intent.TAX_PROCEDURE:
            return self._build_response(
                reply=(
                    "Về thủ tục thuế, tôi có thể hỗ trợ:\n"
                    "• Đăng ký thuế lần đầu\n"
                    "• Kê khai thuế hàng quý/năm\n"
                    "• Quyết toán thuế\n"
                    "• Hoàn thuế GTGT\n\n"
                    "Bạn cần hỗ trợ thủ tục nào?"
                ),
                classification=classification,
            )

        # Fallback
        return self._build_service_menu_response(classification, customer_type, memory_context)

    async def _handle_calculation(
        self, classification: ClassificationResult, customer_type: CustomerType,
        memory_context: str = "",
    ) -> dict:
        """Handle tax calculation requests."""
        category = classification.tax_category
        entities = classification.extracted_entities

        if not category:
            # Ask which tax type
            return self._build_response(
                reply=(
                    "Bạn muốn tính loại thuế nào?\n"
                    "• Thuế GTGT (VAT)\n"
                    "• Thuế TNDN (CIT)\n"
                    "• Thuế TNCN (PIT)\n"
                    "• Thuế Môn bài"
                ),
                classification=classification,
                actions=[
                    {"label": "Thuế GTGT", "action_type": "quick_reply", "payload": "tính thuế GTGT"},
                    {"label": "Thuế TNDN", "action_type": "quick_reply", "payload": "tính thuế TNDN"},
                    {"label": "Thuế TNCN", "action_type": "quick_reply", "payload": "tính thuế TNCN"},
                    {"label": "Thuế Môn bài", "action_type": "quick_reply", "payload": "tính thuế môn bài"},
                ],
            )

        rule = self.tax_rules.get(category)
        if not rule:
            return self._build_response(
                reply="Xin lỗi, tôi chưa hỗ trợ tính loại thuế này.",
                classification=classification,
            )

        context = TaxContext(
            customer_type=customer_type,
            revenue=entities.get("amount"),
            income=entities.get("amount"),
            extra=entities,
        )

        # Check if we have enough data
        if not entities.get("amount"):
            prompts = {
                TaxCategory.VAT: "Vui lòng cung cấp doanh thu để tính thuế GTGT (VD: 500 triệu)",
                TaxCategory.CIT: "Vui lòng cung cấp thu nhập chịu thuế để tính thuế TNDN (VD: 1 tỷ)",
                TaxCategory.PIT: "Vui lòng cung cấp thu nhập hàng tháng để tính thuế TNCN (VD: 30 triệu)",
                TaxCategory.LICENSE: "Vui lòng cung cấp doanh thu hoặc vốn điều lệ để tính thuế Môn bài",
            }
            return self._build_response(
                reply=prompts.get(category, "Vui lòng cung cấp thêm thông tin."),
                classification=classification,
            )

        result = rule.calculate(context)

        # Enrich with RAG-sourced legal references
        references = [{"title": ref, "url": "", "snippet": ""} for ref in result.legal_basis]
        if self.rag and category:
            rag_result = await self.rag.query(
                question=f"căn cứ pháp lý tính {category.value}",
                customer_type=customer_type.value,
                tax_category=category.value,
                n_results=3,
                memory_context=memory_context,
            )
            for s in rag_result.sources:
                references.append({
                    "title": s["title"], "url": s.get("url", ""), "snippet": s.get("snippet", ""),
                })

        return self._build_response(
            reply=result.explanation,
            classification=classification,
            references=references,
        )

    async def _handle_tax_info(
        self, classification: ClassificationResult, customer_type: CustomerType, message: str,
        history: list[dict] | None = None, memory_context: str = "",
    ) -> dict:
        """Handle tax information requests using RAG when available."""
        category = classification.tax_category

        # Try RAG first for richer, regulation-backed answers
        if self.rag:
            category_filter = category.value if category else None
            rag_result = await self.rag.query(
                question=message,
                customer_type=customer_type.value,
                tax_category=category_filter,
                conversation_history=history,
                memory_context=memory_context,
            )
            if rag_result.confidence > 0.4 and rag_result.answer:
                references_list = [
                    {"title": s["title"], "url": s.get("url", ""), "snippet": s.get("snippet", "")}
                    for s in rag_result.sources
                ]
                return self._build_response(
                    reply=rag_result.answer,
                    classification=classification,
                    references=references_list,
                )

        # Fallback to hardcoded rule info
        if category and category in self.tax_rules:
            rule = self.tax_rules[category]
            entities = classification.extracted_entities

            # When the user provided concrete numbers (income/revenue,
            # dependents, etc.) we can go beyond generic info and give a
            # personalised consultation by running the tax calculation.
            if entities.get("amount"):
                context = TaxContext(
                    customer_type=customer_type,
                    revenue=entities.get("amount"),
                    income=entities.get("amount"),
                    extra=entities,
                )
                result = rule.calculate(context)
                references = [
                    {"title": ref, "url": "", "snippet": ""}
                    for ref in result.legal_basis
                ]
                return self._build_response(
                    reply=result.explanation,
                    classification=classification,
                    references=references,
                )

            info = rule.get_consultation(customer_type, entities)
            return self._build_response(reply=info, classification=classification)

        overview = self._get_tax_overview(customer_type)
        return self._build_response(reply=overview, classification=classification)

    async def _handle_procedure(
        self, classification: ClassificationResult, customer_type: CustomerType, message: str,
        history: list[dict] | None = None, memory_context: str = "",
    ) -> dict:
        """Handle procedure/process questions using RAG if available."""
        if self.rag:
            rag_result = await self.rag.query(
                question=message,
                customer_type=customer_type.value,
                tax_category="procedure",
                conversation_history=history,
                memory_context=memory_context,
            )
            if rag_result.answer:
                references = [
                    {"title": s["title"], "url": s.get("url", ""), "snippet": s.get("snippet", "")}
                    for s in rag_result.sources
                ]
                return self._build_response(
                    reply=rag_result.answer,
                    classification=classification,
                    references=references,
                )

        # Provide specific procedure info based on what the user asked about
        msg_lower = message.lower()
        if "kê khai" in msg_lower or "nộp thuế" in msg_lower:
            # User asked about declaration/filing procedure
            if customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
                reply = (
                    "Quy trình kê khai thuế cho Hộ kinh doanh / Cá nhân:\n\n"
                    "📋 Bước 1: Xác định phương pháp tính thuế\n"
                    "• Khoán: doanh thu ≤ 100 triệu/năm → miễn thuế GTGT, TNCN\n"
                    "• Khoán: DT > 100 triệu → thuế GTGT 1-5%, TNCN 0.5-2%\n\n"
                    "📋 Bước 2: Chuẩn bị hồ sơ kê khai\n"
                    "• Tờ khai thuế khoán (Mẫu 01/CNKD)\n"
                    "• Sổ sách, hóa đơn bán hàng\n\n"
                    "📋 Bước 3: Nộp tờ khai\n"
                    "• Qua eTax Mobile hoặc thuedientu.gdt.gov.vn\n"
                    "• Hoặc nộp trực tiếp tại Chi cục Thuế\n\n"
                    "📋 Bước 4: Nộp thuế\n"
                    "• Hạn: theo quý (ngày cuối tháng đầu quý sau)\n"
                    "• Quyết toán năm: trước 31/03 năm sau\n\n"
                    "📎 Căn cứ: Thông tư 40/2021/TT-BTC"
                )
            else:
                reply = (
                    "Quy trình kê khai thuế cho Doanh nghiệp:\n\n"
                    "📋 Bước 1: Đăng ký phương pháp tính thuế GTGT\n"
                    "• Khấu trừ (DT > 1 tỷ/năm) hoặc Trực tiếp\n\n"
                    "📋 Bước 2: Kê khai thuế hàng tháng/quý\n"
                    "• Thuế GTGT: Mẫu 01/GTGT (hạn ngày 20 tháng sau hoặc cuối quý)\n"
                    "• Thuế TNCN: Mẫu 05/KK-TNCN (nếu có khấu trừ)\n"
                    "• Thuế TNDN: tạm tính quý\n\n"
                    "📋 Bước 3: Quyết toán thuế năm\n"
                    "• Hạn: 90 ngày kể từ kết thúc năm tài chính\n"
                    "• Mẫu 03/TNDN, Mẫu 05/QTT-TNCN\n\n"
                    "📋 Bước 4: Nộp thuế qua ngân hàng hoặc Kho bạc\n"
                    "• Kê khai qua thuedientu.gdt.gov.vn hoặc HTKK\n\n"
                    "📎 Căn cứ: Luật Quản lý thuế 38/2019, Nghị định 126/2020"
                )
        elif "đăng ký" in msg_lower or "mã số thuế" in msg_lower.replace("mst", "mã số thuế"):
            reply = (
                "Quy trình đăng ký mã số thuế:\n\n"
                "📋 Bước 1: Chuẩn bị hồ sơ\n"
                "• Tờ khai đăng ký thuế\n"
                "• Bản sao CCCD/CMND\n"
                "• Giấy chứng nhận ĐKKD\n\n"
                "📋 Bước 2: Nộp hồ sơ\n"
                "• Tại Chi cục Thuế quận/huyện\n"
                "• Hoặc qua Cổng DVC quốc gia\n\n"
                "📋 Bước 3: Nhận MST (3 ngày làm việc)\n\n"
                "📎 Căn cứ: Thông tư 105/2020/TT-BTC"
            )
        elif "hoàn thuế" in msg_lower:
            reply = (
                "Quy trình hoàn thuế GTGT:\n\n"
                "📋 Bước 1: Kiểm tra điều kiện hoàn thuế\n"
                "• Xuất khẩu, đầu tư mới, hoặc 12 tháng liên tục có GTGT đầu vào > đầu ra\n\n"
                "📋 Bước 2: Lập hồ sơ hoàn thuế\n"
                "• Giấy đề nghị hoàn thuế (Mẫu 01/HT)\n"
                "• Bảng kê hóa đơn, chứng từ\n\n"
                "📋 Bước 3: Nộp hồ sơ tại cơ quan thuế quản lý\n\n"
                "📋 Bước 4: Cơ quan thuế xét duyệt (40-60 ngày)\n\n"
                "📎 Căn cứ: Luật Thuế GTGT, Thông tư 80/2021/TT-BTC"
            )
        else:
            reply = (
                "Về thủ tục thuế, tôi có thể hỗ trợ:\n"
                "• Quy trình kê khai thuế hàng quý/năm\n"
                "• Quy trình đăng ký mã số thuế\n"
                "• Quy trình quyết toán thuế\n"
                "• Quy trình hoàn thuế GTGT\n"
                "• Thay đổi thông tin đăng ký thuế\n\n"
                "Bạn cần hỗ trợ thủ tục nào cụ thể?"
            )

        return self._build_response(
            reply=reply,
            classification=classification,
            actions=[
                {"label": "Hạn nộp thuế", "action_type": "quick_reply", "payload": "hạn nộp thuế"},
                {"label": "Tính thuế", "action_type": "quick_reply", "payload": "tính thuế"},
            ],
        )

    async def _handle_declaration(
        self, classification: ClassificationResult, customer_type: CustomerType, message: str,
        history: list[dict] | None = None, memory_context: str = "",
    ) -> dict:
        """Handle declaration/filing questions using RAG if available."""
        if self.rag:
            category_filter = classification.tax_category.value if classification.tax_category else "procedure"
            rag_result = await self.rag.query(
                question=message,
                customer_type=customer_type.value,
                tax_category=category_filter,
                conversation_history=history,
                memory_context=memory_context,
            )
            if rag_result.answer:
                references = [
                    {"title": s["title"], "url": s.get("url", ""), "snippet": s.get("snippet", "")}
                    for s in rag_result.sources
                ]
                return self._build_response(
                    reply=rag_result.answer,
                    classification=classification,
                    references=references,
                )

        # Provide process-oriented answer (not just forms list)
        if customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            reply = (
                "Quy trình kê khai thuế cho Hộ kinh doanh / Cá nhân:\n\n"
                "📋 Bước 1: Xác định phương pháp tính thuế\n"
                "• Khoán: doanh thu ≤ 100 triệu/năm (miễn thuế GTGT, TNCN)\n"
                "• Khoán: DT > 100 triệu → thuế GTGT 1-5%, TNCN 0.5-2%\n\n"
                "📋 Bước 2: Chuẩn bị hồ sơ kê khai\n"
                "• Tờ khai thuế khoán (Mẫu 01/CNKD)\n"
                "• Sổ sách, hóa đơn bán hàng\n\n"
                "📋 Bước 3: Nộp tờ khai\n"
                "• Kê khai qua eTax Mobile hoặc thuedientu.gdt.gov.vn\n"
                "• Hoặc nộp trực tiếp tại Chi cục Thuế\n\n"
                "📋 Bước 4: Nộp thuế\n"
                "• Hạn nộp: theo quý (ngày cuối tháng đầu quý sau)\n"
                "• Quyết toán năm: trước 31/03 năm sau\n\n"
                "📎 Căn cứ: Thông tư 40/2021/TT-BTC"
            )
        else:
            reply = (
                "Quy trình kê khai thuế cho Doanh nghiệp:\n\n"
                "📋 Bước 1: Đăng ký phương pháp tính thuế GTGT\n"
                "• Khấu trừ (DT > 1 tỷ/năm) hoặc Trực tiếp\n\n"
                "📋 Bước 2: Kê khai thuế hàng tháng/quý\n"
                "• Thuế GTGT: Mẫu 01/GTGT (hạn ngày 20 tháng sau hoặc cuối tháng đầu quý sau)\n"
                "• Thuế TNCN: Mẫu 05/KK-TNCN (nếu có khấu trừ)\n"
                "• Thuế TNDN: tạm tính quý (không cần nộp tờ khai từ 2021)\n\n"
                "📋 Bước 3: Quyết toán thuế năm\n"
                "• Hạn: 90 ngày kể từ kết thúc năm tài chính (thường 31/03)\n"
                "• Mẫu 03/TNDN (quyết toán TNDN)\n"
                "• Mẫu 05/QTT-TNCN (quyết toán TNCN)\n\n"
                "📋 Bước 4: Nộp thuế\n"
                "• Nộp qua ngân hàng hoặc Kho bạc Nhà nước\n"
                "• Kê khai qua thuedientu.gdt.gov.vn hoặc phần mềm HTKK\n\n"
                "📎 Căn cứ: Luật Quản lý thuế 38/2019, Nghị định 126/2020"
            )

        return self._build_response(
            reply=reply,
            classification=classification,
            actions=[
                {"label": "Hạn nộp thuế", "action_type": "quick_reply", "payload": "hạn nộp thuế"},
                {"label": "Tính thuế", "action_type": "quick_reply", "payload": "tính thuế"},
            ],
        )

    async def _handle_penalty(
        self, classification: ClassificationResult, customer_type: CustomerType, message: str,
        history: list[dict] | None = None, memory_context: str = "",
    ) -> dict:
        """Handle penalty-related questions using RAG when available."""
        if self.rag:
            rag_result = await self.rag.query(
                question=message,
                customer_type=customer_type.value,
                conversation_history=history,
                memory_context=memory_context,
            )
            if rag_result.confidence > 0.4 and rag_result.answer:
                references = [
                    {"title": s["title"], "url": s.get("url", ""), "snippet": s.get("snippet", "")}
                    for s in rag_result.sources
                ]
                return self._build_response(
                    reply=rag_result.answer,
                    classification=classification,
                    references=references,
                )

        # Fallback to hardcoded penalty info
        return self._build_response(
            reply=(
                "Về xử phạt vi phạm thuế:\n\n"
                "⚠️ Chậm nộp tờ khai thuế:\n"
                "• 2-5 triệu VND (tùy mức độ)\n\n"
                "⚠️ Chậm nộp tiền thuế:\n"
                "• 0.03%/ngày trên số tiền chậm nộp\n\n"
                "⚠️ Khai sai, trốn thuế:\n"
                "• 20% số thuế khai thiếu (khai sai)\n"
                "• 1-3 lần số thuế trốn (trốn thuế)\n\n"
                "📎 Căn cứ: Nghị định 125/2020/NĐ-CP"
            ),
            classification=classification,
            references=[{
                "title": "Nghị định 125/2020/NĐ-CP về xử phạt vi phạm hành chính thuế",
                "url": "",
                "snippet": "",
            }],
        )

    async def _handle_registration(
        self, classification: ClassificationResult, customer_type: CustomerType, message: str,
        history: list[dict] | None = None, memory_context: str = "",
    ) -> dict:
        """Handle tax registration questions using RAG if available."""
        if self.rag:
            rag_result = await self.rag.query(
                question=message,
                customer_type=customer_type.value,
                tax_category="procedure",
                conversation_history=history,
                memory_context=memory_context,
            )
            if rag_result.confidence > 0.4 and rag_result.answer:
                references = [
                    {"title": s["title"], "url": s.get("url", ""), "snippet": s.get("snippet", "")}
                    for s in rag_result.sources
                ]
                return self._build_response(
                    reply=rag_result.answer,
                    classification=classification,
                    references=references,
                )

        # Hardcoded fallback for registration questions
        if customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            return self._build_response(
                reply=(
                    "Thủ tục đăng ký thuế cho Hộ kinh doanh / Cá thể:\n\n"
                    "1. Chuẩn bị hồ sơ:\n"
                    "   • Tờ khai đăng ký thuế (Mẫu 03-ĐK-TCT)\n"
                    "   • Bản sao CCCD/CMND\n"
                    "   • Giấy chứng nhận đăng ký hộ kinh doanh\n\n"
                    "2. Nộp hồ sơ tại Chi cục Thuế quận/huyện\n\n"
                    "3. Thời hạn cấp MST: 3 ngày làm việc\n\n"
                    "📎 Căn cứ: Thông tư 105/2020/TT-BTC, Luật Quản lý thuế 38/2019/QH14"
                ),
                classification=classification,
                references=[{
                    "title": "Luật Quản lý thuế 38/2019/QH14",
                    "url": "",
                    "snippet": "Quy định về đăng ký thuế",
                }],
            )

        return self._build_response(
            reply=(
                "Thủ tục đăng ký mã số thuế cho Doanh nghiệp:\n\n"
                "1. Hồ sơ đăng ký thuế lần đầu:\n"
                "   • Tờ khai đăng ký thuế (Mẫu 01-ĐK-TCT)\n"
                "   • Bản sao Giấy chứng nhận ĐKKD\n"
                "   • Bản sao CCCD/CMND người đại diện pháp luật\n"
                "   • Văn bản ủy quyền (nếu có)\n\n"
                "2. Nơi nộp: Cục Thuế / Chi cục Thuế quản lý trực tiếp\n\n"
                "3. Thời hạn:\n"
                "   • Nộp trong 10 ngày kể từ ngày cấp ĐKKD\n"
                "   • Cơ quan thuế cấp MST trong 3 ngày làm việc\n\n"
                "4. Lưu ý: Doanh nghiệp đăng ký qua Cổng DVC quốc gia\n"
                "   sẽ được cấp MST cùng lúc với ĐKKD\n\n"
                "📎 Căn cứ: Luật Quản lý thuế 38/2019/QH14, "
                "Thông tư 105/2020/TT-BTC"
            ),
            classification=classification,
            references=[
                {
                    "title": "Luật Quản lý thuế 38/2019/QH14",
                    "url": "",
                    "snippet": "Điều 30-37: Đăng ký thuế",
                },
                {
                    "title": "Thông tư 105/2020/TT-BTC",
                    "url": "",
                    "snippet": "Hướng dẫn đăng ký thuế",
                },
            ],
            actions=[
                {"label": "Mẫu tờ khai", "action_type": "quick_reply", "payload": "mẫu tờ khai đăng ký thuế"},
                {"label": "Hạn nộp thuế", "action_type": "quick_reply", "payload": "hạn nộp thuế doanh nghiệp mới"},
            ],
        )

    async def _handle_contextual_query(
        self, message: str, classification: ClassificationResult,
        customer_type: CustomerType, history: list[dict],
        memory_context: str = "",
    ) -> dict:
        """Handle follow-up messages using LLM with full conversation history.

        When conversation history exists, we always prefer LLM over hardcoded
        responses so the model can reference earlier context (e.g. the user
        already said "tôi là hộ kinh doanh").
        """
        if self.rag:
            category_filter = classification.tax_category.value if classification.tax_category else None
            rag_result = await self.rag.query(
                question=message,
                customer_type=customer_type.value,
                tax_category=category_filter,
                conversation_history=history,
                memory_context=memory_context,
            )
            if rag_result.answer:
                references = [
                    {"title": s["title"], "url": s.get("url", ""), "snippet": s.get("snippet", "")}
                    for s in rag_result.sources
                ]
                return self._build_response(
                    reply=rag_result.answer,
                    classification=classification,
                    references=references,
                )

        # LLM unavailable or failed — fall back to intent-specific handler.
        # Pass memory_context so handlers can still use customer info.
        handler = {
            Intent.TAX_INFO: lambda: self._handle_tax_info(classification, customer_type, message, memory_context=memory_context),
            Intent.TAX_PROCEDURE: lambda: self._handle_procedure(classification, customer_type, message, memory_context=memory_context),
            Intent.DECLARATION: lambda: self._handle_declaration(classification, customer_type, message, memory_context=memory_context),
            Intent.REGISTRATION: lambda: self._handle_registration(classification, customer_type, message, memory_context=memory_context),
            Intent.PENALTY: lambda: self._handle_penalty(classification, customer_type, message, memory_context=memory_context),
        }.get(classification.intent)

        if handler:
            return await handler()

        # For UNKNOWN intent without RAG, show service menu instead of
        # falling back to _handle_general_query (which would loop).
        return self._build_service_menu_response(classification, customer_type, memory_context)

    async def _handle_general_query(
        self, message: str, classification: ClassificationResult, customer_type: CustomerType,
        history: list[dict] | None = None, memory_context: str = "",
    ) -> dict:
        """
        Handle unclassified queries using RAG pipeline.
        Falls back to suggestion-based response if RAG is unavailable.
        """
        if self.rag:
            category_filter = classification.tax_category.value if classification.tax_category else None
            rag_result = await self.rag.query(
                question=message,
                customer_type=customer_type.value,
                tax_category=category_filter,
                conversation_history=history,
                memory_context=memory_context,
            )
            if rag_result.confidence > 0.4 and rag_result.answer:
                references = [
                    {"title": s["title"], "url": s.get("url", ""), "snippet": s.get("snippet", "")}
                    for s in rag_result.sources
                ]
                return self._build_response(
                    reply=rag_result.answer,
                    classification=classification,
                    references=references,
                )

        # RAG/LLM unavailable — show service menu with customer-aware context
        return self._build_service_menu_response(classification, customer_type, memory_context)

    def _build_service_menu_response(
        self, classification: ClassificationResult, customer_type: CustomerType,
        memory_context: str = "",
    ) -> dict:
        """Build a service menu response that avoids repeating the same
        question and provides actionable choices whose payloads match
        known intent patterns (preventing infinite loops).

        Uses memory_context to show customer info even when LLM is unavailable,
        proving to the user that the bot remembers them.
        """
        type_label = {
            CustomerType.SME: "Doanh nghiệp",
            CustomerType.HOUSEHOLD: "Hộ kinh doanh",
            CustomerType.INDIVIDUAL: "Cá nhân kinh doanh",
        }.get(customer_type, "")

        # Extract customer name from memory_context if available
        customer_name = ""
        if memory_context:
            for line in memory_context.split("\n"):
                if line.startswith("Tên: "):
                    customer_name = line[5:].strip()
                    break

        if customer_name and type_label:
            greeting = f"Xin chào {customer_name} ({type_label})! "
        elif type_label:
            greeting = f"Xin chào {type_label}! "
        else:
            greeting = ""

        reply = (
            f"{greeting}Tôi có thể hỗ trợ bạn các dịch vụ sau:\n\n"
            "1. Tính thuế (GTGT, TNDN, TNCN, Môn bài)\n"
            "2. Hướng dẫn kê khai & quyết toán thuế\n"
            "3. Tra cứu quy định & văn bản pháp luật\n"
            "4. Hạn nộp thuế\n"
            "5. Thủ tục đăng ký mã số thuế\n\n"
            "Bạn có thể gõ số hoặc mô tả câu hỏi cụ thể, ví dụ:\n"
            '• "Tính thuế GTGT doanh thu 500 triệu"\n'
            '• "Thuế TNCN lương 30 triệu 2 người phụ thuộc"\n'
            '• "Hạn nộp thuế TNDN quý 1"'
        )

        return self._build_response(
            reply=reply,
            classification=classification,
            actions=[
                {"label": "Tính thuế", "action_type": "quick_reply", "payload": "tính thuế"},
                {"label": "Kê khai thuế", "action_type": "quick_reply", "payload": "kê khai thuế"},
                {"label": "Hạn nộp thuế", "action_type": "quick_reply", "payload": "hạn nộp thuế"},
                {"label": "Đăng ký MST", "action_type": "quick_reply", "payload": "đăng ký mã số thuế"},
            ],
        )

    def _get_greeting(self, customer_type: CustomerType) -> str:
        type_label = {
            CustomerType.SME: " (Doanh nghiệp)",
            CustomerType.HOUSEHOLD: " (Hộ gia đình)",
            CustomerType.INDIVIDUAL: " (Cá thể kinh doanh)",
        }.get(customer_type, "")

        return (
            f"Xin chào{type_label}! Tôi là Trợ lý Thuế ảo.\n\n"
            "Tôi có thể hỗ trợ bạn:\n"
            "• Tính thuế (GTGT, TNDN, TNCN, Môn bài)\n"
            "• Tra cứu quy định thuế\n"
            "• Hướng dẫn thủ tục kê khai\n"
            "• Kiểm tra hóa đơn, chứng từ\n\n"
            "Hãy gửi câu hỏi của bạn!"
        )

    def _get_help_text(self, customer_type: CustomerType) -> str:
        return (
            "Hướng dẫn sử dụng Trợ lý Thuế:\n\n"
            "💬 Bạn có thể hỏi trực tiếp, ví dụ:\n"
            '• "Thuế GTGT là gì?"\n'
            '• "Tính thuế TNCN lương 25 triệu"\n'
            '• "Hạn nộp thuế quý 2"\n'
            '• "Thủ tục đăng ký mã số thuế"\n\n'
            "📎 Gửi hình ảnh hóa đơn để tôi kiểm tra\n\n"
            "⚙️ Lệnh:\n"
            "• /loai <SME|hogiadia|cathe> - Đặt loại khách hàng\n"
            "• /reset - Bắt đầu lại cuộc trò chuyện"
        )

    def _get_tax_overview(self, customer_type: CustomerType) -> str:
        if customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            return (
                "Tổng quan thuế cho Hộ kinh doanh / Cá thể:\n\n"
                "1. Thuế Môn bài: 0 - 1.000.000 VND/năm\n"
                "2. Thuế GTGT: 1-5% trên doanh thu\n"
                "3. Thuế TNCN: 0.5-2% trên doanh thu\n"
                "   (Miễn nếu DT ≤ 100 triệu/năm)\n\n"
                "Bạn muốn tìm hiểu chi tiết loại thuế nào?"
            )
        return (
            "Tổng quan thuế cho Doanh nghiệp (SME):\n\n"
            "1. Thuế Môn bài: 2-3 triệu VND/năm\n"
            "2. Thuế GTGT: 10% (phương pháp khấu trừ)\n"
            "3. Thuế TNDN: 20% trên lợi nhuận\n"
            "4. Thuế TNCN: Khấu trừ cho nhân viên\n\n"
            "Bạn muốn tìm hiểu chi tiết loại thuế nào?"
        )

    def _get_deadline_info(
        self, category: TaxCategory | None, customer_type: CustomerType
    ) -> str:
        return (
            "Hạn nộp thuế chính:\n\n"
            "📅 Thuế GTGT (kê khai tháng):\n"
            "• Hạn: Ngày 20 tháng sau\n\n"
            "📅 Thuế GTGT (kê khai quý):\n"
            "• Hạn: Ngày cuối tháng đầu quý sau\n\n"
            "📅 Thuế TNDN (tạm tính quý):\n"
            "• Hạn: Ngày 30 tháng đầu quý sau\n\n"
            "📅 Quyết toán thuế năm:\n"
            "• Hạn: 90 ngày kể từ kết thúc năm tài chính\n\n"
            "📅 Thuế Môn bài:\n"
            "• Hạn: Ngày 30/01 hàng năm\n\n"
            "📅 Thuế TNCN (quyết toán):\n"
            "• Hạn: Trước 31/03 năm sau"
        )

    def _build_response(
        self,
        reply: str,
        classification: ClassificationResult,
        actions: list[dict] | None = None,
        references: list[dict] | None = None,
    ) -> dict:
        suggestions = generate_suggestions(
            classification.intent, classification.tax_category,
        )
        reply_with_suggestions = reply + format_suggestions(suggestions)

        # Include suggestions as text_suggestion actions so the gateway can
        # store them and resolve numeric shortcut selections ("1", "2", "3").
        suggestion_actions = [
            {"label": s, "action_type": "text_suggestion", "payload": s}
            for s in suggestions
        ]

        return {
            "reply": reply_with_suggestions,
            "actions": (actions or []) + suggestion_actions,
            "references": references or [],
            "confidence": classification.confidence,
            "category": classification.tax_category.value if classification.tax_category else "",
            "intent": classification.intent.value,
        }
