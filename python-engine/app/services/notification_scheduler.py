"""
Notification Scheduler Service — Issue #56

Background service using APScheduler to run notification jobs on a schedule.
Integrates DeadlineCalculator (#52) and MessageBuilder (#54) to send
personalized tax reminders via Telegram.

Three jobs:
- daily_deadline_check: 8:30 AM daily — deadlines ≤ 14 days
- weekly_summary: Monday 9:00 AM — weekly summary for active users
- monthly_calendar: 1st of month 8:00 AM — monthly calendar

Anti-spam: max 1 notification per 20 hours per user.
Retry: max 3 attempts, 5 min apart, then mark was_delivered=FALSE.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import async_session
from app.db.models import Customer, NotificationLog
from app.services.deadline_calculator import DeadlineCalculator
from app.services.message_builder import NotificationMessageBuilder

logger = logging.getLogger(__name__)

TIMEZONE = "Asia/Ho_Chi_Minh"
VN_TZ = ZoneInfo(TIMEZONE)

# Anti-spam: minimum hours between notifications for the same user
ANTI_SPAM_HOURS = 20

# Retry config
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 300  # 5 minutes

# Deadline check window (days)
DEADLINE_CHECK_DAYS = 14

# Telegram API
TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}/sendMessage"


class NotificationScheduler:
    """APScheduler-based notification scheduler integrated into FastAPI."""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler(timezone=TIMEZONE)
        self._calculator = DeadlineCalculator()
        self._builder = NotificationMessageBuilder()
        self._http_client: httpx.AsyncClient | None = None
        self._last_run_stats: dict[str, dict[str, Any]] = {}

    def start(self) -> None:
        """Start the scheduler and register all jobs.

        Uses replace_existing=True so restarting the container
        does not create duplicate jobs.
        """
        self._http_client = httpx.AsyncClient(timeout=30.0)

        # Job 1: Daily deadline check — 8:30 AM every day
        self._scheduler.add_job(
            self._daily_deadline_check,
            CronTrigger(hour=8, minute=30, timezone=TIMEZONE),
            id="daily_deadline_check",
            replace_existing=True,
        )

        # Job 2: Weekly summary — Monday 9:00 AM
        self._scheduler.add_job(
            self._weekly_summary,
            CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=TIMEZONE),
            id="weekly_summary",
            replace_existing=True,
        )

        # Job 3: Monthly calendar — 1st of month 8:00 AM
        self._scheduler.add_job(
            self._monthly_calendar,
            CronTrigger(day=1, hour=8, minute=0, timezone=TIMEZONE),
            id="monthly_calendar",
            replace_existing=True,
        )

        self._scheduler.start()
        logger.info("NotificationScheduler started with 3 jobs")

    async def shutdown(self) -> None:
        """Gracefully shut down the scheduler and HTTP client."""
        self._scheduler.shutdown(wait=False)
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        logger.info("NotificationScheduler stopped")

    def get_status(self) -> dict[str, Any]:
        """Return status of all scheduled jobs for the /scheduler/status endpoint."""
        jobs_status: list[dict[str, Any]] = []
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            jobs_status.append({
                "job_id": job.id,
                "next_run_time": next_run.isoformat() if next_run else None,
                "last_run_stats": self._last_run_stats.get(job.id),
            })
        return {
            "scheduler_running": self._scheduler.running,
            "timezone": TIMEZONE,
            "jobs": jobs_status,
        }

    # ------------------------------------------------------------------
    # Job implementations
    # ------------------------------------------------------------------

    async def _daily_deadline_check(self) -> None:
        """Check all active users for upcoming deadlines and send reminders."""
        job_id = "daily_deadline_check"
        today = datetime.now(VN_TZ).date()
        stats = {"checked": 0, "sent": 0, "skipped": 0, "errors": 0}

        logger.info("[%s] Starting — date=%s", job_id, today)

        try:
            async with async_session() as session:
                users = await self._get_notifiable_users(session)
                stats["checked"] = len(users)

                for user_row in users:
                    user_dict = self._customer_to_profile(user_row)
                    telegram_id = user_row.channel_user_id

                    # Anti-spam check
                    if await self._was_recently_notified(session, user_row.id):
                        stats["skipped"] += 1
                        continue

                    # Calculate deadlines within 14 days
                    deadlines = self._calculator.get_deadlines_for_user(
                        user_dict, today,
                    )
                    urgent_deadlines = [
                        d for d in deadlines
                        if (d["due_date"] - today).days <= DEADLINE_CHECK_DAYS
                    ]
                    if not urgent_deadlines:
                        stats["skipped"] += 1
                        continue

                    message = self._builder.build_deadline_reminder(
                        user_dict, urgent_deadlines, today,
                    )
                    if not message:
                        stats["skipped"] += 1
                        continue

                    delivered = await self._send_with_retry(
                        session, user_row.id, telegram_id, message,
                        job_id, "deadline_reminder",
                    )
                    if delivered:
                        stats["sent"] += 1
                    else:
                        stats["errors"] += 1

                await session.commit()
        except Exception:
            logger.exception("[%s] Unexpected error", job_id)

        self._last_run_stats[job_id] = {
            **stats,
            "run_at": datetime.now(VN_TZ).isoformat(),
        }
        logger.info(
            "[%s] Finished — checked=%d sent=%d skipped=%d errors=%d",
            job_id, stats["checked"], stats["sent"],
            stats["skipped"], stats["errors"],
        )

    async def _weekly_summary(self) -> None:
        """Send weekly summary to all active users every Monday."""
        job_id = "weekly_summary"
        today = datetime.now(VN_TZ).date()
        stats = {"checked": 0, "sent": 0, "skipped": 0, "errors": 0}

        logger.info("[%s] Starting — date=%s", job_id, today)

        try:
            async with async_session() as session:
                users = await self._get_notifiable_users(session)
                stats["checked"] = len(users)

                for user_row in users:
                    user_dict = self._customer_to_profile(user_row)
                    telegram_id = user_row.channel_user_id

                    if await self._was_recently_notified(session, user_row.id):
                        stats["skipped"] += 1
                        continue

                    # Get deadlines for the current month
                    all_deadlines = self._calculator.get_deadlines_for_user(
                        user_dict, today,
                    )
                    this_month = [
                        d for d in all_deadlines
                        if d["due_date"].month == today.month
                        and d["due_date"].year == today.year
                    ]

                    message = self._builder.build_weekly_summary(
                        user_dict, this_month, today,
                    )
                    if not message:
                        stats["skipped"] += 1
                        continue

                    delivered = await self._send_with_retry(
                        session, user_row.id, telegram_id, message,
                        job_id, "weekly_summary",
                    )
                    if delivered:
                        stats["sent"] += 1
                    else:
                        stats["errors"] += 1

                await session.commit()
        except Exception:
            logger.exception("[%s] Unexpected error", job_id)

        self._last_run_stats[job_id] = {
            **stats,
            "run_at": datetime.now(VN_TZ).isoformat(),
        }
        logger.info(
            "[%s] Finished — checked=%d sent=%d skipped=%d errors=%d",
            job_id, stats["checked"], stats["sent"],
            stats["skipped"], stats["errors"],
        )

    async def _monthly_calendar(self) -> None:
        """Send monthly tax calendar on the 1st of each month."""
        job_id = "monthly_calendar"
        today = datetime.now(VN_TZ).date()
        stats = {"checked": 0, "sent": 0, "skipped": 0, "errors": 0}

        logger.info("[%s] Starting — date=%s", job_id, today)

        try:
            async with async_session() as session:
                users = await self._get_notifiable_users(session)
                stats["checked"] = len(users)

                for user_row in users:
                    user_dict = self._customer_to_profile(user_row)
                    telegram_id = user_row.channel_user_id

                    if await self._was_recently_notified(session, user_row.id):
                        stats["skipped"] += 1
                        continue

                    # Get all deadlines, filter to this month
                    all_deadlines = self._calculator.get_deadlines_for_user(
                        user_dict, today,
                    )
                    this_month = [
                        d for d in all_deadlines
                        if d["due_date"].month == today.month
                        and d["due_date"].year == today.year
                    ]

                    message = self._builder.build_monthly_calendar(
                        user_dict, this_month, today,
                    )
                    if not message:
                        stats["skipped"] += 1
                        continue

                    delivered = await self._send_with_retry(
                        session, user_row.id, telegram_id, message,
                        job_id, "monthly_calendar",
                    )
                    if delivered:
                        stats["sent"] += 1
                    else:
                        stats["errors"] += 1

                await session.commit()
        except Exception:
            logger.exception("[%s] Unexpected error", job_id)

        self._last_run_stats[job_id] = {
            **stats,
            "run_at": datetime.now(VN_TZ).isoformat(),
        }
        logger.info(
            "[%s] Finished — checked=%d sent=%d skipped=%d errors=%d",
            job_id, stats["checked"], stats["sent"],
            stats["skipped"], stats["errors"],
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_notifiable_users(session: AsyncSession) -> list[Customer]:
        """Fetch users with notification_enabled=True on the telegram channel."""
        result = await session.execute(
            select(Customer).where(
                Customer.channel == "telegram",
                Customer.notification_enabled.is_(True),
                Customer.onboarding_step != "new",  # skip users who haven't onboarded
            )
        )
        return list(result.scalars().all())

    @staticmethod
    async def _was_recently_notified(
        session: AsyncSession,
        customer_id: uuid.UUID,
    ) -> bool:
        """Return True if the user received a notification within the last 20 hours."""
        cutoff = datetime.now(VN_TZ) - timedelta(hours=ANTI_SPAM_HOURS)
        result = await session.execute(
            select(sa_func.count()).select_from(NotificationLog).where(
                NotificationLog.customer_id == customer_id,
                NotificationLog.sent_at >= cutoff,
                NotificationLog.was_delivered.is_(True),
            )
        )
        return (result.scalar() or 0) > 0

    @staticmethod
    def _customer_to_profile(c: Customer) -> dict[str, Any]:
        """Convert a Customer ORM row to the dict expected by DeadlineCalculator and MessageBuilder."""
        tax_profile = c.tax_profile or {}
        return {
            "business_type": c.customer_type or "",
            "tax_period": tax_profile.get("tax_period", ""),
            "industry": c.industry or "",
            "has_employees": tax_profile.get("has_employees", False),
            "latest_revenue": tax_profile.get("latest_revenue"),
            "tax_handler": tax_profile.get("tax_handler", "unknown"),
            "display_name": c.display_name or c.first_name or "",
            "first_name": c.first_name or "",
        }

    async def _send_with_retry(
        self,
        session: AsyncSession,
        customer_id: uuid.UUID,
        telegram_id: str,
        message: str,
        job_id: str,
        notification_type: str,
    ) -> bool:
        """Send a Telegram message with up to 3 retries.

        Logs every attempt in notification_logs.
        Returns True if delivered, False after all retries exhausted.
        """
        log_entry = NotificationLog(
            customer_id=customer_id,
            job_id=job_id,
            notification_type=notification_type,
            message_text=message[:500],  # store truncated for reference
            was_delivered=False,
            retry_count=0,
        )
        session.add(log_entry)
        await session.flush()

        for attempt in range(1, MAX_RETRIES + 1):
            success, error = await self._send_telegram_message(telegram_id, message)
            log_entry.retry_count = attempt

            if success:
                log_entry.was_delivered = True
                log_entry.error_message = None
                await session.flush()
                return True

            log_entry.error_message = error
            await session.flush()

            if attempt < MAX_RETRIES:
                logger.warning(
                    "Telegram send failed (attempt %d/%d) for user %s: %s",
                    attempt, MAX_RETRIES, telegram_id, error,
                )
                await asyncio.sleep(RETRY_DELAY_SECONDS)

        logger.error(
            "Telegram send permanently failed for user %s after %d attempts: %s",
            telegram_id, MAX_RETRIES, log_entry.error_message,
        )
        return False

    async def _send_telegram_message(
        self,
        chat_id: str,
        text: str,
    ) -> tuple[bool, str | None]:
        """Send a message via Telegram Bot API.

        Returns (success, error_message).
        """
        token = settings.telegram_bot_token
        if not token:
            return False, "TELEGRAM_BOT_TOKEN not configured"

        if not self._http_client:
            self._http_client = httpx.AsyncClient(timeout=30.0)

        url = TELEGRAM_API_BASE.format(token=token)
        try:
            resp = await self._http_client.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
            )
            data = resp.json()
            if resp.status_code == 200 and data.get("ok"):
                return True, None
            return False, f"Telegram API error: {data.get('description', resp.status_code)}"
        except httpx.HTTPError as exc:
            return False, f"HTTP error: {exc}"


# Singleton instance
notification_scheduler = NotificationScheduler()
