"""Authenticated operator controls for governed Hermes agent runs."""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.administration.service import AdministrationService
from apps.api.app.agents.hermes_client import HermesRuntimeError
from apps.api.app.agents.service import AgentRuntimeService, build_hermes_runs_client
from apps.api.app.agents.skills import SKILLS, WORKFLOW_SKILLS
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.config import Settings
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.execution.service import ExecutionService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/agents",
    tags=["agents"],
    dependencies=[Depends(get_authenticated_principal)],
)
Session = Annotated[AsyncSession, Depends(get_database_session)]
runtime = AgentRuntimeService()
execution = ExecutionService()
administration = AdministrationService()
NOT_EFFECTIVE_ENTITLEMENT_STATUSES = frozenset({"not_enabled", "archived", "suspended"})


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def policy(key: str) -> Any:
    return Depends(require_authorization(key, ScopeType.ORGANIZATION, AssuranceLevel.AAL1))


class AgentRunStart(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    location_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=128)
    objective: str | None = Field(default=None, min_length=1, max_length=4_000)
    context_reference: str | None = Field(default=None, min_length=1, max_length=500)


class SteerCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    text: str = Field(min_length=1, max_length=4_000)


class ApprovalCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    choice: Literal["once", "deny"]


class SessionResetCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    location_id: UUID
    skill_key: str = Field(min_length=3, max_length=128)


async def require_product_entitlement(
    session: AsyncSession,
    organization_id: UUID,
    location_id: UUID,
    product_key: str,
) -> None:
    product = await administration.catalog.get_product_by_key(session, product_key)
    entitlement = (
        await administration.entitlements.get_by_product(session, organization_id, product.id)
        if product is not None
        else None
    )
    if entitlement is None or entitlement.status in NOT_EFFECTIVE_ENTITLEMENT_STATUSES:
        raise HTTPException(status_code=409, detail="Product entitlement is not effective")
    selected_locations = await administration.entitlements.locations(
        session, organization_id, entitlement.id
    )
    if selected_locations and location_id not in {item.location_id for item in selected_locations}:
        raise HTTPException(status_code=403, detail="Location is outside the product entitlement")


@router.get("/capabilities", dependencies=[Depends(no_store)])
async def agent_capabilities(
    request: Request,
    organization_id: UUID,
    _: Annotated[AuthorizationDecision, policy("workflows.read")],
) -> dict[str, object]:
    del organization_id
    settings: Settings = request.app.state.settings
    if settings.ai_provider != "hermes":
        return {
            "data": {"available": False, "reason_code": "HERMES_AGENT_NOT_ENABLED", "features": {}},
            "meta": {"correlation_id": request_correlation_id(request)},
        }
    try:
        capabilities = await build_hermes_runs_client(settings).capabilities()
        missing = capabilities.missing_required
        data = {
            "available": not missing,
            "reason_code": "HERMES_CAPABILITY_UNAVAILABLE" if missing else None,
            "runtime_version": capabilities.runtime_version,
            "runtime_release": settings.hermes_runtime_release,
            "model": settings.ai_hermes_model,
            "api_model_alias": capabilities.model,
            "features": capabilities.features,
            "runtime": capabilities.runtime,
            "sanctioned_tools": list(capabilities.sanctioned_tools),
            "missing_required": list(missing),
        }
    except HermesRuntimeError as exc:
        data = {"available": False, "reason_code": exc.safe_code, "features": {}}
    return {"data": data, "meta": {"correlation_id": request_correlation_id(request)}}


@router.post(
    "/{workflow_key}/runs", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)]
)
async def start_agent_run(
    request: Request,
    organization_id: UUID,
    workflow_key: str,
    command: AgentRunStart,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("workflows.execute")],
) -> dict[str, object]:
    if workflow_key not in WORKFLOW_SKILLS:
        raise HTTPException(status_code=404, detail="Agent workflow not found")
    await require_product_entitlement(
        session,
        organization_id,
        command.location_id,
        SKILLS[WORKFLOW_SKILLS[workflow_key]].product_key,
    )
    run = await execution.start_named(
        session,
        organization_id,
        workflow_key,
        command.idempotency_key,
        location_id=command.location_id,
        input_document={
            key: value
            for key, value in {
                "objective": command.objective,
                "context_reference": command.context_reference,
            }.items()
            if value is not None
        },
        correlation_id=request_correlation_id(request),
        actor_id=principal.platform_user_id,
        enqueue_job=True,
    )
    return {
        "data": {
            "workflow_run_id": str(run.id),
            "status": run.status,
            "skill_key": WORKFLOW_SKILLS[workflow_key],
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.get("/runs", dependencies=[Depends(no_store)])
async def list_agent_runs(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("workflows.read")],
    location_id: UUID | None = Query(default=None),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=100),  # noqa: B008
) -> dict[str, object]:
    rows = await runtime.list_runs(session, organization_id, location_id=location_id, limit=limit)
    return {
        "data": rows,
        "meta": {"correlation_id": request_correlation_id(request), "count": len(rows)},
    }


@router.get("/runs/{agent_run_id}", dependencies=[Depends(no_store)])
async def get_agent_run(
    request: Request,
    organization_id: UUID,
    agent_run_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("workflows.read")],
) -> dict[str, object]:
    detail = await runtime.detail(session, organization_id, agent_run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return {"data": detail, "meta": {"correlation_id": request_correlation_id(request)}}


async def _control(
    request: Request,
    organization_id: UUID,
    agent_run_id: UUID,
    session: AsyncSession,
    principal: Authenticated,
    action: str,
    *,
    text: str | None = None,
    choice: str | None = None,
) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    try:
        run = await runtime.control(
            session,
            settings,
            organization_id,
            agent_run_id,
            action,
            text=text,
            choice=choice,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except (ValueError, HermesRuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return {
        "data": {"id": str(run.id), "status": run.status},
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.post("/runs/{agent_run_id}/stop", dependencies=[Depends(no_store)])
async def stop_agent_run(
    request: Request,
    organization_id: UUID,
    agent_run_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("workflows.manage")],
) -> dict[str, object]:
    return await _control(request, organization_id, agent_run_id, session, principal, "stop")


@router.post("/runs/{agent_run_id}/steer", dependencies=[Depends(no_store)])
async def steer_agent_run(
    request: Request,
    organization_id: UUID,
    agent_run_id: UUID,
    command: SteerCommand,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("workflows.manage")],
) -> dict[str, object]:
    return await _control(
        request, organization_id, agent_run_id, session, principal, "steer", text=command.text
    )


@router.post("/runs/{agent_run_id}/approval", dependencies=[Depends(no_store)])
async def approve_agent_run(
    request: Request,
    organization_id: UUID,
    agent_run_id: UUID,
    command: ApprovalCommand,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("workflows.manage")],
) -> dict[str, object]:
    return await _control(
        request,
        organization_id,
        agent_run_id,
        session,
        principal,
        "approval",
        choice=command.choice,
    )


@router.post("/sessions/reset", dependencies=[Depends(no_store)])
async def reset_agent_session(
    request: Request,
    organization_id: UUID,
    command: SessionResetCommand,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("workflows.manage")],
) -> dict[str, object]:
    if command.skill_key not in SKILLS:
        raise HTTPException(status_code=404, detail="Agent skill not found")
    await require_product_entitlement(
        session,
        organization_id,
        command.location_id,
        SKILLS[command.skill_key].product_key,
    )
    settings: Settings = request.app.state.settings
    try:
        row = await runtime.reset_session(
            session,
            settings,
            organization_id,
            command.location_id,
            command.skill_key,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except (ValueError, HermesRuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {
        "data": {
            "skill_key": row.skill_key,
            "location_id": str(row.location_id) if row.location_id else None,
            "version": row.version,
            "expires_at": row.expires_at.isoformat(),
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }
