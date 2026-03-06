"""
Integration test: Basic tax calculation flow.

Tests the complete flow from TaxAdvisor.process_message() down through
TaxCalculator → TaxRule, verifying output matches expected calculations.
No LLM/RAG - runs in isolation.
"""

import pytest

from core.calculators.tax_calculator import TaxCalculator
from core.tax_rules.base import CustomerType, TaxCategory
from services.ai.tax_advisor import TaxAdvisor


@pytest.fixture
def advisor():
    """TaxAdvisor without RAG - pure rule-based calculation."""
    return TaxAdvisor()


@pytest.fixture
def calculator():
    return TaxCalculator()


class TestBasicVATCalculation:
    def test_sme_vat_500m(self, calculator):
        result = calculator.calculate(
            category=TaxCategory.VAT,
            customer_type=CustomerType.SME,
            revenue=500_000_000,
        )
        assert result is not None
        assert result.amount == 50_000_000  # 500M × 10%
        assert result.rate == 0.10

    def test_household_vat_direct_method(self, calculator):
        result = calculator.calculate(
            category=TaxCategory.VAT,
            customer_type=CustomerType.HOUSEHOLD,
            revenue=200_000_000,
        )
        assert result is not None
        assert result.amount > 0
        assert result.rate < 0.10  # Direct method rate < 10%

    def test_vat_below_threshold_has_warning(self, calculator):
        result = calculator.calculate(
            category=TaxCategory.VAT,
            customer_type=CustomerType.HOUSEHOLD,
            revenue=50_000_000,  # Below 100M threshold
        )
        assert result is not None
        assert any("100 triệu" in w for w in result.warnings)


class TestBasicCITCalculation:
    def test_sme_cit_standard_rate(self, calculator):
        result = calculator.calculate(
            category=TaxCategory.CIT,
            customer_type=CustomerType.SME,
            income=1_000_000_000,
        )
        assert result is not None
        assert result.amount == 200_000_000  # 1B × 20%
        assert result.rate == 0.20

    def test_household_cit_lower_rate(self, calculator):
        result = calculator.calculate(
            category=TaxCategory.CIT,
            customer_type=CustomerType.HOUSEHOLD,
            revenue=500_000_000,
        )
        assert result is not None
        assert result.rate < 0.20  # Household rate is lower


class TestBasicPITCalculation:
    def test_pit_progressive_bracket(self, calculator):
        # 30M/month income → should be in upper brackets
        result = calculator.calculate(
            category=TaxCategory.PIT,
            customer_type=CustomerType.INDIVIDUAL,
            income=30_000_000,
        )
        assert result is not None
        assert result.amount > 0

    def test_pit_low_income_after_deduction(self, calculator):
        # 10M/month - personal deduction 11M → no tax
        result = calculator.calculate(
            category=TaxCategory.PIT,
            customer_type=CustomerType.INDIVIDUAL,
            income=10_000_000,
        )
        assert result is not None
        assert result.amount == 0


class TestEndToEndFlow:
    @pytest.mark.asyncio
    async def test_advisor_calculates_vat_correctly(self, advisor):
        result = await advisor.process_message(
            "tính thuế GTGT doanh thu 500 triệu",
            customer_type="sme",
        )
        assert result["intent"] == "tax_calculate"
        assert result["category"] == "vat"
        assert "GTGT" in result["reply"]
        assert "500" in result["reply"] or "50" in result["reply"]

    @pytest.mark.asyncio
    async def test_advisor_calculates_pit_correctly(self, advisor):
        result = await advisor.process_message(
            "tính thuế TNCN lương 30 triệu",
            customer_type="sme",
        )
        assert result["intent"] == "tax_calculate"
        assert result["category"] == "pit"

    @pytest.mark.asyncio
    async def test_advisor_asks_for_amount_if_missing(self, advisor):
        result = await advisor.process_message("tính thuế GTGT")
        assert result["intent"] == "tax_calculate"
        assert "doanh thu" in result["reply"].lower() or "vui lòng" in result["reply"].lower()
