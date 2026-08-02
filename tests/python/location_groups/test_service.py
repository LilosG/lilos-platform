"""Location-group service lifecycle, membership, audit, rollback, and isolation tests."""

import asyncio
import json

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.database.base import utc_now
from apps.api.app.location_groups.contracts import LocationGroupReplace
from apps.api.app.location_groups.enums import LocationGroupStatus
from apps.api.app.location_groups.errors import (
    LocationGroupLocationStateConflictError,
    LocationGroupMembershipConflictError,
    LocationGroupMembershipNotFoundError,
    LocationGroupNotFoundError,
    LocationGroupParentStateConflictError,
    LocationGroupStateConflictError,
    LocationGroupVersionConflictError,
)
from apps.api.app.location_groups.models import LocationGroup, LocationGroupMembership
from apps.api.app.location_groups.repository import (
    LocationGroupMembershipRepository,
    LocationGroupRepository,
)
from apps.api.app.location_groups.service import LocationGroupService
from apps.api.app.locations.enums import LocationStatus
from apps.api.app.locations.errors import LocationNotFoundError
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from location_groups.helpers import add_location, add_organization, group_command


async def set_organization_status(
    session: AsyncSession, organization_id: object, status: OrganizationStatus
) -> None:
    await session.execute(
        update(Organization)
        .where(Organization.id == organization_id)
        .values(
            status=status,
            archived_at=utc_now() if status is OrganizationStatus.ARCHIVED else None,
        )
    )


@pytest.mark.integration
def test_group_create_replace_archive_audit_concurrency_and_rollback(
    location_group_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationGroupService()
        async with location_group_session_factory.begin() as session:
            organization = await add_organization(session)
            organization_id = organization.id
        with pytest.raises(RuntimeError, match="forced group rollback"):
            async with location_group_session_factory.begin() as session:
                await service.create(
                    session,
                    organization_id,
                    group_command(key="rollback-group"),
                    correlation_id="group-create-rollback",
                )
                raise RuntimeError("forced group rollback")
        async with location_group_session_factory() as session:
            assert (
                await session.scalar(
                    select(LocationGroup).where(LocationGroup.key == "rollback-group")
                )
                is None
            )
            assert (
                await session.scalar(
                    select(AuditEvent).where(AuditEvent.correlation_id == "group-create-rollback")
                )
                is None
            )
        async with location_group_session_factory.begin() as session:
            created = await service.create(
                session,
                organization_id,
                group_command(key="north-region"),
                correlation_id="group-created",
            )
            group_id = created.id
            assert created.version == 1 and created.status is LocationGroupStatus.ACTIVE
        async with location_group_session_factory() as session:
            assert (await service.get(session, organization_id, group_id)).key == "north-region"
        replacement = LocationGroupReplace(
            name="North Operations",
            description="Updated administrative grouping",
            expected_version=1,
        )
        async with location_group_session_factory.begin() as session:
            replaced = await service.replace(
                session,
                organization_id,
                group_id,
                replacement,
                correlation_id="group-updated",
            )
            assert replaced.version == 2 and replaced.name == "North Operations"
        with pytest.raises(LocationGroupVersionConflictError):
            async with location_group_session_factory.begin() as session:
                await service.replace(
                    session,
                    organization_id,
                    group_id,
                    replacement,
                    correlation_id="group-stale",
                )
        async with location_group_session_factory.begin() as session:
            archived = await service.archive(
                session,
                organization_id,
                group_id,
                expected_version=2,
                correlation_id="group-archived",
            )
            assert archived.version == 3
            assert archived.status is LocationGroupStatus.ARCHIVED
            assert archived.archived_at is not None
        with pytest.raises(LocationGroupStateConflictError):
            async with location_group_session_factory.begin() as session:
                await service.archive(
                    session,
                    organization_id,
                    group_id,
                    expected_version=3,
                    correlation_id="group-rearchive",
                )
        async with location_group_session_factory() as session:
            events = list(
                await session.scalars(select(AuditEvent).where(AuditEvent.resource_id == group_id))
            )
        assert len(events) == 3
        serialized = json.dumps([event.event_metadata for event in events])
        assert "North Operations" not in serialized
        assert "Updated administrative grouping" not in serialized
        assert all(event.organization_id == organization_id for event in events)

    asyncio.run(exercise())


@pytest.mark.integration
def test_group_key_is_database_immutable_and_scoped_unique(
    location_group_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationGroupService()
        async with location_group_session_factory.begin() as session:
            first = await add_organization(session)
            second = await add_organization(session)
            first_id, second_id = first.id, second.id
            first_group = await service.create(
                session,
                first_id,
                group_command(key="shared-key"),
                correlation_id="first-group",
            )
            await service.create(
                session,
                second_id,
                group_command(key="shared-key"),
                correlation_id="second-group",
            )
            first_group_id = first_group.id
        with pytest.raises(DBAPIError):
            async with location_group_session_factory.begin() as session:
                await session.execute(
                    update(LocationGroup)
                    .where(LocationGroup.id == first_group_id)
                    .values(key="changed-key")
                )
        with pytest.raises(LocationGroupNotFoundError):
            async with location_group_session_factory() as session:
                await service.get(session, second_id, first_group_id)

    asyncio.run(exercise())


@pytest.mark.integration
def test_membership_cardinality_isolation_listing_audit_and_rollback(
    location_group_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationGroupService()
        async with location_group_session_factory.begin() as session:
            first = await add_organization(session)
            second = await add_organization(session)
            location = await add_location(session, first.id)
            other_location = await add_location(session, second.id)
            first_group = await service.create(
                session,
                first.id,
                group_command(key="first-group"),
                correlation_id="first-group-create",
            )
            second_group = await service.create(
                session,
                first.id,
                group_command(key="second-group"),
                correlation_id="second-group-create",
            )
            first_id, second_id = first.id, second.id
            location_id, other_location_id = location.id, other_location.id
            first_group_id, second_group_id = first_group.id, second_group.id
        async with location_group_session_factory.begin() as session:
            first_membership = await service.add_membership(
                session,
                first_id,
                first_group_id,
                location_id,
                correlation_id="membership-added",
            )
            await service.add_membership(
                session,
                first_id,
                second_group_id,
                location_id,
                correlation_id="second-membership-added",
            )
            membership_id = first_membership.id
        with pytest.raises(LocationGroupMembershipConflictError):
            async with location_group_session_factory.begin() as session:
                await service.add_membership(
                    session,
                    first_id,
                    first_group_id,
                    location_id,
                    correlation_id="membership-duplicate",
                )
        with pytest.raises(LocationNotFoundError):
            async with location_group_session_factory.begin() as session:
                await service.add_membership(
                    session,
                    first_id,
                    first_group_id,
                    other_location_id,
                    correlation_id="membership-cross-scope",
                )
        with pytest.raises(LocationGroupNotFoundError):
            async with location_group_session_factory() as session:
                await service.list_members(session, second_id, first_group_id, limit=10, offset=0)
        async with location_group_session_factory() as session:
            first_page, has_more = await service.list_members(
                session, first_id, first_group_id, limit=1, offset=0
            )
            assert [item.id for item in first_page] == [membership_id]
            assert has_more is False
        with pytest.raises(RuntimeError, match="forced membership rollback"):
            async with location_group_session_factory.begin() as session:
                await service.remove_membership(
                    session,
                    first_id,
                    first_group_id,
                    location_id,
                    correlation_id="membership-remove-rollback",
                )
                raise RuntimeError("forced membership rollback")
        async with location_group_session_factory() as session:
            assert await service.membership_repository.is_member(
                session, first_id, first_group_id, location_id
            )
            assert (
                await session.scalar(
                    select(AuditEvent).where(
                        AuditEvent.correlation_id == "membership-remove-rollback"
                    )
                )
                is None
            )
        async with location_group_session_factory.begin() as session:
            removed = await service.remove_membership(
                session,
                first_id,
                first_group_id,
                location_id,
                correlation_id="membership-removed",
            )
            assert removed.id == membership_id
        with pytest.raises(LocationGroupMembershipNotFoundError):
            async with location_group_session_factory.begin() as session:
                await service.remove_membership(
                    session,
                    first_id,
                    first_group_id,
                    location_id,
                    correlation_id="membership-missing",
                )
        async with location_group_session_factory() as session:
            events = list(
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.resource_id == membership_id)
                )
            )
        assert [event.action for event in events] == [
            "location_group_membership.added",
            "location_group_membership.removed",
        ]
        serialized = json.dumps([event.event_metadata for event in events])
        assert "profile" not in serialized and "contact" not in serialized

    asyncio.run(exercise())


@pytest.mark.integration
def test_parent_organization_permission_matrix(
    location_group_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationGroupService()
        create_update = {
            OrganizationStatus.PROSPECT,
            OrganizationStatus.ONBOARDING,
            OrganizationStatus.ACTIVE,
            OrganizationStatus.PAUSED,
        }
        archive = create_update | {OrganizationStatus.OFFBOARDING}
        add = {
            OrganizationStatus.PROSPECT,
            OrganizationStatus.ONBOARDING,
            OrganizationStatus.ACTIVE,
        }
        remove = add | {OrganizationStatus.PAUSED, OrganizationStatus.OFFBOARDING}
        for organization_status in OrganizationStatus:
            async with location_group_session_factory.begin() as session:
                organization = await add_organization(session)
                location = await add_location(session, organization.id)
                update_group = await service.create(
                    session,
                    organization.id,
                    group_command(),
                    correlation_id="matrix-update-setup",
                )
                archive_group = await service.create(
                    session,
                    organization.id,
                    group_command(),
                    correlation_id="matrix-archive-setup",
                )
                membership_group = await service.create(
                    session,
                    organization.id,
                    group_command(),
                    correlation_id="matrix-membership-setup",
                )
                membership = await service.add_membership(
                    session,
                    organization.id,
                    membership_group.id,
                    location.id,
                    correlation_id="matrix-existing-membership",
                )
                organization_id = organization.id
                location_id = location.id
                update_group_id = update_group.id
                archive_group_id = archive_group.id
                membership_group_id = membership_group.id
                membership_id = membership.id
                await set_organization_status(session, organization_id, organization_status)

            async def expect(operation: object, allowed: bool) -> None:
                if allowed:
                    async with location_group_session_factory.begin() as session:
                        await operation(session)  # type: ignore[operator]
                else:
                    with pytest.raises(LocationGroupParentStateConflictError):
                        async with location_group_session_factory.begin() as session:
                            await operation(session)  # type: ignore[operator]

            await expect(
                lambda session, organization_id=organization_id: service.create(
                    session,
                    organization_id,
                    group_command(),
                    correlation_id="matrix-create",
                ),
                organization_status in create_update,
            )
            await expect(
                lambda session, organization_id=organization_id, update_group_id=update_group_id: (
                    service.replace(
                        session,
                        organization_id,
                        update_group_id,
                        LocationGroupReplace(
                            name="Matrix Updated", description=None, expected_version=1
                        ),
                        correlation_id="matrix-update",
                    )
                ),
                organization_status in create_update,
            )
            await expect(
                lambda session, organization_id=organization_id, archive_group_id=archive_group_id: (  # noqa: E501
                    service.archive(
                        session,
                        organization_id,
                        archive_group_id,
                        expected_version=1,
                        correlation_id="matrix-archive",
                    )
                ),
                organization_status in archive,
            )
            add_group_id = update_group_id if organization_status not in create_update else None
            if add_group_id is None:
                async with location_group_session_factory.begin() as session:
                    extra_group = await service.create(
                        session,
                        organization_id,
                        group_command(),
                        correlation_id="matrix-add-group",
                    )
                    add_group_id = extra_group.id
            await expect(
                lambda session, organization_id=organization_id, add_group_id=add_group_id, location_id=location_id: (  # noqa: E501
                    service.add_membership(
                        session,
                        organization_id,
                        add_group_id,
                        location_id,
                        correlation_id="matrix-add",
                    )
                ),
                organization_status in add,
            )
            await expect(
                lambda session, organization_id=organization_id, membership_group_id=membership_group_id, location_id=location_id: (  # noqa: E501
                    service.remove_membership(
                        session,
                        organization_id,
                        membership_group_id,
                        location_id,
                        correlation_id="matrix-remove",
                    )
                ),
                organization_status in remove,
            )
            if organization_status not in remove:
                async with location_group_session_factory() as session:
                    assert (await session.get(LocationGroupMembership, membership_id)) is not None

    asyncio.run(exercise())


@pytest.mark.integration
def test_location_eligibility_persistence_and_archived_group_cleanup(
    location_group_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationGroupService()
        allowed = {
            LocationStatus.SETUP_REQUIRED,
            LocationStatus.ACTIVE,
            LocationStatus.PAUSED,
            LocationStatus.CLOSED_TEMPORARILY,
        }
        async with location_group_session_factory.begin() as session:
            organization = await add_organization(session)
            organization_id = organization.id
        for location_status in LocationStatus:
            async with location_group_session_factory.begin() as session:
                group = await service.create(
                    session,
                    organization_id,
                    group_command(),
                    correlation_id="eligibility-group",
                )
                location = await add_location(session, organization_id, status=location_status)
                group_id, location_id = group.id, location.id
            if location_status in allowed:
                async with location_group_session_factory.begin() as session:
                    await service.add_membership(
                        session,
                        organization_id,
                        group_id,
                        location_id,
                        correlation_id="eligibility-add",
                    )
            else:
                with pytest.raises(LocationGroupLocationStateConflictError):
                    async with location_group_session_factory.begin() as session:
                        await service.add_membership(
                            session,
                            organization_id,
                            group_id,
                            location_id,
                            correlation_id="eligibility-denied",
                        )
        async with location_group_session_factory.begin() as session:
            group = await service.create(
                session,
                organization_id,
                group_command(),
                correlation_id="archive-membership-group",
            )
            location = await add_location(session, organization_id)
            group_id, location_id = group.id, location.id
            await service.add_membership(
                session,
                organization_id,
                group_id,
                location_id,
                correlation_id="archive-membership-add",
            )
            await service.archive(
                session,
                organization_id,
                group_id,
                expected_version=1,
                correlation_id="archive-membership-archive",
            )
            await session.execute(
                update(Location)
                .where(Location.id == location_id)
                .values(status=LocationStatus.ARCHIVED, archived_at=utc_now())
            )
        with pytest.raises(LocationGroupStateConflictError):
            async with location_group_session_factory.begin() as session:
                replacement = await add_location(session, organization_id)
                await service.add_membership(
                    session,
                    organization_id,
                    group_id,
                    replacement.id,
                    correlation_id="archived-group-add",
                )
        async with location_group_session_factory.begin() as session:
            await service.remove_membership(
                session,
                organization_id,
                group_id,
                location_id,
                correlation_id="archived-location-cleanup",
            )

    asyncio.run(exercise())


@pytest.mark.integration
@pytest.mark.parametrize(
    "later_status",
    [
        LocationStatus.PAUSED,
        LocationStatus.CLOSED_TEMPORARILY,
        LocationStatus.CLOSED_PERMANENTLY,
        LocationStatus.ARCHIVED,
    ],
)
def test_existing_membership_persists_after_location_state_change(
    location_group_session_factory: async_sessionmaker[AsyncSession],
    later_status: LocationStatus,
) -> None:
    async def exercise() -> None:
        service = LocationGroupService()
        async with location_group_session_factory.begin() as session:
            organization = await add_organization(session)
            group = await service.create(
                session,
                organization.id,
                group_command(),
                correlation_id="membership-persistence-group",
            )
            location = await add_location(session, organization.id)
            organization_id, group_id, location_id = organization.id, group.id, location.id
            await service.add_membership(
                session,
                organization_id,
                group_id,
                location_id,
                correlation_id="membership-persistence-add",
            )
            await session.execute(
                update(Location)
                .where(Location.id == location_id)
                .values(
                    status=later_status,
                    archived_at=(utc_now() if later_status is LocationStatus.ARCHIVED else None),
                )
            )
        async with location_group_session_factory() as session:
            assert await service.membership_repository.is_member(
                session, organization_id, group_id, location_id
            )

    asyncio.run(exercise())


@pytest.mark.integration
def test_group_and_membership_listing_are_deterministic_and_bounded(
    location_group_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationGroupService()
        async with location_group_session_factory.begin() as session:
            organization = await add_organization(session)
            organization_id = organization.id
            groups = [
                await service.create(
                    session,
                    organization_id,
                    group_command(),
                    correlation_id=f"deterministic-group-{index}",
                )
                for index in range(3)
            ]
            locations = [await add_location(session, organization_id) for _ in range(3)]
            memberships = [
                await service.add_membership(
                    session,
                    organization_id,
                    groups[0].id,
                    location.id,
                    correlation_id=f"deterministic-membership-{index}",
                )
                for index, location in enumerate(locations)
            ]
            group_id = groups[0].id
            expected_groups = sorted(groups, key=lambda item: (item.created_at, item.id))
            expected_memberships = sorted(memberships, key=lambda item: (item.created_at, item.id))
        async with location_group_session_factory() as session:
            first_groups, groups_more = await service.list_groups(
                session, organization_id, limit=2, offset=0
            )
            second_groups, groups_last = await service.list_groups(
                session, organization_id, limit=2, offset=2
            )
            first_members, members_more = await service.list_members(
                session, organization_id, group_id, limit=2, offset=0
            )
            second_members, members_last = await service.list_members(
                session, organization_id, group_id, limit=2, offset=2
            )
        assert [item.id for item in first_groups + second_groups] == [
            item.id for item in expected_groups
        ]
        assert groups_more is True and groups_last is False
        assert [item.id for item in first_members + second_members] == [
            item.id for item in expected_memberships
        ]
        assert members_more is True and members_last is False

    asyncio.run(exercise())


def test_repository_surfaces_are_narrow() -> None:
    assert {name for name in dir(LocationGroupRepository) if not name.startswith("_")} == {
        "add",
        "archive",
        "get",
        "list",
        "replace",
    }
    assert {
        name for name in dir(LocationGroupMembershipRepository) if not name.startswith("_")
    } == {"add", "is_member", "list_members", "remove"}
    assert not hasattr(LocationGroup, "delete")
