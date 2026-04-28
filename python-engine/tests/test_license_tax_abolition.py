"""
Tests for Issue #71: License tax (Lệ phí môn bài) abolition from 01/01/2026.

These tests target the production codebase under `app.core.*` (which is what
gets shipped via Docker). The legacy top-level `core/*` module is left alone.
"""

import pytest

from app.core.tax_rules.base import CustomerType, TaxContext
from app.core.tax_rules.license_tax import (
    LICENSE_TAX_ABOLISHED_FROM_YEAR,
    LicenseTaxRule,
)


@pytest.fixture
def rule() -> LicenseTaxRule:
    return LicenseTaxRule()


class TestAbolitionFrom2026:
    """From 01/01/2026 the license tax is abolished — return amount=0."""

    def test_year_2026_household_returns_zero(self, rule: LicenseTaxRule):
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=600_000_000,
            year=2026,
        )
        result = rule.calculate(ctx)
        assert result.amount == 0

    def test_year_2027_enterprise_returns_zero(self, rule: LicenseTaxRule):
        ctx = TaxContext(
            customer_type=CustomerType.SME,
            extra={"charter_capital": 50_000_000_000, "year": 2027},
        )
        result = rule.calculate(ctx)
        assert result.amount == 0

    def test_abolition_explanation_mentions_legal_basis(self, rule: LicenseTaxRule):
        ctx = TaxContext(customer_type=CustomerType.SME, year=2026)
        result = rule.calculate(ctx)
        assert "bãi bỏ" in result.explanation.lower()
        assert "01/01/2026" in result.explanation

    def test_abolition_legal_basis_cites_new_law(self, rule: LicenseTaxRule):
        ctx = TaxContext(customer_type=CustomerType.SME, year=2030)
        result = rule.calculate(ctx)
        assert any("198/2025/QH15" in ref for ref in result.legal_basis)
        assert any("362/2025/NĐ-CP" in ref for ref in result.legal_basis)

    def test_abolition_constant_is_2026(self):
        assert LICENSE_TAX_ABOLISHED_FROM_YEAR == 2026


class TestHistoricalYearStillCalculable:
    """Users may still need to query their obligations for kỳ ≤ 2025
    (e.g. completing a late filing). The rule must keep working for those."""

    def test_year_2025_household_gets_old_amount(self, rule: LicenseTaxRule):
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=600_000_000,
            year=2025,
        )
        result = rule.calculate(ctx)
        assert result.amount == 1_000_000

    def test_year_2025_enterprise_gets_old_amount(self, rule: LicenseTaxRule):
        ctx = TaxContext(
            customer_type=CustomerType.SME,
            year=2025,
            extra={"charter_capital": 15_000_000_000},
        )
        result = rule.calculate(ctx)
        assert result.amount == 3_000_000

    def test_year_2024_legal_basis_marks_as_expired(self, rule: LicenseTaxRule):
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=400_000_000,
            year=2024,
        )
        result = rule.calculate(ctx)
        # The historical legal basis must flag that the law has expired so
        # users aren't misled into thinking it still applies.
        joined = " ".join(result.legal_basis).lower()
        assert "139/2016" in joined
        assert "hết hiệu lực" in joined

    def test_historical_warning_about_abolition(self, rule: LicenseTaxRule):
        ctx = TaxContext(
            customer_type=CustomerType.HOUSEHOLD,
            revenue=400_000_000,
            year=2025,
        )
        result = rule.calculate(ctx)
        warnings = " ".join(result.warnings).lower()
        assert "2026" in warnings


class TestDefaultYearBehavior:
    """When `year` is not provided, the rule must use today's year. As long
    as the test runs in 2026 or later, this means abolition is returned."""

    def test_default_uses_current_year_and_returns_zero_in_2026_plus(self, rule: LicenseTaxRule):
        from datetime import date
        ctx = TaxContext(customer_type=CustomerType.SME)
        result = rule.calculate(ctx)
        if date.today().year >= LICENSE_TAX_ABOLISHED_FROM_YEAR:
            assert result.amount == 0
            assert "bãi bỏ" in result.explanation.lower()
        else:
            assert result.amount > 0


class TestGetInfoAdvertisesAbolition:
    """get_info() and get_consultation() must always tell the user that the
    license tax has been abolished so we don't mislead callers who hit the
    info path before providing a year."""

    def test_get_info_household_mentions_abolition(self, rule: LicenseTaxRule):
        info = rule.get_info(CustomerType.HOUSEHOLD).lower()
        assert "bãi bỏ" in info
        assert "01/01/2026" in info

    def test_get_info_sme_mentions_abolition(self, rule: LicenseTaxRule):
        info = rule.get_info(CustomerType.SME).lower()
        assert "bãi bỏ" in info

    def test_get_consultation_mentions_abolition_first(self, rule: LicenseTaxRule):
        consult = rule.get_consultation(CustomerType.HOUSEHOLD).lower()
        # The abolition notice should appear before any historical rate details
        assert "bãi bỏ" in consult
        assert consult.index("bãi bỏ") < consult.index("biểu mức")
