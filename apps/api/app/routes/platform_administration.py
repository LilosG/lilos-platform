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

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.contracts import (
    DataResponse,
    EntitlementCreate,
    EntitlementTransition,
)
from apps.api.app.administration.errors import (
    AdministrationConflictError,
    AdministrationNotFoundError,
    AdministrationVersionConflictError,
    ReadinessBlockedError,
)
from apps.api.app.administration.service import AdministrationService
from apps.api.app.authentication.contracts import UserProfileCreate
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.database.session import get_database_session
from apps.api.app.domains.contracts import (
    OrganizationDomainArchive,
    OrganizationDomainCreate,
    OrganizationDomainData,
    OrganizationDomainSetPrimary,
)
from apps.api.app.domains.service import OrganizationDomainService
from apps.api.app.errors import error_response, request_correlation_id
from apps.api.app.industries.contracts import IndustryData
from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.repository import MAX_INDUSTRY_LIST_LIMIT
from apps.api.app.industries.service import IndustryService
from apps.api.app.locations.contracts import LocationCreate, LocationData, LocationTransition
from apps.api.app.locations.enums import LocationLifecycleAction
from apps.api.app.locations.service import LocationService
from apps.api.app.onboarding.contracts import (
    OnboardingModeSetRequest,
    OnboardingStateResponse,
    StepAssignmentRequest,
)
from apps.api.app.onboarding.service import OnboardingOrchestrationService
from apps.api.app.onboarding.website_provisioning import (
    OnboardingWebsiteProvisioningService,
)
from apps.api.app.organizations.contracts import (
    OrganizationCreate,
    OrganizationData,
    OrganizationIndustryAssignment,
    OrganizationTransition,
)
from apps.api.app.organizations.enums import OrganizationLifecycleAction
from apps.api.app.organizations.service import OrganizationService
from apps.api.app.platform_admin.dependencies import require_platform_administrator
from apps.api.app.platform_admin.service import PlatformAdministrationService
from apps.api.app.profiles.contracts import OrganizationProfileCreate, OrganizationProfileData
from apps.api.app.profiles.errors import OrganizationProfileNotFoundError
from apps.api.app.profiles.service import OrganizationProfileService
from apps.api.app.schemas import ErrorCategory, ErrorDetail, ResponseMeta


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
onboarding_service = OnboardingOrchestrationService()
website_provisioning = OnboardingWebsiteProvisioningService()
organization_profiles = OrganizationProfileService()
organization_domains = OrganizationDomainService()
administration = AdministrationService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def response(request: Request, data: object) -> DataResponse:
    return DataResponse(
        data=data, meta=ResponseMeta(correlation_id=request_correlation_id(request))
    )


def _row(item: Any) -> dict[str, Any]:
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


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
    responses={409: {"description": "Onboarding is not yet complete; see error.blockers"}},
)
async def activate_organization(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: DatabaseSession,
) -> DataResponse | JSONResponse:
    """Activate an organization, failing closed if onboarding is incomplete.

    The frontend never decides activation eligibility itself: this route
    recomputes the authoritative ``OnboardingState`` server-side on every
    call and rejects the transition (409, with the exact blocker list) unless
    ``activation_eligible`` is true.
    """
    state = await onboarding_service.get_state(session, organization_id)
    if not state.activation_eligible:
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="ONBOARDING_INCOMPLETE",
            message="This organization cannot be activated until onboarding is complete.",
            category=ErrorCategory.CONFLICT,
            details=[
                ErrorDetail(field="blocker", code="ONBOARDING_BLOCKER", message=blocker)
                for blocker in state.blockers
            ],
        )
    activated = await _transition_organization(
        request, organization_id, command, session, OrganizationLifecycleAction.ACTIVATE
    )
    # Activation is the point where the configured primary domain becomes a
    # crawlable website: eligibility already guarantees the domain and primary
    # location exist. Provisioning shares this transaction, so the client is
    # either active with a website and a queued first crawl, or not active.
    await website_provisioning.provision(
        session,
        organization_id,
        actor_id=None,
        correlation_id=request_correlation_id(request),
    )
    return activated


@router.get(
    "/organizations/{organization_id}/onboarding-state",
    response_model=OnboardingStateResponse,
    summary="Get the consolidated client-onboarding readiness state",
)
async def get_onboarding_state(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
) -> OnboardingStateResponse:
    state = await onboarding_service.get_state(session, organization_id)
    return OnboardingStateResponse(
        data=state, meta=ResponseMeta(correlation_id=request_correlation_id(request))
    )


@router.post(
    "/organizations/{organization_id}/reconcile-defaults",
    response_model=DataResponse,
    summary="Provision intended safe defaults an existing client may lack",
)
async def reconcile_organization_defaults(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    principal: Authenticated,
) -> DataResponse:
    """Idempotently provision the default approval policy if none exists.

    Existing organizations that predate the default-policy provisioning in
    ``create_entitlement`` would otherwise remain permanently blocked by
    ``APPROVAL_POLICY_MISSING``. This gives them a one-click recovery path
    without manual SQL, without overwriting a custom policy, audited.
    """
    result = await administration.reconcile_defaults(
        session,
        organization_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return response(request, result)


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
    "/organizations/{organization_id}/industry",
    response_model=DataResponse,
    summary="Assign the organization's industry during onboarding",
)
async def set_organization_industry(
    request: Request,
    organization_id: UUID,
    command: OrganizationIndustryAssignment,
    session: DatabaseSession,
) -> DataResponse:
    organization = await organizations.set_industry(
        session,
        organization_id,
        industry_id=command.industry_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return response(request, OrganizationData.model_validate(organization))


@router.post(
    "/organizations/{organization_id}/profile",
    response_model=DataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create the organization profile during onboarding",
)
async def create_organization_profile(
    request: Request,
    organization_id: UUID,
    command: OrganizationProfileCreate,
    session: DatabaseSession,
) -> DataResponse:
    profile = await organization_profiles.create(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return response(request, OrganizationProfileData.model_validate(profile))


@router.get(
    "/organizations/{organization_id}/profile",
    response_model=DataResponse,
    summary="Get the organization profile",
    responses={404: {"description": "No profile has been created yet"}},
)
async def get_organization_profile(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
) -> DataResponse:
    try:
        profile = await organization_profiles.get(session, organization_id)
    except OrganizationProfileNotFoundError:
        return response(request, None)
    return response(request, OrganizationProfileData.model_validate(profile))


@router.post(
    "/organizations/{organization_id}/domains",
    response_model=DataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an approved domain during onboarding",
)
async def create_organization_domain(
    request: Request,
    organization_id: UUID,
    command: OrganizationDomainCreate,
    session: DatabaseSession,
) -> DataResponse:
    domain = await organization_domains.create(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return response(request, OrganizationDomainData.model_validate(domain))


@router.get(
    "/organizations/{organization_id}/domains",
    response_model=DataResponse,
    summary="List approved domains",
)
async def list_organization_domains(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
) -> DataResponse:
    domains = await organization_domains.list(session, organization_id)
    return response(request, [OrganizationDomainData.model_validate(item) for item in domains])


@router.post(
    "/organizations/{organization_id}/domains/{domain_id}/set-primary",
    response_model=DataResponse,
    summary="Mark a domain as the primary domain",
)
async def set_primary_organization_domain(
    request: Request,
    organization_id: UUID,
    domain_id: UUID,
    command: OrganizationDomainSetPrimary,
    session: DatabaseSession,
) -> DataResponse:
    domain = await organization_domains.set_primary(
        session,
        organization_id,
        domain_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return response(request, OrganizationDomainData.model_validate(domain))


@router.post(
    "/organizations/{organization_id}/domains/{domain_id}/archive",
    response_model=DataResponse,
    summary="Archive a domain",
)
async def archive_organization_domain(
    request: Request,
    organization_id: UUID,
    domain_id: UUID,
    command: OrganizationDomainArchive,
    session: DatabaseSession,
) -> DataResponse:
    domain = await organization_domains.archive(
        session,
        organization_id,
        domain_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return response(request, OrganizationDomainData.model_validate(domain))


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


@router.get(
    "/organizations/{organization_id}/product-entitlements",
    response_model=DataResponse,
    summary="List product entitlements for an organization",
)
async def list_product_entitlements(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
) -> DataResponse:
    items = await administration.entitlements.list_by_organization(session, organization_id)
    return response(request, [_row(item) for item in items])


@router.post(
    "/organizations/{organization_id}/product-entitlements",
    response_model=DataResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a product entitlement during onboarding",
    responses={
        409: {"description": "Entitlement already exists or product not seeded"},
    },
)
async def create_product_entitlement(
    request: Request,
    organization_id: UUID,
    command: EntitlementCreate,
    session: DatabaseSession,
    principal: Authenticated,
) -> DataResponse | JSONResponse:
    """Create a product entitlement for an organization during onboarding.

    Reuses ``AdministrationService.create_entitlement`` verbatim — the same
    governed service the per-organization ``products.entitlements.manage``
    route uses — so audit events, integrity guards, and lifecycle protections
    are identical.  The platform administrator's ``platform_user_id`` is
    attributed as the audit actor, exactly as a per-organization admin would
    be through the standard route.

    This eliminates the need for ``scripts/provision_gbp_entitlement.py``:
    normal client onboarding can now enable products through the application
    API instead of a manual database script.
    """
    try:
        item = await administration.create_entitlement(
            session,
            organization_id,
            command,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except AdministrationNotFoundError:
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="PRODUCT_NOT_SEEDED",
            message="The requested product is not seeded in the catalog.",
            category=ErrorCategory.CONFLICT,
        )
    except AdministrationConflictError:
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="ENTITLEMENT_CONFLICT",
            message="An entitlement already exists for this product or the dates are invalid.",
            category=ErrorCategory.CONFLICT,
        )
    return response(request, _row(item))


@router.post(
    "/organizations/{organization_id}/product-entitlements/{entitlement_id}/transition",
    response_model=DataResponse,
    summary="Transition a product entitlement's lifecycle state",
    responses={
        409: {
            "description": "Transition not allowed from current status, or readiness not met",
        },
    },
)
async def transition_product_entitlement(
    request: Request,
    organization_id: UUID,
    entitlement_id: UUID,
    command: EntitlementTransition,
    session: DatabaseSession,
    principal: Authenticated,
) -> DataResponse | JSONResponse:
    try:
        item = await administration.transition_entitlement(
            session,
            organization_id,
            entitlement_id,
            command,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except AdministrationNotFoundError:
        return error_response(
            request,
            status_code=status.HTTP_404_NOT_FOUND,
            code="ENTITLEMENT_NOT_FOUND",
            message="No entitlement found for this organization with that id.",
            category=ErrorCategory.NOT_FOUND,
        )
    except AdministrationVersionConflictError:
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="VERSION_CONFLICT",
            message="The entitlement version does not match; reload and retry.",
            category=ErrorCategory.CONFLICT,
        )
    except AdministrationConflictError:
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="TRANSITION_NOT_ALLOWED",
            message=(
                "The requested transition is not allowed from the current "
                "status, or readiness is not met."
            ),
            category=ErrorCategory.CONFLICT,
        )
    except ReadinessBlockedError:
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="READINESS_NOT_MET",
            message="The product is not ready to activate; resolve blocking requirements first.",
            category=ErrorCategory.CONFLICT,
        )
    return response(request, _row(item))


# ---------------------------------------------------------------------------
# Onboarding responsibility mode and co-managed step assignment
# ---------------------------------------------------------------------------


@router.post(
    "/organizations/{organization_id}/onboarding-mode",
    response_model=DataResponse,
    summary="Set the onboarding responsibility mode",
)
async def set_onboarding_mode(
    request: Request,
    organization_id: UUID,
    command: OnboardingModeSetRequest,
    session: DatabaseSession,
) -> DataResponse | JSONResponse:
    """Set managed, co_managed, or self_service mode for this organization.

    This controls who may perform each onboarding step but does not alter
    the underlying definition of completion/readiness.
    """
    organization = await organizations.get(session, organization_id)
    if command.expected_version != organization.version:
        return error_response(
            request,
            status_code=status.HTTP_409_CONFLICT,
            code="VERSION_CONFLICT",
            message="The organization version does not match; reload and retry.",
            category=ErrorCategory.CONFLICT,
        )
    await onboarding_service.set_onboarding_mode(session, organization_id, command.mode)
    await session.refresh(organization)
    return response(request, OrganizationData.model_validate(organization))


@router.post(
    "/organizations/{organization_id}/onboarding-assign",
    response_model=DataResponse,
    summary="Assign a co-managed onboarding step to agency or client",
)
async def assign_onboarding_step(
    request: Request,
    organization_id: UUID,
    command: StepAssignmentRequest,
    session: DatabaseSession,
) -> DataResponse | JSONResponse:
    """Assign a step in co-managed mode to 'agency' or 'client'.

    Only steps declared as co_managed_clientable may be assigned to the
    client. Agency may always take any step.
    """
    try:
        assignment = await onboarding_service.assign_step(
            session, organization_id, command.step_key, command.assigned_to
        )
    except ValueError as exc:
        return error_response(
            request,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_ASSIGNMENT",
            message=str(exc),
            category=ErrorCategory.VALIDATION,
        )
    return response(
        request,
        {
            "step_key": assignment.step_key,
            "assigned_to": assignment.assigned_to,
            "assigned_at": assignment.assigned_at.isoformat(),
        },
    )


@router.get(
    "/organizations/{organization_id}/onboarding-assign",
    response_model=DataResponse,
    summary="List co-managed step assignments",
)
async def list_step_assignments(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
) -> DataResponse:
    assignments = await onboarding_service.get_assignments(session, organization_id)
    return response(
        request,
        [{"step_key": a.step_key, "assigned_to": a.assigned_to} for a in assignments],
    )
