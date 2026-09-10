"""Protected API for the cross-product Growth Queue."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.growth.contracts import GrowthActionOutcomeRecord, GrowthInitiativeDecision
from apps.api.app.growth.measurement import GrowthMeasurementService
from apps.api.app.growth.service import GrowthService, GrowthStateError

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/growth",
    tags=["growth"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = GrowthService()
measurement = GrowthMeasurementService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def policy(key: str, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            key,
            ScopeType.ORGANIZATION,
            AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1,
        )
    )


def meta(request: Request) -> dict[str, object]:
    return {"correlation_id": request_correlation_id(request)}


def summary_row(item: object) -> dict[str, object]:
    initiative = item
    return {
        "id": str(initiative.id),
        "location_id": str(initiative.location_id) if initiative.location_id else None,
        "objective": initiative.objective,
        "priority_score": initiative.priority_score,
        "confidence": float(initiative.confidence),
        "status": initiative.status,
        "created_at": initiative.created_at.isoformat(),
        "approved_at": initiative.approved_at.isoformat() if initiative.approved_at else None,
        "completed_at": initiative.completed_at.isoformat() if initiative.completed_at else None,
    }


@router.get("", dependencies=[Depends(no_store)])
async def list_growth_queue(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("workflows.read")],
    location_id: UUID | None = Query(default=None),  # noqa: B008
    status_filter: str | None = Query(default=None),  # noqa: B008
    limit: int = Query(default=50, ge=1, le=100),  # noqa: B008
) -> dict[str, object]:
    items = await service.list(
        session,
        organization_id,
        location_id=location_id,
        status=status_filter,
        limit=limit,
    )
    return {
        "data": [summary_row(item) for item in items],
        "meta": {**meta(request), "count": len(items)},
    }


@router.get("/{initiative_id}", dependencies=[Depends(no_store)])
async def get_growth_initiative(
    request: Request,
    organization_id: UUID,
    initiative_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("workflows.read")],
) -> dict[str, object]:
    detail = await service.detail(session, organization_id, initiative_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Growth initiative not found")
    outcomes = await measurement.list_for_initiative(session, organization_id, initiative_id)
    detail["outcomes"] = [
        {
            "id": str(item.id),
            "action_id": str(item.action_id),
            "classification": item.classification,
            "baseline": item.baseline,
            "measurement": item.measurement,
            "limitations": item.limitations,
            "observed_at": item.observed_at.isoformat(),
        }
        for item in outcomes
    ]
    return {"data": detail, "meta": meta(request)}


@router.post("/{initiative_id}/decision", dependencies=[Depends(no_store)])
async def decide_growth_initiative(
    request: Request,
    organization_id: UUID,
    initiative_id: UUID,
    command: GrowthInitiativeDecision,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("workflows.execute")],
) -> dict[str, object]:
    try:
        await service.decide(
            session,
            organization_id,
            initiative_id,
            approve=command.approve,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except GrowthStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    detail = await service.detail(session, organization_id, initiative_id)
    return {"data": detail, "meta": meta(request)}


@router.post("/{initiative_id}/dispatch", dependencies=[Depends(no_store)])
async def dispatch_growth_initiative(
    request: Request,
    organization_id: UUID,
    initiative_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("workflows.execute")],
) -> dict[str, object]:
    try:
        dispatched = await service.dispatch_ready(
            session,
            organization_id,
            initiative_id,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except GrowthStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {
        "data": {
            "dispatched_action_ids": [str(action.id) for action in dispatched],
            "initiative": await service.detail(session, organization_id, initiative_id),
        },
        "meta": meta(request),
    }


@router.post("/{initiative_id}/reconcile", dependencies=[Depends(no_store)])
async def reconcile_growth_initiative(
    request: Request,
    organization_id: UUID,
    initiative_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("workflows.execute")],
) -> dict[str, object]:
    try:
        await service.reconcile(session, organization_id, initiative_id)
    except GrowthStateError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    return {
        "data": await service.detail(session, organization_id, initiative_id),
        "meta": meta(request),
    }


@router.post("/actions/{action_id}/outcomes", dependencies=[Depends(no_store)])
async def record_growth_outcome(
    request: Request,
    organization_id: UUID,
    action_id: UUID,
    command: GrowthActionOutcomeRecord,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("insights.manage")],
) -> dict[str, object]:
    try:
        outcome = await measurement.record(
            session,
            organization_id,
            action_id,
            command,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except GrowthStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return {
        "data": {
            "id": str(outcome.id),
            "action_id": str(outcome.action_id),
            "classification": outcome.classification,
            "baseline": outcome.baseline,
            "measurement": outcome.measurement,
            "limitations": outcome.limitations,
            "observed_at": outcome.observed_at.isoformat(),
        },
        "meta": meta(request),
    }
