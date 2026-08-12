"""Always-mounted authenticated and authorized Phase 2/3 application routes."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.contracts import (
    AccessMutationResponse,
    AccessPagination,
    AssignmentData,
    CatalogResponse,
    DenyData,
    InvitationAccept,
    InvitationCreateByEmail,
    InvitationData,
    InvitationListResponse,
    InvitationResponse,
    MembershipCreateByEmail,
    MembershipData,
    MembershipLifecycleCommand,
    MembershipListResponse,
    MembershipResponse,
    MyOrganizationData,
    MyOrganizationsResponse,
    PermissionData,
    PermissionDenyCreate,
    RoleAssignmentCreate,
    RoleData,
)
from apps.api.app.access_control.enums import MembershipStatus, ScopeType
from apps.api.app.access_control.repository import CatalogRepository
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import AuthenticatedPrincipalResponse
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.business_identity.contracts import (
    LocationBusinessIdentityResponse,
    OrganizationBusinessIdentityResponse,
)
from apps.api.app.business_identity.service import BusinessIdentityService
from apps.api.app.database.session import get_database_session
from apps.api.app.domains.contracts import (
    OrganizationDomainArchive,
    OrganizationDomainCreate,
    OrganizationDomainData,
    OrganizationDomainListResponse,
    OrganizationDomainResponse,
    OrganizationDomainSetPrimary,
)
from apps.api.app.domains.service import OrganizationDomainService
from apps.api.app.errors import error_response, request_correlation_id
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
from apps.api.app.organizations.contracts import (
    OrganizationData,
    OrganizationIndustryAssignment,
    OrganizationResponse,
    OrganizationTransition,
)
from apps.api.app.organizations.enums import OrganizationLifecycleAction
from apps.api.app.organizations.service import OrganizationService
from apps.api.app.platform_admin.contracts import (
    PlatformAdministratorSelfStatus,
    PlatformAdministratorSelfStatusResponse,
)
from apps.api.app.platform_admin.service import PlatformAdministrationService
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
from apps.api.app.schemas import ErrorCategory, ResponseMeta

from apps.api.app.administration.catalog import PRODUCT_CATALOG
from apps.api.app.administration.enums import NOT_SELECTED_ENTITLEMENT_STATUSES
from apps.api.app.administration.service import AdministrationService

administration_service = AdministrationService()


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(get_authenticated_principal), Depends(no_store)],
)
organizations = APIRouter(prefix="/organizations/{organization_id}", tags=["organizations"])
access = APIRouter(prefix="/organizations/{organization_id}", tags=["organization-access"])
invitation_acceptance = APIRouter(prefix="/invitations", tags=["organization-access"])

organization_service = OrganizationService()
location_service = LocationService()
organization_profile_service = OrganizationProfileService()
location_profile_service = LocationProfileService()
group_service = LocationGroupService()
identity_service = BusinessIdentityService()
access_service = AccessControlService()
catalog_repository = CatalogRepository()
domain_service = OrganizationDomainService()
platform_admin_service = PlatformAdministrationService()

DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def meta(request: Request) -> ResponseMeta:
    return ResponseMeta(correlation_id=request_correlation_id(request))


@router.get("/me", response_model=AuthenticatedPrincipalResponse)
async def get_current_principal(
    request: Request,
    principal: Authenticated,
) -> AuthenticatedPrincipalResponse:
    return AuthenticatedPrincipalResponse(data=principal, meta=meta(request))


@router.get("/me/organizations", response_model=MyOrganizationsResponse)
async def list_my_organizations(
    request: Request,
    principal: Authenticated,
    session: DatabaseSession,
) -> MyOrganizationsResponse:
    """List the organizations the authenticated caller belongs to.

    Scoped entirely by the verified principal; no client-supplied identifier
    can widen this beyond the caller's own memberships.
    """
    pairs = await access_service.list_my_organizations(session, principal.platform_user_id)
    return MyOrganizationsResponse(
        data=[
            MyOrganizationData(
                organization_id=organization.id,
                organization_name=organization.name,
                organization_slug=organization.slug,
                organization_status=organization.status.value,
                membership_id=membership.id,
                membership_status=membership.status,
                membership_type=membership.membership_type,
            )
            for membership, organization in pairs
        ],
        meta=meta(request),
    )


@router.get("/me/platform-administrator", response_model=PlatformAdministratorSelfStatusResponse)
async def get_my_platform_administrator_status(
    request: Request,
    principal: Authenticated,
    session: DatabaseSession,
) -> PlatformAdministratorSelfStatusResponse:
    """Self-scoped: does the caller hold an active platform-administrator grant.

    Distinct from the fail-closed, non-disclosing 403
    ``require_platform_administrator`` returns to protect other tenants' data
    — this only ever discloses the caller's own standing, exactly as
    ``/api/v1/me`` already discloses their own identity and assurance level.
    """
    status_data: PlatformAdministratorSelfStatus = await platform_admin_service.self_status(
        session,
        user_profile_id=principal.platform_user_id,
        assurance_level=principal.assurance_level,
    )
    return PlatformAdministratorSelfStatusResponse(data=status_data, meta=meta(request))


def organization_policy(permission: str, *, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            permission,
            ScopeType.ORGANIZATION,
            AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1,
        )
    )


def location_policy(permission: str, *, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            permission,
            ScopeType.LOCATION,
            AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1,
        )
    )


@organizations.get("/products", dependencies=[Depends(no_store)])
async def get_organization_products(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("organization.read")],
) -> dict[str, object]:
    """Return the product keys entitled for the caller's organization.

    A client-readable contract for entitlement-aware navigation.  Returns
    each product's key and its entitlement status so the frontend can
    show entitled products even when readiness is blocked/setup_required.
    """
    entitled: list[dict[str, object]] = []
    for key in PRODUCT_CATALOG:
        product = await administration_service.catalog.get_product_by_key(session, key)
        if product is None:
            continue
        entitlement = await administration_service.entitlements.get_by_product(
            session, organization_id, product.id
        )
        # Reuse the canonical selected-entitlement rule from onboarding:
        # not_enabled and archived are not selected; suspended is selected
        # but not currently effective.  Readiness is evaluated separately.
        selected = (
            entitlement is not None
            and entitlement.status not in NOT_SELECTED_ENTITLEMENT_STATUSES
        )
        entitled.append(
            {
                "product_key": key,
                "entitled": selected,
                "entitlement_status": entitlement.status if entitlement else "not_enabled",
            }
        )
    return {"data": entitled, "meta": meta(request)}


@organizations.get("", response_model=OrganizationResponse)
async def get_organization(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("organization.read")],
) -> OrganizationResponse:
    item = await organization_service.get(session, organization_id)
    return OrganizationResponse(data=OrganizationData.model_validate(item), meta=meta(request))


async def transition_organization(
    request: Request,
    organization_id: UUID,
    command: OrganizationTransition,
    session: AsyncSession,
    action: OrganizationLifecycleAction,
) -> OrganizationResponse:
    item = await organization_service.transition(
        session,
        organization_id,
        action=action,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return OrganizationResponse(data=OrganizationData.model_validate(item), meta=meta(request))


def organization_transition_route(path: str, action: OrganizationLifecycleAction) -> None:
    async def endpoint(
        request: Request,
        organization_id: UUID,
        command: OrganizationTransition,
        session: DatabaseSession,
        _authorization: Annotated[
            AuthorizationDecision, organization_policy("organization.update")
        ],
    ) -> OrganizationResponse:
        return await transition_organization(request, organization_id, command, session, action)

    endpoint.__name__ = f"authorized_organization_{action.value}"
    organizations.post(f"/{path}", response_model=OrganizationResponse)(endpoint)


organization_transition_route("pause", OrganizationLifecycleAction.PAUSE)
organization_transition_route("suspend", OrganizationLifecycleAction.SUSPEND)
organization_transition_route("start-offboarding", OrganizationLifecycleAction.START_OFFBOARDING)


@organizations.post("/industry", response_model=OrganizationResponse)
async def set_industry(
    request: Request,
    organization_id: UUID,
    command: OrganizationIndustryAssignment,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.settings.manage")
    ],
) -> OrganizationResponse:
    item = await organization_service.set_industry(
        session,
        organization_id,
        industry_id=command.industry_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return OrganizationResponse(data=OrganizationData.model_validate(item), meta=meta(request))


@organizations.post(
    "/locations", response_model=LocationResponse, status_code=status.HTTP_201_CREATED
)
async def create_location(
    request: Request,
    organization_id: UUID,
    command: LocationCreate,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("locations.create")],
) -> LocationResponse:
    item = await location_service.create(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return LocationResponse(data=LocationData.model_validate(item), meta=meta(request))


@organizations.get("/locations", response_model=LocationListResponse)
async def list_locations(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("locations.read")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LocationListResponse:
    items, has_more = await location_service.list(
        session, organization_id, limit=limit, offset=offset
    )
    return LocationListResponse(
        data=[LocationData.model_validate(item) for item in items],
        pagination=LocationPagination(
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        ),
        meta=meta(request),
    )


@organizations.get("/locations/{location_id}", response_model=LocationResponse)
async def get_location(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, location_policy("locations.read")],
) -> LocationResponse:
    item = await location_service.get(session, organization_id, location_id)
    return LocationResponse(data=LocationData.model_validate(item), meta=meta(request))


def location_transition_route(path: str, action: LocationLifecycleAction) -> None:
    async def endpoint(
        request: Request,
        organization_id: UUID,
        location_id: UUID,
        command: LocationTransition,
        session: DatabaseSession,
        _authorization: Annotated[
            AuthorizationDecision, location_policy("locations.lifecycle.manage")
        ],
    ) -> LocationResponse:
        item = await location_service.transition(
            session,
            organization_id,
            location_id,
            action=action,
            expected_version=command.expected_version,
            correlation_id=request_correlation_id(request),
        )
        return LocationResponse(data=LocationData.model_validate(item), meta=meta(request))

    endpoint.__name__ = f"authorized_location_{action.value}"
    organizations.post(f"/locations/{{location_id}}/{path}", response_model=LocationResponse)(
        endpoint
    )


location_transition_route("activate", LocationLifecycleAction.ACTIVATE)
location_transition_route("pause", LocationLifecycleAction.PAUSE)
location_transition_route("close-temporarily", LocationLifecycleAction.CLOSE_TEMPORARILY)
location_transition_route("close-permanently", LocationLifecycleAction.CLOSE_PERMANENTLY)
location_transition_route("archive", LocationLifecycleAction.ARCHIVE)


@organizations.post(
    "/domains", response_model=OrganizationDomainResponse, status_code=status.HTTP_201_CREATED
)
async def create_domain(
    request: Request,
    organization_id: UUID,
    command: OrganizationDomainCreate,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.settings.manage")
    ],
) -> OrganizationDomainResponse:
    item = await domain_service.create(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return OrganizationDomainResponse(
        data=OrganizationDomainData.model_validate(item), meta=meta(request)
    )


@organizations.get("/domains", response_model=OrganizationDomainListResponse)
async def list_domains(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("organization.read")],
) -> OrganizationDomainListResponse:
    items = await domain_service.list(session, organization_id)
    return OrganizationDomainListResponse(
        data=[OrganizationDomainData.model_validate(item) for item in items], meta=meta(request)
    )


@organizations.post("/domains/{domain_id}/set-primary", response_model=OrganizationDomainResponse)
async def set_primary_domain(
    request: Request,
    organization_id: UUID,
    domain_id: UUID,
    command: OrganizationDomainSetPrimary,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.settings.manage")
    ],
) -> OrganizationDomainResponse:
    item = await domain_service.set_primary(
        session,
        organization_id,
        domain_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return OrganizationDomainResponse(
        data=OrganizationDomainData.model_validate(item), meta=meta(request)
    )


@organizations.post("/domains/{domain_id}/archive", response_model=OrganizationDomainResponse)
async def archive_domain(
    request: Request,
    organization_id: UUID,
    domain_id: UUID,
    command: OrganizationDomainArchive,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.settings.manage")
    ],
) -> OrganizationDomainResponse:
    item = await domain_service.archive(
        session,
        organization_id,
        domain_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return OrganizationDomainResponse(
        data=OrganizationDomainData.model_validate(item), meta=meta(request)
    )


def organization_profile_response(request: Request, item: object) -> OrganizationProfileResponse:
    return OrganizationProfileResponse(
        data=OrganizationProfileData.model_validate(item), meta=meta(request)
    )


@organizations.post(
    "/profile", response_model=OrganizationProfileResponse, status_code=status.HTTP_201_CREATED
)
async def create_organization_profile(
    request: Request,
    organization_id: UUID,
    command: OrganizationProfileCreate,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("profiles.update")],
) -> OrganizationProfileResponse:
    item = await organization_profile_service.create(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return organization_profile_response(request, item)


@organizations.get("/profile", response_model=OrganizationProfileResponse)
async def get_organization_profile(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("profiles.read")],
) -> OrganizationProfileResponse:
    return organization_profile_response(
        request, await organization_profile_service.get(session, organization_id)
    )


@organizations.put("/profile", response_model=OrganizationProfileResponse)
async def replace_organization_profile(
    request: Request,
    organization_id: UUID,
    command: OrganizationProfileReplace,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("profiles.update")],
) -> OrganizationProfileResponse:
    item = await organization_profile_service.replace(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return organization_profile_response(request, item)


def location_profile_response(request: Request, item: object) -> LocationProfileResponse:
    return LocationProfileResponse(
        data=LocationProfileData.model_validate(item), meta=meta(request)
    )


@organizations.post(
    "/locations/{location_id}/profile",
    response_model=LocationProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_location_profile(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    command: LocationProfileCreate,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, location_policy("profiles.update")],
) -> LocationProfileResponse:
    item = await location_profile_service.create(
        session,
        organization_id,
        location_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return location_profile_response(request, item)


@organizations.get("/locations/{location_id}/profile", response_model=LocationProfileResponse)
async def get_location_profile(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, location_policy("profiles.read")],
) -> LocationProfileResponse:
    return location_profile_response(
        request, await location_profile_service.get(session, organization_id, location_id)
    )


@organizations.put("/locations/{location_id}/profile", response_model=LocationProfileResponse)
async def replace_location_profile(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    command: LocationProfileReplace,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, location_policy("profiles.update")],
) -> LocationProfileResponse:
    item = await location_profile_service.replace(
        session,
        organization_id,
        location_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return location_profile_response(request, item)


@organizations.get("/business-identity", response_model=OrganizationBusinessIdentityResponse)
async def resolve_organization_identity(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("business_identity.read")],
) -> OrganizationBusinessIdentityResponse:
    return OrganizationBusinessIdentityResponse(
        data=await identity_service.resolve_organization(session, organization_id),
        meta=meta(request),
    )


@organizations.get(
    "/locations/{location_id}/business-identity",
    response_model=LocationBusinessIdentityResponse,
)
async def resolve_location_identity(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, location_policy("business_identity.read")],
) -> LocationBusinessIdentityResponse:
    return LocationBusinessIdentityResponse(
        data=await identity_service.resolve_location(session, organization_id, location_id),
        meta=meta(request),
    )


def group_response(request: Request, item: object) -> LocationGroupResponse:
    return LocationGroupResponse(data=LocationGroupData.model_validate(item), meta=meta(request))


@organizations.post(
    "/location-groups", response_model=LocationGroupResponse, status_code=status.HTTP_201_CREATED
)
async def create_group(
    request: Request,
    organization_id: UUID,
    command: LocationGroupCreate,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("locations.groups.manage")
    ],
) -> LocationGroupResponse:
    item = await group_service.create(
        session, organization_id, command, correlation_id=request_correlation_id(request)
    )
    return group_response(request, item)


@organizations.get("/location-groups", response_model=LocationGroupListResponse)
async def list_groups(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("locations.read")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LocationGroupListResponse:
    items, has_more = await group_service.list_groups(
        session, organization_id, limit=limit, offset=offset
    )
    return LocationGroupListResponse(
        data=[LocationGroupData.model_validate(item) for item in items],
        pagination=LocationGroupPagination(
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        ),
        meta=meta(request),
    )


@organizations.get("/location-groups/{group_id}", response_model=LocationGroupResponse)
async def get_group(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("locations.read")],
) -> LocationGroupResponse:
    return group_response(request, await group_service.get(session, organization_id, group_id))


@organizations.put("/location-groups/{group_id}", response_model=LocationGroupResponse)
async def replace_group(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    command: LocationGroupReplace,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("locations.groups.manage")
    ],
) -> LocationGroupResponse:
    item = await group_service.replace(
        session,
        organization_id,
        group_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return group_response(request, item)


@organizations.post("/location-groups/{group_id}/archive", response_model=LocationGroupResponse)
async def archive_group(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    command: LocationGroupArchive,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("locations.groups.manage")
    ],
) -> LocationGroupResponse:
    item = await group_service.archive(
        session,
        organization_id,
        group_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return group_response(request, item)


@organizations.get(
    "/location-groups/{group_id}/locations",
    response_model=LocationGroupMembershipListResponse,
)
async def list_group_memberships(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[AuthorizationDecision, organization_policy("locations.read")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LocationGroupMembershipListResponse:
    items, has_more = await group_service.list_members(
        session, organization_id, group_id, limit=limit, offset=offset
    )
    return LocationGroupMembershipListResponse(
        data=[LocationGroupMembershipData.model_validate(item) for item in items],
        pagination=LocationGroupPagination(
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        ),
        meta=meta(request),
    )


def group_membership_response(request: Request, item: object) -> LocationGroupMembershipResponse:
    return LocationGroupMembershipResponse(
        data=LocationGroupMembershipData.model_validate(item), meta=meta(request)
    )


@organizations.post(
    "/location-groups/{group_id}/locations/{location_id}",
    response_model=LocationGroupMembershipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_group_membership(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    location_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("locations.groups.manage")
    ],
) -> LocationGroupMembershipResponse:
    item = await group_service.add_membership(
        session,
        organization_id,
        group_id,
        location_id,
        correlation_id=request_correlation_id(request),
    )
    return group_membership_response(request, item)


@organizations.delete(
    "/location-groups/{group_id}/locations/{location_id}",
    response_model=LocationGroupMembershipResponse,
)
async def remove_group_membership(
    request: Request,
    organization_id: UUID,
    group_id: UUID,
    location_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("locations.groups.manage")
    ],
) -> LocationGroupMembershipResponse:
    item = await group_service.remove_membership(
        session,
        organization_id,
        group_id,
        location_id,
        correlation_id=request_correlation_id(request),
    )
    return group_membership_response(request, item)


@access.post("/memberships", response_model=MembershipResponse, status_code=status.HTTP_201_CREATED)
async def create_membership(
    request: Request,
    organization_id: UUID,
    command: MembershipCreateByEmail,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision,
        organization_policy("organization.members.manage", aal2=True),
    ],
) -> MembershipResponse:
    """Add an existing platform user (resolved by email) as an active member."""
    item = await access_service.create_membership_by_email(
        session,
        organization_id,
        email=command.email,
        membership_type=command.membership_type,
        correlation_id=request_correlation_id(request),
    )
    return MembershipResponse(data=MembershipData.model_validate(item), meta=meta(request))


@access.get("/memberships", response_model=MembershipListResponse)
async def list_memberships(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.members.manage")
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MembershipListResponse:
    items, has_more = await access_service.list_memberships(
        session, organization_id, limit=limit, offset=offset
    )
    return MembershipListResponse(
        data=[MembershipData.model_validate(item) for item in items],
        pagination=AccessPagination(
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        ),
        meta=meta(request),
    )


@access.get("/memberships/{membership_id}", response_model=MembershipResponse)
async def get_membership(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.members.manage")
    ],
) -> MembershipResponse:
    item = await access_service.get_membership(session, organization_id, membership_id)
    return MembershipResponse(data=MembershipData.model_validate(item), meta=meta(request))


def membership_transition_route(path: str, target: MembershipStatus) -> None:
    async def endpoint(
        request: Request,
        organization_id: UUID,
        membership_id: UUID,
        command: MembershipLifecycleCommand,
        session: DatabaseSession,
        _authorization: Annotated[
            AuthorizationDecision,
            organization_policy("organization.members.manage", aal2=True),
        ],
    ) -> MembershipResponse:
        item = await access_service.transition_membership(
            session,
            organization_id,
            membership_id,
            target=target,
            expected_version=command.expected_version,
            correlation_id=request_correlation_id(request),
        )
        return MembershipResponse(data=MembershipData.model_validate(item), meta=meta(request))

    endpoint.__name__ = f"authorized_membership_{target.value}"
    access.post(f"/memberships/{{membership_id}}/{path}", response_model=MembershipResponse)(
        endpoint
    )


membership_transition_route("suspend", MembershipStatus.SUSPENDED)
membership_transition_route("restore", MembershipStatus.ACTIVE)
membership_transition_route("revoke", MembershipStatus.REVOKED)


@access.post("/invitations", response_model=InvitationResponse, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    request: Request,
    organization_id: UUID,
    command: InvitationCreateByEmail,
    session: DatabaseSession,
    principal: Authenticated,
    _authorization: Annotated[
        AuthorizationDecision,
        organization_policy("organization.invitations.manage", aal2=True),
    ],
) -> InvitationResponse:
    """Invite an existing platform user (resolved by email) to this organization.

    The invitation remains pending until the invitee, already signed in with
    the matching email, accepts it via ``POST /api/v1/invitations/accept``.
    """
    invitation, _token = await access_service.create_invitation_by_email(
        session,
        organization_id,
        email=command.email,
        membership_type=command.membership_type,
        invited_by_user_profile_id=principal.platform_user_id,
        lifetime_days=command.lifetime_days,
        correlation_id=request_correlation_id(request),
    )
    return InvitationResponse(data=InvitationData.model_validate(invitation), meta=meta(request))


@access.get("/invitations", response_model=InvitationListResponse)
async def list_invitations(
    request: Request,
    organization_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.invitations.manage")
    ],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> InvitationListResponse:
    items, has_more = await access_service.list_invitations(
        session, organization_id, limit=limit, offset=offset
    )
    return InvitationListResponse(
        data=[InvitationData.model_validate(item) for item in items],
        pagination=AccessPagination(
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        ),
        meta=meta(request),
    )


@access.get("/invitations/{invitation_id}", response_model=InvitationResponse)
async def get_invitation(
    request: Request,
    organization_id: UUID,
    invitation_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.invitations.manage")
    ],
) -> InvitationResponse:
    item = await access_service.get_invitation(session, organization_id, invitation_id)
    return InvitationResponse(data=InvitationData.model_validate(item), meta=meta(request))


@access.post("/invitations/{invitation_id}/cancel", response_model=InvitationResponse)
async def cancel_invitation(
    request: Request,
    organization_id: UUID,
    invitation_id: UUID,
    command: MembershipLifecycleCommand,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision,
        organization_policy("organization.invitations.manage", aal2=True),
    ],
) -> InvitationResponse:
    item = await access_service.cancel_invitation(
        session,
        organization_id,
        invitation_id,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return InvitationResponse(data=InvitationData.model_validate(item), meta=meta(request))


@invitation_acceptance.post("/accept", response_model=InvitationResponse)
async def accept_invitation(
    request: Request,
    response: Response,
    command: InvitationAccept,
    principal: Authenticated,
    session: DatabaseSession,
) -> InvitationResponse | JSONResponse:
    response.headers["Cache-Control"] = "no-store"
    result = await access_service.accept_invitation(
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


@access.post(
    "/memberships/{membership_id}/role-assignments",
    response_model=AccessMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_role_assignment(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    command: RoleAssignmentCreate,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.roles.manage", aal2=True)
    ],
) -> AccessMutationResponse:
    item = await access_service.add_assignment(
        session,
        organization_id,
        membership_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return AccessMutationResponse(data=AssignmentData.model_validate(item), meta=meta(request))


@access.delete(
    "/memberships/{membership_id}/role-assignments/{assignment_id}",
    response_model=AccessMutationResponse,
)
async def remove_role_assignment(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    assignment_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.roles.manage", aal2=True)
    ],
) -> AccessMutationResponse:
    item = await access_service.remove_assignment(
        session,
        organization_id,
        membership_id,
        assignment_id,
        correlation_id=request_correlation_id(request),
    )
    return AccessMutationResponse(data=AssignmentData.model_validate(item), meta=meta(request))


@access.post(
    "/memberships/{membership_id}/permission-denies",
    response_model=AccessMutationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_permission_deny(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    command: PermissionDenyCreate,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.roles.manage", aal2=True)
    ],
) -> AccessMutationResponse:
    item = await access_service.add_deny(
        session,
        organization_id,
        membership_id,
        command,
        correlation_id=request_correlation_id(request),
    )
    return AccessMutationResponse(data=DenyData.model_validate(item), meta=meta(request))


@access.delete(
    "/memberships/{membership_id}/permission-denies/{deny_id}",
    response_model=AccessMutationResponse,
)
async def remove_permission_deny(
    request: Request,
    organization_id: UUID,
    membership_id: UUID,
    deny_id: UUID,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.roles.manage", aal2=True)
    ],
) -> AccessMutationResponse:
    item = await access_service.remove_deny(
        session,
        organization_id,
        membership_id,
        deny_id,
        correlation_id=request_correlation_id(request),
    )
    return AccessMutationResponse(data=DenyData.model_validate(item), meta=meta(request))


@access.get("/access/roles", response_model=CatalogResponse)
async def list_roles(
    request: Request,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.roles.manage")
    ],
) -> CatalogResponse:
    roles = await catalog_repository.list_roles(session)
    return CatalogResponse(
        data=[RoleData.model_validate(item) for item in roles],
        meta=meta(request),
    )


@access.get("/access/permissions", response_model=CatalogResponse)
async def list_permissions(
    request: Request,
    session: DatabaseSession,
    _authorization: Annotated[
        AuthorizationDecision, organization_policy("organization.roles.manage")
    ],
) -> CatalogResponse:
    return CatalogResponse(
        data=[
            PermissionData.model_validate(item)
            for item in await catalog_repository.list_permissions(session)
        ],
        meta=meta(request),
    )


router.include_router(organizations)
router.include_router(access)
router.include_router(invitation_acceptance)
