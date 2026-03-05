"""
Repository for Customer CRUD operations.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Customer

logger = logging.getLogger(__name__)


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

    async def get_or_create(self, channel: str, channel_user_id: str) -> tuple[Customer, bool]:
        """Get existing customer or create a new one.

        Returns:
            Tuple of (customer, is_new).
        """
        existing = await self.get_by_channel_user(channel, channel_user_id)
        if existing:
            # Update last_active_at
            existing.last_active_at = datetime.now(timezone.utc)
            await self.session.flush()
            return existing, False

        customer = Customer(
            channel=channel,
            channel_user_id=channel_user_id,
            customer_type="unknown",
            onboarding_step="new",
        )
        self.session.add(customer)
        await self.session.flush()
        logger.info("New customer created: %s/%s → %s", channel, channel_user_id, customer.id)
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
