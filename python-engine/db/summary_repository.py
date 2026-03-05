"""
Repository for ConversationSummary CRUD operations.
"""

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ConversationSummary

logger = logging.getLogger(__name__)


class SummaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        customer_id: uuid.UUID,
        summary: str,
        session_date: date | None = None,
        support_case_id: uuid.UUID | None = None,
        key_topics: list[str] | None = None,
        action_items: list[str] | None = None,
    ) -> ConversationSummary:
        entry = ConversationSummary(
            customer_id=customer_id,
            session_date=session_date or date.today(),
            summary=summary,
            support_case_id=support_case_id,
            key_topics=key_topics or [],
            action_items=action_items or [],
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def get_recent(
        self, customer_id: uuid.UUID, limit: int = 5
    ) -> list[ConversationSummary]:
        """Get the most recent conversation summaries for a customer."""
        result = await self.session.execute(
            select(ConversationSummary)
            .where(ConversationSummary.customer_id == customer_id)
            .order_by(ConversationSummary.session_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_case(self, case_id: uuid.UUID) -> list[ConversationSummary]:
        result = await self.session.execute(
            select(ConversationSummary)
            .where(ConversationSummary.support_case_id == case_id)
            .order_by(ConversationSummary.session_date.asc())
        )
        return list(result.scalars().all())
