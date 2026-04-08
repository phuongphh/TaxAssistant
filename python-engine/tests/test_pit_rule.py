"""
Unit tests for PIT (Thuế TNCN) progressive tax calculation.
Verifies 5-bracket progressive tax system (Luật 109/2025/QH15)
and personal deductions (NQ 110/2025/UBTVQH15).
"""

import pytest

from app.core.tax_rules.base import CustomerType, TaxCategory, TaxContext
from app.core.tax_rules.pit import (
    PITRule,
    PERSONAL_DEDUCTION,
    DEPENDENT_DEDUCTION,
)


@pytest.fixture
def pit_rule():
    return PITRule()


class TestPITRuleCategory:
    def test_category_is_pit(self, pit_rule: PITRule):
        assert pit_rule.category == TaxCategory.PIT


class TestPITDeductions:
    """Test personal deduction logic (NQ 110/2025: 15.5M personal, 6.2M dependent)."""

    def test_income_below_personal_deduction_is_zero_tax(self, pit_rule: PITRule):
        """Income ≤ 15.5 triệu → no tax."""
        ctx = TaxContext(income=15_500_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == 0

    def test_income_exactly_at_deduction(self, pit_rule: PITRule):
        ctx = TaxContext(income=PERSONAL_DEDUCTION)
        result = pit_rule.calculate(ctx)

        assert result.amount == 0

    def test_dependent_deduction_applied(self, pit_rule: PITRule):
        """Income 28 triệu, 2 dependents → deduction = 15.5 + 2×6.2 = 27.9 triệu."""
        ctx = TaxContext(income=28_000_000, extra={"dependents": 2})
        result = pit_rule.calculate(ctx)

        # Taxable = 28 - 27.9 = 0.1 triệu → 100k × 5% = 5k
        assert result.amount == pytest.approx(5_000, rel=1e-2)

    def test_zero_income(self, pit_rule: PITRule):
        ctx = TaxContext(income=0)
        result = pit_rule.calculate(ctx)

        assert result.amount == 0

    def test_none_income(self, pit_rule: PITRule):
        ctx = TaxContext(income=None)
        result = pit_rule.calculate(ctx)

        assert result.amount == 0


class TestPITProgressiveBrackets:
    """
    Test the 5-bracket progressive tax calculation (Luật 109/2025/QH15).
    Taxable income = Income - 15,500,000 (personal deduction)

    Brackets (monthly, on taxable income):
       0 -  10 triệu: 5%
      10 -  30 triệu: 10%
      30 -  60 triệu: 20%
      60 - 100 triệu: 30%
     100+  triệu: 35%
    """

    def test_bracket_1_only(self, pit_rule: PITRule):
        """Income 20 triệu → taxable = 4.5 triệu → 4.5tr × 5% = 225k."""
        ctx = TaxContext(income=20_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(225_000)

    def test_bracket_1_full(self, pit_rule: PITRule):
        """Income 25.5 triệu → taxable = 10 triệu → 10tr × 5% = 500k."""
        ctx = TaxContext(income=25_500_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(500_000)

    def test_bracket_2(self, pit_rule: PITRule):
        """Income 30 triệu → taxable = 14.5 triệu.
        10tr × 5% + 4.5tr × 10% = 500k + 450k = 950k.
        """
        ctx = TaxContext(income=30_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(950_000)

    def test_bracket_3(self, pit_rule: PITRule):
        """Income 60 triệu → taxable = 44.5 triệu.
        10×5% + 20×10% + 14.5×20% = 500k + 2,000k + 2,900k = 5,400k.
        """
        ctx = TaxContext(income=60_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(5_400_000)

    def test_bracket_4(self, pit_rule: PITRule):
        """Income 100 triệu → taxable = 84.5 triệu.
        10×5% + 20×10% + 30×20% + 24.5×30%
        = 500k + 2,000k + 6,000k + 7,350k = 15,850k.
        """
        ctx = TaxContext(income=100_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(15_850_000)

    def test_bracket_5_highest(self, pit_rule: PITRule):
        """Income 150 triệu → taxable = 134.5 triệu.
        10×5% + 20×10% + 30×20% + 40×30% + 34.5×35%
        = 500k + 2,000k + 6,000k + 12,000k + 12,075k = 32,575k.
        """
        ctx = TaxContext(income=150_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(32_575_000)

    def test_very_high_income(self, pit_rule: PITRule):
        """Income 200 triệu → taxable = 184.5 triệu.
        10×5% + 20×10% + 30×20% + 40×30% + 84.5×35%.
        """
        ctx = TaxContext(income=200_000_000)
        result = pit_rule.calculate(ctx)

        expected = (
            10_000_000 * 0.05
            + 20_000_000 * 0.10
            + 30_000_000 * 0.20
            + 40_000_000 * 0.30
            + 84_500_000 * 0.35
        )
        assert result.amount == pytest.approx(expected)


class TestPITWithDependents:
    """Test combinations of income + dependents."""

    def test_high_income_3_dependents(self, pit_rule: PITRule):
        """Income 50 triệu, 3 dependents.
        Deduction = 15.5 + 3×6.2 = 34.1 triệu.
        Taxable = 15.9 triệu.
        10×5% + 5.9×10% = 500k + 590k = 1,090k.
        """
        ctx = TaxContext(income=50_000_000, extra={"dependents": 3})
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(1_090_000)

    def test_income_fully_offset_by_dependents(self, pit_rule: PITRule):
        """Income 30 triệu, 3 dependents → deduction 34.1 triệu > income → 0 tax."""
        ctx = TaxContext(income=30_000_000, extra={"dependents": 3})
        result = pit_rule.calculate(ctx)

        assert result.amount == 0


class TestPITResultMetadata:
    def test_effective_rate_calculated(self, pit_rule: PITRule):
        ctx = TaxContext(income=30_000_000)
        result = pit_rule.calculate(ctx)

        assert result.rate > 0
        assert result.rate < 0.35  # Should be less than max bracket

    def test_effective_rate_zero_for_no_income(self, pit_rule: PITRule):
        ctx = TaxContext(income=0)
        result = pit_rule.calculate(ctx)

        assert result.rate == 0

    def test_legal_basis_present(self, pit_rule: PITRule):
        ctx = TaxContext(income=30_000_000)
        result = pit_rule.calculate(ctx)

        assert len(result.legal_basis) >= 2
        assert any("TNCN" in ref for ref in result.legal_basis)
        assert any("110" in ref for ref in result.legal_basis)

    def test_explanation_contains_breakdown(self, pit_rule: PITRule):
        ctx = TaxContext(income=30_000_000)
        result = pit_rule.calculate(ctx)

        assert "lũy tiến" in result.explanation
        assert "giảm trừ" in result.explanation.lower()


class TestPITGetInfo:
    def test_info_contains_deduction_amounts(self, pit_rule: PITRule):
        info = pit_rule.get_info(CustomerType.SME)

        assert "15.5 triệu" in info
        assert "6.2 triệu" in info
        assert "5% - 35%" in info
