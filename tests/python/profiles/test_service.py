"""Profile service lifecycle, concurrency, audit, rollback, and isolation tests."""

import asyncio
import json

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.database.base import utc_now
from apps.api.app.locations.enums import LocationStatus
from apps.api.app.locations.errors import LocationNotFoundError
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.profiles.contracts import LocationProfileReplace, OrganizationProfileReplace
from apps.api.app.profiles.errors import (
    LocationProfileConflictError,
    LocationProfileNotFoundError,
    LocationProfileVersionConflictError,
    OrganizationProfileConflictError,
    OrganizationProfileNotFoundError,
    OrganizationProfileVersionConflictError,
    ProfileParentStateConflictError,
)
from apps.api.app.profiles.models import LocationProfile, OrganizationProfile
from apps.api.app.profiles.repository import (
    LocationProfileRepository,
    OrganizationProfileRepository,
)
from apps.api.app.profiles.service import LocationProfileService, OrganizationProfileService
from profiles.helpers import (
    add_location,
    add_organization,
    location_profile,
    organization_profile,
)


@pytest.mark.integration
def test_organization_profile_create_get_replace_audit_and_rollback(
    profile_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = OrganizationProfileService()
        async with profile_session_factory.begin() as session:
            organization = await add_organization(session)
            organization_id = organization.id
            created = await service.create(
                session,
                organization_id,
                organization_profile(),
                correlation_id="organization-profile-create",
            )
            profile_id = created.id
            assert created.version == 1
        async with profile_session_factory() as session:
            stored = await service.get(session, organization_id)
            assert stored.id == profile_id
        with pytest.raises(OrganizationProfileConflictError):
            async with profile_session_factory.begin() as session:
                await service.create(
                    session,
                    organization_id,
                    organization_profile(),
                    correlation_id="duplicate",
                )
        command = OrganizationProfileReplace(
            expected_version=1,
            brand_name="Replacement Brand",
            approved_claims=["Replacement approved claim"],
            prohibited_claims=["Replacement prohibited claim"],
        )
        with pytest.raises(RuntimeError, match="forced profile rollback"):
            async with profile_session_factory.begin() as session:
                await service.replace(
                    session,
                    organization_id,
                    command,
                    correlation_id="organization-profile-rollback",
                )
                raise RuntimeError("forced profile rollback")
        async with profile_session_factory() as session:
            unchanged = await service.get(session, organization_id)
            rolled_back_audit = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.correlation_id == "organization-profile-rollback"
                )
            )
            assert unchanged.version == 1 and unchanged.brand_name == "Fabricated Brand"
            assert rolled_back_audit is None
        async with profile_session_factory.begin() as session:
            replaced = await service.replace(
                session,
                organization_id,
                command,
                correlation_id="organization-profile-update",
            )
            assert replaced.version == 2 and replaced.brand_name == "Replacement Brand"
        with pytest.raises(OrganizationProfileVersionConflictError):
            async with profile_session_factory.begin() as session:
                await service.replace(
                    session,
                    organization_id,
                    command,
                    correlation_id="stale-profile-update",
                )
        async with profile_session_factory() as session:
            events = list(
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.resource_id == profile_id)
                )
            )
        assert len(events) == 2
        serialized = json.dumps([event.event_metadata for event in events])
        assert "Replacement Brand" not in serialized
        assert "Replacement approved claim" not in serialized
        update_event = next(
            event for event in events if event.correlation_id == "organization-profile-update"
        )
        assert update_event.organization_id == organization_id
        assert update_event.event_metadata["changed_fields"] == [
            "approved_claims",
            "brand_name",
            "brand_summary",
            "primary_services",
            "prohibited_claims",
            "tone_guidelines",
        ]

    asyncio.run(exercise())


@pytest.mark.integration
@pytest.mark.parametrize(
    ("status", "allowed"),
    [
        (OrganizationStatus.PROSPECT, True),
        (OrganizationStatus.ONBOARDING, True),
        (OrganizationStatus.ACTIVE, True),
        (OrganizationStatus.PAUSED, True),
        (OrganizationStatus.SUSPENDED, False),
        (OrganizationStatus.OFFBOARDING, False),
        (OrganizationStatus.ARCHIVED, False),
    ],
)
def test_organization_profile_parent_matrix_and_read_preservation(
    profile_session_factory: async_sessionmaker[AsyncSession],
    status: OrganizationStatus,
    allowed: bool,
) -> None:
    async def exercise() -> None:
        service = OrganizationProfileService()
        async with profile_session_factory.begin() as session:
            organization = await add_organization(session, status=OrganizationStatus.ACTIVE)
            identifier = organization.id
            await service.create(
                session,
                identifier,
                organization_profile(),
                correlation_id="matrix-profile-create",
            )
        async with profile_session_factory.begin() as session:
            await session.execute(
                update(Organization)
                .where(Organization.id == identifier)
                .values(
                    status=status,
                    archived_at=utc_now() if status is OrganizationStatus.ARCHIVED else None,
                )
            )
        async with profile_session_factory() as session:
            assert (await service.get(session, identifier)).organization_id == identifier
        replacement = OrganizationProfileReplace(
            expected_version=1,
            brand_name="Matrix replacement",
        )
        if allowed:
            async with profile_session_factory.begin() as session:
                assert (
                    await service.replace(
                        session,
                        identifier,
                        replacement,
                        correlation_id="matrix-profile-replace",
                    )
                ).version == 2
        else:
            with pytest.raises(ProfileParentStateConflictError):
                async with profile_session_factory.begin() as session:
                    await service.replace(
                        session,
                        identifier,
                        replacement,
                        correlation_id="matrix-profile-rejected",
                    )

    asyncio.run(exercise())


@pytest.mark.integration
def test_organization_profile_create_permission_matrix(
    profile_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = OrganizationProfileService()
        mutable = {
            OrganizationStatus.PROSPECT,
            OrganizationStatus.ONBOARDING,
            OrganizationStatus.ACTIVE,
            OrganizationStatus.PAUSED,
        }
        for status in OrganizationStatus:
            async with profile_session_factory.begin() as session:
                organization = await add_organization(session, status=status)
                identifier = organization.id
            if status in mutable:
                async with profile_session_factory.begin() as session:
                    assert (
                        await service.create(
                            session,
                            identifier,
                            organization_profile(),
                            correlation_id=f"organization-create-{status.value}",
                        )
                    ).version == 1
            else:
                with pytest.raises(ProfileParentStateConflictError):
                    async with profile_session_factory.begin() as session:
                        await service.create(
                            session,
                            identifier,
                            organization_profile(),
                            correlation_id=f"organization-denied-{status.value}",
                        )

    asyncio.run(exercise())


@pytest.mark.integration
def test_location_profile_scope_replace_audit_and_rollback(
    profile_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationProfileService()
        async with profile_session_factory.begin() as session:
            first_org = await add_organization(session)
            second_org = await add_organization(session)
            location = await add_location(session, first_org.id)
            first_id, second_id, location_id = first_org.id, second_org.id, location.id
            created = await service.create(
                session,
                first_id,
                location_id,
                location_profile(),
                correlation_id="location-profile-create",
            )
            profile_id = created.id
        with pytest.raises(LocationProfileConflictError):
            async with profile_session_factory.begin() as session:
                await service.create(
                    session,
                    first_id,
                    location_id,
                    location_profile(),
                    correlation_id="location-profile-duplicate",
                )
        with pytest.raises(LocationNotFoundError):
            async with profile_session_factory.begin() as session:
                await service.create(
                    session,
                    second_id,
                    location_id,
                    location_profile(),
                    correlation_id="cross-organization-create",
                )
        with pytest.raises(LocationProfileNotFoundError):
            async with profile_session_factory() as session:
                await service.get(session, second_id, location_id)
        command = LocationProfileReplace(
            expected_version=1,
            local_description="Replacement local description",
            approved_claims=["Replacement local claim"],
        )
        with pytest.raises(RuntimeError, match="forced location profile rollback"):
            async with profile_session_factory.begin() as session:
                await service.replace(
                    session,
                    first_id,
                    location_id,
                    command,
                    correlation_id="location-profile-rollback",
                )
                raise RuntimeError("forced location profile rollback")
        async with profile_session_factory.begin() as session:
            updated = await service.replace(
                session,
                first_id,
                location_id,
                command,
                correlation_id="location-profile-update",
            )
            assert updated.version == 2
        with pytest.raises(LocationProfileVersionConflictError):
            async with profile_session_factory.begin() as session:
                await service.replace(
                    session,
                    first_id,
                    location_id,
                    command,
                    correlation_id="location-profile-stale",
                )
        async with profile_session_factory() as session:
            events = list(
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.resource_id == profile_id)
                )
            )
            rollback_event = await session.scalar(
                select(AuditEvent).where(AuditEvent.correlation_id == "location-profile-rollback")
            )
        assert len(events) == 2 and rollback_event is None
        assert all(event.organization_id == first_id for event in events)
        assert all(event.location_id == location_id for event in events)
        assert "Replacement local description" not in json.dumps(
            [event.event_metadata for event in events]
        )

    asyncio.run(exercise())


@pytest.mark.integration
@pytest.mark.parametrize(
    ("organization_status", "location_status", "allowed"),
    [
        (OrganizationStatus.PROSPECT, LocationStatus.SETUP_REQUIRED, True),
        (OrganizationStatus.ONBOARDING, LocationStatus.ACTIVE, True),
        (OrganizationStatus.ACTIVE, LocationStatus.PAUSED, True),
        (OrganizationStatus.PAUSED, LocationStatus.CLOSED_TEMPORARILY, True),
        (OrganizationStatus.SUSPENDED, LocationStatus.ACTIVE, False),
        (OrganizationStatus.OFFBOARDING, LocationStatus.PAUSED, False),
        (OrganizationStatus.ARCHIVED, LocationStatus.SETUP_REQUIRED, False),
        (OrganizationStatus.ACTIVE, LocationStatus.CLOSED_PERMANENTLY, False),
        (OrganizationStatus.ACTIVE, LocationStatus.ARCHIVED, False),
    ],
)
def test_location_profile_strictest_parent_matrix_and_read_preservation(
    profile_session_factory: async_sessionmaker[AsyncSession],
    organization_status: OrganizationStatus,
    location_status: LocationStatus,
    allowed: bool,
) -> None:
    async def exercise() -> None:
        service = LocationProfileService()
        async with profile_session_factory.begin() as session:
            organization = await add_organization(session)
            location = await add_location(session, organization.id)
            organization_id, location_id = organization.id, location.id
            await service.create(
                session,
                organization_id,
                location_id,
                location_profile(),
                correlation_id="location-matrix-create",
            )
        async with profile_session_factory.begin() as session:
            await session.execute(
                update(Organization)
                .where(Organization.id == organization_id)
                .values(
                    status=organization_status,
                    archived_at=(
                        utc_now() if organization_status is OrganizationStatus.ARCHIVED else None
                    ),
                )
            )
            await session.execute(
                update(Location)
                .where(Location.id == location_id)
                .values(
                    status=location_status,
                    archived_at=(utc_now() if location_status is LocationStatus.ARCHIVED else None),
                )
            )
        async with profile_session_factory() as session:
            assert (
                await service.get(session, organization_id, location_id)
            ).location_id == location_id
        replacement = LocationProfileReplace(
            expected_version=1,
            local_description="Matrix replacement",
        )
        if allowed:
            async with profile_session_factory.begin() as session:
                assert (
                    await service.replace(
                        session,
                        organization_id,
                        location_id,
                        replacement,
                        correlation_id="location-matrix-replace",
                    )
                ).version == 2
        else:
            with pytest.raises(ProfileParentStateConflictError):
                async with profile_session_factory.begin() as session:
                    await service.replace(
                        session,
                        organization_id,
                        location_id,
                        replacement,
                        correlation_id="location-matrix-rejected",
                    )

    asyncio.run(exercise())


@pytest.mark.integration
def test_location_profile_create_permission_matrix_and_strictest_parent(
    profile_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationProfileService()
        mutable_organizations = {
            OrganizationStatus.PROSPECT,
            OrganizationStatus.ONBOARDING,
            OrganizationStatus.ACTIVE,
            OrganizationStatus.PAUSED,
        }
        mutable_locations = {
            LocationStatus.SETUP_REQUIRED,
            LocationStatus.ACTIVE,
            LocationStatus.PAUSED,
            LocationStatus.CLOSED_TEMPORARILY,
        }
        for organization_status in OrganizationStatus:
            for location_status in LocationStatus:
                async with profile_session_factory.begin() as session:
                    organization = await add_organization(session, status=organization_status)
                    location = await add_location(session, organization.id, status=location_status)
                    organization_id, location_id = organization.id, location.id
                allowed = (
                    organization_status in mutable_organizations
                    and location_status in mutable_locations
                )
                if allowed:
                    async with profile_session_factory.begin() as session:
                        assert (
                            await service.create(
                                session,
                                organization_id,
                                location_id,
                                location_profile(),
                                correlation_id="location-create-matrix",
                            )
                        ).version == 1
                else:
                    with pytest.raises(ProfileParentStateConflictError):
                        async with profile_session_factory.begin() as session:
                            await service.create(
                                session,
                                organization_id,
                                location_id,
                                location_profile(),
                                correlation_id="location-create-denied",
                            )

    asyncio.run(exercise())


def test_missing_profile_and_repository_surfaces_are_narrow() -> None:
    assert {name for name in dir(OrganizationProfileRepository) if not name.startswith("_")} == {
        "add",
        "get_for_organization",
        "replace",
    }
    assert {name for name in dir(LocationProfileRepository) if not name.startswith("_")} == {
        "add",
        "get_for_location",
        "replace",
    }
    assert not hasattr(OrganizationProfile, "delete")
    assert not hasattr(LocationProfile, "delete")


@pytest.mark.integration
def test_missing_profiles_return_profile_specific_not_found(
    profile_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        async with profile_session_factory.begin() as session:
            organization = await add_organization(session)
            location = await add_location(session, organization.id)
            organization_id, location_id = organization.id, location.id
        with pytest.raises(OrganizationProfileNotFoundError):
            async with profile_session_factory() as session:
                await OrganizationProfileService().get(session, organization_id)
        with pytest.raises(LocationProfileNotFoundError):
            async with profile_session_factory() as session:
                await LocationProfileService().get(session, organization_id, location_id)

    asyncio.run(exercise())
