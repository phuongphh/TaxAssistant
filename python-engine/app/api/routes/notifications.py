"""
Notification endpoints — Issue #56, #58.

GET  /notifications/scheduler/status — scheduler status and job info.
POST /notifications/preview/{user_id} — send immediate deadline preview after onboarding step 2.
"""

import logging
import uuid

from fastapi import APIRouter, HTTPException

from app.services.notification_scheduler import notification_scheduler
from app.schemas.notification import SchedulerStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def scheduler_status():
    """Return current status of the notification scheduler and its jobs."""
    return notification_scheduler.get_status()


@router.post("/preview/{user_id}")
async def send_preview(user_id: str):
    """Send an immediate deadline preview to a user after onboarding step 2.

    Called by the Node gateway after the user completes onboarding step 2
    to show them their upcoming tax deadlines right away.
    """
    try:
        customer_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user_id format")

    result = await notification_scheduler.send_preview(customer_id)

    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("detail", "Unknown error"))

    return result
