"""Integration and negative tests for deterministic authorization evaluation."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import (
    MembershipCreate,
    PermissionDenyCreate,
    RoleAssignmentCreate,
)
from apps.api.app.access_control.enums import MembershipStatus, MembershipType, ScopeType
from apps.api.app.access_control.models import OrganizationMembership
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.enums import EntitlementStatus
from apps.api.app.administration.models import ProductEntitlement, ProductEntitlementLocation
from apps.api.app.administration.repository import AdministrationCatalogRepository
from apps.api.app.authentication.contracts import AuthenticatedPrincipal
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.authorization.contracts import AuthorizationRequest
from apps.api.app.authorization.enums import AuthorizationReason
from apps.api.app.authorization.service import AuthorizationService
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.platform_admin.dependencies import require_platform_administrator
from apps.api.app.platform_admin.models import PlatformAdministrator


def make_organization(
    slug: str, status: OrganizationStatus = OrganizationStatus.ACTIVE
) -> Organization:
    return Organization(
        id=uuid4(),
        name=slug.title(),
        slug=slug,
        organization_type=OrganizationType.TEST,
        status=status,
        timezone="UTC",
        default_currency="USD",
        archived_at=datetime.now(UTC) if status is OrganizationStatus.ARCHIVED else None,
        version=1,
    )


def make_user(status: UserStatus = UserStatus.ACTIVE) -> UserProfile:
    return UserProfile(
        id=uuid4(),
        auth_user_id=uuid4(),
        status=status,
        deactivated_at=datetime.now(UTC) if status is UserStatus.DEACTIVATED else None,
        version=1,
    )


def make_location(organization_id: UUID, slug: str) -> Location:
    return Location(
        organization_id=organization_id,
        name=slug.title(),
        slug=slug,
        location_type=LocationType.VIRTUAL,
        status=LocationStatus.ARCHIVED,
        timezone="UTC",
        country_code="US",
        website_url="https://example.invalid",
        is_primary=False,
        archived_at=datetime.now(UTC),
        version=1,
    )


def principal(
    profile: UserProfile, aal: AssuranceLevel = AssuranceLevel.AAL1
) -> AuthenticatedPrincipal:
    now = datetime.now(UTC)
    return AuthenticatedPrincipal(
        platform_user_id=profile.id,
        auth_user_id=profile.auth_user_id,
        user_status=profile.status,
        session_id=uuid4(),
        assurance_level=aal,
        token_issued_at=now,
        token_expires_at=now + timedelta(minutes=5),
    )


def request(
    profile: UserProfile,
    organization: Organization,
    permission: str,
    *,
    location: Location | None = None,
    minimum: AssuranceLevel = AssuranceLevel.AAL1,
) -> AuthorizationRequest:
    return AuthorizationRequest(
        platform_user_id=profile.id,
        organization_id=organization.id,
        permission_key=permission,
        resource_scope=ScopeType.LOCATION if location else ScopeType.ORGANIZATION,
        location_id=location.id if location else None,
        minimum_assurance_level=minimum,
    )


async def add_entitlement(
    session: AsyncSession,
    organization_id: UUID,
    product_key: str,
    *,
    status: EntitlementStatus,
    effective_from: datetime | None = None,
    effective_until: datetime | None = None,
    location_rows: tuple[tuple[UUID, str], ...] = (),
) -> ProductEntitlement:
    product = await AdministrationCatalogRepository().get_product_by_key(session, product_key)
    assert product is not None
    item = ProductEntitlement(
        organization_id=organization_id,
        product_id=product.id,
        status=status.value,
        source="authorization_test",
        reason="Authorization entitlement fixture.",
        effective_from=effective_from or datetime.now(UTC),
        effective_until=effective_until,
        version=1,
    )
    session.add(item)
    await session.flush()
    session.add_all(
        [
            ProductEntitlementLocation(
                organization_id=organization_id,
                entitlement_id=item.id,
                location_id=location_id,
                status=location_status,
                version=1,
            )
            for location_id, location_status in location_rows
        ]
    )
    await session.flush()
    return item


@pytest.mark.integration
def test_role_allows_are_additive_scoped_and_domain_lifecycle_is_not_duplicated(
    authorization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        access, evaluator, seeder = (
            AccessControlService(),
            AuthorizationService(),
            AccessCatalogSeeder(),
        )
        async with authorization_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="authz-catalog")
            organization = make_organization("evaluator-one")
            profile = make_user()
            session.add_all([organization, profile])
            await session.flush()
            first = make_location(organization.id, "archived-one")
            second = make_location(organization.id, "archived-two")
            session.add_all([first, second])
            await session.flush()
            membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id="member",
            )
            member_role = await access.catalog.get_role_by_key(session, "organization_member")
            manager_role = await access.catalog.get_role_by_key(session, "organization_manager")
            assert member_role is not None and manager_role is not None
            organization_assignment = await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(role_id=member_role.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="org-role",
            )
            location_assignment = await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(
                    role_id=manager_role.id,
                    scope_type=ScopeType.LOCATION,
                    location_id=first.id,
                ),
                correlation_id="location-role",
            )

        async with authorization_session_factory() as session:
            read = await evaluator.evaluate(
                session,
                principal(profile),
                request(profile, organization, "organization.read"),
                correlation_id="read",
            )
            assert read.allowed and read.applicable_role_assignment_ids == (
                organization_assignment.id,
            )
            first_update = await evaluator.evaluate(
                session,
                principal(profile),
                request(profile, organization, "locations.update", location=first),
                correlation_id="first-update",
            )
            assert first_update.allowed
            assert first_update.applicable_role_assignment_ids == (location_assignment.id,)
            second_update = await evaluator.evaluate(
                session,
                principal(profile),
                request(profile, organization, "locations.update", location=second),
                correlation_id="second-update",
            )
            assert not second_update.allowed
            assert second_update.reason_code is AuthorizationReason.PERMISSION_NOT_GRANTED
            organization_update = await evaluator.evaluate(
                session,
                principal(profile),
                request(profile, organization, "organization.update"),
                correlation_id="org-update",
            )
            assert not organization_update.allowed
            # Archived location ownership is resolvable; lifecycle validity remains downstream.
            assert first_update.reason_code is AuthorizationReason.ALLOWED

    asyncio.run(exercise())


@pytest.mark.integration
def test_denies_override_all_roles_and_remain_location_scoped(
    authorization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        access, evaluator, seeder = (
            AccessControlService(),
            AuthorizationService(),
            AccessCatalogSeeder(),
        )
        async with authorization_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="deny-catalog")
            organization, profile = make_organization("deny-org"), make_user()
            session.add_all([organization, profile])
            await session.flush()
            first, second = (
                make_location(organization.id, "deny-one"),
                make_location(organization.id, "deny-two"),
            )
            session.add_all([first, second])
            await session.flush()
            membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(
                    user_profile_id=profile.id, membership_type=MembershipType.INTERNAL
                ),
                correlation_id="member",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            read = await access.catalog.get_permission_by_key(session, "organization.read")
            locations_read = await access.catalog.get_permission_by_key(session, "locations.read")
            assert owner and read and locations_read
            await access.add_assignment(
                session,
                organization.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="owner",
            )
            organization_deny = await access.add_deny(
                session,
                organization.id,
                membership.id,
                PermissionDenyCreate(permission_id=read.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="org-deny",
            )
            location_deny = await access.add_deny(
                session,
                organization.id,
                membership.id,
                PermissionDenyCreate(
                    permission_id=locations_read.id,
                    scope_type=ScopeType.LOCATION,
                    location_id=first.id,
                ),
                correlation_id="location-deny",
            )
        async with authorization_session_factory() as session:
            denied = await evaluator.evaluate(
                session,
                principal(profile),
                request(profile, organization, "organization.read"),
                correlation_id="owner-denied",
            )
            assert denied.reason_code is AuthorizationReason.EXPLICIT_DENY
            assert denied.applicable_deny_ids == (organization_deny.id,)
            first_result = await evaluator.evaluate(
                session,
                principal(profile),
                request(profile, organization, "locations.read", location=first),
                correlation_id="first-denied",
            )
            assert first_result.reason_code is AuthorizationReason.EXPLICIT_DENY
            assert first_result.applicable_deny_ids == (location_deny.id,)
            second_result = await evaluator.evaluate(
                session,
                principal(profile),
                request(profile, organization, "locations.read", location=second),
                correlation_id="second-allowed",
            )
            assert second_result.allowed

    asyncio.run(exercise())


@pytest.mark.integration
def test_every_membership_state_and_membership_type_are_enforced_without_side_effects(
    authorization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        evaluator, seeder = AuthorizationService(), AccessCatalogSeeder()
        async with authorization_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="membership-state-catalog")
            organization = make_organization("membership-states")
            session.add(organization)
            await session.flush()
            cases: list[tuple[UserProfile, OrganizationMembership]] = []
            now = datetime.now(UTC)
            for index, status in enumerate(MembershipStatus):
                profile = make_user()
                session.add(profile)
                await session.flush()
                membership = OrganizationMembership(
                    organization_id=organization.id,
                    user_profile_id=profile.id,
                    membership_type=list(MembershipType)[index % len(MembershipType)],
                    status=status,
                    invited_at=now
                    if status in {MembershipStatus.INVITED, MembershipStatus.EXPIRED}
                    else None,
                    activated_at=now
                    if status in {MembershipStatus.ACTIVE, MembershipStatus.SUSPENDED}
                    else None,
                    suspended_at=now if status is MembershipStatus.SUSPENDED else None,
                    revoked_at=now if status is MembershipStatus.REVOKED else None,
                    expired_at=now if status is MembershipStatus.EXPIRED else None,
                    version=1,
                )
                session.add(membership)
                cases.append((profile, membership))
        async with authorization_session_factory() as session:
            for profile, membership in cases:
                before = membership.status
                result = await evaluator.evaluate(
                    session,
                    principal(profile),
                    request(profile, organization, "organization.read"),
                    correlation_id=f"membership-{before.value}",
                )
                if before is MembershipStatus.ACTIVE:
                    assert result.reason_code is AuthorizationReason.PERMISSION_NOT_GRANTED
                else:
                    assert result.reason_code is AuthorizationReason.MEMBERSHIP_INACTIVE
                stored = await session.get(OrganizationMembership, membership.id)
                assert stored is not None and stored.status is before

    asyncio.run(exercise())


@pytest.mark.integration
def test_fixed_role_taxonomy_enforces_catalog_permissions(
    authorization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        access, evaluator, seeder = (
            AccessControlService(),
            AuthorizationService(),
            AccessCatalogSeeder(),
        )
        async with authorization_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="role-taxonomy")
            organization = make_organization("role-taxonomy")
            session.add(organization)
            await session.flush()
            cases: dict[str, tuple[UserProfile, OrganizationMembership]] = {}
            for role_key in (
                "organization_owner",
                "organization_admin",
                "organization_manager",
                "organization_member",
                "organization_viewer",
            ):
                profile = make_user()
                session.add(profile)
                await session.flush()
                membership = await access.create_membership(
                    session,
                    organization.id,
                    MembershipCreate(
                        user_profile_id=profile.id, membership_type=MembershipType.CLIENT
                    ),
                    correlation_id=f"member-{role_key}",
                )
                role = await access.catalog.get_role_by_key(session, role_key)
                assert role is not None
                await access.add_assignment(
                    session,
                    organization.id,
                    membership.id,
                    RoleAssignmentCreate(role_id=role.id, scope_type=ScopeType.ORGANIZATION),
                    correlation_id=f"assignment-{role_key}",
                )
                cases[role_key] = (profile, membership)
        async with authorization_session_factory() as session:
            for role_key, (profile, _) in cases.items():
                read = await evaluator.evaluate(
                    session,
                    principal(profile),
                    request(profile, organization, "organization.read"),
                    correlation_id=f"read-{role_key}",
                )
                assert read.allowed
            for role_key in ("organization_owner", "organization_admin"):
                profile = cases[role_key][0]
                update_result = await evaluator.evaluate(
                    session,
                    principal(profile),
                    request(profile, organization, "organization.update"),
                    correlation_id=f"update-{role_key}",
                )
                assert update_result.allowed
            admin = cases["organization_admin"][0]
            admin_roles = await evaluator.evaluate(
                session,
                principal(admin),
                request(admin, organization, "organization.roles.manage"),
                correlation_id="admin-role-management",
            )
            assert admin_roles.reason_code is AuthorizationReason.PERMISSION_NOT_GRANTED
            for role_key in ("organization_manager", "organization_member", "organization_viewer"):
                profile = cases[role_key][0]
                update_result = await evaluator.evaluate(
                    session,
                    principal(profile),
                    request(profile, organization, "organization.update"),
                    correlation_id=f"limited-{role_key}",
                )
                assert not update_result.allowed

    asyncio.run(exercise())


@pytest.mark.integration
def test_user_organization_membership_mfa_isolation_and_catalog_fail_closed(
    authorization_session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def exercise() -> None:
        evaluator, seeder = AuthorizationService(), AccessCatalogSeeder()
        async with authorization_session_factory.begin() as session:
            await seeder.seed(session, correlation_id="state-catalog")
            active_org = make_organization("state-active")
            other_org = make_organization("state-other")
            active_user = make_user()
            deactivated_user = make_user(UserStatus.DEACTIVATED)
            session.add_all([active_org, other_org, active_user, deactivated_user])
            await session.flush()
            active_location = make_location(active_org.id, "state-location")
            other_location = make_location(other_org.id, "other-location")
            session.add_all([active_location, other_location])
            membership = OrganizationMembership(
                organization_id=active_org.id,
                user_profile_id=active_user.id,
                membership_type=MembershipType.SUPPORT,
                status=MembershipStatus.SUSPENDED,
                activated_at=datetime.now(UTC),
                suspended_at=datetime.now(UTC),
                version=1,
            )
            session.add(membership)
        with caplog.at_level(logging.INFO, logger="lilos.security.authorization"):
            async with authorization_session_factory() as session:
                missing = await evaluator.evaluate(
                    session,
                    principal(deactivated_user),
                    request(deactivated_user, active_org, "organization.read"),
                    correlation_id="deactivated",
                )
                assert missing.reason_code is AuthorizationReason.USER_INACTIVE
                inactive = await evaluator.evaluate(
                    session,
                    principal(active_user),
                    request(active_user, active_org, "organization.read"),
                    correlation_id="membership-inactive",
                )
                assert inactive.reason_code is AuthorizationReason.MEMBERSHIP_INACTIVE
                cross_location = await evaluator.evaluate(
                    session,
                    principal(active_user),
                    request(active_user, active_org, "locations.read", location=other_location),
                    correlation_id="cross-location",
                )
                assert cross_location.reason_code is AuthorizationReason.MEMBERSHIP_INACTIVE
                insufficient = await evaluator.evaluate(
                    session,
                    principal(active_user),
                    request(
                        active_user,
                        active_org,
                        "organization.read",
                        minimum=AssuranceLevel.AAL2,
                    ),
                    correlation_id="aal2",
                )
                assert insufficient.reason_code is AuthorizationReason.MEMBERSHIP_INACTIVE
        log_text = caplog.text
        assert "Authorization" in log_text
        assert "Bearer" not in log_text and "@" not in log_text

        for status in OrganizationStatus:
            if status is OrganizationStatus.ACTIVE:
                continue
            async with authorization_session_factory.begin() as session:
                scoped_org = make_organization(f"state-{status.value.replace('_', '-')}", status)
                scoped_user = make_user()
                session.add_all([scoped_org, scoped_user])
            async with authorization_session_factory() as session:
                result = await evaluator.evaluate(
                    session,
                    principal(scoped_user),
                    request(scoped_user, scoped_org, "organization.read"),
                    correlation_id=f"org-{status.value}",
                )
                assert result.reason_code is AuthorizationReason.ORGANIZATION_NOT_EFFECTIVE

        async with authorization_session_factory.begin() as session:
            await session.execute(
                update(OrganizationMembership)
                .where(OrganizationMembership.id == membership.id)
                .values(status="active", suspended_at=None)
            )
        async with authorization_session_factory() as session:
            aal_denied = await evaluator.evaluate(
                session,
                principal(active_user),
                request(
                    active_user,
                    active_org,
                    "organization.read",
                    minimum=AssuranceLevel.AAL2,
                ),
                correlation_id="aal-denied",
            )
            assert aal_denied.reason_code is AuthorizationReason.INSUFFICIENT_ASSURANCE
            cross_location = await evaluator.evaluate(
                session,
                principal(active_user, AssuranceLevel.AAL2),
                request(active_user, active_org, "locations.read", location=other_location),
                correlation_id="cross-location-active",
            )
            assert cross_location.reason_code is AuthorizationReason.LOCATION_NOT_FOUND
            inconsistent = await evaluator.evaluate(
                session,
                principal(active_user, AssuranceLevel.AAL2),
                request(active_user, active_org, "unregistered.read"),
                correlation_id="catalog-missing",
            )
            assert inconsistent.reason_code is AuthorizationReason.CATALOG_INCONSISTENCY

    asyncio.run(exercise())


@pytest.mark.integration
def test_product_entitlement_is_conjunctive_scoped_and_platform_admin_semantics_remain_separate(
    authorization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        access, evaluator = AccessControlService(), AuthorizationService()
        async with authorization_session_factory.begin() as session:
            await AccessCatalogSeeder().seed(session, correlation_id="entitlement-access-catalog")
            await AdministrationCatalogSeeder().seed(
                session, correlation_id="entitlement-product-catalog"
            )
            organization = make_organization("entitlement-org")
            other_organization = make_organization("entitlement-other-org")
            operator, no_role_user, platform_admin = make_user(), make_user(), make_user()
            session.add_all(
                [organization, other_organization, operator, no_role_user, platform_admin]
            )
            await session.flush()
            selected_location = make_location(organization.id, "entitled-location")
            removed_location = make_location(organization.id, "removed-location")
            cross_tenant_location = make_location(other_organization.id, "cross-tenant-location")
            session.add_all([selected_location, removed_location, cross_tenant_location])
            await session.flush()

            operator_membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(
                    user_profile_id=operator.id, membership_type=MembershipType.CLIENT
                ),
                correlation_id="entitlement-operator-membership",
            )
            no_role_membership = await access.create_membership(
                session,
                organization.id,
                MembershipCreate(
                    user_profile_id=no_role_user.id, membership_type=MembershipType.CLIENT
                ),
                correlation_id="entitlement-no-role-membership",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            reviews_publish = await access.catalog.get_permission_by_key(
                session, "reviews.publish_response"
            )
            assert owner is not None and reviews_publish is not None
            await access.add_assignment(
                session,
                organization.id,
                operator_membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="entitlement-owner-assignment",
            )
            review_deny = await access.add_deny(
                session,
                organization.id,
                operator_membership.id,
                PermissionDenyCreate(
                    permission_id=reviews_publish.id,
                    scope_type=ScopeType.LOCATION,
                    location_id=selected_location.id,
                ),
                correlation_id="entitlement-explicit-deny",
            )

            now = datetime.now(UTC)
            await add_entitlement(
                session,
                organization.id,
                "seo",
                status=EntitlementStatus.SUSPENDED,
            )
            await add_entitlement(
                session,
                organization.id,
                "content",
                status=EntitlementStatus.ARCHIVED,
            )
            await add_entitlement(
                session,
                organization.id,
                "reviews",
                status=EntitlementStatus.ACTIVE,
                location_rows=(
                    (selected_location.id, "active"),
                    (removed_location.id, "removed"),
                ),
            )
            await add_entitlement(
                session,
                organization.id,
                "leads",
                status=EntitlementStatus.SETUP_REQUIRED,
            )
            await add_entitlement(
                session,
                organization.id,
                "insights",
                status=EntitlementStatus.ACTIVE,
                effective_from=now - timedelta(days=2),
                effective_until=now - timedelta(days=1),
            )
            platform_grant = PlatformAdministrator(user_profile_id=platform_admin.id)
            session.add(platform_grant)

        async with authorization_session_factory() as session:
            no_gbp_entitlement = await evaluator.evaluate(
                session,
                principal(operator),
                request(operator, organization, "gbp.read"),
                correlation_id="entitlement-gbp-missing",
            )
            assert (
                no_gbp_entitlement.reason_code
                is AuthorizationReason.PRODUCT_ENTITLEMENT_NOT_EFFECTIVE
            )

            suspended = await evaluator.evaluate(
                session,
                principal(operator),
                request(operator, organization, "seo.read"),
                correlation_id="entitlement-seo-suspended",
            )
            assert suspended.reason_code is AuthorizationReason.PRODUCT_ENTITLEMENT_NOT_EFFECTIVE

            archived = await evaluator.evaluate(
                session,
                principal(operator),
                request(operator, organization, "content.read"),
                correlation_id="entitlement-content-archived",
            )
            assert archived.reason_code is AuthorizationReason.PRODUCT_ENTITLEMENT_NOT_EFFECTIVE

            expired = await evaluator.evaluate(
                session,
                principal(operator),
                request(operator, organization, "insights.read"),
                correlation_id="entitlement-insights-expired",
            )
            assert expired.reason_code is AuthorizationReason.PRODUCT_ENTITLEMENT_NOT_EFFECTIVE

            entitled_and_permitted = await evaluator.evaluate(
                session,
                principal(operator),
                request(operator, organization, "leads.read"),
                correlation_id="entitlement-leads-allowed",
            )
            assert entitled_and_permitted.reason_code is AuthorizationReason.ALLOWED

            entitlement_does_not_grant_role_permission = await evaluator.evaluate(
                session,
                principal(no_role_user),
                request(no_role_user, organization, "leads.read"),
                correlation_id="entitlement-no-role",
            )
            assert (
                entitlement_does_not_grant_role_permission.reason_code
                is AuthorizationReason.PERMISSION_NOT_GRANTED
            )
            assert entitlement_does_not_grant_role_permission.membership_id == no_role_membership.id

            explicit_deny = await evaluator.evaluate(
                session,
                principal(operator),
                request(
                    operator,
                    organization,
                    "reviews.publish_response",
                    location=selected_location,
                ),
                correlation_id="entitlement-explicit-deny-wins",
            )
            assert explicit_deny.reason_code is AuthorizationReason.EXPLICIT_DENY
            assert explicit_deny.applicable_deny_ids == (review_deny.id,)

            entitled_location = await evaluator.evaluate(
                session,
                principal(operator),
                request(
                    operator,
                    organization,
                    "reviews.read",
                    location=selected_location,
                ),
                correlation_id="entitlement-selected-location-allowed",
            )
            assert entitled_location.reason_code is AuthorizationReason.ALLOWED

            wrong_entitled_location = await evaluator.evaluate(
                session,
                principal(operator),
                request(
                    operator,
                    organization,
                    "reviews.read",
                    location=removed_location,
                ),
                correlation_id="entitlement-wrong-location",
            )
            assert (
                wrong_entitled_location.reason_code
                is AuthorizationReason.PRODUCT_ENTITLEMENT_NOT_EFFECTIVE
            )

            cross_tenant_location_result = await evaluator.evaluate(
                session,
                principal(operator),
                request(
                    operator,
                    organization,
                    "reviews.read",
                    location=cross_tenant_location,
                ),
                correlation_id="entitlement-cross-tenant-location",
            )
            assert (
                cross_tenant_location_result.reason_code is AuthorizationReason.LOCATION_NOT_FOUND
            )

            wrong_organization = await evaluator.evaluate(
                session,
                principal(operator),
                request(operator, other_organization, "leads.read"),
                correlation_id="entitlement-wrong-organization",
            )
            assert wrong_organization.reason_code is AuthorizationReason.MEMBERSHIP_MISSING

            non_product = await evaluator.evaluate(
                session,
                principal(operator),
                request(operator, organization, "organization.read"),
                correlation_id="entitlement-non-product-unchanged",
            )
            assert non_product.reason_code is AuthorizationReason.ALLOWED

            # Platform administration is a separate, narrow cross-organization
            # grant. It remains valid for its own routes and does not become a
            # product-role or entitlement bypass.
            grant = await require_platform_administrator()(
                principal(platform_admin, AssuranceLevel.AAL2), session
            )
            assert grant.id == platform_grant.id
            platform_admin_product_access = await evaluator.evaluate(
                session,
                principal(platform_admin, AssuranceLevel.AAL2),
                request(platform_admin, organization, "leads.read"),
                correlation_id="entitlement-platform-admin-separate",
            )
            assert (
                platform_admin_product_access.reason_code is AuthorizationReason.MEMBERSHIP_MISSING
            )

    asyncio.run(exercise())


def test_database_error_fails_closed() -> None:
    class FailingOrganizations:
        async def get_by_id(self, session: AsyncSession, organization_id: UUID) -> None:
            del session, organization_id
            raise OperationalError("select", {}, Exception("offline"))

    async def exercise() -> None:
        organization, profile = make_organization("failure-org"), make_user()
        evaluator = AuthorizationService(organization_repository=FailingOrganizations())  # type: ignore[arg-type]
        result = await evaluator.evaluate(
            None,  # type: ignore[arg-type]
            principal(profile),
            request(profile, organization, "organization.read"),
            correlation_id="database-failure",
        )
        assert not result.allowed
        assert result.reason_code is AuthorizationReason.CATALOG_INCONSISTENCY

    asyncio.run(exercise())
