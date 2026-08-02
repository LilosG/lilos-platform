"""Temporary organization-scoped bootstrap routes for location groups."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.location_groups.contracts import (
    LocationGroupArchive,
    LocationGroupCreate,
    LocationGroupData,
    LocationGroupListResponse,
    LocationGroupMembershipData,
    LocationGroupMembershipListResponse,
    LocationGroupMembershipResponse,
    LocationGroupPagination,
    LocationGroupReplace,
    LocationGroupResponse,
)
from apps.api.app.location_groups.service import LocationGroupService
from apps.api.app.schemas import ResponseMeta

router = APIRouter(
    prefix="/internal/organizations/{organization_id}/location-groups",
    tags=["internal-platform-administration"],
    responses={
        404: {"description": "Organization, group, location, or membership not found"},
        409: {"description": "Key, state, membership, parent-state, or version conflict"},
    },
)
service = LocationGroupService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def group_response(request: Request, group: object) -> LocationGroupResponse:
    return LocationGroupResponse(
        data=LocationGroupData.model_validate(group),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


def membership_response(request: Request, membership: object) -> LocationGroupMembershipResponse:
    return LocationGroupMembershipResponse(
        data=LocationGroupMembershipData.model_validate(membership),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.post(
    "",
    response_model=LocationGroupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a location group (temporary internal bootstrap route)",
)
async def create_location_group(
    request: Request,
    organization_id: UUID,
    command: LocationGroupCreate,
    session: DatabaseSession,
) -> LocationGroupResponse:
    group = await service.create(
        session,
        organization_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return group_response(request, group)


@router.get(
    "",
    response_model=LocationGroupListResponse,
    summary="List location groups (temporary internal bootstrap route)",
)
async def list_location_groups(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LocationGroupListResponse:
    groups, has_more = await service.list_groups(
        session, organization_id, limit=limit, offset=offset
    )
    return LocationGroupListResponse(
        data=[LocationGroupData.model_validate(item) for item in groups],
        pagination=LocationGroupPagination(
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        ),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.get(
    "/{group_id}",
    response_model=LocationGroupResponse,
    summary="Get a location group (temporary internal bootstrap route)",
)
async def get_location_group(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    session: DatabaseSession,
) -> LocationGroupResponse:
    return group_response(request, await service.get(session, organization_id, group_id))


@router.put(
    "/{group_id}",
    response_model=LocationGroupResponse,
    summary="Replace location-group content (temporary internal bootstrap route)",
)
async def replace_location_group(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    command: LocationGroupReplace,
    session: DatabaseSession,
) -> LocationGroupResponse:
    group = await service.replace(
        session,
        organization_id,
        group_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return group_response(request, group)


@router.post(
    "/{group_id}/archive",
    response_model=LocationGroupResponse,
    summary="Archive a location group (temporary internal bootstrap route)",
)
async def archive_location_group(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    command: LocationGroupArchive,
    session: DatabaseSession,
) -> LocationGroupResponse:
    group = await service.archive(
        session,
        organization_id,
        group_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return group_response(request, group)


@router.get(
    "/{group_id}/locations",
    response_model=LocationGroupMembershipListResponse,
    summary="List group memberships (temporary internal bootstrap route)",
)
async def list_group_memberships(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LocationGroupMembershipListResponse:
    memberships, has_more = await service.list_members(
        session,
        organization_id,
        group_id,
        limit=limit,
        offset=offset,
    )
    return LocationGroupMembershipListResponse(
        data=[LocationGroupMembershipData.model_validate(item) for item in memberships],
        pagination=LocationGroupPagination(
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        ),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.post(
    "/{group_id}/locations/{location_id}",
    response_model=LocationGroupMembershipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a location-group membership (temporary internal bootstrap route)",
)
async def add_group_membership(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    location_id: UUID,
    session: DatabaseSession,
) -> LocationGroupMembershipResponse:
    membership = await service.add_membership(
        session,
        organization_id,
        group_id,
        location_id,
        correlation_id=request_correlation_id(request),
    )
    return membership_response(request, membership)


@router.delete(
    "/{group_id}/locations/{location_id}",
    response_model=LocationGroupMembershipResponse,
    summary="Remove a location-group membership (temporary internal bootstrap route)",
)
async def remove_group_membership(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    location_id: UUID,
    session: DatabaseSession,
) -> LocationGroupMembershipResponse:
    membership = await service.remove_membership(
        session,
        organization_id,
        group_id,
        location_id,
        correlation_id=request_correlation_id(request),
    )
    return membership_response(request, membership)
