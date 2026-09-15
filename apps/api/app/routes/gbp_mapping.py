"""Canonical operator routes for attaching and removing GBP location mappings.

A platform Location is the operating resource. A discovered GBPLocation is a
provider resource. This boundary keeps those identities separate and enforces
that one platform Location cannot have multiple confirmed GBP resources.
"""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.integrations.models import ProviderResourceMapping
from apps.api.app.locations.models import Location
from apps.api.app.products.gbp.contracts import MappingConfirm
from apps.api.app.products.gbp.models import GBPLocation
from apps.api.app.products.gbp.operations_errors import (
    GBPLocationAlreadyMappedError,
    GBPLocationNotFoundError,
)
from apps.api.app.products.gbp.service import GBPService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/locations/{location_id}/gbp-mapping",
    tags=["gbp"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = GBPService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


def policy(key: str) -> Any:
    return Depends(require_authorization(key, ScopeType.LOCATION, AssuranceLevel.AAL2))


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


async def _lock_platform_location(
    session: AsyncSession, organization_id: UUID, location_id: UUID
) -> None:
    """Serialize mapping changes for one platform location.

    Locking the owning Location row prevents two concurrent confirm requests
    from both observing "no existing mapping" and creating a duplicate.
    """
    locked = await session.scalar(
        select(Location.id)
        .where(Location.organization_id == organization_id, Location.id == location_id)
        .with_for_update()
    )
    if locked is None:
        raise GBPLocationNotFoundError


async def _provider_mapping_for_location(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    item: GBPLocation,
) -> ProviderResourceMapping | None:
    """Resolve the canonical provider mapping, including legacy rows.

    Older discovery/mapping states can leave the denormalized GBPLocation
    fields out of sync while ProviderResourceMapping still owns the active
    client association. Cleanup must follow that canonical mapping identity so
    operators can remove stale/duplicate profiles without weakening tenant or
    location scoping.
    """
    mapping: ProviderResourceMapping | None = None
    if item.integration_resource_id is not None:
        mapping = await session.scalar(
            select(ProviderResourceMapping)
            .where(
                ProviderResourceMapping.organization_id == organization_id,
                ProviderResourceMapping.id == item.integration_resource_id,
            )
            .with_for_update()
        )

    if mapping is None:
        mapping = await session.scalar(
            select(ProviderResourceMapping)
            .where(
                ProviderResourceMapping.organization_id == organization_id,
                ProviderResourceMapping.connection_id == item.connection_id,
                ProviderResourceMapping.resource_type == "location",
                ProviderResourceMapping.external_resource_id == item.external_location_id,
                ProviderResourceMapping.platform_resource_id == location_id,
            )
            .with_for_update()
        )
    return mapping


async def _detach_mapping(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    archive: bool,
) -> tuple[GBPLocation, bool]:
    """Detach a GBP provider mapping and optionally archive it from the workspace."""
    await _lock_platform_location(session, organization_id, location_id)
    item = await session.scalar(
        select(GBPLocation)
        .where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.id == gbp_location_id,
        )
        .with_for_update()
    )
    if item is None:
        raise GBPLocationNotFoundError

    mapping = await _provider_mapping_for_location(
        session,
        organization_id=organization_id,
        location_id=location_id,
        item=item,
    )

    if mapping is not None:
        if mapping.platform_resource_id != location_id:
            raise GBPLocationNotFoundError
    elif item.location_id != location_id:
        raise GBPLocationNotFoundError

    prior_write_enabled = item.write_enabled
    if mapping is not None:
        mapping.platform_resource_id = None
        mapping.status = "stale"

    item.location_id = None
    item.mapping_status = "archived" if archive else "unmapped"
    item.write_enabled = False
    item.confirmed_by_user_id = None
    item.confirmed_at = None
    await session.flush()
    return item, prior_write_enabled


@router.post("/{gbp_location_id}/confirm", dependencies=[Depends(no_store)])
async def confirm_mapping(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    command: MappingConfirm,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.connect")],
) -> dict[str, object]:
    if command.location_id != location_id:
        raise ValueError("location scope mismatch")

    await _lock_platform_location(session, organization_id, location_id)
    existing = await session.scalar(
        select(GBPLocation.id).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.location_id == location_id,
            GBPLocation.mapping_status == "confirmed",
            GBPLocation.id != gbp_location_id,
        )
    )
    if existing is not None:
        raise GBPLocationAlreadyMappedError

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


@router.delete("/{gbp_location_id}", dependencies=[Depends(no_store)])
async def remove_mapping(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.connect")],
) -> dict[str, object]:
    """Detach one provider resource while keeping it available for remapping."""
    item, prior_write_enabled = await _detach_mapping(
        session,
        organization_id=organization_id,
        location_id=location_id,
        gbp_location_id=gbp_location_id,
        archive=False,
    )

    await service._audit(
        session,
        event="gbp.location.mapping_removed",
        organization_id=organization_id,
        location_id=location_id,
        actor_id=principal.platform_user_id,
        resource_type="gbp_location",
        resource_id=item.id,
        correlation_id=request_correlation_id(request),
        summary="GBP location mapping removed.",
        metadata={"provider_writes_were_enabled": prior_write_enabled},
    )
    return {
        "data": {
            "id": str(item.id),
            "mapping_status": item.mapping_status,
            "write_enabled": item.write_enabled,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }


@router.post("/{gbp_location_id}/archive", dependencies=[Depends(no_store)])
async def archive_mapping(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    gbp_location_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("gbp.connect")],
) -> dict[str, object]:
    """Remove a GBP from the client workspace without changing Google."""
    item, prior_write_enabled = await _detach_mapping(
        session,
        organization_id=organization_id,
        location_id=location_id,
        gbp_location_id=gbp_location_id,
        archive=True,
    )

    await service._audit(
        session,
        event="gbp.location.archived",
        organization_id=organization_id,
        location_id=location_id,
        actor_id=principal.platform_user_id,
        resource_type="gbp_location",
        resource_id=item.id,
        correlation_id=request_correlation_id(request),
        summary="GBP location removed from the client workspace.",
        metadata={"provider_writes_were_enabled": prior_write_enabled},
    )
    return {
        "data": {
            "id": str(item.id),
            "mapping_status": item.mapping_status,
            "write_enabled": item.write_enabled,
        },
        "meta": {"correlation_id": request_correlation_id(request)},
    }
