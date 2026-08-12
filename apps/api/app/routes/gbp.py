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
from apps.api.app.products.gbp.models import GBPLocation, GBPProfileSnapshot, GBPPublication
from apps.api.app.products.gbp.operations_errors import GBPLocationNotFoundError
from apps.api.app.products.gbp.service import GBPService, profile_health

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/locations/{location_id}/gbp",
    tags=["gbp"],
    dependencies=[Depends(get_authenticated_principal)],
)
organization_router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/gbp",
    tags=["gbp"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = GBPService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


def organization_policy(key: str) -> Any:
    return Depends(require_authorization(key, ScopeType.ORGANIZATION, AssuranceLevel.AAL1))


def policy(key: str, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            key, ScopeType.LOCATION, AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1
        )
    )


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


async def require_gbp_location_scope(
    session: AsyncSession,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
) -> None:
    scoped_id = await session.scalar(
        select(GBPLocation.id).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.location_id == location_id,
            GBPLocation.id == gbp_location_id,
        )
    )
    if scoped_id is None:
        raise GBPLocationNotFoundError


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
        session,
        organization_id,
        gbp_location_id,
        command,
        principal.platform_user_id,
        correlation_id=request_correlation_id(request),
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
        .join(
            GBPLocation,
            (GBPLocation.organization_id == GBPProfileSnapshot.organization_id)
            & (GBPLocation.id == GBPProfileSnapshot.gbp_location_id),
        )
        .where(
            GBPProfileSnapshot.organization_id == organization_id,
            GBPProfileSnapshot.gbp_location_id == gbp_location_id,
            GBPLocation.location_id == location_id,
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
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.propose")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    item = await service.propose(
        session,
        organization_id,
        location_id,
        gbp_location_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
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
    current = await service.get_revision(session, organization_id, revision_id)
    if current.location_id != location_id:
        raise GBPLocationNotFoundError
    item = await service.decide(
        session,
        organization_id,
        revision_id,
        principal.platform_user_id,
        command.decision == "approve",
        correlation_id=request_correlation_id(request),
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
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.publish", True)],
) -> dict[str, object]:
    item = await service.reserve_publication(
        session,
        organization_id,
        location_id,
        revision_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {"publication_id": str(item.id), "status": item.status},
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.get("/changes/{revision_id}", dependencies=[Depends(no_store)])
async def get_change(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    revision_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("gbp.read")],
) -> dict[str, object]:
    item = await service.get_revision(session, organization_id, revision_id)
    if item.location_id != location_id:
        raise LookupError("GBP change revision not found")
    return {
        "data": {
            "id": str(item.id),
            "status": item.status,
            "risk_level": item.risk_level,
            "diff": item.diff_document,
            "approved_at": item.approved_at,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.get("/changes/{revision_id}/audit", dependencies=[Depends(no_store)])
async def change_audit(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    revision_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("audit.read")],
) -> dict[str, object]:
    item = await service.get_revision(session, organization_id, revision_id)
    if item.location_id != location_id:
        raise LookupError("GBP change revision not found")
    history = await service.resource_history(
        session,
        organization_id,
        resource_type="gbp_profile_change_revision",
        resource_id=item.id,
    )
    return {"data": history, "meta": {"correlation_id": request_correlation_id(request)}}


@router.get("/publications", dependencies=[Depends(no_store)])
async def list_publications(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("gbp.read")],
) -> dict[str, object]:
    items = await service.list_publications(session, organization_id, location_id)
    return {
        "data": [
            {
                "id": str(item.id),
                "status": item.status,
                "dispatched_at": item.dispatched_at,
                "verified_at": item.verified_at,
                "safe_error_code": item.safe_error_code,
                "change_revision_id": str(item.change_revision_id),
            }
            for item in items
        ],
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.get("/publications/{publication_id}/audit", dependencies=[Depends(no_store)])
async def publication_audit(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    publication_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("audit.read")],
) -> dict[str, object]:
    item = await session.scalar(
        select(GBPPublication).where(
            GBPPublication.organization_id == organization_id,
            GBPPublication.location_id == location_id,
            GBPPublication.id == publication_id,
        )
    )
    if not item:
        raise LookupError("GBP publication not found")
    history = await service.resource_history(
        session, organization_id, resource_type="gbp_publication", resource_id=item.id
    )
    return {"data": history, "meta": {"correlation_id": request_correlation_id(request)}}


@router.get("/locations/{gbp_location_id}/audit", dependencies=[Depends(no_store)])
async def location_audit(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("audit.read")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    history = await service.resource_history(
        session, organization_id, resource_type="gbp_location", resource_id=gbp_location_id
    )
    return {"data": history, "meta": {"correlation_id": request_correlation_id(request)}}


@organization_router.get("/accounts", dependencies=[Depends(no_store)])
async def list_accounts(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, organization_policy("gbp.connect")],
) -> dict[str, object]:
    # Provider account discovery requires the privileged gbp.connect
    # permission, not ordinary gbp.read.  This keeps broad provider
    # resource enumeration inside the Integrations control plane.
    items = await service.list_accounts(session, organization_id)
    return {
        "data": [
            {
                "id": str(item.id),
                "display_name": item.display_name,
                "account_type": item.account_type,
                "status": item.status,
                "discovered_at": item.discovered_at,
            }
            for item in items
        ],
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@organization_router.get("/locations", dependencies=[Depends(no_store)])
async def list_org_locations(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, organization_policy("gbp.read")],
) -> dict[str, object]:
    # The gbp.read permission description says "Read mapped GBP profile state".
    # A caller with only gbp.read must not be able to enumerate unmapped
    # provider-discovered resources.  Only confirmed mappings are returned;
    # broad discovery is gated behind the gbp.connect permission used by the
    # Integrations control plane (POST /integrations/google/discover).
    items = await service.list_locations(session, organization_id, mapping_status="confirmed")
    return {
        "data": [
            {
                "id": str(item.id),
                "business_name": item.business_name,
                "mapping_status": item.mapping_status,
                "location_id": str(item.location_id) if item.location_id else None,
                "write_enabled": item.write_enabled,
                "last_discovered_at": item.last_discovered_at,
                "last_synced_at": item.last_synced_at,
            }
            for item in items
        ],
        "meta": {"correlation_id": request_correlation_id(request)},
    }
