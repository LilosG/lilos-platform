"""Reviews Google stops returning are marked removed, guarded, restored, and never replied to."""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.insights.aggregation_service import InsightsService
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.reviews.errors import ReviewNoLongerOnProviderError
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision, ReviewRevision
from apps.api.app.products.reviews.publish_handler import handle_reviews_publish_response
from apps.api.app.products.reviews.service import ReviewService
from apps.api.app.routes.command_center_reads import review_summary

from .test_review_publish_handler import FakeAdapter, FakeSession, _install_provider, _objects
from .test_reviews_ingestion import (
    _ingestion_service,
    _raw_review,
    _raw_reviews,
    _reply,
    _seed_review_location,
    _settings,
    _sync,
)

REMOVED_EVENT = "reviews.review.removed_from_provider"
RESTORED_EVENT = "reviews.review.restored_on_provider"
MASS_EVENT = "reviews.sync.mass_missing"

Setup = tuple[async_sessionmaker[AsyncSession], UUID, UUID]


@pytest.fixture
def setup(
    reviews_session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[Setup]:
    organization_id, location_id = asyncio.run(_seed_review_location(reviews_session_factory))
    yield reviews_session_factory, organization_id, location_id


def _statuses(factory: async_sessionmaker[AsyncSession], organization_id: UUID) -> dict[str, str]:
    async def read() -> dict[str, str]:
        async with factory() as session:
            rows = await session.execute(
                select(Review.external_review_id, Review.status).where(
                    Review.organization_id == organization_id
                )
            )
            return {external: status for external, status in rows.all()}

    return asyncio.run(read())


def _events(factory: async_sessionmaker[AsyncSession], organization_id: UUID, name: str) -> int:
    async def read() -> int:
        async with factory() as session:
            return (
                await session.scalar(
                    select(func.count())
                    .select_from(AuditEvent)
                    .where(
                        AuditEvent.organization_id == organization_id,
                        AuditEvent.event_type == name,
                    )
                )
                or 0
            )

    return asyncio.run(read())


def _sync_now(
    setup: Setup, postgresql_test_url: str, raw: list[dict[str, Any]], label: str
) -> dict[str, object]:
    factory, organization_id, location_id = setup
    return asyncio.run(
        _sync(factory, _settings(postgresql_test_url), organization_id, location_id, raw, label)
    )


@pytest.mark.integration
def test_missing_reviews_are_marked_removed_with_one_audit_each_and_it_is_idempotent(
    setup: Setup, postgresql_test_url: str
) -> None:
    """Miss B's shape: six recent and two older reviews stop being returned."""
    factory, organization_id, _ = setup
    everything = _raw_reviews(60)
    _sync_now(setup, postgresql_test_url, everything, "first")

    # Give the reviews distinct ages so "recent" and "older" mean something.
    async def age() -> None:
        async with factory.begin() as session:
            for review in await session.scalars(
                select(Review).where(Review.organization_id == organization_id)
            ):
                number = int(review.external_review_id.split("-")[1])
                review.review_created_at = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=number)

    asyncio.run(age())
    vanished = {f"review-{n}" for n in (59, 58, 57, 56, 55, 54, 0, 1)}  # six recent, two old
    returned = [raw for raw in everything if raw["reviewId"] not in vanished]

    summary = _sync_now(setup, postgresql_test_url, returned, "second")

    assert summary["removed"] == 8
    statuses = _statuses(factory, organization_id)
    assert {key for key, value in statuses.items() if value == "removed"} == vanished
    assert all(value != "removed" for key, value in statuses.items() if key not in vanished)
    assert _events(factory, organization_id, REMOVED_EVENT) == 8
    assert _events(factory, organization_id, MASS_EVENT) == 0

    # The same list again changes nothing and audits nothing more.
    again = _sync_now(setup, postgresql_test_url, returned, "third")
    assert again["removed"] == 0
    assert _events(factory, organization_id, REMOVED_EVENT) == 8


@pytest.mark.integration
def test_nothing_is_marked_when_the_ingest_raises(setup: Setup, postgresql_test_url: str) -> None:
    factory, organization_id, location_id = setup
    everything = _raw_reviews(20)
    _sync_now(setup, postgresql_test_url, everything, "first")
    broken = {**_raw_review(review_id="review-broken"), "reviewReply": "not an object"}

    async def failing() -> None:
        async with factory() as session, session.begin():
            await _ingestion_service([*everything[:15], broken]).ingest_for_location(
                session,
                _settings(postgresql_test_url),
                organization_id,
                location_id,
                actor_id=None,
                correlation_id="raises",
            )

    with pytest.raises(ValueError):
        asyncio.run(failing())
    assert "removed" not in _statuses(factory, organization_id).values()
    assert _events(factory, organization_id, REMOVED_EVENT) == 0


@pytest.mark.integration
def test_an_empty_list_marks_nothing_and_records_the_guard(
    setup: Setup, postgresql_test_url: str
) -> None:
    factory, organization_id, _ = setup
    _sync_now(setup, postgresql_test_url, _raw_reviews(12), "first")

    summary = _sync_now(setup, postgresql_test_url, [], "empty")

    assert summary["removed"] == 0
    assert "removed" not in _statuses(factory, organization_id).values()
    assert _events(factory, organization_id, MASS_EVENT) == 1

    async def guard_metadata() -> dict[str, Any]:
        async with factory() as session:
            event = await session.scalar(
                select(AuditEvent).where(
                    AuditEvent.organization_id == organization_id,
                    AuditEvent.event_type == MASS_EVENT,
                )
            )
            assert event is not None
            return dict(event.event_metadata)

    assert asyncio.run(guard_metadata()) == {
        "code": "REVIEW_SYNC_MASS_MISSING",
        "missing": 12,
        "active": 12,
        "returned": 0,
    }


@pytest.mark.integration
@pytest.mark.parametrize(
    ("held", "missing", "marked"),
    [
        (60, 20, 0),  # a third of the reviews, and more than ten: a bad answer
        (40, 11, 0),  # 27.5 percent and more than ten: trips
        (40, 10, 10),  # exactly ten is not more than ten: a real removal
        (60, 11, 11),  # more than ten but only 18 percent: a real removal
        (8, 4, 4),  # half of a small location is still under the minimum count
    ],
)
def test_the_mass_removal_guard_trips_only_on_a_large_share(
    setup: Setup, postgresql_test_url: str, held: int, missing: int, marked: int
) -> None:
    factory, organization_id, _ = setup
    everything = _raw_reviews(held)
    _sync_now(setup, postgresql_test_url, everything, "first")

    summary = _sync_now(setup, postgresql_test_url, everything[missing:], "second")

    assert summary["removed"] == marked
    removed = [k for k, v in _statuses(factory, organization_id).items() if v == "removed"]
    assert len(removed) == marked
    assert _events(factory, organization_id, MASS_EVENT) == (0 if marked else 1)


@pytest.mark.integration
def test_a_review_that_returns_goes_back_through_the_normal_ingest_status(
    setup: Setup, postgresql_test_url: str
) -> None:
    factory, organization_id, _ = setup
    everything = _raw_reviews(5)
    replied = _raw_review(review_id="review-replied", reply=_reply())
    _sync_now(setup, postgresql_test_url, [*everything, replied], "first")
    assert _statuses(factory, organization_id)["review-replied"] == "responded"

    gone = _sync_now(setup, postgresql_test_url, everything[:4], "gone")
    assert gone["removed"] == 2
    statuses = _statuses(factory, organization_id)
    assert (statuses["review-4"], statuses["review-replied"]) == ("removed", "removed")

    _sync_now(setup, postgresql_test_url, [*everything, replied], "back")

    statuses = _statuses(factory, organization_id)
    # A review with an observed reply is responded again; the other is classified as ingest would.
    assert statuses["review-replied"] == "responded"
    assert statuses["review-4"] == "classified"
    assert _events(factory, organization_id, RESTORED_EVENT) == 2
    # A further sync with the same list restores nothing more.
    _sync_now(setup, postgresql_test_url, [*everything, replied], "stable")
    assert _events(factory, organization_id, RESTORED_EVENT) == 2


@pytest.mark.integration
def test_other_locations_mappings_and_tenants_are_never_touched(
    setup: Setup, postgresql_test_url: str
) -> None:
    factory, organization_id, location_id = setup

    async def seed_neighbours() -> tuple[UUID, UUID]:
        async with factory.begin() as session:
            provider = await session.scalar(
                select(Provider).where(Provider.key == "google_business_profile")
            )
            connection = await session.scalar(
                select(IntegrationConnection).where(
                    IntegrationConnection.organization_id == organization_id
                )
            )
            assert provider is not None and connection is not None
            sibling = Location(
                organization_id=organization_id,
                name="Sibling",
                slug="sibling",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://sibling.example.invalid",
                is_primary=False,
                version=1,
            )
            other_org = Organization(
                name="Other Tenant",
                slug="other-tenant-removal",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add_all([sibling, other_org])
            await session.flush()
            other_location = Location(
                organization_id=other_org.id,
                name="Elsewhere",
                slug="elsewhere",
                location_type=LocationType.VIRTUAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                website_url="https://elsewhere.example.invalid",
                is_primary=True,
                version=1,
            )
            other_connection = IntegrationConnection(
                organization_id=other_org.id,
                provider_id=provider.id,
                external_account_reference="accounts/999",
                status="connected",
            )
            session.add_all([other_location, other_connection])
            await session.flush()
            mappings = [
                ProviderResourceMapping(
                    organization_id=organization_id,
                    connection_id=connection.id,
                    resource_type="location",
                    external_resource_id="locations/sibling",
                    platform_resource_id=sibling.id,
                    status="active",
                ),
                ProviderResourceMapping(
                    organization_id=other_org.id,
                    connection_id=other_connection.id,
                    resource_type="location",
                    external_resource_id="locations/999",
                    platform_resource_id=other_location.id,
                    status="active",
                ),
            ]
            session.add_all(mappings)
            await session.flush()
            service = ReviewService()
            # Same external ids as the synced location, held by other scopes.
            for org, loc, mapping in (
                (organization_id, sibling.id, mappings[0].id),
                (other_org.id, other_location.id, mappings[1].id),
            ):
                for index in range(3):
                    await service.ingest(
                        session,
                        organization_id=org,
                        location_id=loc,
                        integration_resource_id=mapping,
                        external_review_id=f"review-{index}",
                        provider="google_business_profile",
                        rating=5,
                        title=None,
                        body=f"Review {index}",
                        created_at=datetime(2026, 1, 1, tzinfo=UTC),
                        updated_at=None,
                        correlation_id="neighbours",
                    )
            return sibling.id, other_org.id

    _sync_now(setup, postgresql_test_url, _raw_reviews(10), "first")
    sibling_id, other_org_id = asyncio.run(seed_neighbours())

    # The synced location now returns only one review; the guard stays quiet for 3 of 10 missing.
    summary = _sync_now(setup, postgresql_test_url, _raw_reviews(10)[3:], "second")
    assert summary["removed"] == 3

    async def untouched() -> tuple[set[str], set[str]]:
        async with factory() as session:
            rows = (
                await session.execute(
                    select(Review.organization_id, Review.location_id, Review.status)
                )
            ).all()
        sibling_states = {s for org, loc, s in rows if loc == sibling_id}
        other_states = {s for org, loc, s in rows if org == other_org_id}
        return sibling_states, other_states

    sibling_states, other_states = asyncio.run(untouched())
    assert "removed" not in sibling_states | other_states
    statuses = _statuses(factory, organization_id)
    assert sum(1 for value in statuses.values() if value == "removed") == 3 + 0


@pytest.mark.integration
def test_aggregates_and_the_default_list_leave_removed_reviews_out(
    setup: Setup, postgresql_test_url: str
) -> None:
    factory, organization_id, location_id = setup
    everything = _raw_reviews(30)
    for raw in everything[:4]:
        raw["starRating"] = "ONE"
    _sync_now(setup, postgresql_test_url, everything, "first")
    # Three one-star reviews vanish: the average must rise, the totals must fall.
    _sync_now(setup, postgresql_test_url, everything[3:], "second")

    async def read() -> dict[str, Any]:
        service = ReviewService()
        async with factory() as session:
            summary = await service.summary(session, organization_id, location_id)
            listed, _ = await service.list_reviews(session, organization_id, location_id)
            removed, _ = await service.list_reviews(
                session, organization_id, location_id, status_in=("removed",)
            )
            portfolio = await review_summary(
                session, [organization_id], {organization_id}, datetime(2025, 1, 1, tzinfo=UTC)
            )
            activity = await InsightsService().summary(
                session, organization_id, location_id=location_id
            )
        return {
            "summary": summary,
            "listed": len(listed),
            "removed": len(removed),
            "portfolio": portfolio[organization_id],
            "activity": activity,
        }

    data = asyncio.run(read())
    assert data["summary"]["by_status"]["removed"] == 3
    assert data["summary"]["average_rating"] == 5.0 * 26 / 27 + 1.0 * 1 / 27
    assert (data["listed"], data["removed"]) == (27, 3)
    portfolio = data["portfolio"]
    assert (portfolio.total, portfolio.average_rating) == (27, round(float(5 * 26 + 1) / 27, 1))
    assert sum(data["activity"]["reviews"].values()) == 27
    assert "removed" not in data["activity"]["reviews"]


@pytest.mark.integration
def test_the_service_refuses_every_reply_step_for_a_removed_review(
    setup: Setup, postgresql_test_url: str
) -> None:
    factory, organization_id, location_id = setup
    _sync_now(setup, postgresql_test_url, _raw_reviews(1), "first")

    async def scenario() -> list[str]:
        service = ReviewService()
        codes: list[str] = []
        async with factory.begin() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            revision = (
                await session.scalars(
                    select(ReviewRevision).where(ReviewRevision.review_id == review.id)
                )
            ).one()
            responses = [
                ReviewResponseRevision(
                    organization_id=organization_id,
                    location_id=location_id,
                    review_id=review.id,
                    review_revision_id=revision.id,
                    revision_number=number,
                    response_text="Thank you.",
                    content_hash=str(number) * 64,
                    status=status,
                    generated_by_type="user",
                    approved_fact_revision_ids=[],
                )
                for number, status in ((1, "awaiting_approval"), (2, "approved"))
            ]
            session.add_all(responses)
            await session.flush()
            review.status = "removed"
            review_id = review.id
            awaiting_id, approved_id = responses[0].id, responses[1].id
        calls: dict[str, Callable[[AsyncSession], Awaitable[object]]] = {
            "approve": lambda s: service.approve(
                s,
                organization_id,
                location_id,
                review_id,
                awaiting_id,
                uuid4(),
                correlation_id="removed",
            ),
            "publish": lambda s: service.reserve_publication(
                s,
                organization_id,
                location_id,
                review_id,
                approved_id,
                "removed-key",
                actor_id=None,
                correlation_id="removed",
            ),
        }
        for call in calls.values():
            try:
                async with factory.begin() as session:
                    await call(session)
            except ReviewNoLongerOnProviderError as exc:
                codes.append(exc.code)
        return codes

    # Both stay on file as history; neither can proceed.
    assert asyncio.run(scenario()) == ["REVIEW_NO_LONGER_ON_PROVIDER"] * 2


def test_the_publish_handler_refuses_a_removed_review_without_calling_google(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response, review, mapping, location, account = _objects(response_status="publishing")
    review.status = "removed"
    adapter = FakeAdapter({"reviewReply": {}})
    _install_provider(monkeypatch, adapter)
    fake = FakeSession([response, review, mapping, location], account=account, review=review)

    outcome = asyncio.run(
        handle_reviews_publish_response(
            cast(AsyncSession, fake),
            organization_id=uuid4(),
            location_id=review.location_id,
            input_document={"response_id": str(response.id)},
            correlation_id="removed-review",
            workflow_run_id=uuid4(),
        )
    )

    assert (outcome.result, outcome.safe_error) == (
        "permanent_failure",
        "REVIEW_NO_LONGER_ON_PROVIDER",
    )
    assert (adapter.update_calls, adapter.get_calls) == (0, 0)
    assert (response.status, response.safe_error_code) == (
        "failed",
        "REVIEW_NO_LONGER_ON_PROVIDER",
    )
