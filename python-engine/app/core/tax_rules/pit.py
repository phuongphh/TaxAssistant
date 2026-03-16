"""
PIT (Thuế Thu Nhập Cá Nhân - TNCN) rules.

Key references:
- Luật Thuế TNCN số 109/2025/QH15 (có hiệu lực từ 01/07/2026,
  áp dụng cho thu nhập từ tiền lương từ kỳ tính thuế 2026)
- Nghị quyết 110/2025/UBTVQH15 (điều chỉnh giảm trừ gia cảnh, từ 01/01/2026)
- Thông tư 111/2013/TT-BTC (hướng dẫn, vẫn áp dụng phần không mâu thuẫn)

Tax parameters are loaded from data/tax_config.json at import time.
To update tax rules, edit tax_config.json and restart the service.
"""

from .base import CustomerType, TaxCategory, TaxContext, TaxResult, TaxRule

# --- Load tax parameters from config (with hardcoded fallbacks) ---
_DEFAULT_PERSONAL_DEDUCTION = 15_500_000
_DEFAULT_DEPENDENT_DEDUCTION = 6_200_000
_DEFAULT_BRACKETS = [
    (10_000_000, 0.05),   # Đến 10 triệu: 5%
    (30_000_000, 0.10),   # Trên 10 - 30 triệu: 10%
    (60_000_000, 0.20),   # Trên 30 - 60 triệu: 20%
    (100_000_000, 0.30),  # Trên 60 - 100 triệu: 30%
    (float("inf"), 0.35), # Trên 100 triệu: 35%
]
_DEFAULT_LEGAL_BASIS = [
    "Luật Thuế TNCN số 109/2025/QH15",
    "Nghị quyết 110/2025/UBTVQH15",
    "Thông tư 111/2013/TT-BTC",
]

try:
    from data.tax_config_loader import tax_config as _cfg
    PERSONAL_DEDUCTION: int = _cfg.pit_personal_deduction
    DEPENDENT_DEDUCTION: int = _cfg.pit_dependent_deduction
    PIT_BRACKETS: list[tuple[float, float]] = _cfg.pit_brackets
    _LEGAL_BASIS: list[str] = _cfg.pit_legal_basis
except Exception:
    # Config unavailable (missing file, test environment, etc.) → use defaults
    PERSONAL_DEDUCTION = _DEFAULT_PERSONAL_DEDUCTION
    DEPENDENT_DEDUCTION = _DEFAULT_DEPENDENT_DEDUCTION
    PIT_BRACKETS = _DEFAULT_BRACKETS
    _LEGAL_BASIS = _DEFAULT_LEGAL_BASIS


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
            legal_basis=list(_LEGAL_BASIS),
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
        min_rate = int(PIT_BRACKETS[0][1] * 100)
        max_rate = int(PIT_BRACKETS[-1][1] * 100)
        n_brackets = len(PIT_BRACKETS)
        return (
            "Thuế Thu nhập cá nhân (TNCN):\n"
            f"• Giảm trừ bản thân: {PERSONAL_DEDUCTION / 1e6:.1f} triệu/tháng\n"
            f"• Giảm trừ người phụ thuộc: {DEPENDENT_DEDUCTION / 1e6:.1f} triệu/người/tháng\n"
            f"• Thuế suất: {min_rate}% - {max_rate}% (biểu lũy tiến {n_brackets} bậc)\n"
            "• Kê khai: Hàng tháng hoặc hàng quý\n"
            "• Quyết toán: Hàng năm (trước 31/3 năm sau)"
        )
