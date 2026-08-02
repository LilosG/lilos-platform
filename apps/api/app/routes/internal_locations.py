"""Temporary organization-scoped bootstrap routes for locations."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.locations.contracts import (
    LocationCreate,
    LocationData,
    LocationListResponse,
    LocationPagination,
    LocationResponse,
    LocationTransition,
)
from apps.api.app.locations.enums import LocationLifecycleAction
from apps.api.app.locations.service import LocationService
from apps.api.app.schemas import ResponseMeta

router = APIRouter(
    prefix="/internal/organizations/{organization_id}/locations",
    tags=["internal-platform-administration"],
    responses={
        404: {"description": "Organization or location not found"},
        409: {"description": "Slug, primary, lifecycle, parent-state, or version conflict"},
    },
)
service = LocationService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def location_response(request: Request, location: object) -> LocationResponse:
    return LocationResponse(
        data=LocationData.model_validate(location),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.post(
    "",
    response_model=LocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a location (temporary internal bootstrap route)",
)
async def create_location(
    request: Request, organization_id: UUID, command: LocationCreate, session: DatabaseSession
) -> LocationResponse:
    location = await service.create(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return location_response(request, location)


@router.get(
    "",
    response_model=LocationListResponse,
    summary="List organization locations (temporary internal bootstrap route)",
)
async def list_locations(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LocationListResponse:
    locations, has_more = await service.list(session, organization_id, limit=limit, offset=offset)
    return LocationListResponse(
        data=[LocationData.model_validate(item) for item in locations],
        pagination=LocationPagination(
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        ),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.get(
    "/{location_id}",
    response_model=LocationResponse,
    summary="Get an organization location (temporary internal bootstrap route)",
)
async def get_location(
    request: Request, organization_id: UUID, location_id: UUID, session: DatabaseSession
) -> LocationResponse:
    return location_response(request, await service.get(session, organization_id, location_id))


async def transition_location(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    command: LocationTransition,
    session: AsyncSession,
    action: LocationLifecycleAction,
) -> LocationResponse:
    location = await service.transition(
        session,
        organization_id,
        location_id,
        action=action,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return location_response(request, location)


def _transition_route(path: str, action: LocationLifecycleAction) -> Any:
    async def endpoint(
        request: Request,
        organization_id: UUID,
        location_id: UUID,
        command: LocationTransition,
        session: DatabaseSession,
    ) -> LocationResponse:
        return await transition_location(
            request, organization_id, location_id, command, session, action
        )

    endpoint.__name__ = f"location_{action.value}"
    router.post(
        f"/{{location_id}}/{path}",
        response_model=LocationResponse,
        summary=(
            f"{action.value.replace('_', ' ').title()} a location "
            "(temporary internal bootstrap route)"
        ),
    )(endpoint)


_transition_route("activate", LocationLifecycleAction.ACTIVATE)
_transition_route("pause", LocationLifecycleAction.PAUSE)
_transition_route("close-temporarily", LocationLifecycleAction.CLOSE_TEMPORARILY)
_transition_route("close-permanently", LocationLifecycleAction.CLOSE_PERMANENTLY)
_transition_route("archive", LocationLifecycleAction.ARCHIVE)
