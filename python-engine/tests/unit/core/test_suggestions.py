"""
Tests for the context-aware suggestion generator.
"""

import pytest

from app.core.suggestions import generate_suggestions
from app.core.intent_classifier import Intent
from app.core.tax_rules.base import TaxCategory


class TestGenerateSuggestions:
    def test_always_returns_three(self):
        for intent in Intent:
            result = generate_suggestions(intent)
            assert len(result) == 3, f"Expected 3 suggestions for {intent}, got {len(result)}"

    def test_returns_strings(self):
        result = generate_suggestions(Intent.TAX_CALCULATE)
        assert all(isinstance(s, str) for s in result)
        assert all(len(s) > 0 for s in result)

    def test_tax_calculate_suggestions(self):
        result = generate_suggestions(Intent.TAX_CALCULATE)
        assert any("thuế" in s.lower() for s in result)

    def test_tax_info_suggestions(self):
        result = generate_suggestions(Intent.TAX_INFO)
        assert any("tra cứu" in s.lower() or "văn bản" in s.lower() for s in result)

    def test_penalty_suggestions(self):
        result = generate_suggestions(Intent.PENALTY)
        assert any("phạt" in s.lower() for s in result)

    def test_category_specific_vat(self):
        result = generate_suggestions(Intent.TAX_CALCULATE, TaxCategory.VAT)
        assert any("GTGT" in s for s in result)

    def test_category_specific_pit(self):
        result = generate_suggestions(Intent.TAX_CALCULATE, TaxCategory.PIT)
        assert any("TNCN" in s for s in result)

    def test_category_specific_cit(self):
        result = generate_suggestions(Intent.TAX_CALCULATE, TaxCategory.CIT)
        assert any("TNDN" in s for s in result)

    def test_category_specific_license(self):
        result = generate_suggestions(Intent.TAX_CALCULATE, TaxCategory.LICENSE)
        assert any("Môn bài" in s for s in result)

    def test_unknown_intent_returns_defaults(self):
        result = generate_suggestions(Intent.UNKNOWN)
        assert len(result) == 3

    def test_category_ignored_for_non_calc_intents(self):
        """Tax category should only affect TAX_CALCULATE and TAX_INFO intents."""
        result_with = generate_suggestions(Intent.PENALTY, TaxCategory.VAT)
        result_without = generate_suggestions(Intent.PENALTY)
        assert result_with == result_without
