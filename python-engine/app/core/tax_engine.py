"""
Tax Engine - Central orchestrator for tax-related queries.
Coordinates between intent classification, tax rules, AI/RAG, and NLP.
"""

import logging

from app.core.intent_classifier import ClassificationResult, Intent, IntentClassifier
from app.core.tax_rules.base import CustomerType, TaxCategory, TaxContext, TaxResult
from app.core.tax_rules.cit import CITRule
from app.core.tax_rules.license_tax import LicenseTaxRule
from app.core.tax_rules.pit import PITRule
from app.core.tax_rules.vat import VATRule

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

    def __init__(self) -> None:
        self.classifier = IntentClassifier()

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
    ) -> dict:
        """
        Process a tax-related message and return a response.

        Returns:
            dict with keys: reply, actions, references, confidence, category
        """
        ct = CustomerType(customer_type) if customer_type in CustomerType.__members__.values() else CustomerType.UNKNOWN

        # 1. Classify intent
        classification = self.classifier.classify(message)
        logger.info(
            "Classified message",
            extra={
                "intent": classification.intent,
                "category": classification.tax_category,
                "confidence": classification.confidence,
            },
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

        if classification.intent == Intent.TAX_CALCULATE:
            return await self._handle_calculation(classification, ct)

        if classification.intent == Intent.TAX_INFO:
            return await self._handle_tax_info(classification, ct)

        if classification.intent == Intent.TAX_DEADLINE:
            return self._build_response(
                reply=self._get_deadline_info(classification.tax_category, ct),
                classification=classification,
            )

        if classification.intent == Intent.TAX_PROCEDURE:
            return await self._handle_procedure(classification, ct, message)

        if classification.intent == Intent.DECLARATION:
            return await self._handle_declaration(classification, ct, message)

        if classification.intent == Intent.PENALTY:
            return await self._handle_penalty(classification, ct, message)

        # Unknown intent → use RAG/LLM for general answer
        return await self._handle_general_query(message, classification, ct)

    async def _handle_calculation(
        self, classification: ClassificationResult, customer_type: CustomerType
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
        return self._build_response(
            reply=result.explanation,
            classification=classification,
            references=[{"title": ref, "url": "", "snippet": ""} for ref in result.legal_basis],
        )

    async def _handle_tax_info(
        self, classification: ClassificationResult, customer_type: CustomerType
    ) -> dict:
        """Handle tax information requests."""
        category = classification.tax_category

        if category and category in self.tax_rules:
            info = self.tax_rules[category].get_info(customer_type)
            return self._build_response(reply=info, classification=classification)

        # General tax overview
        overview = self._get_tax_overview(customer_type)
        return self._build_response(reply=overview, classification=classification)

    async def _handle_procedure(
        self, classification: ClassificationResult, customer_type: CustomerType, message: str
    ) -> dict:
        """Handle procedure/process questions. TODO: integrate RAG."""
        return self._build_response(
            reply=(
                "Về thủ tục thuế, tôi có thể hỗ trợ:\n"
                "• Đăng ký thuế lần đầu\n"
                "• Kê khai thuế hàng quý/năm\n"
                "• Quyết toán thuế\n"
                "• Hoàn thuế GTGT\n"
                "• Thay đổi thông tin đăng ký thuế\n\n"
                "Bạn cần hỗ trợ thủ tục nào cụ thể?"
            ),
            classification=classification,
        )

    async def _handle_declaration(
        self, classification: ClassificationResult, customer_type: CustomerType, message: str
    ) -> dict:
        """Handle declaration/filing questions. TODO: integrate RAG."""
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

    async def _handle_penalty(
        self, classification: ClassificationResult, customer_type: CustomerType, message: str
    ) -> dict:
        """Handle penalty-related questions."""
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

    async def _handle_general_query(
        self, message: str, classification: ClassificationResult, customer_type: CustomerType
    ) -> dict:
        """
        Handle unclassified queries.
        TODO: Use RAG pipeline to search regulations and generate answer via LLM.
        """
        return self._build_response(
            reply=(
                "Tôi hiểu câu hỏi của bạn. Để trả lời chính xác hơn, "
                "bạn có thể cho tôi biết thêm:\n\n"
                "1. Bạn là doanh nghiệp (SME), hộ kinh doanh, hay cá thể?\n"
                "2. Câu hỏi liên quan đến loại thuế nào?\n"
                "3. Có số liệu cụ thể nào không?\n\n"
                "Hoặc bạn có thể thử các câu hỏi như:\n"
                '• "Tính thuế GTGT doanh thu 500 triệu"\n'
                '• "Thuế TNCN lương 30 triệu 2 người phụ thuộc"\n'
                '• "Hạn nộp thuế TNDN quý 1"'
            ),
            classification=classification,
            actions=[
                {"label": "Thuế GTGT", "action_type": "quick_reply", "payload": "thông tin thuế GTGT"},
                {"label": "Thuế TNDN", "action_type": "quick_reply", "payload": "thông tin thuế TNDN"},
                {"label": "Thuế TNCN", "action_type": "quick_reply", "payload": "thông tin thuế TNCN"},
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
        return {
            "reply": reply,
            "actions": actions or [],
            "references": references or [],
            "confidence": classification.confidence,
            "category": classification.tax_category.value if classification.tax_category else "",
            "intent": classification.intent.value,
        }
