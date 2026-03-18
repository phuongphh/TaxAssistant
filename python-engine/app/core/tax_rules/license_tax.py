"""
License Tax (Thuế Môn Bài) rules.

Key references:
- Nghị định 139/2016/NĐ-CP
- Thông tư 302/2016/TT-BTC
"""

from .base import CustomerType, TaxCategory, TaxContext, TaxResult, TaxRule

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


class LicenseTaxRule(TaxRule):
    @property
    def category(self) -> TaxCategory:
        return TaxCategory.LICENSE

    def calculate(self, context: TaxContext) -> TaxResult:
        if context.customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            return self._calculate_household(context)
        return self._calculate_enterprise(context)

    def _calculate_enterprise(self, context: TaxContext) -> TaxResult:
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
                f"Thuế Môn bài cho doanh nghiệp:\n"
                f"• Vốn điều lệ: {charter_capital:,.0f} VND\n"
                f"• Mức thuế: {amount:,.0f} VND/năm\n\n"
                f"Lưu ý: DN mới thành lập được miễn thuế môn bài năm đầu tiên."
            ),
            legal_basis=["Nghị định 139/2016/NĐ-CP"],
        )

    def _calculate_household(self, context: TaxContext) -> TaxResult:
        revenue = context.revenue or 0

        amount = 0
        for threshold, tax in LICENSE_TAX_HOUSEHOLD:
            if revenue > threshold:
                amount = tax
                break

        warnings = []
        if revenue <= 100_000_000:
            warnings.append("Doanh thu ≤ 100 triệu VND/năm: Được miễn thuế môn bài")

        return TaxResult(
            category=TaxCategory.LICENSE,
            amount=amount,
            explanation=(
                f"Thuế Môn bài cho hộ kinh doanh:\n"
                f"• Doanh thu: {revenue:,.0f} VND/năm\n"
                f"• Mức thuế: {amount:,.0f} VND/năm"
            ),
            legal_basis=["Nghị định 139/2016/NĐ-CP", "Thông tư 302/2016/TT-BTC"],
            warnings=warnings,
        )

    def get_info(self, customer_type: CustomerType) -> str:
        if customer_type in (CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL):
            return (
                "Thuế Môn bài cho hộ kinh doanh:\n"
                "• DT > 500 triệu: 1.000.000 VND/năm\n"
                "• DT 300-500 triệu: 500.000 VND/năm\n"
                "• DT 100-300 triệu: 300.000 VND/năm\n"
                "• DT ≤ 100 triệu: Miễn\n"
                "• Nộp: Trước ngày 30/01 hàng năm"
            )
        return (
            "Thuế Môn bài cho doanh nghiệp:\n"
            "• Vốn > 10 tỷ: 3.000.000 VND/năm\n"
            "• Vốn ≤ 10 tỷ: 2.000.000 VND/năm\n"
            "• DN mới: Miễn năm đầu tiên\n"
            "• Nộp: Trước ngày 30/01 hàng năm"
        )

    def get_consultation(
        self, customer_type: CustomerType, entities: dict | None = None,
    ) -> str:
        is_household = customer_type in (
            CustomerType.HOUSEHOLD, CustomerType.INDIVIDUAL,
        )

        lines = ["Tư vấn Thuế Môn bài:\n"]

        lines.append("1. Biểu mức thuế:")
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

        lines.append("\n2. Miễn thuế môn bài:")
        if is_household:
            lines.append("   • Hộ KD có doanh thu ≤ 100 triệu VND/năm")
            lines.append("   • Cá nhân, nhóm cá nhân, hộ gia đình hoạt động sản xuất")
            lines.append("     nông/lâm/ngư/diêm nghiệp")
        else:
            lines.append("   • DN mới thành lập: miễn thuế môn bài năm đầu tiên")
            lines.append("   • Chi nhánh, văn phòng đại diện, địa điểm KD: nộp riêng")

        lines.append("\n3. Thời hạn nộp:")
        lines.append("   • Hạn: Trước ngày 30/01 hàng năm")
        lines.append("   • DN mới thành lập trong năm: nộp trong 30 ngày kể từ ngày được cấp ĐKKD")

        lines.append("\n4. Căn cứ pháp lý:")
        lines.append("   • Nghị định 139/2016/NĐ-CP")
        lines.append("   • Thông tư 302/2016/TT-BTC")

        lines.append(
            "\n💡 Để tính mức thuế cụ thể, bạn có thể cung cấp vốn điều lệ hoặc doanh thu. "
            "VD: \"thuế môn bài vốn 5 tỷ\""
        )
        return "\n".join(lines)
