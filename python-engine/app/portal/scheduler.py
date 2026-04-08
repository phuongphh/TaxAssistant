"""
Background scheduler that computes and stores hourly metrics snapshots.
"""

import asyncio
import logging
from datetime import date

from app.db.database import async_session
from app.db.portal_repository import PortalRepository

logger = logging.getLogger(__name__)

SNAPSHOT_INTERVAL_SECONDS = 3600  # 1 hour


async def compute_and_store_snapshot() -> None:
    """Compute current metrics and persist a snapshot."""
    async with async_session() as session:
        repo = PortalRepository(session)
        today = date.today()

        total_users = await repo.get_total_active_users()
        dau = await repo.get_dau(today)
        mau = await repo.get_mau(today.year, today.month)
        new_day = await repo.get_new_users_count("day", today)
        new_month = await repo.get_new_users_count("month", today)
        new_year = await repo.get_new_users_count("year", today)
        segmentation = await repo.get_customer_segmentation()

        await repo.save_snapshot({
            "total_users": total_users,
            "active_users_day": dau,
            "active_users_month": mau,
            "new_users_day": new_day,
            "new_users_month": new_month,
            "new_users_year": new_year,
            "segmentation": segmentation,
        })
        await session.commit()
        logger.info(
            "Metrics snapshot saved: total=%d, dau=%d, mau=%d",
            total_users, dau, mau,
        )


async def run_scheduler() -> None:
    """Run the snapshot scheduler loop indefinitely."""
    logger.info("Portal metrics scheduler started (interval=%ds)", SNAPSHOT_INTERVAL_SECONDS)
    while True:
        try:
            await compute_and_store_snapshot()
        except Exception:
            logger.exception("Error computing metrics snapshot")
        await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)
