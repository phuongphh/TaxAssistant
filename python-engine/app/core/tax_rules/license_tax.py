"""
License Tax (Thuế Môn Bài) rules.

Key references:
- Nghị định 139/2016/NĐ-CP
- Thông tư 302/2016/TT-BTC
"""

from .base import CustomerType, TaxCategory, TaxContext, TaxResult, TaxRule

# Mức thuế môn bài cho doanh nghiệp (theo vốn điều lệ)
LICENSE_TAX_ENTERPRISE = [
    (10_000_000_000, 3_000_000),  # Vốn > 10 tỷ: 3 triệu/năm
    (0, 2_000_000),  # Vốn ≤ 10 tỷ: 2 triệu/năm
]

# Mức thuế môn bài cho hộ kinh doanh (theo doanh thu)
LICENSE_TAX_HOUSEHOLD = [
    (500_000_000, 1_000_000),  # DT > 500 triệu: 1 triệu/năm
    (300_000_000, 500_000),  # DT 300-500 triệu: 500k/năm
    (100_000_000, 300_000),  # DT 100-300 triệu: 300k/năm
    (0, 0),  # DT ≤ 100 triệu: Miễn thuế môn bài
]


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
