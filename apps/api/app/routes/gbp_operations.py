"""Authenticated and authorized GBP operations routes.

Covers categories, special hours, media, posts, capability snapshots,
completeness/conflicts reporting, and suspension case reporting.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.products.gbp.models import GBPLocation
from apps.api.app.products.gbp.operations_contracts import (
    CapabilitySnapshotRecord,
    ChangeSetDecision,
    ChangeSetPropose,
    MediaPropose,
    PostDecision,
    PostPublishRequest,
    PostRevisionCreate,
    SpecialHoursPropose,
    SuspensionCaseReport,
)
from apps.api.app.products.gbp.operations_errors import GBPLocationNotFoundError
from apps.api.app.products.gbp.operations_models import (
    GBPChangeSet,
    GBPMedia,
    GBPPostPublication,
    GBPPostRevision,
    GBPSpecialHours,
    GBPSuspensionCase,
)
from apps.api.app.products.gbp.operations_service import GBPOperationsService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/locations/{location_id}/gbp/operations",
    tags=["gbp"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = GBPOperationsService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


def policy(key: str, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            key, ScopeType.LOCATION, AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1
        )
    )


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def meta(request: Request) -> dict[str, object]:
    return {"correlation_id": request_correlation_id(request)}


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


async def require_child_location_scope(
    session: AsyncSession,
    organization_id: UUID,
    location_id: UUID,
    resource_model: Any,
    resource_id: UUID,
) -> None:
    scoped_id = await session.scalar(
        select(resource_model.id)
        .join(
            GBPLocation,
            and_(
                GBPLocation.organization_id == resource_model.organization_id,
                GBPLocation.id == resource_model.gbp_location_id,
            ),
        )
        .where(
            resource_model.organization_id == organization_id,
            resource_model.id == resource_id,
            GBPLocation.location_id == location_id,
        )
    )
    if scoped_id is None:
        raise GBPLocationNotFoundError


def change_set_row(item: GBPChangeSet) -> dict[str, object]:
    return {
        "id": str(item.id),
        "revision": item.revision,
        "field_changes": item.field_changes,
        "evidence": item.evidence,
        "risk": item.risk,
        "status": item.status,
    }


def special_hours_row(item: GBPSpecialHours) -> dict[str, object]:
    return {
        "id": str(item.id),
        "service_date": item.service_date,
        "revision": item.revision,
        "periods": item.periods,
        "source": item.source,
        "status": item.status,
    }


def media_row(item: GBPMedia) -> dict[str, object]:
    return {
        "id": str(item.id),
        "media_type": item.media_type,
        "source_reference": item.source_reference,
        "rights_authority": item.rights_authority,
        "status": item.status,
        "verified_at": item.verified_at,
    }


def post_revision_row(item: GBPPostRevision) -> dict[str, object]:
    return {
        "id": str(item.id),
        "post_key": str(item.post_key),
        "revision": item.revision,
        "post_type": item.post_type,
        "content": item.content,
        "call_to_action": item.call_to_action,
        "event_or_offer": item.event_or_offer,
        "status": item.status,
    }


def post_publication_row(item: GBPPostPublication) -> dict[str, object]:
    return {
        "id": str(item.id),
        "status": item.status,
        "scheduled_for": item.scheduled_for,
        "provider_post_id": item.provider_post_id,
        "verified_at": item.verified_at,
    }


def suspension_case_row(item: GBPSuspensionCase) -> dict[str, object]:
    return {
        "id": str(item.id),
        "provider_status": item.provider_status,
        "status": item.status,
        "evidence_references": item.evidence_references,
        "safe_timeline": item.safe_timeline,
    }


@router.post(
    "/locations/{gbp_location_id}/capability-snapshots",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def record_capability_snapshot(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    command: CapabilitySnapshotRecord,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.sync")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    snapshot = await service.record_capability_snapshot(
        session,
        organization_id,
        gbp_location_id,
        command.capabilities,
        datetime.fromisoformat(command.observed_at),
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {"id": str(snapshot.id), "capabilities": snapshot.capabilities},
        "meta": meta(request),
    }


@router.get(
    "/locations/{gbp_location_id}/completeness",
    dependencies=[Depends(no_store)],
)
async def completeness_report(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("gbp.read")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    report = await service.completeness_report(session, organization_id, gbp_location_id)
    return {"data": report, "meta": meta(request)}


@router.get(
    "/locations/{gbp_location_id}/change-sets",
    dependencies=[Depends(no_store)],
)
async def list_change_sets(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("gbp.read")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    items = await service.list_change_sets(session, organization_id, gbp_location_id)
    return {"data": [change_set_row(item) for item in items], "meta": meta(request)}


@router.post(
    "/locations/{gbp_location_id}/change-sets",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def propose_change_set(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    command: ChangeSetPropose,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.propose")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    item = await service.propose_change_set(
        session,
        organization_id,
        gbp_location_id,
        command,
        command.idempotency_key,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": change_set_row(item), "meta": meta(request)}


@router.post(
    "/change-sets/{change_set_id}/decision",
    dependencies=[Depends(no_store)],
)
async def decide_change_set(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    change_set_id: UUID,
    command: ChangeSetDecision,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.approve", True)],
) -> dict[str, object]:
    await require_child_location_scope(
        session, organization_id, location_id, GBPChangeSet, change_set_id
    )
    item = await service.decide_change_set(
        session,
        organization_id,
        change_set_id,
        command.approve,
        principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": change_set_row(item), "meta": meta(request)}


@router.get(
    "/locations/{gbp_location_id}/special-hours",
    dependencies=[Depends(no_store)],
)
async def list_special_hours(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("gbp.read")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    items = await service.list_special_hours(session, organization_id, gbp_location_id)
    return {"data": [special_hours_row(item) for item in items], "meta": meta(request)}


@router.post(
    "/locations/{gbp_location_id}/special-hours",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def propose_special_hours(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    command: SpecialHoursPropose,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.propose")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    item = await service.propose_special_hours(
        session,
        organization_id,
        gbp_location_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": special_hours_row(item), "meta": meta(request)}


@router.post(
    "/special-hours/{special_hours_id}/decision",
    dependencies=[Depends(no_store)],
)
async def decide_special_hours(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    special_hours_id: UUID,
    command: ChangeSetDecision,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.approve", True)],
) -> dict[str, object]:
    await require_child_location_scope(
        session, organization_id, location_id, GBPSpecialHours, special_hours_id
    )
    item = await service.decide_special_hours(
        session,
        organization_id,
        special_hours_id,
        command.approve,
        principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": special_hours_row(item), "meta": meta(request)}


@router.get(
    "/locations/{gbp_location_id}/media",
    dependencies=[Depends(no_store)],
)
async def list_media(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("gbp.read")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    items = await service.list_media(session, organization_id, gbp_location_id)
    return {"data": [media_row(item) for item in items], "meta": meta(request)}


@router.post(
    "/locations/{gbp_location_id}/media",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def propose_media(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    command: MediaPropose,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.propose")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    item = await service.propose_media(
        session,
        organization_id,
        gbp_location_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": media_row(item), "meta": meta(request)}


@router.get(
    "/locations/{gbp_location_id}/posts",
    dependencies=[Depends(no_store)],
)
async def list_post_revisions(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("gbp.read")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    items = await service.list_post_revisions(session, organization_id, gbp_location_id)
    return {"data": [post_revision_row(item) for item in items], "meta": meta(request)}


@router.post(
    "/locations/{gbp_location_id}/posts",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def create_post_revision(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    command: PostRevisionCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.propose")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    item = await service.create_post_revision(
        session,
        organization_id,
        gbp_location_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": post_revision_row(item), "meta": meta(request)}


@router.post(
    "/posts/{revision_id}/decision",
    dependencies=[Depends(no_store)],
)
async def decide_post_revision(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    revision_id: UUID,
    command: PostDecision,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.approve", True)],
) -> dict[str, object]:
    await require_child_location_scope(
        session, organization_id, location_id, GBPPostRevision, revision_id
    )
    item = await service.decide_post_revision(
        session,
        organization_id,
        revision_id,
        command.approve,
        principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": post_revision_row(item), "meta": meta(request)}


@router.post(
    "/posts/{revision_id}/publish",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(no_store)],
)
async def publish_post(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    revision_id: UUID,
    command: PostPublishRequest,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.publish", True)],
) -> dict[str, object]:
    await require_child_location_scope(
        session, organization_id, location_id, GBPPostRevision, revision_id
    )
    item = await service.reserve_post_publication(
        session,
        organization_id,
        revision_id,
        command.workflow_run_id,
        command.idempotency_key,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": post_publication_row(item), "meta": meta(request)}


@router.get(
    "/locations/{gbp_location_id}/suspension-cases",
    dependencies=[Depends(no_store)],
)
async def list_suspension_cases(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("gbp.read")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    items = await service.list_suspension_cases(session, organization_id, gbp_location_id)
    return {"data": [suspension_case_row(item) for item in items], "meta": meta(request)}


@router.post(
    "/locations/{gbp_location_id}/suspension-cases",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def report_suspension_case(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    command: SuspensionCaseReport,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.diagnostics")],
) -> dict[str, object]:
    await require_gbp_location_scope(session, organization_id, location_id, gbp_location_id)
    item = await service.report_suspension_case(
        session,
        organization_id,
        gbp_location_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": suspension_case_row(item), "meta": meta(request)}


@router.get(
    "/locations/{gbp_location_id}/audit",
    dependencies=[Depends(no_store)],
)
async def location_operations_audit(
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
    return {"data": history, "meta": meta(request)}
