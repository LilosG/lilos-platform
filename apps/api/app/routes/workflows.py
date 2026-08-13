"""Shared authenticated route for starting persisted, governed workflow runs.

This is the only supported way for a client to obtain a ``workflow_run_id``
for a product action (content publication, SEO crawl/analysis, GBP change
publication, GBP post publication, ...). It never accepts a caller-supplied
workflow_run_id as authoritative — it always creates or idempotently
resolves a real, tenant-scoped ``WorkflowRun`` row and returns its id.

The Automation & Agents product surface also uses this module for:
- Catalog listing (known workflow types and their definition/version state)
- Run history queries (paginated, filterable by workflow key/status/location)
- Schedule lifecycle (create, list, update status/cron)
"""

from datetime import UTC
from datetime import datetime as dt
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.execution.contracts import ScheduleCreate, ScheduleUpdate
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.execution.service import ExecutionService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/workflows",
    tags=["workflows"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = ExecutionService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def policy(key: str) -> Any:
    return Depends(require_authorization(key, ScopeType.ORGANIZATION, AssuranceLevel.AAL1))


def run_row(run: WorkflowRun) -> dict[str, object]:
    return {
        "workflow_run_id": str(run.id),
        "status": run.status,
        "product_key": run.product_key,
    }


def _parse_dt(value: str) -> dt:
    """Parse an ISO datetime string, defaulting to UTC if timezone-naive."""
    parsed = dt.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


# ---------------------------------------------------------------------------
# Request contracts
# ---------------------------------------------------------------------------


class WorkflowRunStart(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    location_id: UUID | None = None
    idempotency_key: str = Field(min_length=8, max_length=128)
    input_document: dict[str, Any] = Field(default_factory=dict)


class ScheduleCreateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    workflow_key: str = Field(min_length=3, max_length=128)
    key: str = Field(min_length=3, max_length=128)
    cron_expression: str = Field(min_length=5, max_length=100)
    timezone: str = Field(min_length=1, max_length=64)
    next_run_at: str = Field(min_length=1)
    location_id: UUID | None = None


class ScheduleUpdateRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    status: Literal["active", "paused", "cancelled"] | None = Field(default=None)
    cron_expression: str | None = Field(default=None, min_length=5, max_length=100)
    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    next_run_at: str | None = Field(default=None, min_length=1)


# ---------------------------------------------------------------------------
# Catalog — workflow type listing
# ---------------------------------------------------------------------------


@router.get("", dependencies=[Depends(no_store)])
async def list_workflow_types(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("workflows.read")],
) -> dict[str, object]:
    """Return the known workflow catalog with definition/version state."""
    items = await service.list_workflow_types(session)
    return {
        "data": items,
        "meta": {"correlation_id": request_correlation_id(request), "count": len(items)},
    }


# ---------------------------------------------------------------------------
# Run history (MUST be registered before `/{workflow_key}` routes so
# ``GET /runs`` and ``GET /runs/{run_id}`` are not captured by the
# ``/{workflow_key}`` path parameter.)
# ---------------------------------------------------------------------------


@router.get("/runs", dependencies=[Depends(no_store)])
async def list_workflow_runs(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("workflows.read")],
    workflow_key: str | None = Query(default=None),  # noqa: B008
    location_id: UUID | None = Query(default=None),  # noqa: B008
    status_filter: str | None = Query(default=None, alias="status"),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=100),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
) -> dict[str, object]:
    """Return paginated workflow runs for the organization."""
    rows, total = await service.list_runs(
        session,
        organization_id,
        workflow_key=workflow_key,
        location_id=location_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return {
        "data": rows,
        "meta": {
            "correlation_id": request_correlation_id(request),
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }


@router.get("/runs/{run_id}", dependencies=[Depends(no_store)])
async def get_workflow_run(
    request: Request,
    organization_id: UUID,
    run_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("workflows.read")],
) -> dict[str, object]:
    """Return a single workflow run with full job/attempt detail."""
    run = await service.get_run(session, organization_id, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return {"data": run, "meta": {"correlation_id": request_correlation_id(request)}}


# ---------------------------------------------------------------------------
# Schedules (MUST be registered before `/{workflow_key}` routes)
# ---------------------------------------------------------------------------


@router.get("/schedules", dependencies=[Depends(no_store)])
async def list_workflow_schedules(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("schedules.read")],
) -> dict[str, object]:
    """Return all schedules for the organization."""
    rows = await service.list_schedules(session, organization_id)
    return {
        "data": rows,
        "meta": {"correlation_id": request_correlation_id(request), "count": len(rows)},
    }


@router.post(
    "/schedules",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def create_workflow_schedule(
    request: Request,
    organization_id: UUID,
    command: ScheduleCreateRequest,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("schedules.manage")],
) -> dict[str, object]:
    """Create a recurring schedule for a known workflow type."""
    schedule_cmd = ScheduleCreate(
        workflow_key=command.workflow_key,
        key=command.key,
        cron_expression=command.cron_expression,
        timezone=command.timezone,
        next_run_at=_parse_dt(command.next_run_at),
        location_id=command.location_id,
    )
    schedule = await service.create_schedule(
        session,
        organization_id,
        schedule_cmd,
        correlation_id=request_correlation_id(request),
        actor_id=principal.platform_user_id,
    )
    return {
        "data": {
            "id": str(schedule.id),
            "key": schedule.key,
            "status": schedule.status,
            "cron_expression": schedule.cron_expression,
            "timezone": schedule.timezone,
            "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
            "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.patch("/schedules/{schedule_id}", dependencies=[Depends(no_store)])
async def update_workflow_schedule(
    request: Request,
    organization_id: UUID,
    schedule_id: UUID,
    command: ScheduleUpdateRequest,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("schedules.manage")],
) -> dict[str, object]:
    """Update schedule status, cron expression, or next run time."""
    update_cmd = ScheduleUpdate(
        status=command.status,
        cron_expression=command.cron_expression,
        timezone=command.timezone,
        next_run_at=_parse_dt(command.next_run_at) if command.next_run_at else None,
    )
    schedule = await service.update_schedule(
        session,
        organization_id,
        schedule_id,
        update_cmd,
        correlation_id=request_correlation_id(request),
        actor_id=principal.platform_user_id,
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {
        "data": {
            "id": str(schedule.id),
            "key": schedule.key,
            "status": schedule.status,
            "cron_expression": schedule.cron_expression,
            "timezone": schedule.timezone,
            "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
            "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


# ---------------------------------------------------------------------------
# Workflow-type detail (after concrete paths to avoid route shadowing)
# ---------------------------------------------------------------------------


@router.get("/{workflow_key}", dependencies=[Depends(no_store)])
async def get_workflow_type(
    request: Request,
    organization_id: UUID,
    workflow_key: str,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("workflows.read")],
) -> dict[str, object]:
    """Return details for a single workflow type."""
    items = await service.list_workflow_types(session)
    item = next((i for i in items if i["key"] == workflow_key), None)
    if not item:
        raise HTTPException(status_code=404, detail="Workflow type not found")
    return {"data": item, "meta": {"correlation_id": request_correlation_id(request)}}


# ---------------------------------------------------------------------------
# Run start (existing) — must be after concrete `/runs` paths
# ---------------------------------------------------------------------------


@router.post(
    "/{workflow_key}/runs", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)]
)
async def start_workflow_run(
    request: Request,
    organization_id: UUID,
    workflow_key: str,
    command: WorkflowRunStart,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("workflows.execute")],
) -> dict[str, object]:
    """Start (or idempotently resolve) a workflow run."""
    run = await service.start_named(
        session,
        organization_id,
        workflow_key,
        command.idempotency_key,
        location_id=command.location_id,
        input_document=command.input_document,
        correlation_id=request_correlation_id(request),
        actor_id=principal.platform_user_id,
        enqueue_job=False,
    )
    return {"data": run_row(run), "meta": {"correlation_id": request_correlation_id(request)}}


@router.get("/{workflow_key}/runs", dependencies=[Depends(no_store)])
async def list_workflow_key_runs(
    request: Request,
    organization_id: UUID,
    workflow_key: str,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("workflows.read")],
    location_id: UUID | None = Query(default=None),  # noqa: B008
    status_filter: str | None = Query(default=None, alias="status"),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=100),  # noqa: B008
    offset: int = Query(default=0, ge=0),  # noqa: B008
) -> dict[str, object]:
    """Return paginated workflow runs for a specific workflow type."""
    rows, total = await service.list_runs(
        session,
        organization_id,
        workflow_key=workflow_key,
        location_id=location_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return {
        "data": rows,
        "meta": {
            "correlation_id": request_correlation_id(request),
            "total": total,
            "limit": limit,
            "offset": offset,
        },
    }
