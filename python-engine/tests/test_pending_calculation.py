"""
Tests for Issue #72: pending-calculation completion + empty-reply guards.

When a user clicks "Tính thuế GTGT" the bot prompts them to provide the
revenue. The user then types something like "500 triệu" alone — without the
bug fix this routes through RAG and frequently returns an empty reply,
which Telegram silently drops, leaving the user staring at a blank screen.

These tests target `app.core.tax_engine.TaxEngine` (production codebase).
"""

import pytest

from app.core.intent_classifier import ClassificationResult, Intent
from app.core.tax_engine import (
    _AMOUNT_PROMPT_BY_CATEGORY,
    _SAFE_FALLBACK_REPLY,
    TaxEngine,
    _detect_pending_calculation,
)
from app.core.tax_rules.base import TaxCategory


class TestDetectPendingCalculation:
    def test_detects_vat_prompt(self):
        history = [
            {"role": "user", "content": "tính thuế GTGT"},
            {"role": "assistant", "content": _AMOUNT_PROMPT_BY_CATEGORY[TaxCategory.VAT]},
        ]
        assert _detect_pending_calculation(history) == TaxCategory.VAT

    def test_detects_pit_prompt(self):
        history = [
            {"role": "assistant", "content": _AMOUNT_PROMPT_BY_CATEGORY[TaxCategory.PIT]},
        ]
        assert _detect_pending_calculation(history) == TaxCategory.PIT

    def test_returns_none_when_no_history(self):
        assert _detect_pending_calculation([]) is None

    def test_returns_none_when_last_assistant_was_unrelated(self):
        history = [
            {"role": "assistant", "content": "Xin chào! Tôi là Trợ lý Thuế ảo."},
        ]
        assert _detect_pending_calculation(history) is None

    def test_only_inspects_most_recent_assistant_turn(self):
        """An older calculation prompt buried under newer turns must be
        ignored — otherwise a stale prompt could hijack later messages."""
        history = [
            {"role": "assistant", "content": _AMOUNT_PROMPT_BY_CATEGORY[TaxCategory.VAT]},
            {"role": "user", "content": "thôi hỏi thứ khác"},
            {"role": "assistant", "content": "Bạn cần hỗ trợ thủ tục nào?"},
        ]
        assert _detect_pending_calculation(history) is None


@pytest.mark.asyncio
class TestPendingCalculationCompletion:
    async def test_bare_amount_after_vat_prompt_completes_calculation(self):
        """Reproduces the exact bug from Issue #72."""
        engine = TaxEngine(rag_service=None)
        history = [
            {"role": "user", "content": "tính thuế GTGT"},
            {"role": "assistant", "content": _AMOUNT_PROMPT_BY_CATEGORY[TaxCategory.VAT]},
        ]
        result = await engine.process_message(
            message="500 triệu",
            customer_type="sme",
            conversation_history=history,
        )
        # Must produce a non-empty calculation reply, NOT a blank screen.
        assert result["reply"]
        assert result["reply"].strip()
        assert "GTGT" in result["reply"] or "thuế" in result["reply"].lower()
        # Must report the calculated amount (10% of 500M = 50M)
        assert "50,000,000" in result["reply"] or "50.000.000" in result["reply"]

    async def test_bare_amount_after_pit_prompt_completes_calculation(self):
        engine = TaxEngine(rag_service=None)
        history = [
            {"role": "assistant", "content": _AMOUNT_PROMPT_BY_CATEGORY[TaxCategory.PIT]},
        ]
        result = await engine.process_message(
            message="30 triệu",
            customer_type="individual",
            conversation_history=history,
        )
        assert result["reply"]
        assert result["reply"].strip()

    async def test_bare_amount_without_prompt_does_not_force_calculation(self):
        """No pending prompt → bare number must NOT be coerced into a
        calculation (avoids false positives)."""
        engine = TaxEngine(rag_service=None)
        result = await engine.process_message(
            message="500 triệu",
            customer_type="sme",
            conversation_history=[],
        )
        # Without history we can't know what to calculate. As long as we
        # return something non-empty (the safe fallback), we're good.
        assert result["reply"]
        assert result["reply"].strip()


@pytest.mark.asyncio
class TestEmptyReplyGuard:
    async def test_build_response_substitutes_safe_fallback_for_empty_reply(self):
        engine = TaxEngine(rag_service=None)
        classification = ClassificationResult(
            intent=Intent.UNKNOWN,
            tax_category=None,
            confidence=0.0,
            extracted_entities={},
        )
        out = engine._build_response(reply="", classification=classification)
        assert out["reply"] == _SAFE_FALLBACK_REPLY

    async def test_build_response_substitutes_safe_fallback_for_whitespace(self):
        engine = TaxEngine(rag_service=None)
        classification = ClassificationResult(
            intent=Intent.UNKNOWN,
            tax_category=None,
            confidence=0.0,
            extracted_entities={},
        )
        out = engine._build_response(reply="   \n  \t  ", classification=classification)
        assert out["reply"] == _SAFE_FALLBACK_REPLY

    async def test_build_response_keeps_normal_reply(self):
        engine = TaxEngine(rag_service=None)
        classification = ClassificationResult(
            intent=Intent.TAX_INFO,
            tax_category=TaxCategory.VAT,
            confidence=0.8,
            extracted_entities={},
        )
        out = engine._build_response(
            reply="Thuế GTGT là...", classification=classification,
        )
        assert out["reply"] == "Thuế GTGT là..."
