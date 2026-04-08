"""
Tests for NotificationScheduler — Issue #56.

Tests cover:
- Scheduler lifecycle (start/shutdown/get_status)
- Anti-spam logic
- Customer-to-profile conversion
- Job logic (daily_deadline_check, weekly_summary, monthly_calendar)
- Retry logic on Telegram send failure
- Notification logging
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from app.services.notification_scheduler import (
    ANTI_SPAM_HOURS,
    DEADLINE_CHECK_DAYS,
    MAX_RETRIES,
    NotificationScheduler,
    VN_TZ,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VN_TZ_OBJ = ZoneInfo("Asia/Ho_Chi_Minh")


def _make_customer(**overrides) -> MagicMock:
    """Create a mock Customer ORM object."""
    defaults = {
        "id": uuid.uuid4(),
        "channel": "telegram",
        "channel_user_id": "123456789",
        "customer_type": "household",
        "industry": "service",
        "display_name": "Anh Minh",
        "first_name": "Minh",
        "notification_enabled": True,
        "onboarding_step": "completed",
        "tax_profile": {
            "tax_period": "quarterly",
            "tax_handler": "self",
            "has_employees": False,
            "latest_revenue": 100_000_000,
        },
    }
    defaults.update(overrides)
    customer = MagicMock()
    for k, v in defaults.items():
        setattr(customer, k, v)
    return customer


def _make_deadline(
    days_from_now: int = 5,
    dtype: str = "flat_tax",
    label: str = "Thuế khoán Q1/2026",
    urgency: str = "urgent",
) -> dict[str, Any]:
    """Create a deadline dict similar to DeadlineCalculator output."""
    due = date.today() + timedelta(days=days_from_now)
    return {
        "due_date": due,
        "type": dtype,
        "label": label,
        "urgency": urgency,
        "estimated_amount": 5_000_000,
        "penalty_per_day": 1500,
    }


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------

class TestSchedulerLifecycle:
    def test_start_registers_three_jobs(self):
        sched = NotificationScheduler()
        sched.start()

        jobs = sched._scheduler.get_jobs()
        job_ids = {j.id for j in jobs}
        assert "daily_deadline_check" in job_ids
        assert "weekly_summary" in job_ids
        assert "monthly_calendar" in job_ids

        sched._scheduler.shutdown(wait=False)

    def test_start_replace_existing_no_duplicates(self):
        """Calling start() twice should not duplicate jobs."""
        sched = NotificationScheduler()
        sched.start()
        sched._scheduler.shutdown(wait=False)

        # Start again
        sched._scheduler = __import__(
            "apscheduler.schedulers.asyncio", fromlist=["AsyncIOScheduler"]
        ).AsyncIOScheduler(timezone="Asia/Ho_Chi_Minh")
        sched.start()

        jobs = sched._scheduler.get_jobs()
        job_ids = [j.id for j in jobs]
        assert job_ids.count("daily_deadline_check") == 1
        assert job_ids.count("weekly_summary") == 1
        assert job_ids.count("monthly_calendar") == 1

        sched._scheduler.shutdown(wait=False)

    def test_get_status_returns_correct_structure(self):
        sched = NotificationScheduler()
        sched.start()

        status = sched.get_status()
        assert status["scheduler_running"] is True
        assert status["timezone"] == "Asia/Ho_Chi_Minh"
        assert len(status["jobs"]) == 3

        for job in status["jobs"]:
            assert "job_id" in job
            assert "next_run_time" in job

        sched._scheduler.shutdown(wait=False)

    def test_get_status_when_not_started(self):
        sched = NotificationScheduler()
        status = sched.get_status()
        assert status["scheduler_running"] is False
        assert status["jobs"] == []

    @pytest.mark.asyncio
    async def test_shutdown_closes_http_client(self):
        sched = NotificationScheduler()
        sched.start()

        mock_client = AsyncMock()
        sched._http_client = mock_client

        await sched.shutdown()
        mock_client.aclose.assert_awaited_once()
        assert sched._http_client is None


# ---------------------------------------------------------------------------
# Customer to profile conversion
# ---------------------------------------------------------------------------

class TestCustomerToProfile:
    def test_converts_all_fields(self):
        customer = _make_customer()
        profile = NotificationScheduler._customer_to_profile(customer)

        assert profile["business_type"] == "household"
        assert profile["tax_period"] == "quarterly"
        assert profile["industry"] == "service"
        assert profile["has_employees"] is False
        assert profile["latest_revenue"] == 100_000_000
        assert profile["tax_handler"] == "self"
        assert profile["display_name"] == "Anh Minh"

    def test_handles_missing_tax_profile(self):
        customer = _make_customer(tax_profile=None)
        profile = NotificationScheduler._customer_to_profile(customer)

        assert profile["tax_period"] == ""
        assert profile["tax_handler"] == "unknown"
        assert profile["latest_revenue"] is None

    def test_handles_empty_fields(self):
        customer = _make_customer(
            customer_type=None,
            industry=None,
            display_name=None,
            first_name=None,
        )
        profile = NotificationScheduler._customer_to_profile(customer)

        assert profile["business_type"] == ""
        assert profile["industry"] == ""
        assert profile["display_name"] == ""


# ---------------------------------------------------------------------------
# Anti-spam logic
# ---------------------------------------------------------------------------

class TestAntiSpam:
    @pytest.mark.asyncio
    async def test_not_recently_notified_returns_false(self):
        """User with no recent notifications should not be blocked."""
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = 0
        session.execute = AsyncMock(return_value=result_mock)

        result = await NotificationScheduler._was_recently_notified(
            session, uuid.uuid4(),
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_recently_notified_returns_true(self):
        """User notified within 20 hours should be blocked."""
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar.return_value = 1
        session.execute = AsyncMock(return_value=result_mock)

        result = await NotificationScheduler._was_recently_notified(
            session, uuid.uuid4(),
        )
        assert result is True


# ---------------------------------------------------------------------------
# Telegram send + retry
# ---------------------------------------------------------------------------

class TestSendWithRetry:
    @pytest.mark.asyncio
    async def test_successful_send_on_first_attempt(self):
        sched = NotificationScheduler()
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        with patch.object(
            sched, "_send_telegram_message", return_value=(True, None),
        ):
            result = await sched._send_with_retry(
                session, uuid.uuid4(), "123456",
                "Test message", "daily_deadline_check", "deadline_reminder",
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_retry_on_failure_then_success(self):
        """Should retry and succeed on second attempt."""
        sched = NotificationScheduler()
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        call_count = 0

        async def _mock_send(chat_id, text):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return False, "Network error"
            return True, None

        with patch.object(sched, "_send_telegram_message", side_effect=_mock_send):
            with patch("app.services.notification_scheduler.asyncio.sleep", new_callable=AsyncMock):
                result = await sched._send_with_retry(
                    session, uuid.uuid4(), "123456",
                    "Test message", "daily_deadline_check", "deadline_reminder",
                )

        assert result is True
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self):
        """After MAX_RETRIES failures, should return False."""
        sched = NotificationScheduler()
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        with patch.object(
            sched, "_send_telegram_message",
            return_value=(False, "Telegram error"),
        ):
            with patch("app.services.notification_scheduler.asyncio.sleep", new_callable=AsyncMock):
                result = await sched._send_with_retry(
                    session, uuid.uuid4(), "123456",
                    "Test message", "daily_deadline_check", "deadline_reminder",
                )

        assert result is False


# ---------------------------------------------------------------------------
# Telegram message sending
# ---------------------------------------------------------------------------

class TestSendTelegramMessage:
    @pytest.mark.asyncio
    async def test_returns_false_when_no_token(self):
        sched = NotificationScheduler()
        with patch("app.services.notification_scheduler.settings") as mock_settings:
            mock_settings.telegram_bot_token = ""
            success, error = await sched._send_telegram_message("123", "test")

        assert success is False
        assert "not configured" in error

    @pytest.mark.asyncio
    async def test_successful_api_call(self):
        sched = NotificationScheduler()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"ok": True, "result": {}}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        sched._http_client = mock_client

        with patch("app.services.notification_scheduler.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test-token"
            success, error = await sched._send_telegram_message("123", "Hello")

        assert success is True
        assert error is None
        mock_client.post.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_api_error_response(self):
        sched = NotificationScheduler()
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"ok": False, "description": "Forbidden"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        sched._http_client = mock_client

        with patch("app.services.notification_scheduler.settings") as mock_settings:
            mock_settings.telegram_bot_token = "test-token"
            success, error = await sched._send_telegram_message("123", "Hello")

        assert success is False
        assert "Forbidden" in error


# ---------------------------------------------------------------------------
# Daily deadline check job
# ---------------------------------------------------------------------------

class TestDailyDeadlineCheck:
    @pytest.mark.asyncio
    async def test_skips_recently_notified_users(self):
        sched = NotificationScheduler()
        customer = _make_customer()

        with patch("app.services.notification_scheduler.async_session") as mock_session_factory:
            session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            # Return one user
            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = [customer]
            session.execute = AsyncMock(return_value=result_mock)
            session.commit = AsyncMock()

            with patch.object(
                NotificationScheduler, "_was_recently_notified", return_value=True,
            ):
                await sched._daily_deadline_check()

        stats = sched._last_run_stats.get("daily_deadline_check", {})
        assert stats.get("checked") == 1
        assert stats.get("skipped") == 1
        assert stats.get("sent") == 0

    @pytest.mark.asyncio
    async def test_sends_when_urgent_deadlines_exist(self):
        sched = NotificationScheduler()
        customer = _make_customer()

        with patch("app.services.notification_scheduler.async_session") as mock_session_factory:
            session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = [customer]
            session.execute = AsyncMock(return_value=result_mock)
            session.commit = AsyncMock()

            with patch.object(
                NotificationScheduler, "_was_recently_notified", return_value=False,
            ), patch.object(
                sched._calculator, "get_deadlines_for_user",
                return_value=[_make_deadline(days_from_now=5)],
            ), patch.object(
                sched._builder, "build_deadline_reminder",
                return_value="⚠️ Deadline coming!",
            ), patch.object(
                sched, "_send_with_retry", return_value=True,
            ) as mock_send:
                await sched._daily_deadline_check()

        stats = sched._last_run_stats["daily_deadline_check"]
        assert stats["sent"] == 1
        assert stats["skipped"] == 0
        mock_send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_skips_when_no_urgent_deadlines(self):
        sched = NotificationScheduler()
        customer = _make_customer()

        with patch("app.services.notification_scheduler.async_session") as mock_session_factory:
            session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = [customer]
            session.execute = AsyncMock(return_value=result_mock)
            session.commit = AsyncMock()

            with patch.object(
                NotificationScheduler, "_was_recently_notified", return_value=False,
            ), patch.object(
                sched._calculator, "get_deadlines_for_user",
                return_value=[_make_deadline(days_from_now=30)],  # beyond 14 days
            ):
                await sched._daily_deadline_check()

        stats = sched._last_run_stats["daily_deadline_check"]
        assert stats["skipped"] == 1
        assert stats["sent"] == 0


# ---------------------------------------------------------------------------
# Weekly summary job
# ---------------------------------------------------------------------------

class TestWeeklySummary:
    @pytest.mark.asyncio
    async def test_sends_summary_to_active_user(self):
        sched = NotificationScheduler()
        customer = _make_customer()

        with patch("app.services.notification_scheduler.async_session") as mock_session_factory:
            session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = [customer]
            session.execute = AsyncMock(return_value=result_mock)
            session.commit = AsyncMock()

            with patch.object(
                NotificationScheduler, "_was_recently_notified", return_value=False,
            ), patch.object(
                sched._calculator, "get_deadlines_for_user",
                return_value=[_make_deadline(days_from_now=10)],
            ), patch.object(
                sched._builder, "build_weekly_summary",
                return_value="📊 Weekly summary...",
            ), patch.object(
                sched, "_send_with_retry", return_value=True,
            ):
                await sched._weekly_summary()

        stats = sched._last_run_stats["weekly_summary"]
        assert stats["sent"] == 1


# ---------------------------------------------------------------------------
# Monthly calendar job
# ---------------------------------------------------------------------------

class TestMonthlyCalendar:
    @pytest.mark.asyncio
    async def test_sends_calendar_to_active_user(self):
        sched = NotificationScheduler()
        customer = _make_customer()

        with patch("app.services.notification_scheduler.async_session") as mock_session_factory:
            session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = [customer]
            session.execute = AsyncMock(return_value=result_mock)
            session.commit = AsyncMock()

            with patch.object(
                NotificationScheduler, "_was_recently_notified", return_value=False,
            ), patch.object(
                sched._calculator, "get_deadlines_for_user",
                return_value=[_make_deadline(days_from_now=15)],
            ), patch.object(
                sched._builder, "build_monthly_calendar",
                return_value="📅 Monthly calendar...",
            ), patch.object(
                sched, "_send_with_retry", return_value=True,
            ):
                await sched._monthly_calendar()

        stats = sched._last_run_stats["monthly_calendar"]
        assert stats["sent"] == 1

    @pytest.mark.asyncio
    async def test_skips_when_no_deadlines_this_month(self):
        sched = NotificationScheduler()
        customer = _make_customer()

        with patch("app.services.notification_scheduler.async_session") as mock_session_factory:
            session = AsyncMock()
            mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=session)
            mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

            result_mock = MagicMock()
            result_mock.scalars.return_value.all.return_value = [customer]
            session.execute = AsyncMock(return_value=result_mock)
            session.commit = AsyncMock()

            with patch.object(
                NotificationScheduler, "_was_recently_notified", return_value=False,
            ), patch.object(
                sched._calculator, "get_deadlines_for_user",
                return_value=[],  # no deadlines
            ), patch.object(
                sched._builder, "build_monthly_calendar",
                return_value=None,
            ):
                await sched._monthly_calendar()

        stats = sched._last_run_stats["monthly_calendar"]
        assert stats["skipped"] == 1
        assert stats["sent"] == 0


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class TestConstants:
    def test_anti_spam_hours_is_20(self):
        assert ANTI_SPAM_HOURS == 20

    def test_max_retries_is_3(self):
        assert MAX_RETRIES == 3

    def test_deadline_check_days_is_14(self):
        assert DEADLINE_CHECK_DAYS == 14

    def test_timezone_is_vietnam(self):
        from app.services.notification_scheduler import TIMEZONE
        assert TIMEZONE == "Asia/Ho_Chi_Minh"
