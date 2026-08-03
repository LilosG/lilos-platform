"""Transaction-safe last-active-owner continuity tests."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipStatus, MembershipType, ScopeType
from apps.api.app.access_control.errors import LastActiveOwnerConflictError
from apps.api.app.access_control.models import MembershipRoleAssignment
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import UserProfileCreate
from apps.api.app.authentication.enums import UserLifecycleAction, UserStatus
from apps.api.app.authentication.service import UserAdministrationService
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


async def create_owner(
    session: AsyncSession,
    service: AccessControlService,
    organization_id: UUID,
    role_id: UUID,
    label: str,
) -> tuple[UUID, UUID, UUID]:
    user = await UserAdministrationService().provision(
        session,
        UserProfileCreate(auth_user_id=uuid4(), email=f"{label}@example.invalid"),
        correlation_id=f"{label}-user",
    )
    membership = await service.create_membership(
        session,
        organization_id,
        MembershipCreate(user_profile_id=user.id, membership_type=MembershipType.CLIENT),
        correlation_id=f"{label}-membership",
    )
    assignment = await service.add_assignment(
        session,
        organization_id,
        membership.id,
        RoleAssignmentCreate(role_id=role_id, scope_type=ScopeType.ORGANIZATION),
        correlation_id=f"{label}-owner",
    )
    return user.id, membership.id, assignment.id


@pytest.mark.integration
def test_final_owner_removal_membership_change_and_user_deactivation_are_rejected(
    access_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        access = AccessControlService()
        users = UserAdministrationService()
        async with access_session_factory.begin() as session:
            await AccessCatalogSeeder().seed(session, correlation_id="owner-catalog")
            organization = Organization(
                name="Owner Continuity",
                slug="owner-continuity",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(organization)
            await session.flush()
            owner_role = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner_role is not None
            first = await create_owner(session, access, organization.id, owner_role.id, "owner-one")
            second = await create_owner(
                session, access, organization.id, owner_role.id, "owner-two"
            )
            organization_id, owner_role_id = organization.id, owner_role.id

        async with access_session_factory.begin() as session:
            await access.remove_assignment(
                session,
                organization_id,
                first[1],
                first[2],
                correlation_id="remove-one-of-two",
            )
        with pytest.raises(LastActiveOwnerConflictError):
            async with access_session_factory.begin() as session:
                await access.remove_assignment(
                    session,
                    organization_id,
                    second[1],
                    second[2],
                    correlation_id="remove-final",
                )
        with pytest.raises(LastActiveOwnerConflictError):
            async with access_session_factory.begin() as session:
                await access.transition_membership(
                    session,
                    organization_id,
                    second[1],
                    target=MembershipStatus.SUSPENDED,
                    expected_version=1,
                    correlation_id="suspend-final",
                )
        with pytest.raises(LastActiveOwnerConflictError):
            async with access_session_factory.begin() as session:
                await access.transition_membership(
                    session,
                    organization_id,
                    second[1],
                    target=MembershipStatus.REVOKED,
                    expected_version=1,
                    correlation_id="revoke-final",
                )
        with pytest.raises(LastActiveOwnerConflictError):
            async with access_session_factory.begin() as session:
                await users.transition(
                    session,
                    second[0],
                    action=UserLifecycleAction.DEACTIVATE,
                    expected_version=1,
                    correlation_id="deactivate-final",
                )

        async with access_session_factory.begin() as session:
            location = Location(
                organization_id=organization_id,
                name="Owner Scope Location",
                slug="owner-scope-location",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://example.invalid",
                is_primary=False,
                version=1,
            )
            session.add(location)
            await session.flush()
            location_owner = await users.provision(
                session,
                UserProfileCreate(auth_user_id=uuid4()),
                correlation_id="location-owner-user",
            )
            location_membership = await access.create_membership(
                session,
                organization_id,
                MembershipCreate(
                    user_profile_id=location_owner.id, membership_type=MembershipType.SUPPORT
                ),
                correlation_id="location-owner-membership",
            )
            await access.add_assignment(
                session,
                organization_id,
                location_membership.id,
                RoleAssignmentCreate(
                    role_id=owner_role_id,
                    scope_type=ScopeType.LOCATION,
                    location_id=location.id,
                ),
                correlation_id="location-owner-assignment",
            )
        with pytest.raises(LastActiveOwnerConflictError):
            async with access_session_factory.begin() as session:
                await access.remove_assignment(
                    session,
                    organization_id,
                    second[1],
                    second[2],
                    correlation_id="location-owner-does-not-count",
                )
        async with access_session_factory() as session:
            remaining_user = await users.get(session, second[0])
            assert remaining_user.status is UserStatus.ACTIVE

    asyncio.run(exercise())


@pytest.mark.integration
def test_concurrent_owner_removal_cannot_leave_active_organization_ownerless(
    access_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        access = AccessControlService()
        async with access_session_factory.begin() as session:
            await AccessCatalogSeeder().seed(session, correlation_id="concurrent-catalog")
            organization = Organization(
                name="Concurrent Owners",
                slug="concurrent-owners",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(organization)
            await session.flush()
            owner_role = await access.catalog.get_role_by_key(session, "organization_owner")
            assert owner_role is not None
            first = await create_owner(session, access, organization.id, owner_role.id, "race-one")
            second = await create_owner(session, access, organization.id, owner_role.id, "race-two")
            organization_id = organization.id

        async def remove(owner: tuple[UUID, UUID, UUID]) -> str:
            try:
                async with access_session_factory.begin() as session:
                    await AccessControlService().remove_assignment(
                        session,
                        organization_id,
                        owner[1],
                        owner[2],
                        correlation_id=f"race-{owner[2]}",
                    )
                return "removed"
            except LastActiveOwnerConflictError:
                return "protected"

        results = await asyncio.gather(remove(first), remove(second))
        assert sorted(results) == ["protected", "removed"]
        async with access_session_factory() as session:
            remaining = list(
                await session.scalars(
                    select(MembershipRoleAssignment).where(
                        MembershipRoleAssignment.organization_id == organization_id,
                        MembershipRoleAssignment.scope_type == ScopeType.ORGANIZATION,
                    )
                )
            )
            assert len(remaining) == 1

    asyncio.run(exercise())
