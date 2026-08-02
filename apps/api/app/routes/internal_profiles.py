"""Temporary organization-scoped bootstrap routes for controlled profiles."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.profiles.contracts import (
    LocationProfileCreate,
    LocationProfileData,
    LocationProfileReplace,
    LocationProfileResponse,
    OrganizationProfileCreate,
    OrganizationProfileData,
    OrganizationProfileReplace,
    OrganizationProfileResponse,
)
from apps.api.app.profiles.service import LocationProfileService, OrganizationProfileService
from apps.api.app.schemas import ResponseMeta

router = APIRouter(
    prefix="/internal/organizations",
    tags=["internal-platform-administration"],
)
organization_service = OrganizationProfileService()
location_service = LocationProfileService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def organization_response(request: Request, profile: object) -> OrganizationProfileResponse:
    return OrganizationProfileResponse(
        data=OrganizationProfileData.model_validate(profile),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


def location_response(request: Request, profile: object) -> LocationProfileResponse:
    return LocationProfileResponse(
        data=LocationProfileData.model_validate(profile),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.post(
    "/{organization_id}/profile",
    response_model=OrganizationProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization profile (temporary internal bootstrap route)",
)
async def create_organization_profile(
    request: Request,
    organization_id: UUID,
    command: OrganizationProfileCreate,
    session: DatabaseSession,
) -> OrganizationProfileResponse:
    profile = await organization_service.create(
        session,
        organization_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return organization_response(request, profile)


@router.get(
    "/{organization_id}/profile",
    response_model=OrganizationProfileResponse,
    summary="Get an organization profile (temporary internal bootstrap route)",
)
async def get_organization_profile(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
) -> OrganizationProfileResponse:
    return organization_response(request, await organization_service.get(session, organization_id))


@router.put(
    "/{organization_id}/profile",
    response_model=OrganizationProfileResponse,
    summary="Replace an organization profile (temporary internal bootstrap route)",
)
async def replace_organization_profile(
    request: Request,
    organization_id: UUID,
    command: OrganizationProfileReplace,
    session: DatabaseSession,
) -> OrganizationProfileResponse:
    profile = await organization_service.replace(
        session,
        organization_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return organization_response(request, profile)


@router.post(
    "/{organization_id}/locations/{location_id}/profile",
    response_model=LocationProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a location profile (temporary internal bootstrap route)",
)
async def create_location_profile(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    command: LocationProfileCreate,
    session: DatabaseSession,
) -> LocationProfileResponse:
    profile = await location_service.create(
        session,
        organization_id,
        location_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return location_response(request, profile)


@router.get(
    "/{organization_id}/locations/{location_id}/profile",
    response_model=LocationProfileResponse,
    summary="Get a location profile (temporary internal bootstrap route)",
)
async def get_location_profile(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: DatabaseSession,
) -> LocationProfileResponse:
    return location_response(
        request,
        await location_service.get(session, organization_id, location_id),
    )


@router.put(
    "/{organization_id}/locations/{location_id}/profile",
    response_model=LocationProfileResponse,
    summary="Replace a location profile (temporary internal bootstrap route)",
)
async def replace_location_profile(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    command: LocationProfileReplace,
    session: DatabaseSession,
) -> LocationProfileResponse:
    profile = await location_service.replace(
        session,
        organization_id,
        location_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return location_response(request, profile)
