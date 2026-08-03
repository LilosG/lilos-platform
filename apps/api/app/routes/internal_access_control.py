"""Guarded local/test access-domain bootstrap and diagnostic routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import (
    AccessMutationResponse,
    AssignmentData,
    BootstrapOwnerCreate,
    CatalogResponse,
    DenyData,
    InvitationAccept,
    InvitationCreate,
    InvitationCreatedData,
    InvitationCreatedResponse,
    InvitationData,
    InvitationResponse,
    MembershipCreate,
    MembershipData,
    MembershipLifecycleCommand,
    MembershipResponse,
    PermissionData,
    PermissionDenyCreate,
    RoleAssignmentCreate,
    RoleData,
)
from apps.api.app.access_control.enums import MembershipStatus
from apps.api.app.access_control.repository import CatalogRepository
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.dependencies import Authenticated
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import error_response, request_correlation_id
from apps.api.app.schemas import ErrorCategory, ResponseMeta

router = APIRouter(tags=["internal-access-bootstrap"])
service = AccessControlService()
catalog = CatalogRepository()
seeder = AccessCatalogSeeder()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def meta(request: Request) -> ResponseMeta:
    return ResponseMeta(correlation_id=request_correlation_id(request))


@router.post(
    "/internal/organizations/{organization_id}/memberships",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_membership(
    request: Request, organization_id: UUID, command: MembershipCreate, session: DatabaseSession
) -> MembershipResponse:
    item = await service.create_membership(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return MembershipResponse(data=MembershipData.model_validate(item), meta=meta(request))


@router.get(
    "/internal/organizations/{organization_id}/memberships/{membership_id}",
    response_model=MembershipResponse,
)
async def get_membership(
    request: Request, organization_id: UUID, membership_id: UUID, session: DatabaseSession
) -> MembershipResponse:
    item = await service.get_membership(session, organization_id, membership_id)
    return MembershipResponse(data=MembershipData.model_validate(item), meta=meta(request))


async def membership_transition(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    command: MembershipLifecycleCommand,
    session: AsyncSession,
    target: MembershipStatus,
) -> MembershipResponse:
    item = await service.transition_membership(
        session,
        organization_id,
        membership_id,
        target=target,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return MembershipResponse(data=MembershipData.model_validate(item), meta=meta(request))


@router.post(
    "/internal/organizations/{organization_id}/memberships/{membership_id}/suspend",
    response_model=MembershipResponse,
)
async def suspend_membership(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    command: MembershipLifecycleCommand,
    session: DatabaseSession,
) -> MembershipResponse:
    return await membership_transition(
        request, organization_id, membership_id, command, session, MembershipStatus.SUSPENDED
    )


@router.post(
    "/internal/organizations/{organization_id}/memberships/{membership_id}/restore",
    response_model=MembershipResponse,
)
async def restore_membership(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    command: MembershipLifecycleCommand,
    session: DatabaseSession,
) -> MembershipResponse:
    return await membership_transition(
        request, organization_id, membership_id, command, session, MembershipStatus.ACTIVE
    )


@router.post(
    "/internal/organizations/{organization_id}/memberships/{membership_id}/revoke",
    response_model=MembershipResponse,
)
async def revoke_membership(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    command: MembershipLifecycleCommand,
    session: DatabaseSession,
) -> MembershipResponse:
    return await membership_transition(
        request, organization_id, membership_id, command, session, MembershipStatus.REVOKED
    )


@router.post(
    "/internal/organizations/{organization_id}/invitations",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    request: Request,
    response: Response,
    organization_id: UUID,
    command: InvitationCreate,
    session: DatabaseSession,
) -> InvitationCreatedResponse:
    item, token = await service.create_invitation(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache"})
    data = InvitationCreatedData(
        **InvitationData.model_validate(item).model_dump(), invitation_token=token
    )
    return InvitationCreatedResponse(data=data, meta=meta(request))


@router.get(
    "/internal/organizations/{organization_id}/invitations/{invitation_id}",
    response_model=InvitationResponse,
)
async def get_invitation(
    request: Request, organization_id: UUID, invitation_id: UUID, session: DatabaseSession
) -> InvitationResponse:
    item = await service.get_invitation(session, organization_id, invitation_id)
    return InvitationResponse(data=InvitationData.model_validate(item), meta=meta(request))


@router.post(
    "/internal/organizations/{organization_id}/invitations/{invitation_id}/cancel",
    response_model=InvitationResponse,
)
async def cancel_invitation(
    request: Request,
    organization_id: UUID,
    invitation_id: UUID,
    command: MembershipLifecycleCommand,
    session: DatabaseSession,
) -> InvitationResponse:
    item = await service.cancel_invitation(
        session,
        organization_id,
        invitation_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return InvitationResponse(data=InvitationData.model_validate(item), meta=meta(request))


@router.post("/internal/invitations/accept", response_model=InvitationResponse)
async def accept_invitation(
    request: Request,
    response: Response,
    command: InvitationAccept,
    principal: Authenticated,
    session: DatabaseSession,
) -> InvitationResponse | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    result = await service.accept_invitation(
        session, command.token, principal, correlation_id=request_correlation_id(request)
    )
    if not result.accepted or result.invitation is None:
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="INVITATION_ACCEPTANCE_FAILED",
            message="The invitation could not be accepted.",
            category=ErrorCategory.CONFLICT,
            headers={"Cache-Control": "no-store"},
        )
    return InvitationResponse(
        data=InvitationData.model_validate(result.invitation), meta=meta(request)
    )


@router.post(
    "/internal/organizations/{organization_id}/memberships/{membership_id}/role-assignments",
    response_model=AccessMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_assignment(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    command: RoleAssignmentCreate,
    session: DatabaseSession,
) -> AccessMutationResponse:
    item = await service.add_assignment(
        session,
        organization_id,
        membership_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return AccessMutationResponse(data=AssignmentData.model_validate(item), meta=meta(request))


@router.delete(
    "/internal/organizations/{organization_id}/memberships/{membership_id}/role-assignments/{assignment_id}",
    response_model=AccessMutationResponse,
)
async def remove_assignment(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    assignment_id: UUID,
    session: DatabaseSession,
) -> AccessMutationResponse:
    item = await service.remove_assignment(
        session,
        organization_id,
        membership_id,
        assignment_id,
        correlation_id=request_correlation_id(request),
    )
    return AccessMutationResponse(data=AssignmentData.model_validate(item), meta=meta(request))


@router.post(
    "/internal/organizations/{organization_id}/memberships/{membership_id}/permission-denies",
    response_model=AccessMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_deny(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    command: PermissionDenyCreate,
    session: DatabaseSession,
) -> AccessMutationResponse:
    item = await service.add_deny(
        session,
        organization_id,
        membership_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return AccessMutationResponse(data=DenyData.model_validate(item), meta=meta(request))


@router.delete(
    "/internal/organizations/{organization_id}/memberships/{membership_id}/permission-denies/{deny_id}",
    response_model=AccessMutationResponse,
)
async def remove_deny(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    deny_id: UUID,
    session: DatabaseSession,
) -> AccessMutationResponse:
    item = await service.remove_deny(
        session,
        organization_id,
        membership_id,
        deny_id,
        correlation_id=request_correlation_id(request),
    )
    return AccessMutationResponse(data=DenyData.model_validate(item), meta=meta(request))


@router.get("/internal/roles", response_model=CatalogResponse)
async def list_roles(request: Request, session: DatabaseSession) -> CatalogResponse:
    return CatalogResponse(
        data=[RoleData.model_validate(item) for item in await catalog.list_roles(session)],
        meta=meta(request),
    )


@router.get("/internal/permissions", response_model=CatalogResponse)
async def list_permissions(request: Request, session: DatabaseSession) -> CatalogResponse:
    return CatalogResponse(
        data=[
            PermissionData.model_validate(item) for item in await catalog.list_permissions(session)
        ],
        meta=meta(request),
    )


@router.post(
    "/internal/organizations/{organization_id}/bootstrap-owner",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bootstrap_owner(
    request: Request, organization_id: UUID, command: BootstrapOwnerCreate, session: DatabaseSession
) -> MembershipResponse:
    membership, _ = await service.bootstrap_owner(
        session,
        organization_id,
        MembershipCreate(
            user_profile_id=command.user_profile_id, membership_type=command.membership_type
        ),
        correlation_id=request_correlation_id(request),
    )
    return MembershipResponse(data=MembershipData.model_validate(membership), meta=meta(request))
