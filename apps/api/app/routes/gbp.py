"""Authenticated and authorized GBP vertical-slice routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.products.gbp.contracts import (
    Decision,
    MappingConfirm,
    ProfileChangeCreate,
    PublishRequest,
)
from apps.api.app.products.gbp.models import GBPProfileSnapshot
from apps.api.app.products.gbp.service import GBPService, profile_health

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/locations/{location_id}/gbp",
    tags=["gbp"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = GBPService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


def policy(key: str, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            key, ScopeType.LOCATION, AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1
        )
    )


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


@router.post("/locations/{gbp_location_id}/confirm", dependencies=[Depends(no_store)])
async def confirm_mapping(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    command: MappingConfirm,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.connect", True)],
) -> dict[str, object]:
    if command.location_id != location_id:
        raise ValueError("location scope mismatch")
    item = await service.confirm_mapping(
        session, organization_id, gbp_location_id, command, principal.platform_user_id
    )
    return {
        "data": {
            "id": str(item.id),
            "mapping_status": item.mapping_status,
            "write_enabled": item.write_enabled,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.get("/locations/{gbp_location_id}/profile", dependencies=[Depends(no_store)])
async def profile(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("gbp.read")],
) -> dict[str, object]:
    item = await session.scalar(
        select(GBPProfileSnapshot)
        .where(
            GBPProfileSnapshot.organization_id == organization_id,
            GBPProfileSnapshot.gbp_location_id == gbp_location_id,
        )
        .order_by(GBPProfileSnapshot.observed_at.desc())
        .limit(1)
    )
    if not item:
        raise LookupError("GBP profile not found")
    return {
        "data": {
            "profile": item.normalized_profile,
            "observed_at": item.observed_at,
            "health": profile_health(item.normalized_profile, item.observed_at),
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.post(
    "/locations/{gbp_location_id}/changes",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def propose(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    command: ProfileChangeCreate,
    session: Session,
    _principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.propose")],
) -> dict[str, object]:
    item = await service.propose(session, organization_id, location_id, gbp_location_id, command)
    return {
        "data": {"id": str(item.id), "status": item.status, "diff": item.diff_document},
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.post("/changes/{revision_id}/decision", dependencies=[Depends(no_store)])
async def decide(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    revision_id: UUID,
    command: Decision,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.approve", True)],
) -> dict[str, object]:
    item = await service.decide(
        session,
        organization_id,
        revision_id,
        principal.platform_user_id,
        command.decision == "approve",
    )
    return {
        "data": {"id": str(item.id), "status": item.status},
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.post(
    "/changes/{revision_id}/publish",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(no_store)],
)
async def publish(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    revision_id: UUID,
    command: PublishRequest,
    session: Session,
    _principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.publish", True)],
) -> dict[str, object]:
    item = await service.reserve_publication(
        session, organization_id, location_id, revision_id, command
    )
    return {
        "data": {"publication_id": str(item.id), "status": item.status},
        "meta": {"correlation_id": request_correlation_id(request)},
    }
