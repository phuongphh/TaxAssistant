"""
Context-aware suggestion generator for TaxAssistant.

Generates 3 numbered text suggestions after each bot response,
based on the current intent and tax category context.
"""

from __future__ import annotations

from app.core.intent_classifier import Intent
from app.core.tax_rules.base import TaxCategory


# Mapping: (intent, optional tax_category) → list of suggestion texts.
# The generator picks the best match and returns exactly 3 suggestions.
_SUGGESTION_MAP: dict[Intent, list[str]] = {
    Intent.TAX_CALCULATE: [
        "Tính loại thuế khác",
        "Xem căn cứ pháp lý của kết quả tính",
        "Hướng dẫn kê khai thuế",
    ],
    Intent.TAX_INFO: [
        "Tra cứu văn bản pháp luật liên quan",
        "Tính thuế cụ thể cho trường hợp của tôi",
        "Xem hạn nộp thuế",
    ],
    Intent.TAX_DEADLINE: [
        "Tính thuế cần nộp",
        "Hướng dẫn kê khai thuế",
        "Xem mức phạt chậm nộp",
    ],
    Intent.TAX_PROCEDURE: [
        "Xem hạn nộp thuế",
        "Tính thuế cần nộp",
        "Tra cứu quy định liên quan",
    ],
    Intent.DECLARATION: [
        "Xem hạn nộp tờ khai",
        "Tính thuế cần nộp",
        "Tra cứu mẫu tờ khai",
    ],
    Intent.REGISTRATION: [
        "Hướng dẫn kê khai thuế sau đăng ký",
        "Xem thuế cần nộp cho doanh nghiệp mới",
        "Tra cứu quy định đăng ký thuế",
    ],
    Intent.PENALTY: [
        "Tính tiền phạt chậm nộp cụ thể",
        "Hướng dẫn nộp thuế để tránh phạt",
        "Tra cứu quy định xử phạt",
    ],
    Intent.DOCUMENT_CHECK: [
        "Kiểm tra hóa đơn khác",
        "Hướng dẫn kê khai thuế",
        "Tra cứu quy định về hóa đơn",
    ],
    Intent.GREETING: [
        "Tính thuế",
        "Tra cứu quy định thuế",
        "Hướng dẫn kê khai thuế",
    ],
    Intent.HELP: [
        "Tính thuế",
        "Tra cứu quy định thuế",
        "Hướng dẫn kê khai thuế",
    ],
}

# Tax-category-specific overrides for TAX_CALCULATE and TAX_INFO
_CATEGORY_SUGGESTIONS: dict[TaxCategory, list[str]] = {
    TaxCategory.VAT: [
        "Tính thuế GTGT cho số liệu khác",
        "Xem phương pháp tính thuế GTGT (khấu trừ vs trực tiếp)",
        "Hạn nộp thuế GTGT",
    ],
    TaxCategory.CIT: [
        "Tính thuế TNDN cho số liệu khác",
        "Xem các khoản chi được trừ khi tính thuế TNDN",
        "Hạn nộp thuế TNDN",
    ],
    TaxCategory.PIT: [
        "Tính thuế TNCN cho mức lương khác",
        "Xem giảm trừ gia cảnh và người phụ thuộc",
        "Hướng dẫn quyết toán thuế TNCN",
    ],
    TaxCategory.LICENSE: [
        "Xem mức thuế Môn bài theo vốn điều lệ",
        "Hạn nộp thuế Môn bài",
        "Tính loại thuế khác",
    ],
}

_DEFAULT_SUGGESTIONS = [
    "Tính thuế",
    "Tra cứu quy định thuế",
    "Hướng dẫn kê khai thuế",
]


def generate_suggestions(
    intent: Intent,
    tax_category: TaxCategory | None = None,
) -> list[str]:
    """Return exactly 3 context-aware suggestion strings.

    Args:
        intent: The classified intent of the current response.
        tax_category: Optional tax category for more specific suggestions.

    Returns:
        List of 3 suggestion strings.
    """
    # For calculation/info intents with a specific category, use category-specific suggestions
    if tax_category and intent in (Intent.TAX_CALCULATE, Intent.TAX_INFO):
        suggestions = _CATEGORY_SUGGESTIONS.get(tax_category)
        if suggestions:
            return suggestions[:3]

    # Fall back to intent-based suggestions
    suggestions = _SUGGESTION_MAP.get(intent)
    if suggestions:
        return suggestions[:3]

    return _DEFAULT_SUGGESTIONS[:3]


def format_suggestions(suggestions: list[str]) -> str:
    """Format suggestions as a numbered text block to append to bot replies.

    Returns:
        Formatted string like:
        ---
        Bạn muốn làm gì tiếp theo?
        1. Suggestion one
        2. Suggestion two
        3. Suggestion three
    """
    lines = ["", "---", "Bạn muốn làm gì tiếp theo?"]
    for i, s in enumerate(suggestions, 1):
        lines.append(f"{i}. {s}")
    return "\n".join(lines)
