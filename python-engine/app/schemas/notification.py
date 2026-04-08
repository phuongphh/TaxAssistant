"""
Pydantic schemas for notification endpoints — Issue #56, #60.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


# --- Scheduler status (Issue #56) ---

class JobStatus(BaseModel):
    job_id: str
    next_run_time: str | None = None
    last_run_stats: dict[str, Any] | None = None


class SchedulerStatusResponse(BaseModel):
    scheduler_running: bool
    timezone: str
    jobs: list[JobStatus]


# --- Upcoming deadlines (Issue #60) ---

class DeadlineItem(BaseModel):
    due_date: date
    label: str
    type: str
    urgency: str
    days_remaining: int
    estimated_amount: int | None = None


class UpcomingDeadlinesResponse(BaseModel):
    user_id: str
    deadlines: list[DeadlineItem]
    generated_at: datetime


# --- Notification settings (Issue #60) ---

class NotificationSettingsRequest(BaseModel):
    notification_enabled: bool | None = None
    preferred_notify_hour: int | None = Field(None, ge=0, le=23)
    preferred_notify_minute: int | None = Field(None, ge=0, le=59)


class NotificationSettingsResponse(BaseModel):
    status: str
    notification_enabled: bool
    preferred_notify_hour: int | None = None
    preferred_notify_minute: int | None = None


# --- Preview (Issue #60) ---

class PreviewResponse(BaseModel):
    status: str
    sent: bool = False
    deadlines_count: int = 0
    detail: str | None = None


# --- Test message (Issue #60) ---

class TestMessageResponse(BaseModel):
    status: str
    sent: bool = False
    message_preview: str | None = None
    detail: str | None = None
