"""Location service, transaction, lifecycle, and isolation tests."""

import asyncio
from uuid import UUID

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.locations.contracts import LocationCreate
from apps.api.app.locations.enums import LocationLifecycleAction, LocationStatus, LocationType
from apps.api.app.locations.errors import (
    LocationNotFoundError,
    LocationParentStateConflictError,
    LocationPrimaryConflictError,
    LocationSlugConflictError,
    LocationTransitionConflictError,
    LocationVersionConflictError,
)
from apps.api.app.locations.models import Location
from apps.api.app.locations.service import CREATE_ALLOWED, TRANSITIONS, LocationService
from apps.api.app.organizations.contracts import OrganizationCreate
from apps.api.app.organizations.enums import (
    OrganizationLifecycleAction,
    OrganizationStatus,
    OrganizationType,
)
from apps.api.app.organizations.service import OrganizationService


def organization(slug: str) -> OrganizationCreate:
    return OrganizationCreate(
        # Derived from the slug: creation refuses a second client whose name
        # matches an existing one, and these fixtures share a database.
        name=f"Fabricated Organization {slug}",
        slug=slug,
        organization_type=OrganizationType.TEST,
        timezone="UTC",
        default_currency="USD",
    )


def location(slug: str = "fabricated-location", *, primary: bool = False) -> LocationCreate:
    return LocationCreate(
        name="Fabricated Location",
        slug=slug,
        location_type=LocationType.PHYSICAL,
        timezone="UTC",
        address_line_1="1 Example Way",
        city="Example",
        region="CA",
        postal_code="00000",
        country_code="US",
        is_primary=primary,
    )


def typed_location(location_type: LocationType) -> LocationCreate:
    shared: dict[str, object] = {
        "name": f"Fabricated {location_type.value}",
        "slug": f"fabricated-{location_type.value.replace('_', '-')}",
        "location_type": location_type,
        "timezone": "UTC",
        "country_code": "US",
    }
    if location_type in {LocationType.PHYSICAL, LocationType.HYBRID}:
        shared.update(
            address_line_1="1 Example Way",
            city="Example",
            region="CA",
            postal_code="00000",
        )
    if location_type in {LocationType.SERVICE_AREA, LocationType.HYBRID}:
        shared["service_area_description"] = "Fabricated service boundary"
    if location_type is LocationType.VIRTUAL:
        shared["website_url"] = "https://example.invalid"
    return LocationCreate.model_validate(shared)


async def setup_organization(
    factory: async_sessionmaker[AsyncSession], slug: str, *, active: bool = True
) -> UUID:
    service = OrganizationService()
    async with factory.begin() as session:
        item = await service.create(session, organization(slug), correlation_id="org-create")
        identifier = item.id
    if active:
        async with factory.begin() as session:
            await service.transition(
                session,
                identifier,
                action=OrganizationLifecycleAction.START_ONBOARDING,
                expected_version=1,
                correlation_id="org-onboard",
            )
        async with factory.begin() as session:
            await service.transition(
                session,
                identifier,
                action=OrganizationLifecycleAction.ACTIVATE,
                expected_version=2,
                correlation_id="org-active",
            )
    return identifier


@pytest.mark.integration
def test_creation_lifecycle_audit_rollback_and_isolation(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationService()
        first_org = await setup_organization(location_session_factory, "location-org-one")
        second_org = await setup_organization(location_session_factory, "location-org-two")
        async with location_session_factory.begin() as session:
            first = await service.create(
                session, first_org, location(), correlation_id="location-create"
            )
            first_id = first.id
            second = await service.create(
                session, second_org, location(), correlation_id="location-create-two"
            )
            assert second.slug == first.slug
        with pytest.raises(RuntimeError, match="forced transition rollback"):
            async with location_session_factory.begin() as session:
                await service.transition(
                    session,
                    first_org,
                    first_id,
                    action=LocationLifecycleAction.ACTIVATE,
                    expected_version=1,
                    correlation_id="rolled-back-activate",
                )
                raise RuntimeError("forced transition rollback")
        async with location_session_factory() as session:
            rolled_back = await service.get(session, first_org, first_id)
            rolled_back_events = list(
                await session.scalars(select(AuditEvent).where(AuditEvent.location_id == first_id))
            )
            assert rolled_back.status is LocationStatus.SETUP_REQUIRED
            assert rolled_back.version == 1
            assert len(rolled_back_events) == 1
        async with location_session_factory.begin() as session:
            active = await service.transition(
                session,
                first_org,
                first_id,
                action=LocationLifecycleAction.ACTIVATE,
                expected_version=1,
                correlation_id="activate",
            )
            assert active.status is LocationStatus.ACTIVE and active.version == 2
        async with location_session_factory.begin() as session:
            permanent = await service.transition(
                session,
                first_org,
                first_id,
                action=LocationLifecycleAction.CLOSE_PERMANENTLY,
                expected_version=2,
                correlation_id="close",
            )
            assert permanent.version == 3
        async with location_session_factory.begin() as session:
            archived = await service.transition(
                session,
                first_org,
                first_id,
                action=LocationLifecycleAction.ARCHIVE,
                expected_version=3,
                correlation_id="archive",
            )
            assert archived.archived_at is not None and archived.version == 4
        with pytest.raises(LocationTransitionConflictError):
            async with location_session_factory.begin() as session:
                await service.transition(
                    session,
                    first_org,
                    first_id,
                    action=LocationLifecycleAction.ACTIVATE,
                    expected_version=4,
                    correlation_id="reopen",
                )
        with pytest.raises(LocationNotFoundError):
            async with location_session_factory() as session:
                await service.get(session, second_org, first_id)
        with pytest.raises(RuntimeError):
            async with location_session_factory.begin() as session:
                await service.create(
                    session, first_org, location("rolled-back"), correlation_id="rollback"
                )
                raise RuntimeError("forced")
        async with location_session_factory() as session:
            assert (
                await session.scalar(select(Location).where(Location.slug == "rolled-back")) is None
            )
            events = list(
                await session.scalars(select(AuditEvent).where(AuditEvent.location_id == first_id))
            )
            assert len(events) == 4 and all(event.organization_id == first_org for event in events)

    asyncio.run(exercise())


@pytest.mark.integration
def test_versions_invalid_transitions_parent_rules_and_pagination(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationService()
        active_org = await setup_organization(location_session_factory, "active-location-org")
        prospect_org = await setup_organization(
            location_session_factory, "prospect-location-org", active=False
        )
        async with location_session_factory.begin() as session:
            item = await service.create(
                session, active_org, location("page-one", primary=True), correlation_id="create"
            )
            identifier = item.id
            await service.create(
                session, active_org, location("page-two"), correlation_id="create-two"
            )
            prospect = await service.create(
                session, prospect_org, location("prospect-one"), correlation_id="prospect"
            )
        with pytest.raises(LocationSlugConflictError):
            async with location_session_factory.begin() as session:
                await service.create(
                    session, active_org, location("page-one"), correlation_id="duplicate"
                )
        with pytest.raises(LocationPrimaryConflictError):
            async with location_session_factory.begin() as session:
                await service.create(
                    session,
                    active_org,
                    location("second-primary", primary=True),
                    correlation_id="primary-conflict",
                )
        with pytest.raises(DBAPIError):
            async with location_session_factory.begin() as session:
                await session.execute(
                    update(Location)
                    .where(Location.id == identifier)
                    .values(slug="mutated-location")
                )
        with pytest.raises(LocationVersionConflictError):
            async with location_session_factory.begin() as session:
                await service.transition(
                    session,
                    active_org,
                    identifier,
                    action=LocationLifecycleAction.ACTIVATE,
                    expected_version=9,
                    correlation_id="stale",
                )
        with pytest.raises(LocationTransitionConflictError):
            async with location_session_factory.begin() as session:
                await service.transition(
                    session,
                    active_org,
                    identifier,
                    action=LocationLifecycleAction.PAUSE,
                    expected_version=1,
                    correlation_id="invalid",
                )
        with pytest.raises(LocationParentStateConflictError):
            async with location_session_factory.begin() as session:
                await service.transition(
                    session,
                    prospect_org,
                    prospect.id,
                    action=LocationLifecycleAction.ACTIVATE,
                    expected_version=1,
                    correlation_id="parent",
                )
        async with location_session_factory() as session:
            page, more = await service.list(session, active_org, limit=1, offset=0)
            assert len(page) == 1 and more
            assert await service.repository.get_by_id(session, prospect_org, identifier) is None
        assert not any(
            name in {"delete", "update", "update_slug"} for name in dir(service.repository)
        )

    asyncio.run(exercise())


@pytest.mark.integration
def test_database_accepts_every_approved_location_type(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationService()
        organization_id = await setup_organization(location_session_factory, "all-location-types")
        async with location_session_factory.begin() as session:
            created = [
                await service.create(
                    session,
                    organization_id,
                    typed_location(location_type),
                    correlation_id=f"create-{location_type.value}",
                )
                for location_type in LocationType
            ]
        assert {item.location_type for item in created} == set(LocationType)

    asyncio.run(exercise())


def test_lifecycle_matrix_matches_approved_policy() -> None:
    assert {
        LocationStatus.SETUP_REQUIRED: {LocationStatus.ACTIVE, LocationStatus.ARCHIVED},
        LocationStatus.ACTIVE: {
            LocationStatus.PAUSED,
            LocationStatus.CLOSED_TEMPORARILY,
            LocationStatus.CLOSED_PERMANENTLY,
        },
        LocationStatus.PAUSED: {
            LocationStatus.ACTIVE,
            LocationStatus.CLOSED_TEMPORARILY,
            LocationStatus.CLOSED_PERMANENTLY,
            LocationStatus.ARCHIVED,
        },
        LocationStatus.CLOSED_TEMPORARILY: {
            LocationStatus.ACTIVE,
            LocationStatus.PAUSED,
            LocationStatus.CLOSED_PERMANENTLY,
        },
        LocationStatus.CLOSED_PERMANENTLY: {LocationStatus.ARCHIVED},
        LocationStatus.ARCHIVED: set(),
    } == TRANSITIONS


def test_parent_organization_matrix_matches_approved_policy() -> None:
    assert {
        OrganizationStatus.PROSPECT,
        OrganizationStatus.ONBOARDING,
        OrganizationStatus.ACTIVE,
        OrganizationStatus.PAUSED,
    } == CREATE_ALLOWED
    for parent in {OrganizationStatus.SUSPENDED, OrganizationStatus.ARCHIVED}:
        for target in LocationStatus:
            assert not LocationService._parent_allows(parent, LocationStatus.SETUP_REQUIRED, target)
    for parent in {
        OrganizationStatus.PROSPECT,
        OrganizationStatus.ONBOARDING,
        OrganizationStatus.PAUSED,
    }:
        assert not LocationService._parent_allows(
            parent, LocationStatus.PAUSED, LocationStatus.ACTIVE
        )
        assert LocationService._parent_allows(
            parent, LocationStatus.PAUSED, LocationStatus.CLOSED_PERMANENTLY
        )
    assert LocationService._parent_allows(
        OrganizationStatus.OFFBOARDING,
        LocationStatus.ACTIVE,
        LocationStatus.CLOSED_PERMANENTLY,
    )
    assert LocationService._parent_allows(
        OrganizationStatus.OFFBOARDING,
        LocationStatus.SETUP_REQUIRED,
        LocationStatus.ARCHIVED,
    )
    assert not LocationService._parent_allows(
        OrganizationStatus.OFFBOARDING,
        LocationStatus.CLOSED_TEMPORARILY,
        LocationStatus.ARCHIVED,
    )
