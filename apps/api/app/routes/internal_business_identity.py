"""Temporary read-only bootstrap routes for business identity."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.business_identity.contracts import (
    LocationBusinessIdentityResponse,
    OrganizationBusinessIdentityResponse,
)
from apps.api.app.business_identity.service import BusinessIdentityService
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.schemas import ResponseMeta

router = APIRouter(
    prefix="/internal/organizations",
    tags=["internal-platform-administration"],
)
service = BusinessIdentityService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


@router.get(
    "/{organization_id}/business-identity",
    response_model=OrganizationBusinessIdentityResponse,
    summary="Resolve organization business identity (temporary internal bootstrap route)",
)
async def resolve_organization_business_identity(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
) -> OrganizationBusinessIdentityResponse:
    return OrganizationBusinessIdentityResponse(
        data=await service.resolve_organization(session, organization_id),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.get(
    "/{organization_id}/locations/{location_id}/business-identity",
    response_model=LocationBusinessIdentityResponse,
    summary="Resolve location business identity (temporary internal bootstrap route)",
)
async def resolve_location_business_identity(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: DatabaseSession,
) -> LocationBusinessIdentityResponse:
    return LocationBusinessIdentityResponse(
        data=await service.resolve_location(session, organization_id, location_id),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )
