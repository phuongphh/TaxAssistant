"""
Notification endpoints — Issue #56.

GET /notifications/scheduler/status — scheduler status and job info.
"""

import logging

from fastapi import APIRouter

from app.services.notification_scheduler import notification_scheduler
from app.schemas.notification import SchedulerStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def scheduler_status():
    """Return current status of the notification scheduler and its jobs."""
    return notification_scheduler.get_status()
