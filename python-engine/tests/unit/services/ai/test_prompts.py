"""
Tests for LLM prompt templates — Issue #48 regression guard.

The TAX_CONSULTATION_PROMPT must NOT instruct the LLM to generate
follow-up suggestions, because the system already provides inline
suggestion buttons via generate_suggestions().
"""

from app.ai.prompts import TAX_CONSULTATION_PROMPT


class TestConsultationPromptNoFollowUp:
    """Issue #48: Ensure the prompt doesn't tell the LLM to add follow-up suggestions."""

    def test_no_follow_up_instruction(self):
        """The prompt should not contain '4. Gợi ý hành động tiếp theo'."""
        assert "Gợi ý hành động tiếp theo" not in TAX_CONSULTATION_PROMPT

    def test_explicit_no_follow_up_rule(self):
        """The prompt should explicitly tell the LLM NOT to add follow-up questions."""
        assert "KHÔNG thêm câu hỏi gợi ý tiếp theo" in TAX_CONSULTATION_PROMPT
