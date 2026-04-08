"""
Notification endpoints — Issue #56, #58, #60.

GET  /notifications/upcoming/{telegram_id}  — upcoming deadlines for a user.
POST /notifications/preview/{telegram_id}   — send immediate deadline preview.
PUT  /notifications/settings/{telegram_id}  — update notification preferences.
GET  /notifications/scheduler/status        — scheduler job statuses.
POST /notifications/test/{telegram_id}      — send test message (dev/staging only).
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.config import settings
from app.db.database import async_session
from app.db.models import Customer
from app.services.deadline_calculator import DeadlineCalculator
from app.services.message_builder import NotificationMessageBuilder
from app.services.notification_scheduler import notification_scheduler
from app.schemas.notification import (
    DeadlineItem,
    NotificationSettingsRequest,
    NotificationSettingsResponse,
    PreviewResponse,
    SchedulerStatusResponse,
    TestMessageResponse,
    UpcomingDeadlinesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

_calculator = DeadlineCalculator()
_builder = NotificationMessageBuilder()


async def _get_customer_by_telegram_id(telegram_id: str) -> Customer:
    """Look up a customer by their Telegram user ID. Raises 404 if not found."""
    async with async_session() as session:
        result = await session.execute(
            select(Customer).where(
                Customer.channel == "telegram",
                Customer.channel_user_id == telegram_id,
            )
        )
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="User not found")
        return customer


# ------------------------------------------------------------------
# 1. GET /notifications/upcoming/{telegram_id}
# ------------------------------------------------------------------

@router.get("/upcoming/{telegram_id}", response_model=UpcomingDeadlinesResponse)
async def upcoming_deadlines(telegram_id: str):
    """Return upcoming tax deadlines for a user.

    Called by the Node gateway when the user sends "lich thue".
    """
    customer = await _get_customer_by_telegram_id(telegram_id)
    today = datetime.now(VN_TZ).date()
    profile = notification_scheduler._customer_to_profile(customer)

    deadlines_raw = _calculator.get_deadlines_for_user(profile, today)

    deadlines = [
        DeadlineItem(
            due_date=d["due_date"],
            label=d["label"],
            type=d["type"],
            urgency=d["urgency"],
            days_remaining=(d["due_date"] - today).days,
            estimated_amount=int(d["estimated_amount"]) if d.get("estimated_amount") else None,
        )
        for d in deadlines_raw
    ]

    return UpcomingDeadlinesResponse(
        user_id=str(customer.id),
        deadlines=deadlines,
        generated_at=datetime.now(VN_TZ),
    )


# ------------------------------------------------------------------
# 2. POST /notifications/preview/{telegram_id}
# ------------------------------------------------------------------

@router.post("/preview/{telegram_id}", response_model=PreviewResponse)
async def send_preview(telegram_id: str):
    """Send an immediate deadline preview to a user after onboarding step 2.

    Bypasses anti-spam since this is user-initiated.
    """
    customer = await _get_customer_by_telegram_id(telegram_id)
    result = await notification_scheduler.send_preview(customer.id)

    if result.get("status") == "error":
        detail = result.get("detail", "Unknown error")
        raise HTTPException(status_code=500, detail=detail)

    return PreviewResponse(
        status=result.get("status", "ok"),
        sent=result.get("sent", False),
        deadlines_count=result.get("deadlines_count", 0),
        detail=result.get("detail"),
    )


# ------------------------------------------------------------------
# 3. PUT /notifications/settings/{telegram_id}
# ------------------------------------------------------------------

@router.put("/settings/{telegram_id}", response_model=NotificationSettingsResponse)
async def update_settings(telegram_id: str, body: NotificationSettingsRequest):
    """Update notification preferences for a user."""
    async with async_session() as session:
        result = await session.execute(
            select(Customer).where(
                Customer.channel == "telegram",
                Customer.channel_user_id == telegram_id,
            )
        )
        customer = result.scalar_one_or_none()
        if not customer:
            raise HTTPException(status_code=404, detail="User not found")

        if body.notification_enabled is not None:
            customer.notification_enabled = body.notification_enabled

        # Store preferred notification time in preferences JSONB
        prefs = customer.preferences or {}
        if body.preferred_notify_hour is not None:
            prefs["preferred_notify_hour"] = body.preferred_notify_hour
        if body.preferred_notify_minute is not None:
            prefs["preferred_notify_minute"] = body.preferred_notify_minute
        customer.preferences = prefs

        await session.commit()
        await session.refresh(customer)

        return NotificationSettingsResponse(
            status="ok",
            notification_enabled=customer.notification_enabled,
            preferred_notify_hour=prefs.get("preferred_notify_hour"),
            preferred_notify_minute=prefs.get("preferred_notify_minute"),
        )


# ------------------------------------------------------------------
# 4. GET /notifications/scheduler/status
# ------------------------------------------------------------------

@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def scheduler_status():
    """Return current status of the notification scheduler and its jobs."""
    return notification_scheduler.get_status()


# ------------------------------------------------------------------
# 5. POST /notifications/test/{telegram_id} — dev/staging only
# ------------------------------------------------------------------

@router.post("/test/{telegram_id}", response_model=TestMessageResponse)
async def send_test(telegram_id: str):
    """Send a test notification immediately. Disabled in production.

    Does not check anti-spam. Only active when ENV != production.
    """
    if settings.is_production:
        raise HTTPException(status_code=403, detail="Test endpoint is disabled in production")

    customer = await _get_customer_by_telegram_id(telegram_id)
    today = datetime.now(VN_TZ).date()
    profile = notification_scheduler._customer_to_profile(customer)

    deadlines = _calculator.get_deadlines_for_user(profile, today)
    if not deadlines:
        return TestMessageResponse(
            status="ok",
            sent=False,
            detail="No upcoming deadlines to include in test message",
        )

    message = _builder.build_deadline_reminder(profile, deadlines, today)
    if not message:
        return TestMessageResponse(
            status="ok",
            sent=False,
            detail="Message builder returned empty message",
        )

    # Send directly via scheduler's Telegram helper, bypassing anti-spam and retry
    success, error = await notification_scheduler._send_telegram_message(
        customer.channel_user_id, message,
    )

    if not success:
        return TestMessageResponse(
            status="error",
            sent=False,
            detail=error,
            message_preview=message[:200],
        )

    return TestMessageResponse(
        status="ok",
        sent=True,
        message_preview=message[:200],
    )
