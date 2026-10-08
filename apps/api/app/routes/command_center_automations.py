"""Automations: scheduled workflows across the clients the caller may open.

Reads are set-based projections of ``workflow_schedules`` and the latest ``workflow_runs`` of
the same organization, workflow and location, with no provider I/O. Run now reuses the
canonical operator run path and is allowed only for the read-only sync, ingest and crawl
workflows. Every state, source, cause and recovery action is a code; the console writes the
words.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict

from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.errors import AuthorizationError, NotFoundError, request_correlation_id
from apps.api.app.execution.automations import (
    AutomationReason,
    AutomationRecord,
    AutomationSource,
    AutomationStatus,
    FrequencyKind,
    RecoveryAction,
    RunOutcome,
    RunSnapshot,
    RunStatus,
    attention_of,
    load_automations,
    outcome_of,
    parse_frequency,
    source_of,
)
from apps.api.app.execution.service import ExecutionService
from apps.api.app.organizations.models import Organization
from apps.api.app.routes.command_center_portfolio import (
    Scope,
    permitted_organizations,
    visible_scope,
)
from apps.api.app.routes.command_center_search import allowed
from apps.api.app.routes.seo import Session, no_store

router = APIRouter(
    prefix="/api/v1/command-center/automations",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(no_store)],
)
service = ExecutionService()


class WorkflowTypeCode(StrEnum):
    """Every tenant workflow type that can be scheduled."""

    CONTENT_PUBLISH = "content.publish"
    CONTENT_DRAFT_REVISION = "content.draft_revision"
    CONTENT_COMPOSE = "content.compose"
    SEO_CRAWL_OR_ANALYSIS = "seo.crawl_or_analysis"
    SEO_ANALYZE = "seo.analyze"
    SEO_SYNC_SEARCH_CONSOLE = "seo.sync_search_console"
    INSIGHTS_SYNC_ANALYTICS = "insights.sync_analytics"
    SEO_APPLY_SITE_CHANGE = "seo.apply_site_change"
    GBP_GENERATE_POST = "gbp.generate_post"
    GBP_PUBLISH_CHANGE = "gbp.publish_change"
    GBP_PUBLISH_POST = "gbp.publish_post"
    GBP_UPLOAD_MEDIA = "gbp.upload_media"
    GBP_PUBLISH_SPECIAL_HOURS = "gbp.publish_special_hours"
    REVIEWS_PUBLISH_RESPONSE = "reviews.publish_response"
    LEADS_SEND_COMMUNICATION = "leads.send_communication"
    GBP_SYNC = "gbp.sync"
    GBP_SYNC_PERFORMANCE = "gbp.sync_performance"
    REVIEWS_INGEST = "reviews.ingest"
    AGENT_GBP = "agent.gbp"
    AGENT_SEO = "agent.seo"
    AGENT_CONTENT = "agent.content"
    AGENT_REVIEWS = "agent.reviews"
    AGENT_LEADS = "agent.leads"
    AGENT_INSIGHTS = "agent.insights"
    AGENT_GROWTH = "agent.growth"


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClientRef(DTO):
    id: UUID
    name: str
    slug: str


class Frequency(DTO):
    """A schedule as a typed value; the console formats it in the schedule's timezone."""

    kind: FrequencyKind
    interval: int | None
    hour: int | None
    minute: int | None
    # Cron numbering: 0 is Sunday.
    weekday: int | None
    day_of_month: int | None
    timezone: str


class LatestRun(DTO):
    status: RunStatus
    outcome: RunOutcome
    started_at: datetime | None
    finished_at: datetime | None


class Attention(DTO):
    reason: AutomationReason
    recovery_actions: list[RecoveryAction]
    occurred_at: datetime | None


class AutomationItem(DTO):
    id: UUID
    workflow_type: WorkflowTypeCode
    client: ClientRef
    frequency: Frequency
    status: AutomationStatus
    latest_run: LatestRun | None
    next_run_at: datetime | None
    source: AutomationSource
    attention: Attention | None
    run_now_allowed: bool


class AutomationCounts(DTO):
    total: int
    healthy: int
    needs_attention: int
    running: int
    paused: int
    not_run_yet: int


class AutomationList(DTO):
    generated_at: datetime
    counts: AutomationCounts
    data: list[AutomationItem]


class RunHistoryItem(DTO):
    id: UUID
    status: RunStatus
    outcome: RunOutcome
    reason: AutomationReason | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_seconds: int | None


class AutomationDetail(AutomationItem):
    runs: list[RunHistoryItem]


class RunNowResult(DTO):
    schedule_id: UUID
    run_id: UUID
    run_status: RunStatus
    # True when this key already started a run, so nothing new was queued.
    replayed: bool


def latest_view(run: RunSnapshot) -> LatestRun:
    return LatestRun(
        status=run.status,
        outcome=outcome_of(run),
        started_at=run.started_at,
        finished_at=run.finished_at,
    )


def item_of(record: AutomationRecord, organization: Organization) -> AutomationItem:
    schedule = record.schedule
    frequency = parse_frequency(schedule.cron_expression)
    latest = record.latest
    attention = (
        attention_of(latest)
        if latest and record.status is AutomationStatus.NEEDS_ATTENTION
        else None
    )
    return AutomationItem(
        id=schedule.id,
        workflow_type=WorkflowTypeCode(record.workflow_key),
        client=ClientRef(id=organization.id, name=organization.name, slug=organization.slug),
        frequency=Frequency(
            kind=frequency.kind,
            interval=frequency.interval,
            hour=frequency.hour,
            minute=frequency.minute,
            weekday=frequency.weekday,
            day_of_month=frequency.day_of_month,
            timezone=schedule.timezone,
        ),
        status=record.status,
        latest_run=latest_view(latest) if latest else None,
        next_run_at=schedule.next_run_at if schedule.status == "active" else None,
        source=source_of(record.workflow_key),
        attention=Attention(
            reason=attention.reason,
            recovery_actions=list(attention.actions),
            occurred_at=attention.occurred_at,
        )
        if attention
        else None,
        run_now_allowed=record.run_now_allowed,
    )


def history_of(run: RunSnapshot) -> RunHistoryItem:
    attention = attention_of(run)
    duration = (
        int((run.finished_at - run.started_at).total_seconds())
        if run.started_at and run.finished_at
        else None
    )
    return RunHistoryItem(
        id=run.id,
        status=run.status,
        outcome=outcome_of(run),
        reason=attention.reason if attention else None,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_seconds=max(duration, 0) if duration is not None else None,
    )


async def readable_organizations(
    request: Request, session: Session, principal: Authenticated
) -> tuple[Scope, list[Organization]]:
    """The organizations whose workflows the caller may read; decided on the server."""
    scope = await visible_scope(session, principal)
    permitted = await permitted_organizations(
        session, principal, scope, scope.organizations, str(request_correlation_id(request))
    )
    return scope, [o for o in scope.organizations if o.id in permitted["workflows.read"]]


@router.get("", response_model=AutomationList)
async def list_automations(
    request: Request,
    session: Session,
    principal: Authenticated,
    organization_id: UUID | None = None,
) -> AutomationList:
    """Every scheduled workflow of the clients the caller may open, newest outcome included."""
    scope, organizations = await readable_organizations(request, session, principal)
    if organization_id is not None:
        if all(o.id != organization_id for o in scope.organizations):
            # Same answer for "does not exist" and "not yours": no tenant disclosure.
            raise NotFoundError
        organizations = [o for o in organizations if o.id == organization_id]
    owners = {o.id: o for o in organizations}
    records = await load_automations(session, list(owners))
    items = [item_of(record, owners[record.schedule.organization_id]) for record in records]
    items.sort(key=lambda item: (item.client.name.lower(), item.workflow_type.value))

    def count(wanted: AutomationStatus) -> int:
        return sum(1 for item in items if item.status is wanted)

    return AutomationList(
        generated_at=datetime.now(UTC),
        counts=AutomationCounts(
            total=len(items),
            healthy=count(AutomationStatus.HEALTHY),
            needs_attention=count(AutomationStatus.NEEDS_ATTENTION),
            running=count(AutomationStatus.RUNNING),
            paused=count(AutomationStatus.PAUSED),
            not_run_yet=count(AutomationStatus.NOT_RUN_YET),
        ),
        data=items,
    )


async def find_record(
    request: Request, session: Session, principal: Authenticated, schedule_id: UUID, history: int
) -> tuple[AutomationRecord, Organization]:
    _, organizations = await readable_organizations(request, session, principal)
    owners = {o.id: o for o in organizations}
    records = await load_automations(
        session, list(owners), schedule_id=schedule_id, history=history
    )
    if not records:
        raise NotFoundError
    return records[0], owners[records[0].schedule.organization_id]


@router.get("/{schedule_id}", response_model=AutomationDetail)
async def automation_detail(
    schedule_id: UUID,
    request: Request,
    session: Session,
    principal: Authenticated,
    runs: int = Query(10, ge=1, le=50),
) -> AutomationDetail:
    record, organization = await find_record(request, session, principal, schedule_id, runs)
    return AutomationDetail(
        **item_of(record, organization).model_dump(),
        runs=[history_of(run) for run in record.runs],
    )


@router.post(
    "/{schedule_id}/run",
    response_model=RunNowResult,
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_automation_now(
    schedule_id: UUID,
    request: Request,
    response: Response,
    session: Session,
    principal: Authenticated,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
) -> RunNowResult:
    """Run a read-only scheduled workflow now. Nothing that publishes can be run from here."""
    record, organization = await find_record(request, session, principal, schedule_id, 1)
    if not await allowed(session, principal, organization.id, request, "workflows.execute"):
        raise AuthorizationError
    run, created = await service.run_schedule_now(
        session,
        schedule_id,
        organization.id,
        idempotency_key,
        correlation_id=str(request_correlation_id(request)),
        actor_id=principal.platform_user_id,
    )
    return RunNowResult(
        schedule_id=schedule_id,
        run_id=run.id,
        run_status=RunStatus(run.status),
        replayed=not created,
    )
