"""
License Tax (Lệ phí Môn Bài) rules.

Key references:
- Nghị quyết 198/2025/QH15 (17/05/2025) — bãi bỏ lệ phí môn bài từ 01/01/2026
- Nghị định 362/2025/NĐ-CP (31/12/2025) — quy định chi tiết Luật Phí và lệ phí,
  bãi bỏ Nghị định 139/2016/NĐ-CP và Nghị định 22/2020/NĐ-CP
- Công văn 645/CT-CS (Tổng cục Thuế) — hướng dẫn không thu lệ phí môn bài
  từ 01/01/2026

Văn bản hết hiệu lực (chỉ áp dụng cho kỳ ≤ 2025):
- Nghị định 139/2016/NĐ-CP
- Nghị định 22/2020/NĐ-CP (sửa đổi NĐ 139/2016)
- Thông tư 302/2016/TT-BTC

Xem thêm: docs/legal-changelog.md
"""

from datetime import date

from .base import CustomerType, TaxCategory, TaxContext, TaxResult, TaxRule

# Năm bắt đầu bãi bỏ lệ phí môn bài. Trước năm này (≤ 2025) vẫn áp dụng
# Nghị định 139/2016/NĐ-CP để hoàn tất nghĩa vụ kỳ cũ.
LICENSE_TAX_ABOLISHED_FROM_YEAR = 2026

_ABOLITION_LEGAL_BASIS = [
    "Nghị quyết 198/2025/QH15 (Điều 10) — bãi bỏ lệ phí môn bài từ 01/01/2026",
    "Nghị định 362/2025/NĐ-CP — bãi bỏ Nghị định 139/2016/NĐ-CP và 22/2020/NĐ-CP",
]

_HISTORICAL_LEGAL_BASIS = [
    "Nghị định 139/2016/NĐ-CP (hết hiệu lực từ 01/01/2026)",
    "Nghị định 22/2020/NĐ-CP (hết hiệu lực từ 01/01/2026)",
    "Thông tư 302/2016/TT-BTC (hết hiệu lực từ 01/01/2026)",
]

# --- Load License Tax parameters from config (with hardcoded fallbacks) ---
_DEFAULT_ENTERPRISE_TIERS = [
    (10_000_000_000, 3_000_000),  # Vốn > 10 tỷ: 3 triệu/năm
    (0, 2_000_000),  # Vốn ≤ 10 tỷ: 2 triệu/năm
]
_DEFAULT_HOUSEHOLD_TIERS = [
    (500_000_000, 1_000_000),  # DT > 500 triệu: 1 triệu/năm
    (300_000_000, 500_000),  # DT 300-500 triệu: 500k/năm
    (100_000_000, 300_000),  # DT 100-300 triệu: 300k/năm
    (0, 0),  # DT ≤ 100 triệu: Miễn thuế môn bài
]

try:
    from data.tax_config_loader import tax_config as _cfg
    _raw_enterprise = _cfg._data.get("license_tax", {}).get("enterprise_tiers")
    _raw_household = _cfg._data.get("license_tax", {}).get("household_tiers")
    LICENSE_TAX_ENTERPRISE: list[tuple[int, int]] = (
        [(t["capital_threshold"], t["amount"]) for t in _raw_enterprise]
        if _raw_enterprise else _DEFAULT_ENTERPRISE_TIERS
    )
    LICENSE_TAX_HOUSEHOLD: list[tuple[int, int]] = (
        [(t["revenue_threshold"], t["amount"]) for t in _raw_household]
        if _raw_household else _DEFAULT_HOUSEHOLD_TIERS
    )
except Exception:
    LICENSE_TAX_ENTERPRISE = _DEFAULT_ENTERPRISE_TIERS
    LICENSE_TAX_HOUSEHOLD = _DEFAULT_HOUSEHOLD_TIERS


def _resolve_tax_year(context: TaxContext) -> int:
    """Tax year = context.year nếu được cung cấp, không thì lấy năm hiện tại.

    Cho phép user query chính xác cho năm cũ (vd hoàn tất nghĩa vụ 2025).
    """
    if context.year:
        return context.year
    extra_year = (context.extra or {}).get("tax_year") or (context.extra or {}).get("year")
    if extra_year:
        try:
            return int(extra_year)
        except (TypeError, ValueError):
            pass
    return date.today().year


class LicenseTaxRule(TaxRule):
    @property
    def category(self) -> TaxCategory:
        return TaxCategory.LICENSE

    def calculate(self, context: TaxContext) -> TaxResult:
        tax_year = _resolve_tax_year(context)
        if tax_year >= LICENSE_TAX_ABOLISHED_FROM_YEAR:
            return self._abolished_result(tax_year)
        if context.customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            return self._calculate_household(context, tax_year=tax_year)
        return self._calculate_enterprise(context, tax_year=tax_year)

    @staticmethod
    def _abolished_result(tax_year: int) -> TaxResult:
        return TaxResult(
            category=TaxCategory.LICENSE,
            amount=0,
            rate=0,
            explanation=(
                f"Lệ phí môn bài đã được BÃI BỎ từ ngày 01/01/2026.\n\n"
                f"• Năm tính phí: {tax_year}\n"
                f"• Mức phải nộp: 0 đồng\n"
                f"• Người nộp thuế KHÔNG phải kê khai và nộp lệ phí môn bài "
                f"cho năm {tax_year} và các năm tiếp theo.\n\n"
                "Căn cứ:\n"
                "• Nghị quyết 198/2025/QH15 ngày 17/05/2025 (Điều 10)\n"
                "• Nghị định 362/2025/NĐ-CP ngày 31/12/2025\n"
                "• Công văn 645/CT-CS của Tổng cục Thuế\n\n"
                "Lưu ý: Nếu bạn còn nghĩa vụ chưa hoàn thành cho năm 2025 trở về "
                "trước, vui lòng cung cấp năm cụ thể (ví dụ: \"lệ phí môn bài 2025\")."
            ),
            legal_basis=list(_ABOLITION_LEGAL_BASIS),
            warnings=[
                "Thông tin này dựa trên Nghị quyết 198/2025/QH15 và Nghị định "
                "362/2025/NĐ-CP. Vui lòng xác nhận với cơ quan thuế nếu có thay "
                "đổi pháp luật gần đây."
            ],
        )

    def _calculate_enterprise(self, context: TaxContext, tax_year: int) -> TaxResult:
        charter_capital = context.extra.get("charter_capital", 0)

        amount = LICENSE_TAX_ENTERPRISE[-1][1]  # default
        for threshold, tax in LICENSE_TAX_ENTERPRISE:
            if charter_capital > threshold:
                amount = tax
                break

        return TaxResult(
            category=TaxCategory.LICENSE,
            amount=amount,
            explanation=(
                f"Lệ phí môn bài cho doanh nghiệp (kỳ {tax_year}):\n"
                f"• Vốn điều lệ: {charter_capital:,.0f} VND\n"
                f"• Mức phí: {amount:,.0f} VND/năm\n\n"
                f"Lưu ý: DN mới thành lập được miễn lệ phí môn bài năm đầu tiên.\n"
                f"⚠️ Quan trọng: Lệ phí môn bài đã được bãi bỏ từ 01/01/2026 "
                f"(Nghị quyết 198/2025/QH15). Mức phí trên chỉ áp dụng cho kỳ ≤ 2025."
            ),
            legal_basis=list(_HISTORICAL_LEGAL_BASIS),
            warnings=[
                f"Thông tin áp dụng cho kỳ {tax_year}. Từ năm 2026 trở đi, "
                "lệ phí môn bài đã được bãi bỏ — vui lòng không kê khai cho "
                "năm 2026 và các năm sau."
            ],
        )

    def _calculate_household(self, context: TaxContext, tax_year: int) -> TaxResult:
        revenue = context.revenue or 0

        amount = 0
        for threshold, tax in LICENSE_TAX_HOUSEHOLD:
            if revenue > threshold:
                amount = tax
                break

        warnings = [
            f"Thông tin áp dụng cho kỳ {tax_year}. Từ năm 2026 trở đi, "
            "lệ phí môn bài đã được bãi bỏ — vui lòng không kê khai cho "
            "năm 2026 và các năm sau."
        ]
        if revenue <= 100_000_000:
            warnings.insert(0, "Doanh thu ≤ 100 triệu VND/năm: Được miễn lệ phí môn bài")

        return TaxResult(
            category=TaxCategory.LICENSE,
            amount=amount,
            explanation=(
                f"Lệ phí môn bài cho hộ kinh doanh (kỳ {tax_year}):\n"
                f"• Doanh thu: {revenue:,.0f} VND/năm\n"
                f"• Mức phí: {amount:,.0f} VND/năm\n\n"
                f"⚠️ Quan trọng: Lệ phí môn bài đã được bãi bỏ từ 01/01/2026 "
                f"(Nghị quyết 198/2025/QH15). Mức phí trên chỉ áp dụng cho kỳ ≤ 2025."
            ),
            legal_basis=list(_HISTORICAL_LEGAL_BASIS),
            warnings=warnings,
        )

    def get_info(self, customer_type: CustomerType) -> str:
        # Thông tin chung — luôn nêu rõ tình trạng pháp lý hiện hành
        header = (
            "⚠️ Lệ phí môn bài đã được BÃI BỎ từ 01/01/2026 theo Nghị quyết "
            "198/2025/QH15 và Nghị định 362/2025/NĐ-CP.\n"
            "→ Năm 2026 và các năm tiếp theo: KHÔNG phải kê khai/nộp lệ phí môn bài.\n\n"
            "Mức phí áp dụng cho kỳ ≤ 2025 (để tham khảo lịch sử / hoàn tất "
            "nghĩa vụ kỳ cũ):\n"
        )
        if customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            return header + (
                "Hộ kinh doanh:\n"
                "• DT > 500 triệu: 1.000.000 VND/năm\n"
                "• DT 300-500 triệu: 500.000 VND/năm\n"
                "• DT 100-300 triệu: 300.000 VND/năm\n"
                "• DT ≤ 100 triệu: Miễn\n"
                "• Hạn nộp (kỳ ≤ 2025): Trước 30/01 hàng năm"
            )
        return header + (
            "Doanh nghiệp:\n"
            "• Vốn > 10 tỷ: 3.000.000 VND/năm\n"
            "• Vốn ≤ 10 tỷ: 2.000.000 VND/năm\n"
            "• DN mới: Miễn năm đầu tiên\n"
            "• Hạn nộp (kỳ ≤ 2025): Trước 30/01 hàng năm"
        )

    def get_consultation(
        self, customer_type: CustomerType, entities: dict | None = None,
    ) -> str:
        is_household = customer_type in (
            CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL,
        )

        lines = [
            "Tư vấn Lệ phí môn bài:\n",
            "⚠️ THAY ĐỔI PHÁP LUẬT QUAN TRỌNG:",
            "• Từ 01/01/2026, lệ phí môn bài đã chính thức bị BÃI BỎ.",
            "• Người nộp thuế (cả DN và hộ KD) KHÔNG còn phải kê khai và nộp",
            "  lệ phí môn bài cho năm 2026 và các năm tiếp theo.",
            "• Căn cứ: Nghị quyết 198/2025/QH15 (Điều 10),",
            "  Nghị định 362/2025/NĐ-CP (bãi bỏ NĐ 139/2016 và 22/2020).\n",
            "Phần dưới chỉ áp dụng cho kỳ ≤ 2025 (để tham khảo / hoàn tất nghĩa vụ kỳ cũ):\n",
            "1. Biểu mức phí (kỳ ≤ 2025):",
        ]
        if is_household:
            lines.append("   Hộ kinh doanh (theo doanh thu/năm):")
            for threshold, amount in LICENSE_TAX_HOUSEHOLD:
                if threshold == 0 and amount == 0:
                    lines.append("   • DT ≤ 100 triệu: Miễn thuế môn bài")
                elif threshold == 100_000_000:
                    lines.append(f"   • DT 100-300 triệu: {amount:,.0f} VND/năm")
                elif threshold == 300_000_000:
                    lines.append(f"   • DT 300-500 triệu: {amount:,.0f} VND/năm")
                else:
                    lines.append(f"   • DT > {threshold / 1e6:.0f} triệu: {amount:,.0f} VND/năm")
        else:
            lines.append("   Doanh nghiệp (theo vốn điều lệ/vốn đầu tư):")
            for threshold, amount in LICENSE_TAX_ENTERPRISE:
                if threshold == 0:
                    lines.append(f"   • Vốn ≤ 10 tỷ: {amount:,.0f} VND/năm")
                else:
                    lines.append(f"   • Vốn > {threshold / 1e9:.0f} tỷ: {amount:,.0f} VND/năm")

        lines.append("\n2. Miễn lệ phí môn bài (theo NĐ 22/2020 — kỳ ≤ 2025):")
        if is_household:
            lines.append("   • Hộ KD có doanh thu ≤ 100 triệu VND/năm")
            lines.append("   • Cá nhân, nhóm cá nhân, hộ gia đình hoạt động sản xuất")
            lines.append("     nông/lâm/ngư/diêm nghiệp")
        else:
            lines.append("   • DN mới thành lập: miễn lệ phí môn bài năm đầu tiên")
            lines.append("   • Chi nhánh, văn phòng đại diện, địa điểm KD: nộp riêng")

        lines.append("\n3. Thời hạn nộp (kỳ ≤ 2025):")
        lines.append("   • Hạn: Trước ngày 30/01 hàng năm")
        lines.append("   • DN mới thành lập trong năm: nộp trong 30 ngày kể từ ngày được cấp ĐKKD")

        lines.append("\n4. Căn cứ pháp lý:")
        lines.append("   • Hiện hành (từ 01/01/2026):")
        lines.append("     - Nghị quyết 198/2025/QH15 (Điều 10) — BÃI BỎ lệ phí môn bài")
        lines.append("     - Nghị định 362/2025/NĐ-CP")
        lines.append("   • Hết hiệu lực (chỉ áp dụng kỳ ≤ 2025):")
        lines.append("     - Nghị định 139/2016/NĐ-CP")
        lines.append("     - Nghị định 22/2020/NĐ-CP")
        lines.append("     - Thông tư 302/2016/TT-BTC")

        lines.append(
            "\n💡 Lưu ý: Thông tin này dựa trên các văn bản nêu trên. Vui lòng "
            "xác nhận với cơ quan thuế nếu có thay đổi pháp luật gần đây."
        )
        return "\n".join(lines)
