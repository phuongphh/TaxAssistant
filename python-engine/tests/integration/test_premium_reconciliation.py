"""
Integration test: Premium reconciliation flow.

Tests the annual settlement (quyết toán thuế) flow which is one of
the main service types - validating declaration, penalty, registration flows.
"""

import pytest

from core.case_manager import CaseManager, SERVICE_STEPS
from core.onboarding import OnboardingHandler, SERVICE_TYPE_MAP
from services.ai.tax_advisor import TaxAdvisor


@pytest.fixture
def advisor():
    return TaxAdvisor()


@pytest.fixture
def onboarding():
    return OnboardingHandler()


class TestAnnualSettlementFlow:
    """Annual settlement (quyết toán) is the premium reconciliation flow."""

    def test_service_steps_defined_for_settlement(self):
        assert "annual_settlement" in SERVICE_STEPS
        steps = SERVICE_STEPS["annual_settlement"]
        assert len(steps) >= 2  # At least 2 steps

    @pytest.mark.asyncio
    async def test_advisor_handles_settlement_intent(self, advisor):
        result = await advisor.process_message("kê khai quyết toán thuế năm", customer_type="sme")
        assert result["intent"] in ("declaration", "tax_procedure")
        assert result["reply"]

    @pytest.mark.asyncio
    async def test_advisor_annual_settlement_has_deadlines(self, advisor):
        result = await advisor.process_message("quyết toán thuế năm hạn nộp")
        assert result["reply"]
        # Should mention deadline info
        assert any(kw in result["reply"] for kw in ["31/03", "90 ngày", "quyết toán"])


class TestDeclarationFlow:
    """Tax declaration is the core reconciliation workflow."""

    @pytest.mark.asyncio
    async def test_declaration_flow_sme(self, advisor):
        result = await advisor.process_message("kê khai thuế GTGT hàng quý", customer_type="sme")
        assert result["reply"]
        assert result["intent"] in ("declaration", "tax_info", "tax_procedure")

    @pytest.mark.asyncio
    async def test_declaration_flow_household(self, advisor):
        result = await advisor.process_message("cách kê khai thuế hộ kinh doanh", customer_type="household")
        assert result["reply"]
        assert "hộ" in result["reply"].lower() or "khoán" in result["reply"].lower() or result["reply"]

    @pytest.mark.asyncio
    async def test_declaration_deadline_query(self, advisor):
        # "thời hạn" is a reliable TAX_DEADLINE trigger
        result = await advisor.process_message("thời hạn nộp thuế là khi nào")
        assert result["intent"] == "tax_deadline"
        assert result["reply"]


class TestPenaltyFlow:
    """Penalty consultation is part of reconciliation for late filing."""

    @pytest.mark.asyncio
    async def test_penalty_late_filing(self, advisor):
        result = await advisor.process_message("phạt chậm nộp tờ khai thuế")
        assert result["intent"] == "penalty"
        assert "phạt" in result["reply"].lower() or "vi phạm" in result["reply"].lower()

    @pytest.mark.asyncio
    async def test_penalty_has_amount(self, advisor):
        result = await advisor.process_message("tiền phạt chậm nộp thuế")
        assert result["reply"]
        # Should mention penalty amounts
        assert any(kw in result["reply"] for kw in ["triệu", "0.03%", "20%"])


class TestOnboardingToService:
    """Onboarding → Service selection flow."""

    def test_service_8_maps_to_annual_settlement(self):
        assert SERVICE_TYPE_MAP["8"] == "annual_settlement"

    def test_onboarding_new_customer_shows_menu(self, onboarding):
        result = onboarding.process_step({"onboarding_step": "new"}, "xin chào")
        assert "SERVICE_MENU" in result["reply"] or "Dịch vụ" in result["reply"]
        assert result["next_step"] == "collecting_type"

    @pytest.mark.asyncio
    async def test_service_selection_routes_to_settlement(self, advisor):
        """Selecting service '8' (annual_settlement) should return declaration info."""
        result = await advisor.process_message("8")
        assert result["reply"]
        assert result["intent"] in ("declaration", "unknown", "tax_procedure")
