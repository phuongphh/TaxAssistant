"""
Repository for Customer CRUD operations.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Customer

logger = logging.getLogger(__name__)


def _build_display_name(
    first_name: str | None,
    last_name: str | None,
    username: str | None,
) -> str | None:
    """Build a human-readable display name from available identity fields."""
    parts = [p for p in [first_name, last_name] if p]
    if parts:
        return " ".join(parts)
    return username or None


class CustomerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, customer_id: uuid.UUID) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        return result.scalar_one_or_none()

    async def get_by_channel_user(self, channel: str, channel_user_id: str) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(
                Customer.channel == channel,
                Customer.channel_user_id == channel_user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        channel: str,
        channel_user_id: str,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> tuple[Customer, bool]:
        """Get existing customer or create a new one.

        Args:
            channel: Channel name (e.g. "telegram")
            channel_user_id: Platform user ID (Telegram user_id)
            username: Platform @username (optional)
            first_name: User's first name (optional)
            last_name: User's last name (optional)

        Returns:
            Tuple of (customer, is_new).
        """
        existing = await self.get_by_channel_user(channel, channel_user_id)
        if existing:
            existing.last_active_at = datetime.now(timezone.utc)
            if username and not existing.username:
                existing.username = username
            if first_name and not existing.first_name:
                existing.first_name = first_name
            if last_name and not existing.last_name:
                existing.last_name = last_name
            if not existing.display_name:
                existing.display_name = _build_display_name(first_name, last_name, username)
            await self.session.flush()
            return existing, False

        display_name = _build_display_name(first_name, last_name, username)
        customer = Customer(
            channel=channel,
            channel_user_id=channel_user_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            customer_type="unknown",
            onboarding_step="new",
        )
        self.session.add(customer)
        await self.session.flush()
        logger.info(
            "New customer created: %s/%s (display='%s') → %s",
            channel, channel_user_id, display_name or "", customer.id,
        )
        return customer, True

    async def update_profile(
        self,
        customer_id: uuid.UUID,
        **fields,
    ) -> Customer | None:
        """Update customer profile fields."""
        allowed_fields = {
            "customer_type", "business_name", "tax_code", "industry",
            "province", "annual_revenue_range", "employee_count_range",
            "onboarding_step", "preferences", "tax_profile", "notes",
            "username", "first_name", "last_name", "display_name",
        }
        update_data = {k: v for k, v in fields.items() if k in allowed_fields}
        if not update_data:
            return await self.get_by_id(customer_id)

        update_data["updated_at"] = datetime.now(timezone.utc)
        await self.session.execute(
            update(Customer).where(Customer.id == customer_id).values(**update_data)
        )
        await self.session.flush()
        return await self.get_by_id(customer_id)

    async def add_note(self, customer_id: uuid.UUID, note: str) -> None:
        """Append a note to customer's notes array."""
        customer = await self.get_by_id(customer_id)
        if not customer:
            return
        notes = list(customer.notes or [])
        notes.append({
            "date": datetime.now(timezone.utc).isoformat(),
            "note": note,
        })
        # Keep last 50 notes
        if len(notes) > 50:
            notes = notes[-50:]
        customer.notes = notes
        await self.session.flush()

    def to_dict(self, customer: Customer) -> dict:
        """Convert Customer model to a plain dict for gRPC / context injection."""
        return {
            "customer_id": str(customer.id),
            "channel": customer.channel,
            "channel_user_id": customer.channel_user_id,
            "username": customer.username or "",
            "first_name": customer.first_name or "",
            "last_name": customer.last_name or "",
            "display_name": customer.display_name or "",
            "customer_type": customer.customer_type,
            "business_name": customer.business_name or "",
            "tax_code": customer.tax_code or "",
            "industry": customer.industry or "",
            "province": customer.province or "",
            "annual_revenue_range": customer.annual_revenue_range or "",
            "employee_count_range": customer.employee_count_range or "",
            "onboarding_step": customer.onboarding_step,
            "preferences": customer.preferences or {},
            "tax_profile": customer.tax_profile or {},
            "notes": customer.notes or [],
        }
