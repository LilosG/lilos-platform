"""Governed persistence and validation for cross-product growth plans."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.agents.models import AgentRun
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES
from apps.api.app.growth.contracts import GrowthPlanCreate
from apps.api.app.growth.models import GrowthAction, GrowthInitiative


class GrowthPlanValidationError(ValueError):
    """A proposed plan violates a deterministic orchestration boundary."""


class GrowthService:
    """Create and query cross-product initiatives without bypassing product domains."""

    def __init__(self) -> None:
        self.audit = AuditEventService()

    @staticmethod
    def _validate_executor_bindings(command: GrowthPlanCreate) -> None:
        """Ensure workflow actions delegate only to registered, product-owned executors."""
        for action in command.actions:
            if action.execution_mode != "workflow":
                continue
            workflow_key = action.executor_workflow_key
            if workflow_key is None or workflow_key not in WORKFLOW_TYPES:
                raise GrowthPlanValidationError(
                    f"unknown executor workflow for action {action.action_key}"
                )
            if workflow_key == "agent.growth":
                raise GrowthPlanValidationError("growth planner cannot recursively execute itself")
            _name, owner = WORKFLOW_TYPES[workflow_key]
            if owner != action.product_key:
                raise GrowthPlanValidationError(
                    f"executor owner mismatch for action {action.action_key}: "
                    f"{workflow_key} belongs to {owner}, not {action.product_key}"
                )

    async def create_from_agent(
        self,
        session: AsyncSession,
        run: AgentRun,
        command: GrowthPlanCreate,
    ) -> GrowthInitiative:
        """Persist one idempotent plan produced by a bound Hermes planner run."""
        self._validate_executor_bindings(command)
        idempotency_key = f"growth-plan:{run.id}"
        existing = await session.scalar(
            select(GrowthInitiative).where(
                GrowthInitiative.organization_id == run.organization_id,
                GrowthInitiative.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing

        initiative = GrowthInitiative(
            organization_id=run.organization_id,
            location_id=run.location_id,
            planner_agent_run_id=run.id,
            idempotency_key=idempotency_key,
            objective=command.objective,
            rationale=command.rationale,
            source_references=list(command.source_references),
            priority_score=command.priority_score,
            confidence=Decimal(str(command.confidence)),
            status="proposed",
        )
        session.add(initiative)
        await session.flush()

        for position, action in enumerate(command.actions):
            session.add(
                GrowthAction(
                    organization_id=run.organization_id,
                    initiative_id=initiative.id,
                    action_key=action.action_key,
                    product_key=action.product_key,
                    action_type=action.action_type,
                    target_reference=action.target_reference,
                    execution_mode=action.execution_mode,
                    executor_workflow_key=action.executor_workflow_key,
                    dependency_keys=list(action.dependency_keys),
                    evidence_references=list(action.evidence_references),
                    expected_result_hypothesis=action.expected_result_hypothesis,
                    verification_plan=action.verification_plan,
                    risk=action.risk,
                    effort=action.effort,
                    approval_required=action.approval_required,
                    position=position,
                    status="proposed",
                )
            )
        await session.flush()

        await self.audit.record(
            session,
            AuditEventCreate(
                event_type="growth.initiative.proposed",
                action="growth.initiative.propose",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.WORKFLOW,
                organization_id=run.organization_id,
                location_id=run.location_id,
                product_key="growth",
                resource_type="growth_initiative",
                resource_id=initiative.id,
                correlation_id=run.correlation_id,
                workflow_execution_id=run.workflow_run_id,
                summary="Hermes proposed a governed cross-product growth initiative.",
                metadata={
                    "planner_agent_run_id": str(run.id),
                    "priority_score": command.priority_score,
                    "action_count": len(command.actions),
                },
            ),
        )
        return initiative

    async def actions(
        self,
        session: AsyncSession,
        organization_id: UUID,
        initiative_id: UUID,
    ) -> list[GrowthAction]:
        return list(
            await session.scalars(
                select(GrowthAction)
                .where(
                    GrowthAction.organization_id == organization_id,
                    GrowthAction.initiative_id == initiative_id,
                )
                .order_by(GrowthAction.position, GrowthAction.created_at)
            )
        )
