"""
Repository for SupportCase CRUD operations.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SupportCase

logger = logging.getLogger(__name__)


class CaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, case_id: uuid.UUID) -> SupportCase | None:
        result = await self.session.execute(
            select(SupportCase).where(SupportCase.id == case_id)
        )
        return result.scalar_one_or_none()

    async def get_active_cases(self, customer_id: uuid.UUID) -> list[SupportCase]:
        """Get all non-completed cases for a customer."""
        result = await self.session.execute(
            select(SupportCase)
            .where(
                SupportCase.customer_id == customer_id,
                SupportCase.status.notin_(["completed", "cancelled"]),
            )
            .order_by(SupportCase.updated_at.desc())
        )
        return list(result.scalars().all())

    async def get_cases_by_customer(
        self, customer_id: uuid.UUID, limit: int = 10
    ) -> list[SupportCase]:
        """Get recent cases for a customer (all statuses)."""
        result = await self.session.execute(
            select(SupportCase)
            .where(SupportCase.customer_id == customer_id)
            .order_by(SupportCase.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def create(
        self,
        customer_id: uuid.UUID,
        service_type: str,
        title: str,
        context: dict | None = None,
    ) -> SupportCase:
        case = SupportCase(
            customer_id=customer_id,
            service_type=service_type,
            title=title,
            status="open",
            current_step="step_1",
            steps_data={},
            context=context or {},
        )
        self.session.add(case)
        await self.session.flush()
        logger.info("Support case created: %s (type=%s, customer=%s)", case.id, service_type, customer_id)
        return case

    async def update_step(
        self,
        case_id: uuid.UUID,
        current_step: str,
        step_data: dict | None = None,
        status: str | None = None,
    ) -> SupportCase | None:
        """Advance the case to a new step, optionally saving step data."""
        case = await self.get_by_id(case_id)
        if not case:
            return None

        # Save data for the current step before advancing
        if step_data:
            steps = dict(case.steps_data or {})
            steps[case.current_step] = {
                "status": "completed",
                "data": step_data,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            case.steps_data = steps

        case.current_step = current_step
        if status:
            case.status = status
            if status == "completed":
                case.completed_at = datetime.now(timezone.utc)

        case.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return case

    async def complete(self, case_id: uuid.UUID) -> SupportCase | None:
        return await self.update_step(case_id, current_step="done", status="completed")

    async def cancel(self, case_id: uuid.UUID) -> SupportCase | None:
        case = await self.get_by_id(case_id)
        if not case:
            return None
        case.status = "cancelled"
        case.updated_at = datetime.now(timezone.utc)
        await self.session.flush()
        return case

    def to_dict(self, case: SupportCase) -> dict:
        return {
            "case_id": str(case.id),
            "customer_id": str(case.customer_id),
            "service_type": case.service_type,
            "title": case.title,
            "status": case.status,
            "current_step": case.current_step,
            "steps_data": case.steps_data or {},
            "context": case.context or {},
            "created_at": case.created_at.isoformat() if case.created_at else "",
            "updated_at": case.updated_at.isoformat() if case.updated_at else "",
        }
