"""Measurement and outcome persistence for Growth actions."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.growth.contracts import GrowthActionOutcomeRecord
from apps.api.app.growth.models import GrowthAction, GrowthOutcome
from apps.api.app.growth.service import GrowthStateError


class GrowthMeasurementService:
    """Persist measured outcomes without conflating execution with effectiveness."""

    def __init__(self) -> None:
        self.audit = AuditEventService()

    async def record(
        self,
        session: AsyncSession,
        organization_id: UUID,
        action_id: UUID,
        command: GrowthActionOutcomeRecord,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> GrowthOutcome:
        action = await session.scalar(
            select(GrowthAction).where(
                GrowthAction.organization_id == organization_id,
                GrowthAction.id == action_id,
            )
        )
        if action is None:
            raise GrowthStateError("growth action not found")
        if action.status != "completed":
            raise GrowthStateError("only completed growth actions may be measured")

        outcome = GrowthOutcome(
            organization_id=organization_id,
            action_id=action.id,
            classification=command.classification,
            baseline=command.baseline,
            measurement=command.measurement,
            limitations=list(command.limitations),
        )
        session.add(outcome)
        await session.flush()

        await self.audit.record(
            session,
            AuditEventCreate(
                event_type="growth.outcome.recorded",
                action="growth.outcome.record",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER,
                actor_id=actor_id,
                organization_id=organization_id,
                product_key="growth",
                resource_type="growth_outcome",
                resource_id=outcome.id,
                correlation_id=correlation_id,
                summary="Measured outcome recorded for a Growth action.",
                metadata={
                    "action_id": str(action.id),
                    "classification": command.classification,
                },
            ),
        )
        return outcome

    async def list_for_initiative(
        self,
        session: AsyncSession,
        organization_id: UUID,
        initiative_id: UUID,
    ) -> list[GrowthOutcome]:
        return list(
            await session.scalars(
                select(GrowthOutcome)
                .join(
                    GrowthAction,
                    (GrowthAction.organization_id == GrowthOutcome.organization_id)
                    & (GrowthAction.id == GrowthOutcome.action_id),
                )
                .where(
                    GrowthOutcome.organization_id == organization_id,
                    GrowthAction.initiative_id == initiative_id,
                )
                .order_by(GrowthOutcome.observed_at.desc())
            )
        )
