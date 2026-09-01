"""Editing an existing location, and moving the primary designation.

Neither was possible. A location could be created and its lifecycle changed,
but never corrected — so a typo in the name, or a wrong address, was permanent.
The only way around it was to create a second location, and that made things
worse: product readiness evaluates every non-archived location, so the spare
one blocked activation, and there was no way to remove it either.

That is the shape these tests pin: not just that the writes work, but that they
cannot leave a client in a state that blocks its own activation.
"""

import asyncio
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.locations.contracts import LocationCreate, LocationUpdate
from apps.api.app.locations.enums import LocationLifecycleAction, LocationStatus, LocationType
from apps.api.app.locations.errors import (
    LocationNotFoundError,
    LocationTransitionConflictError,
    LocationVersionConflictError,
)
from apps.api.app.locations.models import Location
from apps.api.app.locations.service import LocationService
from apps.api.app.organizations.contracts import OrganizationCreate
from apps.api.app.organizations.enums import (
    OrganizationLifecycleAction,
    OrganizationType,
)
from apps.api.app.organizations.service import OrganizationService


def organization(slug: str) -> OrganizationCreate:
    return OrganizationCreate(
        name=f"Fabricated Organization {slug}",
        slug=slug,
        organization_type=OrganizationType.TEST,
        timezone="UTC",
        default_currency="USD",
    )


def location(
    slug: str, *, primary: bool = False, name: str = "Fabricated Location"
) -> LocationCreate:
    return LocationCreate(
        name=name,
        slug=slug,
        location_type=LocationType.PHYSICAL,
        timezone="UTC",
        address_line_1="1 Example Way",
        city="Example",
        region="CA",
        postal_code="00000",
        country_code="US",
        phone="+15550000000",
        is_primary=primary,
    )


async def setup_organization(factory: async_sessionmaker[AsyncSession], slug: str) -> UUID:
    service = OrganizationService()
    async with factory.begin() as session:
        item = await service.create(session, organization(slug), correlation_id="org-create")
        identifier = item.id
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
def test_update_corrects_fields_without_blanking_the_others(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationService()
        org = await setup_organization(location_session_factory, "loc-edit-basic")
        async with location_session_factory.begin() as session:
            created = await service.create(session, org, location("edit-basic"), correlation_id="c")
            location_id, version = created.id, created.version

        # Correct only the name and city. Everything else must survive: the
        # form this is reached from may not render every field, and an omitted
        # field must not be read as "clear it".
        async with location_session_factory.begin() as session:
            updated = await service.update(
                session,
                org,
                location_id,
                LocationUpdate(expected_version=version, name="Corrected Name", city="Oceanside"),
                correlation_id="u",
            )
            assert updated.name == "Corrected Name"
            assert updated.city == "Oceanside"
            assert updated.phone == "+15550000000"
            assert updated.address_line_1 == "1 Example Way"
            assert updated.postal_code == "00000"
            assert updated.version == version + 1

    asyncio.run(exercise())


@pytest.mark.integration
def test_update_is_rejected_on_a_stale_version(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationService()
        org = await setup_organization(location_session_factory, "loc-edit-stale")
        async with location_session_factory.begin() as session:
            created = await service.create(session, org, location("edit-stale"), correlation_id="c")
            location_id = created.id

        async with location_session_factory.begin() as session:
            await service.update(
                session,
                org,
                location_id,
                LocationUpdate(expected_version=1, name="First Writer"),
                correlation_id="u1",
            )

        # Second operator still holding version 1 must lose, not silently
        # overwrite the first operator's correction.
        with pytest.raises(LocationVersionConflictError):
            async with location_session_factory.begin() as session:
                await service.update(
                    session,
                    org,
                    location_id,
                    LocationUpdate(expected_version=1, name="Second Writer"),
                    correlation_id="u2",
                )

        async with location_session_factory() as session:
            current = await session.get(Location, location_id)
            assert current is not None
            assert current.name == "First Writer"

    asyncio.run(exercise())


@pytest.mark.integration
def test_a_no_op_update_does_not_burn_a_version(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationService()
        org = await setup_organization(location_session_factory, "loc-edit-noop")
        async with location_session_factory.begin() as session:
            created = await service.create(session, org, location("edit-noop"), correlation_id="c")
            location_id, version = created.id, created.version

        async with location_session_factory.begin() as session:
            unchanged = await service.update(
                session,
                org,
                location_id,
                LocationUpdate(expected_version=version, name="Fabricated Location"),
                correlation_id="u",
            )
            # Saving a form without changing anything must not invalidate the
            # copy the operator still has open in another tab.
            assert unchanged.version == version

    asyncio.run(exercise())


@pytest.mark.integration
def test_update_refuses_an_unknown_location(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationService()
        org = await setup_organization(location_session_factory, "loc-edit-missing")
        with pytest.raises(LocationNotFoundError):
            async with location_session_factory.begin() as session:
                await service.update(
                    session,
                    org,
                    uuid4(),
                    LocationUpdate(expected_version=1, name="Nowhere"),
                    correlation_id="u",
                )

    asyncio.run(exercise())


@pytest.mark.integration
def test_update_records_which_fields_changed_and_not_their_values(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationService()
        org = await setup_organization(location_session_factory, "loc-edit-audit")
        async with location_session_factory.begin() as session:
            created = await service.create(session, org, location("edit-audit"), correlation_id="c")
            location_id = created.id

        async with location_session_factory.begin() as session:
            await service.update(
                session,
                org,
                location_id,
                LocationUpdate(expected_version=1, phone="+15551234567"),
                correlation_id="audit-me",
            )

        async with location_session_factory() as session:
            event = (
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.action == "location.update")
                )
            ).one()
            assert event.event_metadata["fields"] == "phone"
            # A client's phone number is not audit payload.
            assert "+15551234567" not in str(event.event_metadata)

    asyncio.run(exercise())


@pytest.mark.integration
def test_set_primary_moves_the_designation_and_leaves_exactly_one(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationService()
        org = await setup_organization(location_session_factory, "loc-primary-move")
        async with location_session_factory.begin() as session:
            first = await service.create(
                session, org, location("primary-first", primary=True), correlation_id="c1"
            )
            second = await service.create(
                session, org, location("primary-second"), correlation_id="c2"
            )
            first_id, second_id, second_version = first.id, second.id, second.version

        async with location_session_factory.begin() as session:
            promoted = await service.set_primary(
                session,
                org,
                second_id,
                expected_version=second_version,
                correlation_id="p",
            )
            assert promoted.is_primary is True

        # A partial unique index enforces one primary. The demote-then-promote
        # order is what keeps this from tripping it.
        async with location_session_factory() as session:
            primaries = list(
                await session.scalars(
                    select(Location).where(
                        Location.organization_id == org, Location.is_primary.is_(True)
                    )
                )
            )
            assert len(primaries) == 1
            assert primaries[0].id == second_id
            demoted = await session.get(Location, first_id)
            assert demoted is not None and demoted.is_primary is False

    asyncio.run(exercise())


@pytest.mark.integration
def test_set_primary_on_the_current_primary_is_a_no_op(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = LocationService()
        org = await setup_organization(location_session_factory, "loc-primary-noop")
        async with location_session_factory.begin() as session:
            only = await service.create(
                session, org, location("primary-only", primary=True), correlation_id="c"
            )
            only_id, version = only.id, only.version

        async with location_session_factory.begin() as session:
            same = await service.set_primary(
                session, org, only_id, expected_version=version, correlation_id="p"
            )
            assert same.is_primary is True
            assert same.version == version

    asyncio.run(exercise())


@pytest.mark.integration
def test_a_retired_location_cannot_become_primary(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The primary location is what readiness and GBP mapping resolve against.

    Pointing it at an archived location would produce a client that looks
    configured and cannot work.
    """

    async def exercise() -> None:
        service = LocationService()
        org = await setup_organization(location_session_factory, "loc-primary-retired")
        async with location_session_factory.begin() as session:
            keeper = await service.create(
                session, org, location("primary-keeper", primary=True), correlation_id="c1"
            )
            spare = await service.create(
                session, org, location("primary-spare"), correlation_id="c2"
            )
            spare_id = spare.id
            assert keeper.is_primary

        async with location_session_factory.begin() as session:
            await service.transition(
                session,
                org,
                spare_id,
                action=LocationLifecycleAction.ARCHIVE,
                expected_version=1,
                correlation_id="archive",
            )

        async with location_session_factory() as session:
            archived = await session.get(Location, spare_id)
            assert archived is not None
            archived_version = archived.version
            assert archived.status is LocationStatus.ARCHIVED

        with pytest.raises(LocationTransitionConflictError):
            async with location_session_factory.begin() as session:
                await service.set_primary(
                    session,
                    org,
                    spare_id,
                    expected_version=archived_version,
                    correlation_id="p",
                )

    asyncio.run(exercise())


@pytest.mark.integration
def test_archiving_the_spare_location_is_what_unblocks_activation(
    location_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The exact situation a client got stuck in.

    Two locations exist, one of them unwanted. Product readiness evaluates
    every location that is not closed-permanently or archived, so the unwanted
    one keeps the client blocked. Archiving it is the escape, and this pins
    that the archived location really does drop out of that set.
    """

    async def exercise() -> None:
        service = LocationService()
        org = await setup_organization(location_session_factory, "loc-spare-archive")
        async with location_session_factory.begin() as session:
            await service.create(
                session,
                org,
                location("spare-real", primary=True, name="Cococabana"),
                correlation_id="c1",
            )
            spare = await service.create(
                session, org, location("spare-extra", name="Main"), correlation_id="c2"
            )
            spare_id = spare.id

        def evaluated() -> Any:  # noqa: ANN401 - local helper
            return select(Location).where(
                Location.organization_id == org,
                Location.status.notin_(
                    (LocationStatus.CLOSED_PERMANENTLY, LocationStatus.ARCHIVED)
                ),
            )

        async with location_session_factory() as session:
            assert len(list(await session.scalars(evaluated()))) == 2

        async with location_session_factory.begin() as session:
            await service.transition(
                session,
                org,
                spare_id,
                action=LocationLifecycleAction.ARCHIVE,
                expected_version=1,
                correlation_id="archive",
            )

        async with location_session_factory() as session:
            remaining = list(await session.scalars(evaluated()))
            assert len(remaining) == 1
            assert remaining[0].name == "Cococabana"

    asyncio.run(exercise())
