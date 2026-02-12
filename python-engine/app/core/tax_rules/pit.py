"""
PIT (Thuế Thu Nhập Cá Nhân - TNCN) rules.

Key references:
- Luật Thuế TNCN số 04/2007/QH12 (sửa đổi, bổ sung)
- Thông tư 111/2013/TT-BTC
- Nghị quyết 954/2020/UBTVQH14 (mức giảm trừ gia cảnh)
"""

from .base import CustomerType, TaxCategory, TaxContext, TaxResult, TaxRule

# Mức giảm trừ gia cảnh (Personal deduction)
PERSONAL_DEDUCTION = 11_000_000  # 11 triệu VND/tháng cho bản thân
DEPENDENT_DEDUCTION = 4_400_000  # 4.4 triệu VND/tháng/người phụ thuộc

# Biểu thuế lũy tiến từng phần (Progressive tax brackets) - tháng
PIT_BRACKETS = [
    (5_000_000, 0.05),  # Đến 5 triệu: 5%
    (10_000_000, 0.10),  # Trên 5 - 10 triệu: 10%
    (18_000_000, 0.15),  # Trên 10 - 18 triệu: 15%
    (32_000_000, 0.20),  # Trên 18 - 32 triệu: 20%
    (52_000_000, 0.25),  # Trên 32 - 52 triệu: 25%
    (80_000_000, 0.30),  # Trên 52 - 80 triệu: 30%
    (float("inf"), 0.35),  # Trên 80 triệu: 35%
]


class PITRule(TaxRule):
    @property
    def category(self) -> TaxCategory:
        return TaxCategory.PIT

    def calculate(self, context: TaxContext) -> TaxResult:
        """Calculate PIT (progressive method for salary income)."""
        monthly_income = context.income or 0
        num_dependents = context.extra.get("dependents", 0)

        # Tính thu nhập chịu thuế
        deduction = PERSONAL_DEDUCTION + (DEPENDENT_DEDUCTION * num_dependents)
        taxable_income = max(0, monthly_income - deduction)

        # Tính thuế theo biểu lũy tiến
        tax_amount, breakdown = self._calculate_progressive(taxable_income)

        explanation_lines = [
            f"Thuế TNCN (thu nhập từ tiền lương, tiền công):\n",
            f"• Thu nhập hàng tháng: {monthly_income:,.0f} VND",
            f"• Giảm trừ bản thân: {PERSONAL_DEDUCTION:,.0f} VND",
            f"• Giảm trừ người phụ thuộc ({num_dependents} người): "
            f"{DEPENDENT_DEDUCTION * num_dependents:,.0f} VND",
            f"• Thu nhập chịu thuế: {taxable_income:,.0f} VND\n",
        ]

        if breakdown:
            explanation_lines.append("Tính thuế lũy tiến:")
            for bracket_desc, bracket_tax in breakdown:
                explanation_lines.append(f"  {bracket_desc}: {bracket_tax:,.0f} VND")

        explanation_lines.append(f"\n• Tổng thuế TNCN/tháng: {tax_amount:,.0f} VND")

        return TaxResult(
            category=TaxCategory.PIT,
            amount=tax_amount,
            rate=tax_amount / monthly_income if monthly_income > 0 else 0,
            explanation="\n".join(explanation_lines),
            legal_basis=[
                "Luật Thuế TNCN số 04/2007/QH12",
                "Thông tư 111/2013/TT-BTC",
                "Nghị quyết 954/2020/UBTVQH14",
            ],
        )

    def _calculate_progressive(
        self, taxable_income: float
    ) -> tuple[float, list[tuple[str, float]]]:
        """Apply progressive tax brackets."""
        total_tax = 0.0
        breakdown: list[tuple[str, float]] = []
        remaining = taxable_income
        prev_limit = 0

        for limit, rate in PIT_BRACKETS:
            if remaining <= 0:
                break
            bracket_amount = min(remaining, limit - prev_limit)
            bracket_tax = bracket_amount * rate
            total_tax += bracket_tax

            desc = f"Bậc {rate * 100:.0f}% ({prev_limit / 1e6:.0f}-{min(limit, taxable_income) / 1e6:.0f} triệu)"
            breakdown.append((desc, bracket_tax))

            remaining -= bracket_amount
            prev_limit = limit

        return total_tax, breakdown

    def get_info(self, customer_type: CustomerType) -> str:
        return (
            "Thuế Thu nhập cá nhân (TNCN):\n"
            f"• Giảm trừ bản thân: {PERSONAL_DEDUCTION / 1e6:.0f} triệu/tháng\n"
            f"• Giảm trừ người phụ thuộc: {DEPENDENT_DEDUCTION / 1e6:.1f} triệu/người/tháng\n"
            "• Thuế suất: 5% - 35% (biểu lũy tiến 7 bậc)\n"
            "• Kê khai: Hàng tháng hoặc hàng quý\n"
            "• Quyết toán: Hàng năm (trước 31/3 năm sau)"
        )
