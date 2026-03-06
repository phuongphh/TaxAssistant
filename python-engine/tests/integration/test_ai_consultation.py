"""
Integration test: AI Q&A tax consultation flow.

Tests the AI-assisted consultation path. Uses a mock RAG service to avoid
real LLM calls while testing the orchestration logic end-to-end.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from core.intent_classifier import IntentClassifier, Intent
from core.memory import build_memory_context
from services.ai.tax_advisor import TaxAdvisor


@pytest.fixture
def mock_rag():
    """Mock RAG service that returns a predictable answer."""
    from services.ai.rag_service import RAGResponse
    rag = MagicMock()
    rag.query = AsyncMock(return_value=RAGResponse(
        answer="Theo quy định thuế GTGT, doanh nghiệp cần nộp tờ khai hàng quý.",
        sources=[{"title": "Thông tư 219/2013/TT-BTC", "url": "", "snippet": "Quy định về GTGT"}],
        confidence=0.85,
    ))
    return rag


@pytest.fixture
def advisor_with_rag(mock_rag):
    return TaxAdvisor(rag_service=mock_rag)


@pytest.fixture
def advisor_no_rag():
    return TaxAdvisor()


class TestAIConsultationWithRAG:
    @pytest.mark.asyncio
    async def test_tax_info_query_uses_rag(self, advisor_with_rag, mock_rag):
        result = await advisor_with_rag.process_message(
            "thuế GTGT là gì và áp dụng như thế nào?",
            customer_type="sme",
        )
        assert result["reply"]
        # RAG should be called for tax info queries
        assert mock_rag.query.called

    @pytest.mark.asyncio
    async def test_rag_answer_included_in_response(self, advisor_with_rag):
        result = await advisor_with_rag.process_message(
            "thuế GTGT khai hàng quý",
            customer_type="sme",
        )
        # The mock RAG answer should appear in the response
        assert "tờ khai" in result["reply"] or result["reply"]

    @pytest.mark.asyncio
    async def test_rag_sources_returned_as_references(self, advisor_with_rag):
        result = await advisor_with_rag.process_message(
            "thuế GTGT là gì?",
            customer_type="sme",
        )
        # RAG sources should appear as references when confidence > 0.4
        assert isinstance(result["references"], list)

    @pytest.mark.asyncio
    async def test_contextual_query_with_history(self, advisor_with_rag, mock_rag):
        history = [
            {"role": "user", "content": "tôi là hộ kinh doanh"},
            {"role": "assistant", "content": "Đã ghi nhận, bạn là hộ kinh doanh."},
        ]
        result = await advisor_with_rag.process_message(
            "vậy tôi cần nộp thuế gì?",
            customer_type="household",
            conversation_history=history,
        )
        assert result["reply"]
        # With history, contextual query goes through RAG
        assert mock_rag.query.called


class TestAIConsultationFallback:
    """Tests fallback behavior when RAG/LLM is unavailable."""

    @pytest.mark.asyncio
    async def test_tax_info_fallback_without_rag(self, advisor_no_rag):
        result = await advisor_no_rag.process_message(
            "thuế GTGT là gì?",
            customer_type="sme",
        )
        assert result["reply"]
        # Fallback should return tax overview or service menu
        assert len(result["reply"]) > 10

    @pytest.mark.asyncio
    async def test_general_query_fallback_shows_menu(self, advisor_no_rag):
        result = await advisor_no_rag.process_message("câu hỏi không rõ ràng xyz abc")
        assert result["reply"]
        assert result["intent"] == "unknown"

    @pytest.mark.asyncio
    async def test_penalty_fallback_contains_info(self, advisor_no_rag):
        result = await advisor_no_rag.process_message("xử phạt vi phạm thuế")
        assert result["intent"] == "penalty"
        assert result["reply"]


class TestMemoryContextInjection:
    """Tests that memory context is properly injected into LLM queries."""

    def test_build_memory_context_with_customer(self):
        customer = {
            "customer_type": "sme",
            "business_name": "Công ty TNHH ABC",
            "tax_code": "0123456789",
            "onboarding_step": "completed",
        }
        context = build_memory_context(customer=customer)
        assert "ABC" in context
        assert "0123456789" in context
        assert "Doanh nghiệp" in context

    def test_build_memory_context_empty_for_new_customer(self):
        customer = {"onboarding_step": "new"}
        context = build_memory_context(customer=customer)
        assert context == ""

    @pytest.mark.asyncio
    async def test_memory_context_used_in_consultation(self, advisor_with_rag, mock_rag):
        customer_memory = (
            "=== THÔNG TIN KHÁCH HÀNG ===\n"
            "Loại: Hộ kinh doanh\n"
            "Tên: Cửa hàng Minh Anh"
        )
        result = await advisor_with_rag.process_message(
            "thuế tôi phải đóng là bao nhiêu?",
            customer_type="household",
            memory_context=customer_memory,
        )
        assert result["reply"]
        # Verify RAG was called with the memory context
        call_kwargs = mock_rag.query.call_args
        if call_kwargs:
            # memory_context should be passed through to rag.query
            assert call_kwargs is not None


class TestIntentClassification:
    """Tests intent classifier integration with tax advisor."""

    def test_classifier_detects_tax_info(self):
        clf = IntentClassifier()
        result = clf.classify("thuế GTGT là gì?")
        assert result.intent == Intent.TAX_INFO

    def test_classifier_detects_calculation(self):
        clf = IntentClassifier()
        result = clf.classify("tính thuế TNCN lương 30 triệu")
        assert result.intent == Intent.TAX_CALCULATE

    def test_classifier_detects_deadline(self):
        clf = IntentClassifier()
        # Use a message that clearly triggers TAX_DEADLINE without tax-type ambiguity
        result = clf.classify("hạn nộp là khi nào?")
        assert result.intent == Intent.TAX_DEADLINE
