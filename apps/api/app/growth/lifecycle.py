"""Durable scheduler-owned advancement for approved Growth initiatives.

This service does not create a second execution plane. It projects durable child
workflow and product-artifact state back into Growth and delegates newly
 dependency-ready product agent actions through the existing
ExecutionService-backed GrowthService.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.growth.artifacts import GrowthArtifactLifecycleService
from apps.api.app.growth.models import GrowthInitiative
from apps.api.app.growth.service import GrowthService


@dataclass(frozen=True, slots=True)
class GrowthLifecycleSweepResult:
    scanned: int = 0
    reconciled: int = 0
    artifact_transitions: int = 0
    dispatched: int = 0


class GrowthLifecycleService:
    """Advance approved initiatives without requiring operator lifecycle clicks."""

    def __init__(
        self,
        growth: GrowthService | None = None,
        artifacts: GrowthArtifactLifecycleService | None = None,
    ) -> None:
        self.growth = growth or GrowthService()
        self.artifacts = artifacts or GrowthArtifactLifecycleService()

    async def advance_batch(
        self,
        session: AsyncSession,
        *,
        limit: int = 100,
    ) -> GrowthLifecycleSweepResult:
        bounded_limit = min(max(limit, 1), 500)
        initiatives = list(
            await session.scalars(
                select(GrowthInitiative)
                .where(GrowthInitiative.status.in_(("approved", "executing")))
                .order_by(GrowthInitiative.updated_at, GrowthInitiative.id)
                .limit(bounded_limit)
            )
        )

        reconciled = 0
        artifact_transitions = 0
        dispatched = 0
        for candidate in initiatives:
            initiative = await self.growth.reconcile(
                session,
                candidate.organization_id,
                candidate.id,
            )
            reconciled += 1

            transitioned = await self.artifacts.reconcile_waiting_actions(
                session,
                candidate.organization_id,
                candidate.id,
            )
            artifact_transitions += transitioned
            if transitioned:
                # Re-project initiative terminal state after canonical downstream
                # product execution changed one or more Growth actions.
                initiative = await self.growth.reconcile(
                    session,
                    candidate.organization_id,
                    candidate.id,
                )
                reconciled += 1

            if initiative.status not in {"approved", "executing"}:
                continue

            # The approving human is the durable authorization for delegation.
            # The scheduler does not invent authority or bypass product approvals;
            # downstream product workflows retain their own approval/write gates.
            if initiative.approved_by_user_id is None:
                continue
            newly_dispatched = await self.growth.dispatch_ready(
                session,
                initiative.organization_id,
                initiative.id,
                actor_id=initiative.approved_by_user_id,
                correlation_id=f"growth-lifecycle-{initiative.id}"[:64],
            )
            dispatched += len(newly_dispatched)

        return GrowthLifecycleSweepResult(
            scanned=len(initiatives),
            reconciled=reconciled,
            artifact_transitions=artifact_transitions,
            dispatched=dispatched,
        )
