"""
Repository for portal dashboard metrics queries.
"""

import csv
import io
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import Date, cast, distinct, extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer, MetricsSnapshot, TaxQuery

logger = logging.getLogger(__name__)


class PortalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Summary metrics
    # ------------------------------------------------------------------

    async def get_total_active_users(self) -> int:
        result = await self.session.execute(
            select(func.count(Customer.id))
        )
        return result.scalar() or 0

    async def get_new_users_count(
        self,
        period: str,
        ref_date: date | None = None,
    ) -> int:
        """Count new users for a given period (day/month/year)."""
        ref = ref_date or date.today()
        stmt = select(func.count(Customer.id))

        if period == "day":
            stmt = stmt.where(
                cast(Customer.created_at, Date) == ref,
            )
        elif period == "month":
            stmt = stmt.where(
                extract("year", Customer.created_at) == ref.year,
                extract("month", Customer.created_at) == ref.month,
            )
        elif period == "year":
            stmt = stmt.where(
                extract("year", Customer.created_at) == ref.year,
            )

        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def get_dau(self, target_date: date | None = None) -> int:
        """Daily Active Users — distinct user_ids in tax_queries for a given day."""
        d = target_date or date.today()
        result = await self.session.execute(
            select(func.count(distinct(TaxQuery.user_id))).where(
                cast(TaxQuery.created_at, Date) == d,
            )
        )
        return result.scalar() or 0

    async def get_mau(self, year: int | None = None, month: int | None = None) -> int:
        """Monthly Active Users — distinct user_ids in tax_queries for a given month."""
        now = date.today()
        y = year or now.year
        m = month or now.month
        result = await self.session.execute(
            select(func.count(distinct(TaxQuery.user_id))).where(
                extract("year", TaxQuery.created_at) == y,
                extract("month", TaxQuery.created_at) == m,
            )
        )
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Segmentation
    # ------------------------------------------------------------------

    async def get_customer_segmentation(self) -> list[dict]:
        """Count customers grouped by customer_type."""
        result = await self.session.execute(
            select(
                Customer.customer_type,
                func.count(Customer.id).label("count"),
            ).group_by(Customer.customer_type)
        )
        return [
            {"customer_type": row.customer_type, "count": row.count}
            for row in result.all()
        ]

    # ------------------------------------------------------------------
    # Trends (time-series)
    # ------------------------------------------------------------------

    async def get_growth_trends(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Daily new-user counts between start and end dates."""
        result = await self.session.execute(
            select(
                cast(Customer.created_at, Date).label("day"),
                func.count(Customer.id).label("count"),
            )
            .where(
                cast(Customer.created_at, Date) >= start_date,
                cast(Customer.created_at, Date) <= end_date,
            )
            .group_by(cast(Customer.created_at, Date))
            .order_by(cast(Customer.created_at, Date))
        )
        return [
            {"date": row.day.isoformat(), "count": row.count}
            for row in result.all()
        ]

    async def get_activity_trends(
        self,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        """Daily active user counts between start and end dates."""
        result = await self.session.execute(
            select(
                cast(TaxQuery.created_at, Date).label("day"),
                func.count(distinct(TaxQuery.user_id)).label("count"),
            )
            .where(
                cast(TaxQuery.created_at, Date) >= start_date,
                cast(TaxQuery.created_at, Date) <= end_date,
            )
            .group_by(cast(TaxQuery.created_at, Date))
            .order_by(cast(TaxQuery.created_at, Date))
        )
        return [
            {"date": row.day.isoformat(), "count": row.count}
            for row in result.all()
        ]

    # ------------------------------------------------------------------
    # Snapshots
    # ------------------------------------------------------------------

    async def save_snapshot(self, data: dict) -> MetricsSnapshot:
        snapshot = MetricsSnapshot(
            snapshot_at=datetime.now(timezone.utc),
            total_users=data.get("total_users", 0),
            active_users_day=data.get("active_users_day", 0),
            active_users_month=data.get("active_users_month", 0),
            new_users_day=data.get("new_users_day", 0),
            new_users_month=data.get("new_users_month", 0),
            new_users_year=data.get("new_users_year", 0),
            segmentation_json=data.get("segmentation", {}),
        )
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    # ------------------------------------------------------------------
    # CSV Export
    # ------------------------------------------------------------------

    async def export_users_csv(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> str:
        """Export customer data as CSV string, optionally filtered by created_at range."""
        stmt = select(Customer).order_by(Customer.created_at.desc())

        if start_date:
            stmt = stmt.where(cast(Customer.created_at, Date) >= start_date)
        if end_date:
            stmt = stmt.where(cast(Customer.created_at, Date) <= end_date)

        result = await self.session.execute(stmt)
        customers = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "channel", "customer_type", "business_name",
            "tax_code", "industry", "province", "created_at", "last_active_at",
        ])
        for c in customers:
            writer.writerow([
                str(c.id),
                c.channel,
                c.customer_type,
                c.business_name or "",
                c.tax_code or "",
                c.industry or "",
                c.province or "",
                c.created_at.isoformat() if c.created_at else "",
                c.last_active_at.isoformat() if c.last_active_at else "",
            ])

        return output.getvalue()
