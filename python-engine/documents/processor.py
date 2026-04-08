"""
Document processing pipeline for tax documents.
Handles invoices, receipts, tax returns, and other tax-related documents.
"""

import logging
from dataclasses import dataclass, field

from documents.ocr import OCRService
from documents.extractor import DataExtractor

logger = logging.getLogger(__name__)


@dataclass
class ProcessingResult:
    """Result from document processing."""

    document_type: str
    extracted_data: dict = field(default_factory=dict)
    raw_text: str = ""
    summary: str = ""
    warnings: list[str] = field(default_factory=list)
    confidence: float = 0.0


class DocumentProcessor:
    """
    Main document processing pipeline:
    1. Download document (image/PDF)
    2. OCR text extraction (for images)
    3. Data field extraction
    4. Validation
    """

    def __init__(self) -> None:
        self.ocr = OCRService()
        self.extractor = DataExtractor()

    async def process(
        self,
        file_url: str,
        mime_type: str,
        document_type: str = "unknown",
    ) -> ProcessingResult:
        """Process a document and extract relevant tax information."""
        logger.info("Processing document: type=%s, mime=%s", document_type, mime_type)

        # 1. Extract text via OCR
        raw_text = ""
        if mime_type.startswith("image/"):
            raw_text = await self.ocr.extract_from_url(file_url)
        elif mime_type == "application/pdf":
            raw_text = await self.ocr.extract_from_pdf_url(file_url)
        else:
            return ProcessingResult(
                document_type=document_type,
                warnings=[f"Unsupported file type: {mime_type}"],
            )

        if not raw_text.strip():
            return ProcessingResult(
                document_type=document_type,
                warnings=["Không thể đọc nội dung tài liệu. Vui lòng gửi ảnh rõ hơn."],
            )

        # 2. Extract structured data
        if document_type == "invoice":
            extracted = self.extractor.extract_invoice(raw_text)
        elif document_type == "receipt":
            extracted = self.extractor.extract_receipt(raw_text)
        else:
            extracted = self.extractor.extract_generic(raw_text)

        # 3. Validate
        warnings = self._validate(extracted, document_type)

        # 4. Build summary
        summary = self._build_summary(extracted, document_type)

        return ProcessingResult(
            document_type=document_type,
            extracted_data=extracted,
            raw_text=raw_text,
            summary=summary,
            warnings=warnings,
            confidence=0.8 if extracted else 0.3,
        )

    def _validate(self, data: dict, document_type: str) -> list[str]:
        """Validate extracted data against tax rules."""
        warnings = []

        if document_type == "invoice":
            if not data.get("tax_code"):
                warnings.append("Không tìm thấy mã số thuế người bán trên hóa đơn")
            if not data.get("invoice_number"):
                warnings.append("Không xác định được số hóa đơn")
            if not data.get("total_amount"):
                warnings.append("Không xác định được tổng tiền")

        return warnings

    def _build_summary(self, data: dict, document_type: str) -> str:
        """Build a human-readable summary of extracted data."""
        if not data:
            return "Không trích xuất được thông tin từ tài liệu."

        lines = [f"Kết quả xử lý {document_type}:\n"]
        field_labels = {
            "invoice_number": "Số hóa đơn",
            "invoice_date": "Ngày lập",
            "seller_name": "Người bán",
            "seller_tax_code": "MST người bán",
            "buyer_name": "Người mua",
            "buyer_tax_code": "MST người mua",
            "subtotal": "Tiền hàng",
            "vat_rate": "Thuế suất VAT",
            "vat_amount": "Tiền thuế GTGT",
            "total_amount": "Tổng thanh toán",
            "tax_code": "Mã số thuế",
        }

        for key, value in data.items():
            label = field_labels.get(key, key)
            lines.append(f"• {label}: {value}")

        return "\n".join(lines)
