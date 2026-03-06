"""
Unit tests for CIT (Thuế TNDN) rules.
Tests enterprise method and household method.
"""

import pytest

from core.tax_rules.base import CustomerType, TaxCategory, TaxContext
from core.tax_rules.cit import CITRule, CIT_RATE_STANDARD, CIT_REVENUE_THRESHOLD_SIMPLIFIED


@pytest.fixture
def cit_rule():
    return CITRule()


class TestCITRuleCategory:
    def test_category_is_cit(self, cit_rule: CITRule):
        assert cit_rule.category == TaxCategory.CIT


class TestCITEnterprise:
    """Thuế TNDN cho doanh nghiệp."""

    def test_standard_rate_20_percent(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.SME, income=1_000_000_000)
        result = cit_rule.calculate(ctx)

        assert result.rate == CIT_RATE_STANDARD  # 20%
        assert result.amount == 200_000_000  # 1 tỷ × 20%

    def test_zero_income(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.SME, income=0)
        result = cit_rule.calculate(ctx)

        assert result.amount == 0

    def test_none_income_defaults_to_zero(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.SME, income=None)
        result = cit_rule.calculate(ctx)

        assert result.amount == 0

    def test_large_income(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.SME, income=10_000_000_000)
        result = cit_rule.calculate(ctx)

        assert result.amount == 2_000_000_000  # 10 tỷ × 20%

    def test_explanation_mentions_tndn(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.SME, income=500_000_000)
        result = cit_rule.calculate(ctx)

        assert "TNDN" in result.explanation

    def test_legal_basis_present(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.SME, income=500_000_000)
        result = cit_rule.calculate(ctx)

        assert len(result.legal_basis) >= 2
        assert any("78/2014" in ref for ref in result.legal_basis)

    def test_unknown_customer_uses_enterprise(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.UNKNOWN, income=1_000_000_000)
        result = cit_rule.calculate(ctx)

        assert result.rate == CIT_RATE_STANDARD
        assert "TNDN" in result.explanation


class TestCITHousehold:
    """Thuế TNCN cho hộ kinh doanh (tính trên doanh thu)."""

    def test_default_rate_other_industry(self, cit_rule: CITRule):
        """Default industry 'other' → 1%."""
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=500_000_000)
        result = cit_rule.calculate(ctx)

        assert result.rate == 0.01
        assert result.amount == 5_000_000  # 500tr × 1%

    def test_individual_uses_household_method(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.INDIVIDUAL, revenue=500_000_000)
        result = cit_rule.calculate(ctx)

        assert "hộ kinh doanh" in result.explanation

    def test_distribution_rate(self, cit_rule: CITRule):
        """Phân phối hàng hóa → 0.5%."""
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=1_000_000_000,
            industry_code="distribution",
        )
        result = cit_rule.calculate(ctx)

        assert result.rate == 0.005
        assert result.amount == 5_000_000

    def test_services_rate(self, cit_rule: CITRule):
        """Dịch vụ → 2%."""
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=200_000_000,
            industry_code="services",
        )
        result = cit_rule.calculate(ctx)

        assert result.rate == 0.02
        assert result.amount == 4_000_000

    def test_manufacturing_rate(self, cit_rule: CITRule):
        """Sản xuất → 1.5%."""
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=400_000_000,
            industry_code="manufacturing",
        )
        result = cit_rule.calculate(ctx)

        assert result.rate == 0.015
        assert result.amount == 6_000_000

    def test_legal_basis_references_tt40(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=500_000_000)
        result = cit_rule.calculate(ctx)

        assert any("40/2021" in ref for ref in result.legal_basis)


class TestCITHouseholdWarnings:
    def test_warning_below_threshold(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=80_000_000)
        result = cit_rule.calculate(ctx)

        assert len(result.warnings) == 1
        assert "100 triệu" in result.warnings[0]

    def test_no_warning_above_threshold(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=200_000_000)
        result = cit_rule.calculate(ctx)

        assert len(result.warnings) == 0

    def test_no_warning_at_exact_threshold(self, cit_rule: CITRule):
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=CIT_REVENUE_THRESHOLD_SIMPLIFIED,
        )
        result = cit_rule.calculate(ctx)

        assert len(result.warnings) == 0

    def test_no_warning_for_enterprise(self, cit_rule: CITRule):
        ctx = TaxContext(customer_type=CustomerType.SME, income=50_000_000)
        result = cit_rule.calculate(ctx)

        assert len(result.warnings) == 0


class TestCITGetInfo:
    def test_sme_info(self, cit_rule: CITRule):
        info = cit_rule.get_info(CustomerType.SME)
        assert "20%" in info
        assert "TNDN" in info

    def test_household_info(self, cit_rule: CITRule):
        info = cit_rule.get_info(CustomerType.HOUSEHOLD)
        assert "TNCN" in info
        assert "100 triệu" in info

    def test_individual_same_as_household(self, cit_rule: CITRule):
        assert cit_rule.get_info(CustomerType.INDIVIDUAL) == cit_rule.get_info(CustomerType.HOUSEHOLD)
