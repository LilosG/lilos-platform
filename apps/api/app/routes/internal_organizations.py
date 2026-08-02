"""Temporary bootstrap administration routes for organization lifecycle management."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.organizations.contracts import (
    OrganizationCreate,
    OrganizationData,
    OrganizationIndustryAssignment,
    OrganizationListResponse,
    OrganizationPagination,
    OrganizationResponse,
    OrganizationTransition,
)
from apps.api.app.organizations.enums import OrganizationLifecycleAction
from apps.api.app.organizations.service import OrganizationService
from apps.api.app.schemas import ResponseMeta

router = APIRouter(
    prefix="/internal/organizations",
    tags=["internal-platform-administration"],
    responses={
        404: {"description": "Organization not found"},
        409: {"description": "Slug, lifecycle, or version conflict"},
    },
)
service = OrganizationService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def organization_response(request: Request, organization: object) -> OrganizationResponse:
    """Build the standard internal organization success envelope."""
    return OrganizationResponse(
        data=OrganizationData.model_validate(organization),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an organization (temporary internal bootstrap route)",
)
async def create_organization(
    request: Request,
    command: OrganizationCreate,
    session: DatabaseSession,
) -> OrganizationResponse:
    """Create an organization; this temporary surface is not an authorization substitute."""
    organization = await service.create(
        session,
        command,
        correlation_id=request_correlation_id(request),
    )
    return organization_response(request, organization)


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Get an organization (temporary internal bootstrap route)",
)
async def get_organization(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
) -> OrganizationResponse:
    """Retrieve one organization by internal identifier."""
    organization = await service.get(session, organization_id)
    return organization_response(request, organization)


@router.get(
    "",
    response_model=OrganizationListResponse,
    summary="List organizations (temporary internal bootstrap route)",
)
async def list_organizations(
    request: Request,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> OrganizationListResponse:
    """List a small administrative collection in deterministic creation order."""
    organizations, has_more = await service.list(session, limit=limit, offset=offset)
    return OrganizationListResponse(
        data=[OrganizationData.model_validate(item) for item in organizations],
        pagination=OrganizationPagination(
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        ),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


async def transition_organization(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: AsyncSession,
    action: OrganizationLifecycleAction,
) -> OrganizationResponse:
    """Apply one explicit lifecycle action through the organization service."""
    organization = await service.transition(
        session,
        organization_id,
        action=action,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return organization_response(request, organization)


@router.post(
    "/{organization_id}/start-onboarding",
    response_model=OrganizationResponse,
    summary="Start onboarding (temporary internal bootstrap route)",
)
async def start_onboarding(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> OrganizationResponse:
    return await transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.START_ONBOARDING
    )


@router.post(
    "/{organization_id}/activate",
    response_model=OrganizationResponse,
    summary="Activate an organization (temporary internal bootstrap route)",
)
async def activate(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> OrganizationResponse:
    return await transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.ACTIVATE
    )


@router.post(
    "/{organization_id}/pause",
    response_model=OrganizationResponse,
    summary="Pause an organization (temporary internal bootstrap route)",
)
async def pause(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> OrganizationResponse:
    return await transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.PAUSE
    )


@router.post(
    "/{organization_id}/resume",
    response_model=OrganizationResponse,
    summary="Resume a paused organization (temporary internal bootstrap route)",
)
async def resume(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> OrganizationResponse:
    return await transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.RESUME
    )


@router.post(
    "/{organization_id}/suspend",
    response_model=OrganizationResponse,
    summary="Suspend an organization (temporary internal bootstrap route)",
)
async def suspend(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> OrganizationResponse:
    return await transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.SUSPEND
    )


@router.post(
    "/{organization_id}/start-offboarding",
    response_model=OrganizationResponse,
    summary="Start offboarding (temporary internal bootstrap route)",
)
async def start_offboarding(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> OrganizationResponse:
    return await transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.START_OFFBOARDING
    )


@router.post(
    "/{organization_id}/archive",
    response_model=OrganizationResponse,
    summary="Archive an organization (temporary internal bootstrap route)",
)
async def archive(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> OrganizationResponse:
    return await transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.ARCHIVE
    )


@router.post(
    "/{organization_id}/industry",
    response_model=OrganizationResponse,
    summary="Assign an organization industry (temporary internal bootstrap route)",
)
async def set_industry(
    request: Request,
    organization_id: UUID,
    command: OrganizationIndustryAssignment,
    session: DatabaseSession,
) -> OrganizationResponse:
    organization = await service.set_industry(
        session,
        organization_id,
        industry_id=command.industry_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return organization_response(request, organization)
