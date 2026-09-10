"""Governed persistence, approval, and delegation for cross-product growth plans."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.agents.models import AgentRun
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES
from apps.api.app.growth.contracts import GrowthPlanCreate
from apps.api.app.growth.models import GrowthAction, GrowthInitiative

# The planner coordinates product agents; it never jumps directly into a
# publication/provider-write workflow. Product agents translate the plan into
# their canonical product-domain proposals and retain all product guardrails.
GROWTH_EXECUTOR_WORKFLOWS: dict[str, str] = {
    "agent.seo": "seo",
    "agent.content": "content",
    "agent.gbp": "gbp",
    "agent.reviews": "reviews",
}


class GrowthPlanValidationError(ValueError):
    """A proposed plan violates a deterministic orchestration boundary."""


class GrowthStateError(ValueError):
    """A requested initiative transition is invalid for its current state."""


class GrowthService:
    """Coordinate product domains without bypassing their governed lifecycles."""

    def __init__(self) -> None:
        self.audit = AuditEventService()
        self.execution = ExecutionService()

    @staticmethod
    def _validate_executor_bindings(command: GrowthPlanCreate) -> None:
        """Allow delegation only to registered, product-owned agent executors."""
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
            owner = GROWTH_EXECUTOR_WORKFLOWS.get(workflow_key)
            if owner is None:
                raise GrowthPlanValidationError(
                    f"workflow {workflow_key} is not a growth-delegatable product agent"
                )
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

    async def get(
        self, session: AsyncSession, organization_id: UUID, initiative_id: UUID, *, lock: bool = False
    ) -> GrowthInitiative | None:
        statement = select(GrowthInitiative).where(
            GrowthInitiative.organization_id == organization_id,
            GrowthInitiative.id == initiative_id,
        )
        if lock:
            statement = statement.with_for_update()
        return await session.scalar(statement)

    async def list(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        location_id: UUID | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[GrowthInitiative]:
        statement = select(GrowthInitiative).where(
            GrowthInitiative.organization_id == organization_id
        )
        if location_id is not None:
            statement = statement.where(GrowthInitiative.location_id == location_id)
        if status is not None:
            statement = statement.where(GrowthInitiative.status == status)
        return list(
            await session.scalars(
                statement.order_by(
                    GrowthInitiative.priority_score.desc(), GrowthInitiative.created_at.desc()
                ).limit(limit)
            )
        )

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

    async def decide(
        self,
        session: AsyncSession,
        organization_id: UUID,
        initiative_id: UUID,
        *,
        approve: bool,
        actor_id: UUID,
        correlation_id: str,
    ) -> GrowthInitiative:
        """Human approval is the sole transition out of a proposed initiative."""
        initiative = await self.get(session, organization_id, initiative_id, lock=True)
        if initiative is None:
            raise GrowthStateError("growth initiative not found")
        if initiative.status != "proposed":
            raise GrowthStateError("growth initiative is no longer awaiting a decision")

        now = datetime.now(UTC)
        initiative.status = "approved" if approve else "rejected"
        if approve:
            initiative.approved_by_user_id = actor_id
            initiative.approved_at = now
        else:
            initiative.rejected_at = now

        actions = await self.actions(session, organization_id, initiative.id)
        for action in actions:
            action.status = "approved" if approve else "cancelled"
            if not approve:
                action.completed_at = now

        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=(
                    "growth.initiative.approved" if approve else "growth.initiative.rejected"
                ),
                action="growth.initiative.decide",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER,
                actor_id=actor_id,
                organization_id=organization_id,
                location_id=initiative.location_id,
                product_key="growth",
                resource_type="growth_initiative",
                resource_id=initiative.id,
                correlation_id=correlation_id,
                summary=(
                    "Growth initiative approved for governed delegation."
                    if approve
                    else "Growth initiative rejected."
                ),
                metadata={"decision": "approved" if approve else "rejected"},
            ),
        )
        await session.flush()
        return initiative

    @staticmethod
    def _dependencies_complete(action: GrowthAction, by_key: dict[str, GrowthAction]) -> bool:
        return all(
            dependency in by_key and by_key[dependency].status == "completed"
            for dependency in (str(value) for value in action.dependency_keys)
        )

    async def dispatch_ready(
        self,
        session: AsyncSession,
        organization_id: UUID,
        initiative_id: UUID,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> list[GrowthAction]:
        """Delegate dependency-ready workflow actions through the durable executor.

        Manual and monitor actions remain explicit queue items; they are never
        silently converted into automated work.
        """
        initiative = await self.get(session, organization_id, initiative_id, lock=True)
        if initiative is None:
            raise GrowthStateError("growth initiative not found")
        if initiative.status not in {"approved", "executing"}:
            raise GrowthStateError("growth initiative is not approved for execution")

        actions = await self.actions(session, organization_id, initiative.id)
        by_key = {action.action_key: action for action in actions}
        dispatched: list[GrowthAction] = []
        for action in actions:
            if (
                action.status != "approved"
                or action.execution_mode != "workflow"
                or not self._dependencies_complete(action, by_key)
            ):
                continue
            workflow_key = action.executor_workflow_key
            if workflow_key is None or GROWTH_EXECUTOR_WORKFLOWS.get(workflow_key) != action.product_key:
                raise GrowthStateError("growth action executor binding is no longer valid")

            objective = (
                f"Execute the approved Growth action '{action.action_key}' for target "
                f"{action.target_reference}. Action type: {action.action_type}. "
                f"Expected result hypothesis: {action.expected_result_hypothesis}. "
                "Re-read current authoritative product evidence before proposing any change; "
                "the parent Growth evidence references are provenance, not a substitute for "
                "this agent run observing its own evidence."
            )
            workflow = await self.execution.start_named(
                session,
                organization_id,
                workflow_key,
                f"growth-action-{action.id}",
                location_id=initiative.location_id,
                input_document={
                    "objective": objective[:4_000],
                    "context_reference": f"growth-action:{action.id}",
                },
                correlation_id=correlation_id,
                actor_id=actor_id,
                enqueue_job=True,
            )
            action.workflow_run_id = workflow.id
            action.status = "queued"
            dispatched.append(action)

        if dispatched:
            initiative.status = "executing"
            await self.audit.record(
                session,
                AuditEventCreate(
                    event_type="growth.actions.delegated",
                    action="growth.actions.delegate",
                    result=AuditResult.SUCCEEDED,
                    actor_type=AuditActorType.USER,
                    actor_id=actor_id,
                    organization_id=organization_id,
                    location_id=initiative.location_id,
                    product_key="growth",
                    resource_type="growth_initiative",
                    resource_id=initiative.id,
                    correlation_id=correlation_id,
                    summary="Dependency-ready Growth actions delegated to governed product agents.",
                    metadata={
                        "action_ids": [str(action.id) for action in dispatched],
                        "workflow_run_ids": [str(action.workflow_run_id) for action in dispatched],
                    },
                ),
            )
        await session.flush()
        return dispatched

    async def reconcile(
        self,
        session: AsyncSession,
        organization_id: UUID,
        initiative_id: UUID,
    ) -> GrowthInitiative:
        """Project durable workflow state into the Growth queue without inventing success."""
        initiative = await self.get(session, organization_id, initiative_id, lock=True)
        if initiative is None:
            raise GrowthStateError("growth initiative not found")
        actions = await self.actions(session, organization_id, initiative.id)
        now = datetime.now(UTC)
        for action in actions:
            if action.workflow_run_id is None or action.status in {
                "completed",
                "failed",
                "cancelled",
                "skipped",
            }:
                continue
            workflow = await session.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.id == action.workflow_run_id,
                )
            )
            if workflow is None:
                action.status = "failed"
                action.safe_error_code = "WORKFLOW_RUN_MISSING"
                action.completed_at = now
                continue
            if workflow.status in {"queued", "retry_scheduled"}:
                action.status = "queued"
            elif workflow.status == "running":
                action.status = "running"
                action.started_at = action.started_at or workflow.started_at or now
            elif workflow.status == "completed":
                # A product agent completing means delegation succeeded. If it created
                # a canonical product proposal, that proposal still owns its own
                # approval/publication lifecycle; keep the Growth action waiting for
                # that downstream decision instead of claiming business execution.
                agent_run = await session.scalar(
                    select(AgentRun).where(
                        AgentRun.organization_id == organization_id,
                        AgentRun.workflow_run_id == workflow.id,
                    )
                )
                proposals = list(agent_run.output_references) if agent_run else []
                product_proposals = [
                    str(ref)
                    for ref in proposals
                    if not str(ref).startswith("growth-initiative:")
                ]
                if product_proposals:
                    action.status = "waiting_approval"
                    action.result_reference = product_proposals[0][:500]
                else:
                    action.status = "completed"
                    action.result_reference = workflow.output_reference
                    action.completed_at = workflow.completed_at or now
            elif workflow.status == "cancelled":
                action.status = "cancelled"
                action.safe_error_code = workflow.failure_code
                action.completed_at = workflow.cancelled_at or now
            elif workflow.status in {"failed", "escalated"}:
                action.status = "failed"
                action.safe_error_code = workflow.failure_code or "WORKFLOW_FAILED"
                action.completed_at = workflow.completed_at or now

        terminal = {"completed", "failed", "skipped", "cancelled"}
        if actions and all(action.status in terminal for action in actions):
            initiative.status = "completed"
            initiative.completed_at = initiative.completed_at or now
        await session.flush()
        return initiative

    async def detail(
        self, session: AsyncSession, organization_id: UUID, initiative_id: UUID
    ) -> dict[str, object] | None:
        initiative = await self.get(session, organization_id, initiative_id)
        if initiative is None:
            return None
        actions = await self.actions(session, organization_id, initiative.id)
        return {
            "id": str(initiative.id),
            "location_id": str(initiative.location_id) if initiative.location_id else None,
            "planner_agent_run_id": str(initiative.planner_agent_run_id),
            "objective": initiative.objective,
            "rationale": initiative.rationale,
            "source_references": initiative.source_references,
            "priority_score": initiative.priority_score,
            "confidence": float(initiative.confidence),
            "status": initiative.status,
            "approved_at": initiative.approved_at.isoformat() if initiative.approved_at else None,
            "completed_at": initiative.completed_at.isoformat() if initiative.completed_at else None,
            "created_at": initiative.created_at.isoformat(),
            "actions": [
                {
                    "id": str(action.id),
                    "action_key": action.action_key,
                    "product_key": action.product_key,
                    "action_type": action.action_type,
                    "target_reference": action.target_reference,
                    "execution_mode": action.execution_mode,
                    "executor_workflow_key": action.executor_workflow_key,
                    "dependency_keys": action.dependency_keys,
                    "evidence_references": action.evidence_references,
                    "expected_result_hypothesis": action.expected_result_hypothesis,
                    "verification_plan": action.verification_plan,
                    "risk": action.risk,
                    "effort": action.effort,
                    "approval_required": action.approval_required,
                    "status": action.status,
                    "workflow_run_id": str(action.workflow_run_id) if action.workflow_run_id else None,
                    "result_reference": action.result_reference,
                    "safe_error_code": action.safe_error_code,
                    "started_at": action.started_at.isoformat() if action.started_at else None,
                    "completed_at": action.completed_at.isoformat() if action.completed_at else None,
                }
                for action in actions
            ],
        }
