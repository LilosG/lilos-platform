"""Read-only Automation presentation over durable execution records.

No scheduler, provider I/O, payload replay or generic recovery is introduced.
"""

import json
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Select, func, or_, select

from apps.api.app.agents.access import AgentAccessService
from apps.api.app.agents.models import AgentRun
from apps.api.app.agents.skills import SKILLS, WORKFLOW_SKILLS
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.execution.models import (
    Job,
    JobAttempt,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from apps.api.app.locations.models import Location
from apps.api.app.products.content.models import ContentPublication
from apps.api.app.routes.command_center_reviews import private
from apps.api.app.routes.command_center_search import allowed
from apps.api.app.routes.workflows import Session, policy, service

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center/automations",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(private)],
)
RunStatus = Literal[
    "created",
    "queued",
    "running",
    "waiting",
    "waiting_approval",
    "retry_scheduled",
    "completed",
    "partially_completed",
    "cancelled",
    "expired",
    "failed",
    "escalated",
]
ATTENTION = (
    "waiting",
    "waiting_approval",
    "retry_scheduled",
    "partially_completed",
    "expired",
    "failed",
    "escalated",
)


class AutomationDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AutomationDefinition(AutomationDTO):
    key: str
    display_name: str
    product_key: str
    definition_status: str
    latest_version: int | None
    agent_eligible: bool | None = None
    eligibility_reason: str | None = None


class AutomationSchedule(AutomationDTO):
    id: UUID
    key: str
    workflow_key: str | None
    workflow_name: str | None
    cron_expression: str
    timezone: str
    status: Literal["active", "paused", "cancelled"]
    next_run_at: datetime | None
    last_run_at: datetime | None
    location_id: UUID | None
    overdue: bool = False
    can_manage: bool = False


class AutomationRun(AutomationDTO):
    id: UUID
    workflow_key: str
    workflow_name: str
    location_id: UUID | None
    status: RunStatus
    failure_code: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    correlation_id: str
    output_reference: str | None
    attention: (
        Literal["failure", "approval", "waiting", "retry", "partial", "stale", "reconciliation"]
        | None
    ) = None
    outcome: Literal[
        "execution_only", "recorded_result", "verified_publication", "unconfirmed_publication"
    ]
    publication_status: str | None = None
    publication_error: str | None = None
    job_status: str | None = None
    job_error_category: str | None = None
    retry_at: datetime | None = None
    agent_run_id: UUID | None = None
    agent_status: str | None = None
    agent_error: str | None = None


class AutomationLocation(AutomationDTO):
    id: UUID
    name: str


class AutomationWorkspace(AutomationDTO):
    organization_id: UUID
    location_id: UUID | None
    observed_at: datetime
    quality: Literal["partial"] = "partial"
    locations: list[AutomationLocation]
    can_manage_schedules: bool
    can_execute: bool
    schedules_state: Literal["available", "unavailable_permission"]
    runtime_health: Literal["unavailable_no_scoped_heartbeat"] = "unavailable_no_scoped_heartbeat"
    definitions: list[AutomationDefinition]
    schedules: list[AutomationSchedule]
    runs: list[AutomationRun]
    attention: list[AutomationRun]
    outcomes: list[AutomationRun]
    total_runs: int
    next_offset: int | None
    attention_limit: Literal[50] = 50
    outcomes_limit: Literal[10] = 10


class AutomationJob(AutomationDTO):
    id: UUID
    status: str
    job_type: str
    attempt_count: int
    max_attempts: int
    available_at: datetime
    last_error_category: str | None
    result_reference: str | None


class AutomationAttempt(AutomationDTO):
    id: UUID
    job_id: UUID
    attempt_number: int
    status: str
    started_at: datetime
    completed_at: datetime | None
    error_category: str | None


class AutomationAudit(AutomationDTO):
    id: UUID
    action: str
    result: str
    occurred_at: datetime
    correlation_id: str | None


class AutomationDetail(AutomationDTO):
    organization_id: UUID
    run: AutomationRun
    idempotency_key: str
    jobs: list[AutomationJob]
    attempts: list[AutomationAttempt]
    history: list[AutomationAudit]
    history_state: Literal["bounded_partial", "unavailable_permission"]
    can_stop: bool = False
    can_steer: bool = False
    can_respond_approval: bool = False
    approval_request: str | None = None
    recovery: Literal["domain_controls_only"] = "domain_controls_only"
    quality: Literal["bounded_partial"] = "bounded_partial"


async def check_location(session: Session, org: UUID, location: UUID | None) -> None:
    if location and not await session.scalar(
        select(Location.id).where(Location.organization_id == org, Location.id == location)
    ):
        raise HTTPException(404, "Location not found")


def run_query(org: UUID, location: UUID | None) -> Select[tuple[WorkflowRun]]:
    query = select(WorkflowRun).where(WorkflowRun.organization_id == org)
    return query.where(WorkflowRun.location_id == location) if location else query


async def project_runs(
    session: Session, org: UUID, rows: list[WorkflowRun], now: datetime
) -> list[AutomationRun]:
    if not rows:
        return []
    ids = [r.id for r in rows]
    key_rows = (
        await session.execute(
            select(WorkflowVersion.id, WorkflowDefinition.key, WorkflowDefinition.name)
            .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
            .where(WorkflowVersion.id.in_([r.workflow_version_id for r in rows]))
        )
    ).all()
    keys = {r[0]: (r[1], r[2]) for r in key_rows}
    jobs = list(
        await session.scalars(
            select(Job)
            .where(Job.organization_id == org, Job.workflow_run_id.in_(ids))
            .order_by(Job.created_at.desc(), Job.id.desc())
        )
    )
    latest: dict[UUID, Job] = {}
    for job_row in jobs:
        latest.setdefault(job_row.workflow_run_id, job_row)
    agents = {
        a.workflow_run_id: a
        for a in await session.scalars(
            select(AgentRun).where(
                AgentRun.organization_id == org, AgentRun.workflow_run_id.in_(ids)
            )
        )
    }
    publications = {
        p.workflow_run_id: p
        for p in await session.scalars(
            select(ContentPublication)
            .where(
                ContentPublication.organization_id == org,
                ContentPublication.workflow_run_id.in_(ids),
            )
            .order_by(ContentPublication.created_at, ContentPublication.id)
        )
    }
    result = []
    for row in rows:
        job, agent, pub = latest.get(row.id), agents.get(row.id), publications.get(row.id)
        item = AutomationRun(
            id=row.id,
            workflow_key=keys[row.workflow_version_id][0],
            workflow_name=keys[row.workflow_version_id][1],
            location_id=row.location_id,
            status=cast(RunStatus, row.status),
            failure_code=row.failure_code,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            correlation_id=row.correlation_id,
            output_reference=row.output_reference,
            outcome="execution_only",
            job_status=job.status if job else None,
            job_error_category=job.last_error_category if job else None,
            retry_at=job.available_at if job and job.status == "retry_scheduled" else None,
            agent_run_id=agent.id if agent else None,
            agent_status=agent.status if agent else None,
            agent_error=agent.safe_error_code if agent else None,
            publication_status=pub.status if pub else None,
            publication_error=pub.safe_error_code if pub else None,
        )
        if (
            row.status in ("failed", "expired", "escalated")
            or (job and job.status in ("failed", "dead_lettered"))
            or (agent and agent.status in ("failed", "capability_unavailable"))
        ):
            item.attention = "failure"
        elif row.status == "waiting_approval" or (agent and agent.status == "waiting_approval"):
            item.attention = "approval"
        elif row.status == "retry_scheduled" or (job and job.status == "retry_scheduled"):
            item.attention = "retry"
        elif row.status == "partially_completed":
            item.attention = "partial"
        elif row.status == "waiting":
            item.attention = "waiting"
        elif row.status in ("created", "queued", "running") and row.updated_at < now - timedelta(
            hours=24
        ):
            item.attention = "stale"
        if pub and pub.status in ("failed", "checks_failed", "reconciliation_required"):
            item.attention = "reconciliation"
        if pub:
            item.outcome = (
                "verified_publication"
                if row.status == "completed" and pub.status == "verified" and pub.verified_at
                else "unconfirmed_publication"
            )
        elif item.workflow_key in (
            "content.publish",
            "seo.apply_site_change",
            "gbp.publish_change",
            "gbp.publish_post",
            "gbp.upload_media",
            "reviews.publish_response",
            "leads.send_communication",
        ):
            item.outcome = "unconfirmed_publication"
        elif (
            row.status == "completed"
            and row.output_reference
            and (not job or job.status == "completed")
            and (not agent or agent.status == "completed")
        ):
            # Recorded execution output is not confirmation of a provider/business result.
            item.outcome = "recorded_result"
        result.append(item)
    return result


@router.get("", response_model=AutomationWorkspace)
async def workspace(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[object, policy("workflows.read")],
    location_id: UUID | None = Query(default=None),  # noqa: B008
    offset: int = Query(default=0, ge=0, le=100000),  # noqa: B008
) -> AutomationWorkspace:
    await check_location(session, organization_id, location_id)
    now = datetime.now(UTC)
    base = run_query(organization_id, location_id)
    total = int(await session.scalar(select(func.count()).select_from(base.subquery())) or 0)
    recent = list(
        await session.scalars(
            base.order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
            .offset(offset)
            .limit(50)
        )
    )
    # Attention is independently queried so failures do not disappear behind recent successes.
    attention_ids = (
        select(WorkflowRun.id)
        .where(WorkflowRun.organization_id == organization_id)
        .outerjoin(
            Job, (Job.workflow_run_id == WorkflowRun.id) & (Job.organization_id == organization_id)
        )
        .outerjoin(
            AgentRun,
            (AgentRun.workflow_run_id == WorkflowRun.id)
            & (AgentRun.organization_id == organization_id),
        )
        .outerjoin(
            ContentPublication,
            (ContentPublication.workflow_run_id == WorkflowRun.id)
            & (ContentPublication.organization_id == organization_id),
        )
        .where(
            or_(
                WorkflowRun.status.in_(ATTENTION),
                (WorkflowRun.status.in_(("created", "queued", "running")))
                & (WorkflowRun.updated_at < now - timedelta(hours=24)),
                Job.status.in_(("failed", "dead_lettered", "retry_scheduled")),
                AgentRun.status.in_(("failed", "waiting_approval", "capability_unavailable")),
                ContentPublication.status.in_(
                    ("failed", "checks_failed", "reconciliation_required")
                ),
            )
        )
    )
    exceptions = list(
        await session.scalars(
            base.where(WorkflowRun.id.in_(attention_ids))
            .order_by(WorkflowRun.updated_at.desc(), WorkflowRun.id.desc())
            .limit(50)
        )
    )
    completed = list(
        await session.scalars(
            base.where(WorkflowRun.status == "completed")
            .order_by(WorkflowRun.completed_at.desc(), WorkflowRun.id.desc())
            .limit(10)
        )
    )
    schedules_read = await allowed(session, principal, organization_id, request, "schedules.read")
    schedules_manage = schedules_read and await allowed(
        session, principal, organization_id, request, "schedules.manage"
    )
    schedules = []
    if schedules_read:
        for data in await service.list_schedules(session, organization_id):
            item = AutomationSchedule.model_validate(data)
            if location_id and item.location_id != location_id:
                continue
            item.can_manage = schedules_manage
            item.overdue = (
                item.status == "active"
                and item.next_run_at is not None
                and item.next_run_at < now - timedelta(minutes=5)
            )
            schedules.append(item)
    definitions = []
    for data in await service.list_workflow_types(session):
        definition = AutomationDefinition.model_validate(data)
        if definition.key in WORKFLOW_SKILLS and location_id:
            decision = await AgentAccessService().decision(
                session,
                organization_id=organization_id,
                location_id=location_id,
                product_key=SKILLS[WORKFLOW_SKILLS[definition.key]].product_key,
            )
            definition.agent_eligible = decision.eligible
            definition.eligibility_reason = decision.reason_code
        definitions.append(definition)
    locations = list(
        await session.scalars(
            select(Location)
            .where(Location.organization_id == organization_id)
            .order_by(Location.name, Location.id)
        )
    )
    outcomes = await project_runs(session, organization_id, completed, now)
    return AutomationWorkspace(
        organization_id=organization_id,
        location_id=location_id,
        observed_at=now,
        locations=[AutomationLocation.model_validate(location) for location in locations],
        can_manage_schedules=schedules_manage,
        can_execute=await allowed(
            session, principal, organization_id, request, "workflows.execute"
        ),
        schedules_state="available" if schedules_read else "unavailable_permission",
        definitions=definitions,
        schedules=schedules,
        runs=await project_runs(session, organization_id, recent, now),
        attention=[
            r
            for r in await project_runs(session, organization_id, exceptions, now)
            if r.attention is not None
        ],
        outcomes=[
            r
            for r in outcomes
            if r.outcome in ("recorded_result", "verified_publication") and r.attention is None
        ],
        total_runs=total,
        next_offset=offset + 50 if offset + 50 < total else None,
    )


@router.get("/runs/{run_id}", response_model=AutomationDetail)
async def detail(
    request: Request,
    organization_id: UUID,
    run_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[object, policy("workflows.read")],
) -> AutomationDetail:
    row = await session.scalar(run_query(organization_id, None).where(WorkflowRun.id == run_id))
    if not row:
        raise HTTPException(404, "Workflow run not found")
    run = (await project_runs(session, organization_id, [row], datetime.now(UTC)))[0]
    jobs = list(
        await session.scalars(
            select(Job)
            .where(Job.organization_id == organization_id, Job.workflow_run_id == run_id)
            .order_by(Job.created_at.desc(), Job.id.desc())
            .limit(50)
        )
    )
    attempts = list(
        await session.scalars(
            select(JobAttempt)
            .where(
                JobAttempt.organization_id == organization_id,
                JobAttempt.job_id.in_([j.id for j in jobs]),
            )
            .order_by(JobAttempt.started_at.desc(), JobAttempt.id.desc())
            .limit(100)
        )
    )
    audit_allowed = await allowed(session, principal, organization_id, request, "audit.read")
    history = (
        list(
            await session.scalars(
                select(AuditEvent)
                .where(
                    AuditEvent.organization_id == organization_id,
                    or_(
                        AuditEvent.workflow_execution_id == run_id,
                        (AuditEvent.resource_type == "workflow_run")
                        & (AuditEvent.resource_id == run_id),
                    ),
                )
                .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
                .limit(50)
            )
        )
        if audit_allowed
        else []
    )
    agent = await session.scalar(
        select(AgentRun).where(
            AgentRun.organization_id == organization_id, AgentRun.workflow_run_id == run_id
        )
    )
    manage = agent is not None and await allowed(
        session, principal, organization_id, request, "workflows.manage"
    )
    features = agent.capability_snapshot.get("features", {}) if agent else {}
    features = features if isinstance(features, dict) else {}
    active = bool(manage and agent and agent.hermes_run_id)
    return AutomationDetail(
        organization_id=organization_id,
        run=run,
        idempotency_key=row.idempotency_key,
        jobs=[AutomationJob.model_validate(j) for j in jobs],
        attempts=[AutomationAttempt.model_validate(a) for a in attempts],
        history=[AutomationAudit.model_validate(a) for a in history],
        history_state="bounded_partial" if audit_allowed else "unavailable_permission",
        can_stop=bool(
            active
            and agent
            and agent.status in ("running", "waiting_approval")
            and features.get("run_stop")
        ),
        can_steer=bool(
            active and agent and agent.status == "running" and features.get("run_steer")
        ),
        can_respond_approval=bool(
            active
            and agent
            and agent.status == "waiting_approval"
            and agent.current_approval
            and features.get("run_approval_response")
        ),
        approval_request=json.dumps(agent.current_approval, sort_keys=True)
        if active and agent and agent.current_approval
        else None,
    )
