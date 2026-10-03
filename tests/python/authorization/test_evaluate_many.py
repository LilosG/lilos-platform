"""``evaluate_many`` decides exactly as ``evaluate`` for every organization and permission.

Both call ``decide_organization_access``; these tests pin that the set-based loading hands it
the same rows, scenario by scenario, including every refusal reason.
"""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import (
    MembershipCreate,
    PermissionDenyCreate,
    RoleAssignmentCreate,
)
from apps.api.app.access_control.enums import MembershipStatus, MembershipType, ScopeType
from apps.api.app.access_control.models import OrganizationMembership, Role
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.enums import EntitlementStatus
from apps.api.app.authentication.contracts import AuthenticatedPrincipal
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authorization.contracts import AuthorizationDecision, AuthorizationRequest
from apps.api.app.authorization.enums import AuthorizationReason
from apps.api.app.authorization.service import AuthorizationService
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization

from .test_service import add_entitlement, make_location, make_organization, make_user, principal

KEYS = (
    "leads.read",
    "seo.read",
    "reviews.read",
    "insights.read",
    "workflows.read",
    "organization.read",
    "locations.update",
)


def single_request(
    profile_id: UUID, organization_id: UUID, key: str, minimum: AssuranceLevel
) -> AuthorizationRequest:
    return AuthorizationRequest(
        platform_user_id=profile_id,
        organization_id=organization_id,
        permission_key=key,
        resource_scope=ScopeType.ORGANIZATION,
        minimum_assurance_level=minimum,
    )


def shape(decision: AuthorizationDecision) -> tuple[Any, ...]:
    return (
        decision.allowed,
        decision.reason_code,
        decision.membership_id,
        decision.applicable_role_assignment_ids,
        decision.applicable_deny_ids,
    )


async def agree(
    session: AsyncSession,
    who: AuthenticatedPrincipal,
    organization_ids: list[UUID],
    *,
    minimum: AssuranceLevel = AssuranceLevel.AAL1,
) -> dict[tuple[UUID, str], AuthorizationDecision]:
    """Every pair decides identically through evaluate and evaluate_many; returns the decisions."""
    evaluator = AuthorizationService()
    many = await evaluator.evaluate_many(
        session,
        who,
        organization_ids,
        KEYS,
        correlation_id="evaluate-many",
        minimum_assurance_level=minimum,
    )
    assert set(many) == {(o, k) for o in organization_ids for k in KEYS}
    for (organization_id, key), decision in many.items():
        single = await evaluator.evaluate(
            session,
            who,
            single_request(who.platform_user_id, organization_id, key, minimum),
            correlation_id="evaluate-one",
        )
        assert shape(decision) == shape(single), (organization_id, key, decision, single)
        assert decision.organization_id == single.organization_id
        assert decision.minimum_assurance_level == single.minimum_assurance_level
    return many


@pytest.mark.integration
def test_every_scenario_agrees_between_evaluate_and_evaluate_many(
    authorization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        access = AccessControlService()
        async with authorization_session_factory.begin() as session:
            await AccessCatalogSeeder().seed(session, correlation_id="many-catalog")
            await AdministrationCatalogSeeder().seed(session, correlation_id="many-products")
            profile = make_user()
            session.add(profile)
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            manager = await access.catalog.get_role_by_key(session, "organization_manager")
            assert owner is not None and manager is not None

            async def organization(
                slug: str,
                *,
                status: OrganizationStatus = OrganizationStatus.ACTIVE,
                membership_status: MembershipStatus = MembershipStatus.ACTIVE,
                role: Role | None = owner,
                scope: ScopeType = ScopeType.ORGANIZATION,
                location_id: UUID | None = None,
                entitle: tuple[str, ...] = ("leads", "seo", "reviews", "insights"),
            ) -> UUID:
                item = make_organization(slug)
                session.add(item)
                await session.flush()
                membership = await access.create_membership(
                    session,
                    item.id,
                    MembershipCreate(
                        user_profile_id=profile.id, membership_type=MembershipType.CLIENT
                    ),
                    correlation_id=f"member-{slug}",
                )
                if role is not None:
                    await access.add_assignment(
                        session,
                        item.id,
                        membership.id,
                        RoleAssignmentCreate(
                            role_id=role.id, scope_type=scope, location_id=location_id
                        ),
                        correlation_id=f"role-{slug}",
                    )
                if membership_status is not MembershipStatus.ACTIVE:
                    await session.execute(
                        update(OrganizationMembership)
                        .where(OrganizationMembership.id == membership.id)
                        .values(
                            status=membership_status,
                            revoked_at=now
                            if membership_status is MembershipStatus.REVOKED
                            else None,
                            suspended_at=now
                            if membership_status is MembershipStatus.SUSPENDED
                            else None,
                        )
                    )
                for product in entitle:
                    await add_entitlement(
                        session, item.id, product, status=EntitlementStatus.ACTIVE
                    )
                if status is not OrganizationStatus.ACTIVE:
                    # Memberships can only be created while the client is active.
                    await session.execute(
                        update(Organization).where(Organization.id == item.id).values(status=status)
                    )
                return item.id

            now = datetime.now(UTC)
            ids: dict[str, UUID] = {}
            ids["healthy"] = await organization("many-healthy")
            ids["inactive_org"] = await organization(
                "many-suspended", status=OrganizationStatus.SUSPENDED
            )
            ids["onboarding"] = await organization(
                "many-onboarding", status=OrganizationStatus.ONBOARDING
            )
            ids["revoked_membership"] = await organization(
                "many-revoked", membership_status=MembershipStatus.REVOKED
            )
            ids["suspended_membership"] = await organization(
                "many-suspended-member", membership_status=MembershipStatus.SUSPENDED
            )
            ids["no_entitlement"] = await organization("many-unentitled", entitle=())
            ids["partial_entitlement"] = await organization("many-partial", entitle=("leads",))
            ids["no_role"] = await organization("many-norole", role=None)
            location_org = await organization("many-location-org", role=None)
            location_for_org = make_location(location_org, "many-location-scope")
            session.add(location_for_org)
            await session.flush()
            location_membership = await _membership_of(session, location_org, profile.id)
            await access.add_assignment(
                session,
                location_org,
                location_membership,
                RoleAssignmentCreate(
                    role_id=manager.id,
                    scope_type=ScopeType.LOCATION,
                    location_id=location_for_org.id,
                ),
                correlation_id="location-scoped-role",
            )
            ids["location_scoped_role"] = location_org
            ids["denied"] = await organization("many-denied")
            leads_read = await _permission_id(session, "leads.read")
            await access.add_deny(
                session,
                ids["denied"],
                await _membership_of(session, ids["denied"], profile.id),
                PermissionDenyCreate(permission_id=leads_read, scope_type=ScopeType.ORGANIZATION),
                correlation_id="deny",
            )

        async with authorization_session_factory() as session:
            stranger = make_organization("many-stranger-real")
            session.add(stranger)
            await session.flush()
            ids["not_a_member"] = stranger.id
            ids["unknown"] = uuid4()
            who = principal(profile, AssuranceLevel.AAL1)
            decisions = await agree(session, who, list(ids.values()))
            reasons = {
                name: {k: decisions[(organization_id, k)].reason_code for k in KEYS}
                for name, organization_id in ids.items()
            }
            allowed = AuthorizationReason.ALLOWED
            assert reasons["healthy"]["leads.read"] is allowed
            assert reasons["healthy"]["workflows.read"] is allowed
            assert (
                reasons["inactive_org"]["leads.read"]
                is AuthorizationReason.ORGANIZATION_NOT_EFFECTIVE
            )
            assert (
                reasons["onboarding"]["leads.read"]
                is AuthorizationReason.ORGANIZATION_NOT_EFFECTIVE
            )
            assert (
                reasons["revoked_membership"]["leads.read"]
                is AuthorizationReason.MEMBERSHIP_INACTIVE
            )
            assert (
                reasons["suspended_membership"]["leads.read"]
                is AuthorizationReason.MEMBERSHIP_INACTIVE
            )
            assert (
                reasons["no_entitlement"]["leads.read"]
                is AuthorizationReason.PRODUCT_ENTITLEMENT_NOT_EFFECTIVE
            )
            assert reasons["no_entitlement"]["organization.read"] is allowed
            assert reasons["partial_entitlement"]["leads.read"] is allowed
            assert (
                reasons["partial_entitlement"]["seo.read"]
                is AuthorizationReason.PRODUCT_ENTITLEMENT_NOT_EFFECTIVE
            )
            assert reasons["no_role"]["leads.read"] is AuthorizationReason.PERMISSION_NOT_GRANTED
            # A location-scoped assignment never grants an organization-scope permission.
            assert (
                reasons["location_scoped_role"]["locations.update"]
                is AuthorizationReason.PERMISSION_NOT_GRANTED
            )
            assert reasons["denied"]["leads.read"] is AuthorizationReason.EXPLICIT_DENY
            assert reasons["denied"]["seo.read"] is allowed
            assert reasons["not_a_member"]["leads.read"] is AuthorizationReason.MEMBERSHIP_MISSING
            assert (
                reasons["unknown"]["leads.read"] is AuthorizationReason.ORGANIZATION_NOT_EFFECTIVE
            )

            # Assurance: aal1 cannot satisfy an aal2 minimum, in both.
            insufficient = await agree(session, who, [ids["healthy"]], minimum=AssuranceLevel.AAL2)
            assert {d.reason_code for d in insufficient.values()} == {
                AuthorizationReason.INSUFFICIENT_ASSURANCE
            }
            satisfied = await agree(
                session,
                principal(profile, AssuranceLevel.AAL2),
                [ids["healthy"]],
                minimum=AssuranceLevel.AAL2,
            )
            assert satisfied[(ids["healthy"], "leads.read")].allowed

            # An inactive principal holds nothing and reads nothing.
            gone = make_user(UserStatus.DEACTIVATED)
            nobody = await agree(session, principal(gone), [ids["healthy"], ids["unknown"]])
            assert {d.reason_code for d in nobody.values()} == {AuthorizationReason.USER_INACTIVE}
            await session.rollback()

    asyncio.run(exercise())


@pytest.mark.integration
def test_a_role_that_is_not_active_agrees_in_both_paths(
    authorization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The catalog forbids a non-active role, but the rule refuses one defensively.

    The loaded role is altered in memory only (never flushed), so both paths read the same
    non-active role from the session.
    """

    async def exercise() -> None:
        access = AccessControlService()
        async with authorization_session_factory.begin() as session:
            await AccessCatalogSeeder().seed(session, correlation_id="many-role-catalog")
            await AdministrationCatalogSeeder().seed(session, correlation_id="many-role-products")
            profile = make_user()
            item = make_organization("many-role-org")
            session.add_all([profile, item])
            await session.flush()
            membership = await access.create_membership(
                session,
                item.id,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id="member-role",
            )
            owner = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner is not None
            await access.add_assignment(
                session,
                item.id,
                membership.id,
                RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id="role-role",
            )
            await add_entitlement(session, item.id, "leads", status=EntitlementStatus.ACTIVE)
            organization_id = item.id

        async with authorization_session_factory() as session:
            who = principal(profile)
            before = await agree(session, who, [organization_id])
            assert before[(organization_id, "leads.read")].allowed
            role = await session.get(Role, owner.id)
            assert role is not None
            with session.no_autoflush:
                role.status = SimpleNamespace(value="retired")  # type: ignore[assignment]
                after = await agree(session, who, [organization_id])
            assert {d.reason_code for d in after.values()} == {
                AuthorizationReason.CATALOG_INCONSISTENCY
            }
            session.expunge_all()

    asyncio.run(exercise())


async def _org_id_for(session: AsyncSession, slug: str) -> UUID:
    from sqlalchemy import select

    found = await session.scalar(select(Organization.id).where(Organization.slug == slug))
    assert found is not None
    return found


async def _membership_of(session: AsyncSession, organization_id: UUID, user_id: UUID) -> UUID:
    from sqlalchemy import select

    found = await session.scalar(
        select(OrganizationMembership.id).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_profile_id == user_id,
        )
    )
    assert found is not None
    return found


async def _permission_id(session: AsyncSession, key: str) -> UUID:
    from sqlalchemy import select

    from apps.api.app.access_control.models import Permission

    found = await session.scalar(select(Permission.id).where(Permission.key == key))
    assert found is not None
    return found
