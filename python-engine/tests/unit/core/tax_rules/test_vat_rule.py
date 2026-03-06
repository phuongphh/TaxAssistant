"""
Unit tests for VAT (Thuế GTGT) rules.
Tests both deduction method (SME) and direct method (household/individual).
"""

import pytest

from core.tax_rules.base import CustomerType, TaxCategory, TaxContext
from core.tax_rules.vat import VATRule, VAT_RATE_STANDARD, VAT_REGISTRATION_THRESHOLD


@pytest.fixture
def vat_rule():
    return VATRule()


class TestVATRuleCategory:
    def test_category_is_vat(self, vat_rule: VATRule):
        assert vat_rule.category == TaxCategory.VAT


class TestVATDeductionMethod:
    """Phương pháp khấu trừ - SME."""

    def test_sme_standard_rate(self, vat_rule: VATRule):
        ctx = TaxContext(customer_type=CustomerType.SME, revenue=1_000_000_000)
        result = vat_rule.calculate(ctx)

        assert result.category == TaxCategory.VAT
        assert result.rate == VAT_RATE_STANDARD  # 10%
        assert result.amount == 100_000_000  # 1 tỷ × 10%

    def test_sme_zero_revenue(self, vat_rule: VATRule):
        ctx = TaxContext(customer_type=CustomerType.SME, revenue=0)
        result = vat_rule.calculate(ctx)

        assert result.amount == 0
        assert result.rate == VAT_RATE_STANDARD

    def test_sme_none_revenue_defaults_to_zero(self, vat_rule: VATRule):
        ctx = TaxContext(customer_type=CustomerType.SME, revenue=None)
        result = vat_rule.calculate(ctx)

        assert result.amount == 0

    def test_sme_large_revenue(self, vat_rule: VATRule):
        ctx = TaxContext(customer_type=CustomerType.SME, revenue=50_000_000_000)  # 50 tỷ
        result = vat_rule.calculate(ctx)

        assert result.amount == 5_000_000_000  # 5 tỷ

    def test_sme_explanation_contains_method(self, vat_rule: VATRule):
        ctx = TaxContext(customer_type=CustomerType.SME, revenue=500_000_000)
        result = vat_rule.calculate(ctx)

        assert "khấu trừ" in result.explanation

    def test_sme_has_legal_basis(self, vat_rule: VATRule):
        ctx = TaxContext(customer_type=CustomerType.SME, revenue=500_000_000)
        result = vat_rule.calculate(ctx)

        assert len(result.legal_basis) >= 1
        assert any("GTGT" in ref or "219" in ref for ref in result.legal_basis)

    def test_unknown_customer_uses_deduction_method(self, vat_rule: VATRule):
        """UNKNOWN customer type should default to deduction (SME) method."""
        ctx = TaxContext(customer_type=CustomerType.UNKNOWN, revenue=1_000_000_000)
        result = vat_rule.calculate(ctx)

        assert result.rate == VAT_RATE_STANDARD
        assert "khấu trừ" in result.explanation


class TestVATDirectMethod:
    """Phương pháp trực tiếp - Hộ kinh doanh / Cá thể."""

    def test_household_default_rate(self, vat_rule: VATRule):
        """Default industry ('other') → 2%."""
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=500_000_000)
        result = vat_rule.calculate(ctx)

        assert result.rate == 0.02
        assert result.amount == 10_000_000  # 500tr × 2%

    def test_individual_uses_direct_method(self, vat_rule: VATRule):
        ctx = TaxContext(customer_type=CustomerType.INDIVIDUAL, revenue=500_000_000)
        result = vat_rule.calculate(ctx)

        assert "trực tiếp" in result.explanation

    def test_distribution_industry_rate(self, vat_rule: VATRule):
        """Phân phối hàng hóa → 1%."""
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=1_000_000_000,
            industry_code="distribution",
        )
        result = vat_rule.calculate(ctx)

        assert result.rate == 0.01
        assert result.amount == 10_000_000

    def test_services_industry_rate(self, vat_rule: VATRule):
        """Dịch vụ → 5%."""
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=200_000_000,
            industry_code="services",
        )
        result = vat_rule.calculate(ctx)

        assert result.rate == 0.05
        assert result.amount == 10_000_000

    def test_manufacturing_industry_rate(self, vat_rule: VATRule):
        """Sản xuất → 3%."""
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=300_000_000,
            industry_code="manufacturing",
        )
        result = vat_rule.calculate(ctx)

        assert result.rate == 0.03
        assert result.amount == 9_000_000

    def test_unknown_industry_defaults_to_other(self, vat_rule: VATRule):
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=200_000_000,
            industry_code="unknown_industry",
        )
        result = vat_rule.calculate(ctx)

        assert result.rate == 0.02  # "other" rate


class TestVATWarnings:
    def test_warning_below_threshold(self, vat_rule: VATRule):
        """Revenue < 100 triệu → warning about exemption."""
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=80_000_000)
        result = vat_rule.calculate(ctx)

        assert len(result.warnings) == 1
        assert "100 triệu" in result.warnings[0]

    def test_no_warning_above_threshold(self, vat_rule: VATRule):
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=200_000_000)
        result = vat_rule.calculate(ctx)

        assert len(result.warnings) == 0

    def test_no_warning_at_exact_threshold(self, vat_rule: VATRule):
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=VAT_REGISTRATION_THRESHOLD)
        result = vat_rule.calculate(ctx)

        assert len(result.warnings) == 0

    def test_no_warning_for_sme(self, vat_rule: VATRule):
        """SME uses deduction method, no threshold warning."""
        ctx = TaxContext(customer_type=CustomerType.SME, revenue=50_000_000)
        result = vat_rule.calculate(ctx)

        assert len(result.warnings) == 0


class TestVATGetInfo:
    def test_sme_info_mentions_deduction(self, vat_rule: VATRule):
        info = vat_rule.get_info(CustomerType.SME)
        assert "khấu trừ" in info
        assert "10%" in info

    def test_household_info_mentions_direct(self, vat_rule: VATRule):
        info = vat_rule.get_info(CustomerType.HOUSEHOLD)
        assert "Trực tiếp" in info
        assert "100 triệu" in info

    def test_individual_info_same_as_household(self, vat_rule: VATRule):
        info_household = vat_rule.get_info(CustomerType.HOUSEHOLD)
        info_individual = vat_rule.get_info(CustomerType.INDIVIDUAL)
        assert info_household == info_individual
