"""
Unit tests for PIT (Thuế TNCN) progressive tax calculation.
Verifies 7-bracket progressive tax system and personal deductions.
"""

import pytest

from core.tax_rules.base import CustomerType, TaxCategory, TaxContext
from core.tax_rules.pit import (
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
    """Test personal deduction logic."""

    def test_income_below_personal_deduction_is_zero_tax(self, pit_rule: PITRule):
        """Income ≤ 11 triệu → no tax."""
        ctx = TaxContext(income=11_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == 0

    def test_income_exactly_at_deduction(self, pit_rule: PITRule):
        ctx = TaxContext(income=PERSONAL_DEDUCTION)
        result = pit_rule.calculate(ctx)

        assert result.amount == 0

    def test_dependent_deduction_applied(self, pit_rule: PITRule):
        """Income 20 triệu, 2 dependents → deduction = 11 + 2×4.4 = 19.8 triệu."""
        ctx = TaxContext(income=20_000_000, extra={"dependents": 2})
        result = pit_rule.calculate(ctx)

        # Taxable = 20 - 19.8 = 0.2 triệu → 200k × 5% = 10k
        assert result.amount == pytest.approx(10_000, rel=1e-2)

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
    Test the 7-bracket progressive tax calculation.
    Taxable income = Income - 11,000,000 (personal deduction)

    Brackets (monthly, on taxable income):
      0 -  5 triệu: 5%
      5 - 10 triệu: 10%
     10 - 18 triệu: 15%
     18 - 32 triệu: 20%
     32 - 52 triệu: 25%
     52 - 80 triệu: 30%
     80+  triệu: 35%
    """

    def test_bracket_1_only(self, pit_rule: PITRule):
        """Income 15 triệu → taxable = 4 triệu → 4tr × 5% = 200k."""
        ctx = TaxContext(income=15_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(200_000)

    def test_bracket_1_full(self, pit_rule: PITRule):
        """Income 16 triệu → taxable = 5 triệu → 5tr × 5% = 250k."""
        ctx = TaxContext(income=16_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(250_000)

    def test_bracket_2(self, pit_rule: PITRule):
        """Income 20 triệu → taxable = 9 triệu.
        5tr × 5% + 4tr × 10% = 250k + 400k = 650k.
        """
        ctx = TaxContext(income=20_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(650_000)

    def test_bracket_3(self, pit_rule: PITRule):
        """Income 25 triệu → taxable = 14 triệu.
        5tr × 5% + 5tr × 10% + 4tr × 15% = 250k + 500k + 600k = 1,350k.
        """
        ctx = TaxContext(income=25_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(1_350_000)

    def test_bracket_4(self, pit_rule: PITRule):
        """Income 40 triệu → taxable = 29 triệu.
        5×5% + 5×10% + 8×15% + 11×20%
        = 250k + 500k + 1,200k + 2,200k = 4,150k.
        """
        ctx = TaxContext(income=40_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(4_150_000)

    def test_bracket_5(self, pit_rule: PITRule):
        """Income 60 triệu → taxable = 49 triệu.
        5×5% + 5×10% + 8×15% + 14×20% + 17×25%
        = 250k + 500k + 1,200k + 2,800k + 4,250k = 9,000k.
        """
        ctx = TaxContext(income=60_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(9_000_000)

    def test_bracket_6(self, pit_rule: PITRule):
        """Income 80 triệu → taxable = 69 triệu.
        5×5% + 5×10% + 8×15% + 14×20% + 20×25% + 17×30%
        = 250k + 500k + 1,200k + 2,800k + 5,000k + 5,100k = 14,850k.
        """
        ctx = TaxContext(income=80_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(14_850_000)

    def test_bracket_7_highest(self, pit_rule: PITRule):
        """Income 100 triệu → taxable = 89 triệu.
        5×5% + 5×10% + 8×15% + 14×20% + 20×25% + 28×30% + 9×35%
        = 250k + 500k + 1,200k + 2,800k + 5,000k + 8,400k + 3,150k = 21,300k.
        """
        ctx = TaxContext(income=100_000_000)
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(21_300_000)

    def test_very_high_income(self, pit_rule: PITRule):
        """Income 200 triệu → taxable = 189 triệu.
        5×5% + 5×10% + 8×15% + 14×20% + 20×25% + 28×30% + 109×35%.
        """
        ctx = TaxContext(income=200_000_000)
        result = pit_rule.calculate(ctx)

        expected = (
            5_000_000 * 0.05
            + 5_000_000 * 0.10
            + 8_000_000 * 0.15
            + 14_000_000 * 0.20
            + 20_000_000 * 0.25
            + 28_000_000 * 0.30
            + 109_000_000 * 0.35
        )
        assert result.amount == pytest.approx(expected)


class TestPITWithDependents:
    """Test combinations of income + dependents."""

    def test_high_income_3_dependents(self, pit_rule: PITRule):
        """Income 50 triệu, 3 dependents.
        Deduction = 11 + 3×4.4 = 24.2 triệu.
        Taxable = 25.8 triệu.
        5×5% + 5×10% + 8×15% + 7.8×20%
        = 250k + 500k + 1,200k + 1,560k = 3,510k.
        """
        ctx = TaxContext(income=50_000_000, extra={"dependents": 3})
        result = pit_rule.calculate(ctx)

        assert result.amount == pytest.approx(3_510_000)

    def test_income_fully_offset_by_dependents(self, pit_rule: PITRule):
        """Income 20 triệu, 3 dependents → deduction 24.2 triệu > income → 0 tax."""
        ctx = TaxContext(income=20_000_000, extra={"dependents": 3})
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
        assert any("954" in ref for ref in result.legal_basis)

    def test_explanation_contains_breakdown(self, pit_rule: PITRule):
        ctx = TaxContext(income=30_000_000)
        result = pit_rule.calculate(ctx)

        assert "lũy tiến" in result.explanation
        assert "giảm trừ" in result.explanation.lower()


class TestPITGetInfo:
    def test_info_contains_deduction_amounts(self, pit_rule: PITRule):
        info = pit_rule.get_info(CustomerType.SME)

        assert "11 triệu" in info
        assert "4.4 triệu" in info
        assert "5% - 35%" in info
