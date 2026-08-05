"""Authenticated, production-mounted platform-administrator bootstrap routes.

Unlike ``internal_organizations.py`` / ``internal_locations.py`` (gated behind
``internal_admin_routes_enabled`` and forbidden outside local/test), this
router is always mounted. Every route requires an authenticated principal
holding an active ``PlatformAdministrator`` grant (see
``apps.api.app.platform_admin``), which is a narrow, additive, cross-organization
authorization primitive independent of the existing per-organization RBAC
engine. It exists so a platform administrator can create client organizations
and locations from the UI instead of running a one-off script against the
database.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.contracts import DataResponse
from apps.api.app.authentication.contracts import UserProfileCreate
from apps.api.app.authentication.dependencies import get_authenticated_principal
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.industries.contracts import IndustryData
from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.repository import MAX_INDUSTRY_LIST_LIMIT
from apps.api.app.industries.service import IndustryService
from apps.api.app.locations.contracts import LocationCreate, LocationData, LocationTransition
from apps.api.app.locations.enums import LocationLifecycleAction
from apps.api.app.locations.service import LocationService
from apps.api.app.organizations.contracts import (
    OrganizationCreate,
    OrganizationData,
    OrganizationTransition,
)
from apps.api.app.organizations.enums import OrganizationLifecycleAction
from apps.api.app.organizations.service import OrganizationService
from apps.api.app.platform_admin.dependencies import require_platform_administrator
from apps.api.app.platform_admin.service import PlatformAdministrationService
from apps.api.app.schemas import ResponseMeta


async def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1/platform",
    tags=["platform-administration"],
    dependencies=[
        Depends(get_authenticated_principal),
        Depends(require_platform_administrator()),
        Depends(no_store),
    ],
    responses={
        403: {"description": "Caller is not an active platform administrator"},
        404: {"description": "Organization or location not found"},
        409: {"description": "Slug, lifecycle, primary, or version conflict"},
    },
)
organizations = OrganizationService()
locations = LocationService()
industries = IndustryService()
platform_administration = PlatformAdministrationService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def response(request: Request, data: object) -> DataResponse:
    return DataResponse(
        data=data, meta=ResponseMeta(correlation_id=request_correlation_id(request))
    )


@router.post(
    "/organizations",
    response_model=DataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization",
)
async def create_organization(
    request: Request,
    command: OrganizationCreate,
    session: DatabaseSession,
) -> DataResponse:
    organization = await organizations.create(
        session, command, correlation_id=request_correlation_id(request)
    )
    return response(request, OrganizationData.model_validate(organization))


@router.get("/organizations", response_model=DataResponse, summary="List organizations")
async def list_organizations(
    request: Request,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DataResponse:
    items, has_more = await organizations.list(session, limit=limit, offset=offset)
    return response(
        request,
        {
            "items": [OrganizationData.model_validate(item) for item in items],
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if has_more else None,
            "has_more": has_more,
        },
    )


@router.get(
    "/organizations/{organization_id}", response_model=DataResponse, summary="Get an organization"
)
async def get_organization(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
) -> DataResponse:
    organization = await organizations.get(session, organization_id)
    return response(request, OrganizationData.model_validate(organization))


@router.get(
    "/industries",
    response_model=DataResponse,
    summary="List active industries",
)
async def list_industries(
    request: Request,
    session: DatabaseSession,
) -> DataResponse:
    items, _ = await industries.list(session, limit=MAX_INDUSTRY_LIST_LIMIT, offset=0)
    active = [
        IndustryData.model_validate(item) for item in items if item.status is IndustryStatus.ACTIVE
    ]
    return response(request, {"items": active})


async def _transition_organization(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: AsyncSession,
    action: OrganizationLifecycleAction,
) -> DataResponse:
    organization = await organizations.transition(
        session,
        organization_id,
        action=action,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return response(request, OrganizationData.model_validate(organization))


@router.post(
    "/organizations/{organization_id}/start-onboarding",
    response_model=DataResponse,
    summary="Start organization onboarding",
)
async def start_onboarding(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> DataResponse:
    return await _transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.START_ONBOARDING
    )


@router.post(
    "/organizations/{organization_id}/activate",
    response_model=DataResponse,
    summary="Activate an organization",
)
async def activate_organization(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> DataResponse:
    return await _transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.ACTIVATE
    )


@router.post(
    "/organizations/{organization_id}/pause",
    response_model=DataResponse,
    summary="Pause an organization",
)
async def pause_organization(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> DataResponse:
    return await _transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.PAUSE
    )


@router.post(
    "/organizations/{organization_id}/resume",
    response_model=DataResponse,
    summary="Resume a paused organization",
)
async def resume_organization(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> DataResponse:
    return await _transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.RESUME
    )


@router.post(
    "/organizations/{organization_id}/locations",
    response_model=DataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a location",
)
async def create_location(
    request: Request,
    organization_id: UUID,
    command: LocationCreate,
    session: DatabaseSession,
) -> DataResponse:
    location = await locations.create(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return response(request, LocationData.model_validate(location))


@router.get(
    "/organizations/{organization_id}/locations",
    response_model=DataResponse,
    summary="List organization locations",
)
async def list_locations(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DataResponse:
    items, has_more = await locations.list(session, organization_id, limit=limit, offset=offset)
    return response(
        request,
        {
            "items": [LocationData.model_validate(item) for item in items],
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if has_more else None,
            "has_more": has_more,
        },
    )


@router.post(
    "/organizations/{organization_id}/locations/{location_id}/activate",
    response_model=DataResponse,
    summary="Activate a location",
)
async def activate_location(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    command: LocationTransition,
    session: DatabaseSession,
) -> DataResponse:
    location = await locations.transition(
        session,
        organization_id,
        location_id,
        action=LocationLifecycleAction.ACTIVATE,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return response(request, LocationData.model_validate(location))


@router.post(
    "/organizations/{organization_id}/owner",
    response_model=DataResponse,
    status_code=status.HTTP_200_OK,
    summary="Bootstrap the first owner of an organization",
)
async def bootstrap_owner(
    request: Request,
    organization_id: UUID,
    command: UserProfileCreate,
    session: DatabaseSession,
) -> DataResponse:
    result = await platform_administration.bootstrap_owner(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return response(request, result)
