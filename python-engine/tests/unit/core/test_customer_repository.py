"""
Unit tests for customer identity helper functions.
"""

import pytest


def _build_display_name(first_name, last_name, username):
    """Build a human-readable display name from available identity fields."""
    parts = [p for p in [first_name, last_name] if p]
    if parts:
        return " ".join(parts)
    return username or None


class TestBuildDisplayName:
    def test_first_and_last_name(self):
        assert _build_display_name("Nguyen", "Van A", None) == "Nguyen Van A"

    def test_first_name_only(self):
        assert _build_display_name("Minh", None, None) == "Minh"

    def test_last_name_only(self):
        assert _build_display_name(None, "Tran", None) == "Tran"

    def test_username_fallback(self):
        assert _build_display_name(None, None, "minhbiz") == "minhbiz"

    def test_all_empty_returns_none(self):
        assert _build_display_name(None, None, None) is None

    def test_first_name_takes_priority_over_username(self):
        result = _build_display_name("An", None, "ankd123")
        assert result == "An"
        assert "ankd123" not in result

    def test_full_name_with_all_fields(self):
        result = _build_display_name("Nguyen", "Van Minh", "minhng")
        assert result == "Nguyen Van Minh"
        assert "minhng" not in result

    def test_handles_missing_telegram_username(self):
        """Missing Telegram username (user didn't set one) should fall through gracefully."""
        assert _build_display_name("Lan", "Tran", None) == "Lan Tran"

    def test_empty_strings_treated_as_none(self):
        """Empty strings from proto should be treated like missing values."""
        result = _build_display_name("", "", "")
        assert result is None
