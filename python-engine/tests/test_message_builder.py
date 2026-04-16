"""
Tests for NotificationMessageBuilder — Issue #54.
"""

from datetime import date

import pytest

from app.services.message_builder import (
    NotificationMessageBuilder,
    format_vnd,
    TELEGRAM_MAX_LENGTH,
)


@pytest.fixture
def builder() -> NotificationMessageBuilder:
    return NotificationMessageBuilder()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user(
    business_type: str = "household",
    tax_handler: str = "self",
    industry: str = "service",
    display_name: str = "Anh Minh",
) -> dict:
    return {
        "business_type": business_type,
        "tax_handler": tax_handler,
        "industry": industry,
        "display_name": display_name,
    }


def _deadline(
    due_date: date = date(2025, 10, 30),
    dtype: str = "flat_tax",
    label: str = "Thuế khoán Q3/2025",
    urgency: str = "warning",
    estimated_amount: int | None = 5_000_000,
    penalty_per_day: int | None = 1500,
) -> dict:
    return {
        "due_date": due_date,
        "type": dtype,
        "label": label,
        "urgency": urgency,
        "estimated_amount": estimated_amount,
        "penalty_per_day": penalty_per_day,
    }


# ---------------------------------------------------------------------------
# format_vnd tests
# ---------------------------------------------------------------------------

class TestFormatVnd:
    def test_under_million(self):
        assert format_vnd(850_000) == "850.000 đồng"

    def test_millions(self):
        assert format_vnd(8_500_000) == "8.5 triệu đồng"

    def test_exact_million(self):
        assert format_vnd(1_000_000) == "1.0 triệu đồng"

    def test_billions(self):
        assert format_vnd(1_200_000_000) == "1.2 tỷ đồng"

    def test_zero(self):
        assert format_vnd(0) == "0 đồng"

    def test_small_amount(self):
        assert format_vnd(1500) == "1.500 đồng"


# ---------------------------------------------------------------------------
# build_deadline_reminder tests
# ---------------------------------------------------------------------------

class TestBuildDeadlineReminder:
    def test_returns_none_for_empty_deadlines(self, builder):
        result = builder.build_deadline_reminder(_user(), [], date(2025, 10, 1))
        assert result is None

    def test_contains_user_display_name(self, builder):
        result = builder.build_deadline_reminder(
            _user(display_name="Chị Lan"),
            [_deadline()],
            date(2025, 10, 20),
        )
        assert "Chị Lan" in result

    def test_no_name_still_works(self, builder):
        result = builder.build_deadline_reminder(
            _user(display_name=""),
            [_deadline()],
            date(2025, 10, 20),
        )
        assert result is not None
        assert "Chào" not in result

    def test_critical_urgency_header(self, builder):
        dl = _deadline(
            due_date=date(2025, 10, 22),
            urgency="critical",
        )
        result = builder.build_deadline_reminder(
            _user(), [dl], date(2025, 10, 20),
        )
        assert "KHẨN CẤP" in result

    def test_urgent_urgency_header(self, builder):
        dl = _deadline(
            due_date=date(2025, 10, 25),
            urgency="urgent",
        )
        result = builder.build_deadline_reminder(
            _user(), [dl], date(2025, 10, 20),
        )
        assert "Sắp đến hạn" in result

    def test_warning_urgency_header(self, builder):
        dl = _deadline(
            due_date=date(2025, 10, 30),
            urgency="warning",
        )
        result = builder.build_deadline_reminder(
            _user(), [dl], date(2025, 10, 20),
        )
        assert "Nhắc nhở deadline" in result

    def test_info_urgency_header(self, builder):
        dl = _deadline(
            due_date=date(2025, 11, 15),
            urgency="info",
        )
        result = builder.build_deadline_reminder(
            _user(), [dl], date(2025, 10, 20),
        )
        assert "Thông báo deadline" in result

    def test_max_3_deadlines_shown(self, builder):
        deadlines = [
            _deadline(due_date=date(2025, 10, 20), label=f"DL{i}")
            for i in range(5)
        ]
        result = builder.build_deadline_reminder(
            _user(), deadlines, date(2025, 10, 15),
        )
        # Should mention remaining count
        assert "2 deadline khác" in result

    def test_exactly_3_deadlines_no_more_note(self, builder):
        deadlines = [
            _deadline(due_date=date(2025, 10, 20 + i), label=f"DL{i}")
            for i in range(3)
        ]
        result = builder.build_deadline_reminder(
            _user(), deadlines, date(2025, 10, 15),
        )
        assert "deadline khác" not in result

    def test_estimated_amount_displayed(self, builder):
        dl = _deadline(estimated_amount=5_000_000)
        result = builder.build_deadline_reminder(
            _user(), [dl], date(2025, 10, 20),
        )
        assert "5.0 triệu đồng" in result

    def test_no_amount_when_none(self, builder):
        dl = _deadline(estimated_amount=None, penalty_per_day=None)
        result = builder.build_deadline_reminder(
            _user(), [dl], date(2025, 10, 20),
        )
        assert "triệu đồng" not in result

    def test_penalty_shown_for_critical(self, builder):
        dl = _deadline(
            due_date=date(2025, 10, 22),
            urgency="critical",
            penalty_per_day=1500,
        )
        result = builder.build_deadline_reminder(
            _user(), [dl], date(2025, 10, 20),
        )
        assert "Phạt chậm nộp" in result

    def test_penalty_not_shown_for_info(self, builder):
        dl = _deadline(
            due_date=date(2025, 11, 15),
            urgency="info",
            penalty_per_day=1500,
        )
        result = builder.build_deadline_reminder(
            _user(), [dl], date(2025, 10, 20),
        )
        assert "Phạt chậm nộp" not in result

    def test_under_telegram_limit(self, builder):
        deadlines = [
            _deadline(due_date=date(2025, 10, 20 + i), label=f"DL{i}")
            for i in range(5)
        ]
        result = builder.build_deadline_reminder(
            _user(), deadlines, date(2025, 10, 15),
        )
        assert len(result) <= TELEGRAM_MAX_LENGTH


# ---------------------------------------------------------------------------
# Tax handler personalization tests
# ---------------------------------------------------------------------------

class TestTaxHandlerPersonalization:
    def test_self_handler_mentions_action(self, builder):
        result = builder.build_deadline_reminder(
            _user(tax_handler="self"),
            [_deadline()],
            date(2025, 10, 20),
        )
        assert "thuedientu.gdt.gov.vn" in result

    def test_accountant_handler_mentions_accountant(self, builder):
        result = builder.build_deadline_reminder(
            _user(tax_handler="accountant"),
            [_deadline()],
            date(2025, 10, 20),
        )
        assert "kế toán" in result

    def test_unknown_handler_mentions_help(self, builder):
        result = builder.build_deadline_reminder(
            _user(tax_handler="unknown"),
            [_deadline()],
            date(2025, 10, 20),
        )
        assert "/help" in result

    def test_missing_handler_defaults_to_unknown(self, builder):
        user = _user()
        user.pop("tax_handler", None)
        result = builder.build_deadline_reminder(
            user, [_deadline()], date(2025, 10, 20),
        )
        assert "/help" in result


# ---------------------------------------------------------------------------
# Business type + industry tip tests
# ---------------------------------------------------------------------------

class TestBusinessTips:
    def test_household_service_tip(self, builder):
        result = builder.build_deadline_reminder(
            _user(business_type="household", industry="service"),
            [_deadline()],
            date(2025, 10, 20),
        )
        assert "Tip" in result

    def test_household_ecommerce_tip(self, builder):
        result = builder.build_deadline_reminder(
            _user(business_type="household", industry="ecommerce"),
            [_deadline()],
            date(2025, 10, 20),
        )
        assert "Tip" in result

    def test_fallback_to_business_type_tip(self, builder):
        result = builder.build_deadline_reminder(
            _user(business_type="company", industry="agriculture"),
            [_deadline()],
            date(2025, 10, 20),
        )
        assert "Tip" in result

    def test_generic_tip_when_no_match(self, builder):
        result = builder.build_deadline_reminder(
            _user(business_type="nonprofit", industry=""),
            [_deadline()],
            date(2025, 10, 20),
        )
        assert "0.03%" in result  # generic tip about late penalty


# ---------------------------------------------------------------------------
# build_weekly_summary tests
# ---------------------------------------------------------------------------

class TestBuildWeeklySummary:
    def test_no_deadlines_shows_all_clear(self, builder):
        result = builder.build_weekly_summary(
            _user(), [], today=date(2025, 10, 6),
        )
        assert "Không có deadline" in result

    def test_returns_string_not_none_even_when_empty(self, builder):
        """Weekly summary always returns a message, even with 0 deadlines."""
        result = builder.build_weekly_summary(
            _user(), [], today=date(2025, 10, 6),
        )
        assert result is not None

    def test_contains_month_year(self, builder):
        result = builder.build_weekly_summary(
            _user(),
            [_deadline(due_date=date(2025, 10, 20))],
            today=date(2025, 10, 6),
        )
        assert "10/2025" in result

    def test_lists_all_deadlines(self, builder):
        deadlines = [
            _deadline(due_date=date(2025, 10, 20), label="VAT T9/2025"),
            _deadline(due_date=date(2025, 10, 30), label="CIT Q3/2025"),
        ]
        result = builder.build_weekly_summary(
            _user(), deadlines, today=date(2025, 10, 6),
        )
        assert "VAT T9/2025" in result
        assert "CIT Q3/2025" in result

    def test_contains_weekly_tip(self, builder):
        result = builder.build_weekly_summary(
            _user(), [], today=date(2025, 10, 6),
        )
        assert "Tip tuần này" in result

    def test_under_telegram_limit(self, builder):
        deadlines = [
            _deadline(due_date=date(2025, 10, i + 1), label=f"DL{i}")
            for i in range(10)
        ]
        result = builder.build_weekly_summary(
            _user(), deadlines, today=date(2025, 10, 6),
        )
        assert len(result) <= TELEGRAM_MAX_LENGTH

    def test_display_name_shown(self, builder):
        result = builder.build_weekly_summary(
            _user(display_name="Anh Tùng"),
            [_deadline()],
            today=date(2025, 10, 6),
        )
        assert "Anh Tùng" in result


# ---------------------------------------------------------------------------
# build_monthly_calendar tests
# ---------------------------------------------------------------------------

class TestBuildMonthlyCalendar:
    def test_returns_none_for_empty_deadlines(self, builder):
        result = builder.build_monthly_calendar(
            _user(), [], today=date(2025, 10, 1),
        )
        assert result is None

    def test_contains_month_header(self, builder):
        result = builder.build_monthly_calendar(
            _user(),
            [_deadline(due_date=date(2025, 10, 20))],
            today=date(2025, 10, 1),
        )
        assert "Lịch thuế tháng 10/2025" in result

    def test_contains_day_and_label(self, builder):
        result = builder.build_monthly_calendar(
            _user(),
            [_deadline(due_date=date(2025, 10, 20), label="VAT T9/2025")],
            today=date(2025, 10, 1),
        )
        assert "20/10" in result
        assert "VAT T9/2025" in result

    def test_deadlines_sorted_by_date(self, builder):
        deadlines = [
            _deadline(due_date=date(2025, 10, 30), label="CIT"),
            _deadline(due_date=date(2025, 10, 20), label="VAT"),
        ]
        result = builder.build_monthly_calendar(
            _user(), deadlines, today=date(2025, 10, 1),
        )
        vat_pos = result.index("VAT")
        cit_pos = result.index("CIT")
        assert vat_pos < cit_pos

    def test_amount_shown_when_present(self, builder):
        result = builder.build_monthly_calendar(
            _user(),
            [_deadline(estimated_amount=8_500_000)],
            today=date(2025, 10, 1),
        )
        assert "8.5 triệu đồng" in result

    def test_contains_tip(self, builder):
        result = builder.build_monthly_calendar(
            _user(),
            [_deadline()],
            today=date(2025, 10, 1),
        )
        assert "Tip" in result

    def test_under_telegram_limit(self, builder):
        deadlines = [
            _deadline(due_date=date(2025, 10, i + 1), label=f"DL{i}")
            for i in range(15)
        ]
        result = builder.build_monthly_calendar(
            _user(), deadlines, today=date(2025, 10, 1),
        )
        assert len(result) <= TELEGRAM_MAX_LENGTH


# ---------------------------------------------------------------------------
# Truncation test
# ---------------------------------------------------------------------------

class TestTruncation:
    def test_long_message_truncated(self, builder):
        # Create many deadlines with long labels to exceed limit
        deadlines = [
            _deadline(
                due_date=date(2025, 10, 20),
                label="A" * 200,
                estimated_amount=999_999_999,
            )
            for _ in range(3)
        ]
        # Use a user with a very long name
        user = _user(display_name="X" * 500)
        result = builder.build_deadline_reminder(
            user, deadlines, date(2025, 10, 15),
        )
        assert len(result) <= TELEGRAM_MAX_LENGTH
        if len(result) == TELEGRAM_MAX_LENGTH:
            assert result.endswith("...")
