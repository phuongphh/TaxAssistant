"""
Tests for Notification REST Endpoints — Issue #60.

Tests cover:
- GET  /notifications/upcoming/{telegram_id}
- POST /notifications/preview/{telegram_id}
- PUT  /notifications/settings/{telegram_id}
- GET  /notifications/scheduler/status
- POST /notifications/test/{telegram_id} (dev/staging only)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


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
        "tax_period": "quarterly",
        "has_employees": False,
        "tax_profile": {
            "tax_handler": "self",
            "latest_revenue": 100_000_000,
        },
        "preferences": {},
    }
    defaults.update(overrides)
    customer = MagicMock()
    for k, v in defaults.items():
        setattr(customer, k, v)
    return customer


def _make_deadline(days_from_now: int = 5) -> dict[str, Any]:
    due = date.today() + timedelta(days=days_from_now)
    return {
        "due_date": due,
        "type": "flat_tax",
        "label": "Thuế khoán Q1/2026",
        "urgency": "urgent",
        "estimated_amount": 5_000_000,
        "penalty_per_day": 1500,
    }


def _mock_async_session(customer):
    """Create a mock async_session context manager that returns a customer."""
    session = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = customer
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=session)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm, session


# ---------------------------------------------------------------------------
# GET /notifications/upcoming/{telegram_id}
# ---------------------------------------------------------------------------

class TestUpcomingDeadlines:
    @pytest.mark.asyncio
    async def test_returns_deadlines_for_valid_user(self):
        from app.api.routes.notifications import upcoming_deadlines

        customer = _make_customer()
        cm, session = _mock_async_session(customer)

        with patch("app.api.routes.notifications.async_session", return_value=cm), \
             patch("app.api.routes.notifications.notification_scheduler") as mock_sched, \
             patch("app.api.routes.notifications._calculator") as mock_calc:

            mock_sched._customer_to_profile.return_value = {
                "business_type": "household",
                "tax_period": "quarterly",
                "industry": "service",
                "has_employees": False,
                "latest_revenue": 100_000_000,
                "tax_handler": "self",
                "display_name": "Anh Minh",
                "first_name": "Minh",
            }
            mock_calc.get_deadlines_for_user.return_value = [_make_deadline(5)]

            result = await upcoming_deadlines("123456789")

        assert result.user_id == str(customer.id)
        assert len(result.deadlines) == 1
        assert result.deadlines[0].type == "flat_tax"
        assert result.deadlines[0].urgency == "urgent"
        assert result.deadlines[0].days_remaining == 5

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_user(self):
        from fastapi import HTTPException
        from app.api.routes.notifications import upcoming_deadlines

        cm, session = _mock_async_session(None)

        with patch("app.api.routes.notifications.async_session", return_value=cm):
            with pytest.raises(HTTPException) as exc_info:
                await upcoming_deadlines("999999999")
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_deadlines(self):
        from app.api.routes.notifications import upcoming_deadlines

        customer = _make_customer()
        cm, session = _mock_async_session(customer)

        with patch("app.api.routes.notifications.async_session", return_value=cm), \
             patch("app.api.routes.notifications.notification_scheduler") as mock_sched, \
             patch("app.api.routes.notifications._calculator") as mock_calc:

            mock_sched._customer_to_profile.return_value = {"business_type": "household"}
            mock_calc.get_deadlines_for_user.return_value = []

            result = await upcoming_deadlines("123456789")

        assert result.deadlines == []


# ---------------------------------------------------------------------------
# POST /notifications/preview/{telegram_id}
# ---------------------------------------------------------------------------

class TestPreview:
    @pytest.mark.asyncio
    async def test_sends_preview_successfully(self):
        from app.api.routes.notifications import send_preview

        customer = _make_customer()
        cm, session = _mock_async_session(customer)

        with patch("app.api.routes.notifications.async_session", return_value=cm), \
             patch("app.api.routes.notifications.notification_scheduler") as mock_sched:

            mock_sched.send_preview = AsyncMock(return_value={
                "status": "ok",
                "sent": True,
                "deadlines_count": 2,
            })

            result = await send_preview("123456789")

        assert result.status == "ok"
        assert result.sent is True
        assert result.deadlines_count == 2

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_user(self):
        from fastapi import HTTPException
        from app.api.routes.notifications import send_preview

        cm, session = _mock_async_session(None)

        with patch("app.api.routes.notifications.async_session", return_value=cm):
            with pytest.raises(HTTPException) as exc_info:
                await send_preview("999999999")
            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# PUT /notifications/settings/{telegram_id}
# ---------------------------------------------------------------------------

class TestUpdateSettings:
    @pytest.mark.asyncio
    async def test_updates_notification_enabled(self):
        from app.api.routes.notifications import update_settings
        from app.schemas.notification import NotificationSettingsRequest

        customer = _make_customer(notification_enabled=True, preferences={})
        cm, session = _mock_async_session(customer)

        body = NotificationSettingsRequest(notification_enabled=False)

        with patch("app.api.routes.notifications.async_session", return_value=cm):
            result = await update_settings("123456789", body)

        assert result.status == "ok"
        assert customer.notification_enabled is False

    @pytest.mark.asyncio
    async def test_updates_preferred_time(self):
        from app.api.routes.notifications import update_settings
        from app.schemas.notification import NotificationSettingsRequest

        customer = _make_customer(preferences={})
        cm, session = _mock_async_session(customer)

        body = NotificationSettingsRequest(
            preferred_notify_hour=9,
            preferred_notify_minute=15,
        )

        with patch("app.api.routes.notifications.async_session", return_value=cm):
            result = await update_settings("123456789", body)

        assert result.preferred_notify_hour == 9
        assert result.preferred_notify_minute == 15

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_user(self):
        from fastapi import HTTPException
        from app.api.routes.notifications import update_settings
        from app.schemas.notification import NotificationSettingsRequest

        cm, session = _mock_async_session(None)
        body = NotificationSettingsRequest(notification_enabled=True)

        with patch("app.api.routes.notifications.async_session", return_value=cm):
            with pytest.raises(HTTPException) as exc_info:
                await update_settings("999999999", body)
            assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# GET /notifications/scheduler/status
# ---------------------------------------------------------------------------

class TestSchedulerStatus:
    @pytest.mark.asyncio
    async def test_returns_scheduler_status(self):
        from app.api.routes.notifications import scheduler_status

        with patch("app.api.routes.notifications.notification_scheduler") as mock_sched:
            mock_sched.get_status.return_value = {
                "scheduler_running": True,
                "timezone": "Asia/Ho_Chi_Minh",
                "jobs": [
                    {"job_id": "daily_deadline_check", "next_run_time": "2026-04-08T08:30:00", "last_run_stats": None}
                ],
            }
            result = await scheduler_status()

        assert result == mock_sched.get_status.return_value


# ---------------------------------------------------------------------------
# POST /notifications/test/{telegram_id} — dev/staging only
# ---------------------------------------------------------------------------

class TestSendTest:
    @pytest.mark.asyncio
    async def test_blocked_in_production(self):
        from fastapi import HTTPException
        from app.api.routes.notifications import send_test

        with patch("app.api.routes.notifications.settings") as mock_settings:
            mock_settings.is_production = True
            with pytest.raises(HTTPException) as exc_info:
                await send_test("123456789")
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_sends_test_message_in_dev(self):
        from app.api.routes.notifications import send_test

        customer = _make_customer()
        cm, session = _mock_async_session(customer)

        with patch("app.api.routes.notifications.settings") as mock_settings, \
             patch("app.api.routes.notifications.async_session", return_value=cm), \
             patch("app.api.routes.notifications.notification_scheduler") as mock_sched, \
             patch("app.api.routes.notifications._calculator") as mock_calc, \
             patch("app.api.routes.notifications._builder") as mock_builder:

            mock_settings.is_production = False
            mock_sched._customer_to_profile.return_value = {"business_type": "household"}
            mock_calc.get_deadlines_for_user.return_value = [_make_deadline(5)]
            mock_builder.build_deadline_reminder.return_value = "Test notification message"
            mock_sched._send_telegram_message = AsyncMock(return_value=(True, None))

            result = await send_test("123456789")

        assert result.status == "ok"
        assert result.sent is True

    @pytest.mark.asyncio
    async def test_no_deadlines_returns_not_sent(self):
        from app.api.routes.notifications import send_test

        customer = _make_customer()
        cm, session = _mock_async_session(customer)

        with patch("app.api.routes.notifications.settings") as mock_settings, \
             patch("app.api.routes.notifications.async_session", return_value=cm), \
             patch("app.api.routes.notifications.notification_scheduler") as mock_sched, \
             patch("app.api.routes.notifications._calculator") as mock_calc:

            mock_settings.is_production = False
            mock_sched._customer_to_profile.return_value = {"business_type": "household"}
            mock_calc.get_deadlines_for_user.return_value = []

            result = await send_test("123456789")

        assert result.sent is False

    @pytest.mark.asyncio
    async def test_returns_404_for_unknown_user(self):
        from fastapi import HTTPException
        from app.api.routes.notifications import send_test

        cm, session = _mock_async_session(None)

        with patch("app.api.routes.notifications.settings") as mock_settings, \
             patch("app.api.routes.notifications.async_session", return_value=cm):
            mock_settings.is_production = False
            with pytest.raises(HTTPException) as exc_info:
                await send_test("999999999")
            assert exc_info.value.status_code == 404
