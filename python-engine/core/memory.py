"""
Long-term memory assembly for the Tax Assistant.

Combines customer profile, recent conversation summaries, and active support
cases into a context string that gets injected into LLM prompts.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Vietnamese labels
_CUSTOMER_TYPE_LABELS = {
    "sme": "Doanh nghiệp vừa và nhỏ (SME)",
    "household": "Hộ kinh doanh",
    "individual": "Cá nhân kinh doanh",
    "unknown": "Chưa xác định",
}

_SERVICE_TYPE_LABELS = {
    "tax_calculation": "Tính thuế",
    "tax_declaration": "Kê khai thuế",
    "tax_registration": "Đăng ký mã số thuế",
    "tax_consultation": "Tư vấn quy định thuế",
    "invoice_check": "Kiểm tra hóa đơn",
    "tax_refund": "Hoàn thuế GTGT",
    "penalty_consultation": "Tư vấn xử phạt",
    "annual_settlement": "Quyết toán thuế năm",
}


def build_memory_context(
    customer: dict | None,
    active_cases: list[dict] | None = None,
    recent_summaries: list[str] | None = None,
) -> str:
    """Build a memory context string for LLM prompt injection.

    Args:
        customer: Customer profile dict (from CustomerRepository.to_dict)
        active_cases: List of active case dicts (from CaseRepository.to_dict)
        recent_summaries: List of summary strings from past conversations

    Returns:
        A Vietnamese context block to prepend to the LLM system prompt.
    """
    if not customer or customer.get("onboarding_step") == "new":
        return ""

    parts: list[str] = []

    # Customer profile section
    parts.append("=== THÔNG TIN KHÁCH HÀNG ===")
    ctype = _CUSTOMER_TYPE_LABELS.get(customer.get("customer_type", ""), "Chưa xác định")
    parts.append(f"Loại: {ctype}")

    if customer.get("business_name"):
        parts.append(f"Tên: {customer['business_name']}")
    if customer.get("tax_code"):
        parts.append(f"MST: {customer['tax_code']}")
    if customer.get("industry"):
        parts.append(f"Ngành nghề: {customer['industry']}")
    if customer.get("province"):
        parts.append(f"Tỉnh/TP: {customer['province']}")
    if customer.get("annual_revenue_range"):
        revenue_labels = {
            "under_100m": "Dưới 100 triệu/năm",
            "100m_1b": "100 triệu - 1 tỷ/năm",
            "1b_10b": "1 - 10 tỷ/năm",
            "over_10b": "Trên 10 tỷ/năm",
        }
        parts.append(f"Doanh thu: {revenue_labels.get(customer['annual_revenue_range'], customer['annual_revenue_range'])}")

    # Tax profile
    tax_profile = customer.get("tax_profile") or {}
    if tax_profile:
        profile_parts = []
        if tax_profile.get("vat_method"):
            profile_parts.append(f"PP thuế GTGT: {tax_profile['vat_method']}")
        if tax_profile.get("registered_taxes"):
            profile_parts.append(f"Thuế đã ĐK: {', '.join(tax_profile['registered_taxes'])}")
        if profile_parts:
            parts.append("Hồ sơ thuế: " + "; ".join(profile_parts))

    # Recent notes
    notes = customer.get("notes") or []
    if notes:
        recent_notes = notes[-3:]  # Last 3 notes
        parts.append("\nGhi chú gần đây:")
        for n in recent_notes:
            parts.append(f"- [{n.get('date', '?')[:10]}] {n.get('note', '')}")

    # Active support cases
    cases = active_cases or []
    if cases:
        parts.append("\n=== HỖ TRỢ ĐANG TIẾN HÀNH ===")
        for c in cases:
            label = _SERVICE_TYPE_LABELS.get(c.get("service_type", ""), c.get("service_type", ""))
            parts.append(f"- {c.get('title', label)} (trạng thái: {c.get('status', '?')}, bước: {c.get('current_step', '?')})")

    # Recent conversation summaries
    summaries = recent_summaries or []
    if summaries:
        parts.append("\n=== TÓM TẮT CUỘC TRÒ CHUYỆN GẦN ĐÂY ===")
        for s in summaries:
            parts.append(f"- {s}")

    return "\n".join(parts)
