"""Client-facing onboarding routes for self-service and co-managed modes.

These routes enforce per-organization access verification using the
actual domain models rather than the platform-administrator gate used
by ``platform_administration.py``. They allow properly authorized users to:

- Create a new organization in self-service mode
- View their onboarding state filtered by responsibility mode
- Complete client-assigned or client-safe onboarding steps
- Activate their organization when ready
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import UserProfileCreate
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.repository import UserProfileRepository
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.onboarding.service import OnboardingOrchestrationService
from apps.api.app.organizations.contracts import (
    OrganizationCreate,
    OrganizationData,
    OrganizationTransition,
)
from apps.api.app.organizations.enums import OrganizationLifecycleAction
from apps.api.app.organizations.service import OrganizationService
from apps.api.app.platform_admin.repository import PlatformAdministratorRepository
from apps.api.app.platform_admin.service import PlatformAdministrationService

router = APIRouter(
    prefix="/api/v1/client/onboarding",
    tags=["client-onboarding"],
    dependencies=[Depends(get_authenticated_principal)],
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Not authorized for this organization"},
        404: {"description": "Organization not found"},
        409: {"description": "Conflict or onboarding incomplete"},
    },
)

organizations = OrganizationService()
onboarding_service = OnboardingOrchestrationService()
access = AccessControlService()
platform_admin_repo = PlatformAdministratorRepository()
user_profile_repo = UserProfileRepository()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def _api_response(request: Request, data: object) -> dict[str, object]:
    return {
        "data": data,
        "meta": {"correlation_id": request_correlation_id(request)},
    }


async def _resolve_user_profile(
    session: AsyncSession, principal: Authenticated
) -> object | None:
    """Find the UserProfile row for the authenticated principal."""
    return await user_profile_repo.get_by_auth_user_id(
        session, principal.platform_user_id
    )


async def _is_platform_admin(
    session: AsyncSession, principal: Authenticated
) -> bool:
    """Return True when the principal holds an active PlatformAdministrator grant."""
    profile = await _resolve_user_profile(session, principal)
    if profile is None:
        return False
    admin = await platform_admin_repo.get_active_by_user_profile_id(
        session, profile.id  # type: ignore[attr-defined]
    )
    return admin is not None


async def _verify_organization_access(
    session: AsyncSession,
    organization_id: UUID,
    principal: Authenticated,
) -> bool:
    """Return True when the principal has any active membership or is a platform admin."""
    if await _is_platform_admin(session, principal):
        return True
    profile = await _resolve_user_profile(session, principal)
    if profile is None:
        return False
    membership = await access.memberships.get_by_user(
        session, organization_id, profile.id  # type: ignore[attr-defined]
    )
    return membership is not None and membership.status.value == "active"


def _forbidden() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": {
                "code": "FORBIDDEN",
                "message": "You do not have access to this organization.",
                "category": "authorization",
            }
        },
    )


# ---------------------------------------------------------------------------
# Self-service organization creation
# ---------------------------------------------------------------------------


@router.post(
    "/organizations",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new organization in self-service mode",
)
async def create_self_service_organization(
    request: Request,
    command: OrganizationCreate,
    session: DatabaseSession,
    principal: Authenticated,
) -> JSONResponse:
    """Create an organization and bootstrap the calling user as owner.

    The organization is created with onboarding_mode='self_service'.
    Only the creating user is granted access.
    """
    command_dict = command.model_dump()
    command_dict["onboarding_mode"] = "self_service"
    create_cmd = OrganizationCreate(**command_dict)

    organization = await organizations.create(
        session, create_cmd, correlation_id=request_correlation_id(request)
    )

    platform_admin_svc = PlatformAdministrationService()
    await platform_admin_svc.bootstrap_owner(
        session,
        organization.id,
        UserProfileCreate(
            auth_user_id=principal.platform_user_id,
        ),
        correlation_id=request_correlation_id(request),
    )

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=_api_response(
            request, OrganizationData.model_validate(organization).model_dump(mode="json")
        ),
    )


# ---------------------------------------------------------------------------
# Client onboarding state (filtered by responsibility mode)
# ---------------------------------------------------------------------------


@router.get(
    "/organizations/{organization_id}/state",
    summary="Get client-visible onboarding state",
)
async def get_client_onboarding_state(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    principal: Authenticated,
) -> JSONResponse:
    """Return onboarding state filtered by responsibility mode.

    - managed:   client sees no actionable steps
    - co_managed: client sees only persisted agency-assigned steps
    - self_service: client sees all client-safe steps

    Authorization: requires organization membership or platform admin.
    """
    if not await _verify_organization_access(session, organization_id, principal):
        return _forbidden()

    is_admin = await _is_platform_admin(session, principal)
    state = await onboarding_service.get_client_state(
        session, organization_id, is_platform_admin=is_admin
    )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=_api_response(request, state.model_dump(mode="json")),
    )


# ---------------------------------------------------------------------------
# Self-service organization activation
# ---------------------------------------------------------------------------


@router.post(
    "/organizations/{organization_id}/activate",
    summary="Activate an organization (self-service)",
    responses={409: {"description": "Onboarding is not yet complete"}},
)
async def activate_self_service_organization(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
    principal: Authenticated,
) -> JSONResponse:
    """Activate an organization, failing closed if onboarding is incomplete.

    Uses the authoritative OnboardingOrchestrationService — never duplicates
    readiness calculations.
    """
    if not await _verify_organization_access(session, organization_id, principal):
        return _forbidden()

    state = await onboarding_service.get_state(session, organization_id)
    if not state.activation_eligible:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "error": {
                    "code": "ONBOARDING_INCOMPLETE",
                    "message": (
                        "This organization cannot be activated "
                        "until onboarding is complete."
                    ),
                    "category": "conflict",
                    "details": [
                        {
                            "field": "blocker",
                            "code": "ONBOARDING_BLOCKER",
                            "message": blocker,
                        }
                        for blocker in state.blockers
                    ],
                }
            },
        )

    organization = await organizations.transition(
        session,
        organization_id,
        action=OrganizationLifecycleAction.ACTIVATE,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=_api_response(
            request, OrganizationData.model_validate(organization).model_dump(mode="json")
        ),
    )