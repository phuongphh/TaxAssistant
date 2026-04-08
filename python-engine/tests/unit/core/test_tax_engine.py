"""
Unit tests for TaxEngine orchestrator.
Tests message routing, response format, and handler logic.
"""

import pytest

from services.ai.tax_advisor import TaxAdvisor as TaxEngine


@pytest.fixture
def engine():
    return TaxEngine()


class TestGreeting:
    @pytest.mark.asyncio
    async def test_greeting_response(self, engine: TaxEngine):
        result = await engine.process_message("xin chào")

        assert "Trợ lý Thuế" in result["reply"]
        assert result["intent"] == "greeting"

    @pytest.mark.asyncio
    async def test_greeting_with_customer_type_sme(self, engine: TaxEngine):
        result = await engine.process_message("chào", customer_type="sme")

        assert "Doanh nghiệp" in result["reply"]

    @pytest.mark.asyncio
    async def test_greeting_with_customer_type_household(self, engine: TaxEngine):
        result = await engine.process_message("hello", customer_type="household")

        assert "Hộ gia đình" in result["reply"]


class TestHelp:
    @pytest.mark.asyncio
    async def test_help_response(self, engine: TaxEngine):
        result = await engine.process_message("giúp tôi với")

        assert result["intent"] == "help"
        assert "/loai" in result["reply"]
        assert "/reset" in result["reply"]


class TestTaxCalculation:
    @pytest.mark.asyncio
    async def test_vat_calculation_with_amount(self, engine: TaxEngine):
        """'tính thuế GTGT 500 triệu' → should calculate and return result."""
        result = await engine.process_message("tính thuế GTGT doanh thu 500 triệu")

        assert result["intent"] == "tax_calculate"
        assert result["category"] == "vat"
        assert "GTGT" in result["reply"]

    @pytest.mark.asyncio
    async def test_pit_calculation_with_amount(self, engine: TaxEngine):
        result = await engine.process_message("tính thuế TNCN lương 30 triệu")

        assert result["intent"] == "tax_calculate"
        assert result["category"] == "pit"

    @pytest.mark.asyncio
    async def test_calculation_without_category_asks(self, engine: TaxEngine):
        """'tính thuế' without specifying type → should ask which tax type."""
        result = await engine.process_message("tính thuế cho tôi")

        assert result["intent"] == "tax_calculate"
        assert len(result["actions"]) > 0
        assert "GTGT" in result["reply"]

    @pytest.mark.asyncio
    async def test_calculation_without_amount_prompts(self, engine: TaxEngine):
        """'tính thuế GTGT' without amount → should ask for amount."""
        result = await engine.process_message("tính thuế GTGT")

        assert result["intent"] == "tax_calculate"
        assert "doanh thu" in result["reply"].lower()

    @pytest.mark.asyncio
    async def test_calculation_returns_references(self, engine: TaxEngine):
        result = await engine.process_message("tính thuế GTGT doanh thu 1 tỷ")

        assert len(result["references"]) > 0


class TestTaxInfo:
    @pytest.mark.asyncio
    async def test_vat_info(self, engine: TaxEngine):
        result = await engine.process_message("thuế GTGT là gì")

        assert result["intent"] == "tax_info"
        assert result["category"] == "vat"

    @pytest.mark.asyncio
    async def test_cit_info_for_sme(self, engine: TaxEngine):
        result = await engine.process_message("thông tin thuế TNDN", customer_type="sme")

        assert "20%" in result["reply"] or "TNDN" in result["reply"]

    @pytest.mark.asyncio
    async def test_general_info_without_category(self, engine: TaxEngine):
        """Generic tax info question → overview."""
        result = await engine.process_message("thuế suất hiện tại")

        assert result["intent"] == "tax_info"


class TestTaxDeadline:
    @pytest.mark.asyncio
    async def test_deadline_response(self, engine: TaxEngine):
        result = await engine.process_message("hạn nộp thuế GTGT quý 1")

        assert result["intent"] == "tax_deadline"
        assert "Hạn" in result["reply"]

    @pytest.mark.asyncio
    async def test_deadline_contains_key_dates(self, engine: TaxEngine):
        result = await engine.process_message("deadline nộp thuế")

        assert "20" in result["reply"]  # Ngày 20 tháng sau
        assert "30/01" in result["reply"]  # Thuế Môn bài


class TestDeclaration:
    @pytest.mark.asyncio
    async def test_declaration_response(self, engine: TaxEngine):
        result = await engine.process_message("kê khai thuế quý 1")

        assert result["intent"] == "declaration"
        assert "tờ khai" in result["reply"].lower() or "Mẫu" in result["reply"]


class TestPenalty:
    @pytest.mark.asyncio
    async def test_penalty_response(self, engine: TaxEngine):
        result = await engine.process_message("phạt chậm nộp thuế")

        assert result["intent"] == "penalty"
        assert "0.03%" in result["reply"]
        assert len(result["references"]) > 0


class TestResponseFormat:
    """Verify all responses have consistent structure."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("message", [
        "xin chào",
        "tính thuế GTGT 500 triệu",
        "thuế TNDN là gì",
        "hạn nộp thuế",
        "phạt vi phạm thuế",
        "random unknown text xyz",
    ])
    async def test_response_has_required_keys(self, engine: TaxEngine, message: str):
        result = await engine.process_message(message)

        assert "reply" in result
        assert "actions" in result
        assert "references" in result
        assert "confidence" in result
        assert "intent" in result

        assert isinstance(result["reply"], str)
        assert isinstance(result["actions"], list)
        assert isinstance(result["references"], list)
        assert isinstance(result["confidence"], float)
        assert len(result["reply"]) > 0

    @pytest.mark.asyncio
    async def test_unknown_message_returns_suggestions(self, engine: TaxEngine):
        result = await engine.process_message("abcdef random")

        assert result["intent"] == "unknown"
        assert len(result["actions"]) > 0
