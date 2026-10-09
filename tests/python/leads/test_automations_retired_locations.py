"""Archived and permanently closed locations: no dispatch, no automations, schedules paused."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.models import Schedule
from apps.api.app.execution.service import ExecutionService
from apps.api.app.locations.enums import LocationLifecycleAction, LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.locations.service import LocationService
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from leads import test_command_center_automations as automations
from leads import test_leads_api as canonical

HEADERS = canonical.HEADERS
run_db = canonical.run_db
canonical_leads_client = canonical.leads_client
AUTOMATIONS = automations.AUTOMATIONS
PORTFOLIO = automations.PORTFOLIO
LONG_AGO = datetime(2020, 1, 1, tzinfo=UTC)


async def second_location(session: AsyncSession, org: UUID, status: LocationStatus) -> UUID:
    place = Location(
        organization_id=org,
        name="DONT USE",
        slug="dont-use",
        location_type=LocationType.VIRTUAL,
        status=status,
        timezone="UTC",
        country_code="US",
        website_url="https://example.invalid/second",
        is_primary=False,
        archived_at=datetime.now(UTC) if status is LocationStatus.ARCHIVED else None,
        version=1,
    )
    session.add(place)
    await session.flush()
    return place.id


async def due(session: AsyncSession, schedule_id: UUID, when: datetime) -> None:
    await session.execute(
        update(Schedule).where(Schedule.id == schedule_id).values(next_run_at=when)
    )


def test_dispatch_skips_retired_locations_and_other_work_still_runs(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    _, ids = canonical_leads_client
    org, other, active = ids["organization"], ids["other_organization"], ids["location"]
    seeded: dict[str, UUID] = {}

    async def seed(session: AsyncSession) -> None:
        archived = await second_location(session, org, LocationStatus.ARCHIVED)
        closed = Location(
            organization_id=org,
            name="Closed",
            slug="closed-place",
            location_type=LocationType.VIRTUAL,
            status=LocationStatus.CLOSED_PERMANENTLY,
            timezone="UTC",
            country_code="US",
            website_url="https://example.invalid/closed",
            is_primary=False,
            version=1,
        )
        session.add(closed)
        await session.flush()
        # The retired schedules are due first, ahead of everything that can run.
        for name, key, location, when in [
            ("archived-a", "reviews.ingest", archived, LONG_AGO),
            ("archived-b", "gbp.sync_performance", archived, LONG_AGO),
            ("closed", "reviews.ingest", closed.id, LONG_AGO + timedelta(days=1)),
            ("good-location", "reviews.ingest", active, LONG_AGO + timedelta(days=2)),
            ("client-wide", "gbp.sync", None, LONG_AGO + timedelta(days=3)),
            ("other-client", "reviews.ingest", None, LONG_AGO + timedelta(days=4)),
        ]:
            owner = other if name == "other-client" else org
            seeded[name] = await automations.schedule(session, owner, key, location=location)
            await due(session, seeded[name], when)
        # The other client is archived, and a third schedule belongs to a removed client.
        await session.execute(
            update(Organization)
            .where(Organization.id == other)
            .values(status=OrganizationStatus.ARCHIVED, archived_at=datetime.now(UTC))
        )
        await session.commit()

    run_db(postgresql_test_url, seed)

    async def dispatch(session: AsyncSession) -> list[UUID]:
        service, started = ExecutionService(), []
        for _ in range(10):
            run = await service.dispatch_due_schedule(session, "retired-locations")
            if run is None:
                break
            scheduled = UUID(str(run.input_document["schedule_id"]))
            started.append(scheduled)
            # Move it into the future so the loop sees each schedule once.
            await due(session, scheduled, datetime.now(UTC) + timedelta(days=1))
            await session.commit()
        return started

    started = run_db(postgresql_test_url, dispatch)
    # Only the two that can run were dispatched, in order: nothing was stuck behind the rest.
    assert started == [seeded["good-location"], seeded["client-wide"]]

    async def untouched(session: AsyncSession) -> None:
        for name in ("archived-a", "archived-b", "closed", "other-client"):
            row = await session.get(Schedule, seeded[name])
            assert row is not None
            assert row.status == "active" and row.last_run_at is None
            assert row.next_run_at <= LONG_AGO + timedelta(days=4)

    run_db(postgresql_test_url, untouched)


def test_retiring_a_location_pauses_its_schedules_and_audits_it(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    _, ids = canonical_leads_client
    org, active = ids["organization"], ids["location"]
    seeded: dict[str, UUID] = {}

    async def seed(session: AsyncSession) -> UUID:
        place = await second_location(session, org, LocationStatus.ACTIVE)
        seeded["a"] = await automations.schedule(session, org, "reviews.ingest", location=place)
        seeded["b"] = await automations.schedule(
            session, org, "gbp.sync_performance", location=place
        )
        seeded["keep"] = await automations.schedule(session, org, "reviews.ingest", location=active)
        await session.commit()
        return place

    place = run_db(postgresql_test_url, seed)

    async def close(session: AsyncSession) -> None:
        await LocationService().transition(
            session,
            org,
            place,
            action=LocationLifecycleAction.CLOSE_PERMANENTLY,
            expected_version=1,
            correlation_id="retire-test",
        )
        await session.commit()

    run_db(postgresql_test_url, close)

    async def check(session: AsyncSession) -> None:
        statuses = {
            name: (await session.get(Schedule, schedule_id)).status  # type: ignore[union-attr]
            for name, schedule_id in seeded.items()
        }
        assert statuses == {"a": "paused", "b": "paused", "keep": "active"}
        events = list(
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.event_type.in_(
                        ["workflow.schedule.updated", "platform.location.lifecycle_changed"]
                    ),
                    AuditEvent.correlation_id == "retire-test",
                )
            )
        )
        paused = [e for e in events if e.event_type == "workflow.schedule.updated"]
        assert {e.resource_id for e in paused} == {seeded["a"], seeded["b"]}
        lifecycle = next(e for e in events if e.event_type == "platform.location.lifecycle_changed")
        assert lifecycle.event_metadata["paused_schedules"] == 2

    run_db(postgresql_test_url, check)


def test_retired_location_is_not_an_automation_and_cannot_run(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    org, active = ids["organization"], ids["location"]
    seeded: dict[str, UUID] = {}

    async def seed(session: AsyncSession) -> None:
        retired = await second_location(session, org, LocationStatus.ARCHIVED)
        seeded["live"] = await automations.schedule(
            session, org, "gbp.sync_performance", location=active
        )
        await automations.run(session, org, "gbp.sync_performance", "completed", 3, location=active)
        seeded["retired"] = await automations.schedule(
            session, org, "reviews.ingest", location=retired
        )
        # Its latest run is failing; that must not count anywhere.
        await automations.run(
            session,
            org,
            "reviews.ingest",
            "failed",
            1,
            "GBP_PERFORMANCE_ACCESS_DENIED",
            location=retired,
        )
        await session.commit()

    run_db(postgresql_test_url, seed)
    body = client.get(AUTOMATIONS, headers=HEADERS).json()
    assert [row["id"] for row in body["data"]] == [str(seeded["live"])]
    assert body["counts"]["needs_attention"] == 0 and body["counts"]["total"] == 1
    # Dashboard health shares the loader, so it agrees.
    portfolio = client.get(PORTFOLIO, headers=HEADERS).json()
    health = next(s for s in portfolio["systems"] if s["key"] == "automations")
    assert health == {"key": "automations", "status": "healthy", "affected_clients": 0}
    # No detail for it, and Run now is refused with a typed code.
    assert client.get(f"{AUTOMATIONS}/{seeded['retired']}", headers=HEADERS).status_code == 404
    refused = automations.run_now(client, seeded["retired"])
    assert refused.status_code == 409, refused.text
    assert refused.json()["error"]["code"] == "AUTOMATION_LOCATION_RETIRED"

    async def none_started(session: AsyncSession) -> int:
        rows = await session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "automation.run_now.requested")
        )
        return len(list(rows))

    assert run_db(postgresql_test_url, none_started) == 0
