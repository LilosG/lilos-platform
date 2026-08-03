"""Guarded local/test bootstrap routes that remain necessary for deterministic setup."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.contracts import (
    BootstrapOwnerCreate,
    InvitationCreate,
    InvitationCreatedData,
    InvitationCreatedResponse,
    InvitationData,
    InvitationIssue,
    MembershipCreate,
    MembershipData,
    MembershipResponse,
)
from apps.api.app.access_control.enums import ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.dependencies import Authenticated
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.schemas import ResponseMeta

router = APIRouter(tags=["internal-access-bootstrap"])
service = AccessControlService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]
InvitationAdministration = Annotated[
    AuthorizationDecision,
    Depends(
        require_authorization(
            "organization.invitations.manage",
            ScopeType.ORGANIZATION,
            AssuranceLevel.AAL2,
        )
    ),
]


def meta(request: Request) -> ResponseMeta:
    return ResponseMeta(correlation_id=request_correlation_id(request))


@router.post(
    "/internal/organizations/{organization_id}/memberships",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_membership(
    request: Request,
    organization_id: UUID,
    command: MembershipCreate,
    session: DatabaseSession,
) -> MembershipResponse:
    """Create a direct active membership only on the guarded bootstrap surface."""
    item = await service.create_membership(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return MembershipResponse(data=MembershipData.model_validate(item), meta=meta(request))


@router.post(
    "/internal/organizations/{organization_id}/invitations",
    response_model=InvitationCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invitation(
    request: Request,
    response: Response,
    organization_id: UUID,
    command: InvitationIssue,
    principal: Authenticated,
    _authorization: InvitationAdministration,
    session: DatabaseSession,
) -> InvitationCreatedResponse:
    """Issue plaintext once only on local/test after AAL2 authorization."""
    item, token = await service.create_invitation(
        session,
        organization_id,
        InvitationCreate(
            user_profile_id=command.user_profile_id,
            email=command.email,
            membership_type=command.membership_type,
            invited_by_user_profile_id=principal.platform_user_id,
            lifetime_days=command.lifetime_days,
        ),
        correlation_id=request_correlation_id(request),
    )
    response.headers.update({"Cache-Control": "no-store", "Pragma": "no-cache"})
    data = InvitationCreatedData(
        **InvitationData.model_validate(item).model_dump(), invitation_token=token
    )
    return InvitationCreatedResponse(data=data, meta=meta(request))


@router.post(
    "/internal/organizations/{organization_id}/bootstrap-owner",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def bootstrap_owner(
    request: Request,
    organization_id: UUID,
    command: BootstrapOwnerCreate,
    session: DatabaseSession,
) -> MembershipResponse:
    """Establish the first local/test owner without creating a hidden administrator."""
    membership, _ = await service.bootstrap_owner(
        session,
        organization_id,
        MembershipCreate(
            user_profile_id=command.user_profile_id, membership_type=command.membership_type
        ),
        correlation_id=request_correlation_id(request),
    )
    return MembershipResponse(data=MembershipData.model_validate(membership), meta=meta(request))
