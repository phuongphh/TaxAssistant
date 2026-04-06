"""
Pydantic schemas for notification endpoints — Issue #56.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobStatus(BaseModel):
    job_id: str
    next_run_time: str | None = None
    last_run_stats: dict[str, Any] | None = None


class SchedulerStatusResponse(BaseModel):
    scheduler_running: bool
    timezone: str
    jobs: list[JobStatus]
