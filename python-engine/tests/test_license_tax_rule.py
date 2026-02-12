"""
Unit tests for License Tax (Thuế Môn Bài) rules.
Tests enterprise tiers (by charter capital) and household tiers (by revenue).
"""

import pytest

from app.core.tax_rules.base import CustomerType, TaxCategory, TaxContext
from app.core.tax_rules.license_tax import LicenseTaxRule


@pytest.fixture
def license_rule():
    return LicenseTaxRule()


class TestLicenseTaxCategory:
    def test_category_is_license(self, license_rule: LicenseTaxRule):
        assert license_rule.category == TaxCategory.LICENSE


class TestLicenseTaxEnterprise:
    """Thuế Môn bài cho doanh nghiệp (theo vốn điều lệ)."""

    def test_capital_above_10_billion(self, license_rule: LicenseTaxRule):
        """Vốn > 10 tỷ → 3 triệu/năm."""
        ctx = TaxContext(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 15_000_000_000},
        )
        result = license_rule.calculate(ctx)

        assert result.amount == 3_000_000

    def test_capital_below_10_billion(self, license_rule: LicenseTaxRule):
        """Vốn ≤ 10 tỷ → 2 triệu/năm."""
        ctx = TaxContext(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 5_000_000_000},
        )
        result = license_rule.calculate(ctx)

        assert result.amount == 2_000_000

    def test_capital_exactly_10_billion(self, license_rule: LicenseTaxRule):
        """Vốn = 10 tỷ (not greater) → 2 triệu."""
        ctx = TaxContext(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 10_000_000_000},
        )
        result = license_rule.calculate(ctx)

        assert result.amount == 2_000_000

    def test_zero_capital_defaults(self, license_rule: LicenseTaxRule):
        ctx = TaxContext(customer_type=CustomerType.SME, extra={"charter_capital": 0})
        result = license_rule.calculate(ctx)

        assert result.amount == 2_000_000

    def test_no_capital_in_context(self, license_rule: LicenseTaxRule):
        """No charter_capital → defaults to 0."""
        ctx = TaxContext(customer_type=CustomerType.SME)
        result = license_rule.calculate(ctx)

        assert result.amount == 2_000_000

    def test_enterprise_legal_basis(self, license_rule: LicenseTaxRule):
        ctx = TaxContext(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 5_000_000_000},
        )
        result = license_rule.calculate(ctx)

        assert any("139/2016" in ref for ref in result.legal_basis)

    def test_explanation_mentions_new_enterprise_exemption(self, license_rule: LicenseTaxRule):
        ctx = TaxContext(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 5_000_000_000},
        )
        result = license_rule.calculate(ctx)

        assert "miễn" in result.explanation.lower()


class TestLicenseTaxHousehold:
    """Thuế Môn bài cho hộ kinh doanh (theo doanh thu)."""

    def test_revenue_above_500m(self, license_rule: LicenseTaxRule):
        """DT > 500 triệu → 1 triệu/năm."""
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=600_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 1_000_000

    def test_revenue_300m_to_500m(self, license_rule: LicenseTaxRule):
        """DT 300-500 triệu → 500k/năm."""
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=400_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 500_000

    def test_revenue_100m_to_300m(self, license_rule: LicenseTaxRule):
        """DT 100-300 triệu → 300k/năm."""
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=200_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 300_000

    def test_revenue_exactly_300m(self, license_rule: LicenseTaxRule):
        """DT = 300 triệu (not greater) → 300k/năm."""
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=300_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 300_000

    def test_revenue_exactly_500m(self, license_rule: LicenseTaxRule):
        """DT = 500 triệu (not greater) → 500k/năm."""
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=500_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 500_000

    def test_revenue_below_100m_exempt(self, license_rule: LicenseTaxRule):
        """DT ≤ 100 triệu → miễn (0)."""
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=80_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 0

    def test_revenue_exactly_100m_exempt(self, license_rule: LicenseTaxRule):
        """DT = 100 triệu → miễn."""
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=100_000_000)
        result = license_rule.calculate(ctx)

        assert result.amount == 0

    def test_zero_revenue(self, license_rule: LicenseTaxRule):
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=0)
        result = license_rule.calculate(ctx)

        assert result.amount == 0

    def test_individual_same_as_household(self, license_rule: LicenseTaxRule):
        """INDIVIDUAL uses same household method."""
        ctx_h = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=400_000_000)
        ctx_i = TaxContext(customer_type=CustomerType.INDIVIDUAL, revenue=400_000_000)

        assert license_rule.calculate(ctx_h).amount == license_rule.calculate(ctx_i).amount


class TestLicenseTaxHouseholdWarnings:
    def test_warning_below_100m(self, license_rule: LicenseTaxRule):
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=80_000_000)
        result = license_rule.calculate(ctx)

        assert len(result.warnings) == 1
        assert "miễn" in result.warnings[0].lower()

    def test_warning_at_100m(self, license_rule: LicenseTaxRule):
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=100_000_000)
        result = license_rule.calculate(ctx)

        assert len(result.warnings) == 1

    def test_no_warning_above_100m(self, license_rule: LicenseTaxRule):
        ctx = TaxContext(customer_type=CustomerType.HOUSEHOLD, revenue=200_000_000)
        result = license_rule.calculate(ctx)

        assert len(result.warnings) == 0


class TestLicenseTaxGetInfo:
    def test_sme_info(self, license_rule: LicenseTaxRule):
        info = license_rule.get_info(CustomerType.SME)
        assert "10 tỷ" in info
        assert "3.000.000" in info
        assert "2.000.000" in info

    def test_household_info(self, license_rule: LicenseTaxRule):
        info = license_rule.get_info(CustomerType.HOUSEHOLD)
        assert "500 triệu" in info
        assert "1.000.000" in info
        assert "Miễn" in info
