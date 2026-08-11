"""PostgreSQL integration coverage for complete GBP review ingestion."""

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.integrations.connection_service import GBPConnectionService
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.adapter import GBPAdapter
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.reviews.ingestion_service import ReviewIngestionService
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision, ReviewRevision
from apps.api.app.products.reviews.service import ReviewService


class FakeConnectionService(GBPConnectionService):
    async def ensure_fresh_token(
        self, session: AsyncSession, settings: Settings, connection: IntegrationConnection
    ) -> str:
        del session, settings, connection
        return "fake-access-token"


class FakeReviewsAdapter:
    def __init__(self, reviews: list[dict[str, Any]]) -> None:
        self.reviews = reviews

    async def list_reviews(self, access_token: str, location_name: str) -> list[dict[str, Any]]:
        del access_token, location_name
        return list(self.reviews)


def _raw_reviews(count: int) -> list[dict[str, Any]]:
    return [
        {
            "reviewId": f"review-{index}",
            "starRating": "FIVE",
            "comment": f"Review {index}",
            "createTime": "2026-01-01T00:00:00Z",
            "updateTime": "2026-01-01T00:00:00Z",
        }
        for index in range(count)
    ]


def _raw_review(
    *,
    reply: dict[str, Any] | None = None,
    review_id: str = "review-provider-reply",
    comment: str = "Great service",
) -> dict[str, Any]:
    review: dict[str, Any] = {
        "name": f"accounts/123/locations/456/reviews/{review_id}",
        "reviewId": review_id,
        "starRating": "FIVE",
        "comment": comment,
        "createTime": "2026-01-01T00:00:00Z",
        "updateTime": "2026-01-01T00:00:00Z",
    }
    if reply is not None:
        review["reviewReply"] = reply
    return review


def _reply(
    comment: str = "Thank you for choosing us!",
    *,
    state: str | None = "APPROVED",
    update_time: str = "2026-01-02T00:00:00Z",
    policy_violation: str | None = None,
) -> dict[str, Any]:
    reply: dict[str, Any] = {"comment": comment, "updateTime": update_time}
    if state is not None:
        reply["reviewReplyState"] = state
    if policy_violation is not None:
        reply["policyViolation"] = policy_violation
    return reply


def _settings(postgresql_test_url: str) -> Settings:
    return Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )


def _ingestion_service(raw_reviews: list[dict[str, Any]]) -> ReviewIngestionService:
    return ReviewIngestionService(
        adapter=cast(GBPAdapter, FakeReviewsAdapter(raw_reviews)),
        connection=FakeConnectionService(),
        reviews=ReviewService(),
    )


async def _sync(
    factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    organization_id: UUID,
    location_id: UUID,
    raw_reviews: list[dict[str, Any]],
    correlation_id: str,
) -> dict[str, object]:
    async with factory() as session, session.begin():
        return await _ingestion_service(raw_reviews).ingest_for_location(
            session,
            settings,
            organization_id,
            location_id,
            actor_id=None,
            correlation_id=correlation_id,
        )


async def _seed_lilos_published_response(
    factory: async_sessionmaker[AsyncSession],
    organization_id: UUID,
    location_id: UUID,
    *,
    response_text: str = "LILOs-published response",
    generated_by_type: str = "user",
) -> tuple[UUID, UUID, datetime]:
    approval_reference_id = uuid4()
    approved_at = datetime(2026, 1, 1, 12, tzinfo=UTC)
    published_at = datetime(2026, 1, 2, tzinfo=UTC)
    async with factory() as session, session.begin():
        review = (
            await session.scalars(select(Review).where(Review.organization_id == organization_id))
        ).one()
        revision = (
            await session.scalars(
                select(ReviewRevision).where(ReviewRevision.review_id == review.id)
            )
        ).one()
        review.status = "responded"
        response = ReviewResponseRevision(
            organization_id=organization_id,
            location_id=location_id,
            review_id=review.id,
            review_revision_id=revision.id,
            revision_number=1,
            response_text=response_text,
            content_hash="a" * 64,
            status="published",
            generated_by_type=generated_by_type,
            approved_fact_revision_ids=[str(uuid4())],
            approval_reference_id=approval_reference_id,
            approved_at=approved_at,
            external_response_id="accounts/123/locations/456/reviews/review-provider-reply",
            published_at=published_at,
            idempotency_key="lilos-published-response",
        )
        session.add(response)
        await session.flush()
        return response.id, approval_reference_id, published_at


async def _seed_review_location(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[UUID, UUID]:
    async with factory.begin() as session:
        organization = Organization(
            name="Review Ingestion Org",
            slug="review-ingestion-org",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(organization)
        await session.flush()
        location = Location(
            organization_id=organization.id,
            name="Review Ingestion Location",
            slug="review-ingestion-location",
            location_type=LocationType.VIRTUAL,
            status=LocationStatus.ACTIVE,
            timezone="UTC",
            country_code="US",
            website_url="https://example.invalid",
            is_primary=True,
            version=1,
        )
        provider = Provider(
            key="google_business_profile",
            name="Google Business Profile",
            status="active",
            capabilities=["reviews.read"],
        )
        session.add_all([location, provider])
        await session.flush()
        connection = IntegrationConnection(
            organization_id=organization.id,
            provider_id=provider.id,
            external_account_reference="accounts/123",
            status="connected",
        )
        session.add(connection)
        await session.flush()
        mapping = ProviderResourceMapping(
            organization_id=organization.id,
            connection_id=connection.id,
            resource_type="location",
            external_resource_id="locations/456",
            platform_resource_id=location.id,
            status="active",
        )
        session.add(mapping)
        await session.flush()
        account = GBPAccount(
            organization_id=organization.id,
            connection_id=connection.id,
            external_account_id="123",
            display_name="Review Ingestion Account",
        )
        session.add(account)
        await session.flush()
        session.add(
            GBPLocation(
                organization_id=organization.id,
                location_id=location.id,
                connection_id=connection.id,
                account_id=account.id,
                integration_resource_id=mapping.id,
                external_location_id="locations/456",
                business_name="Review Ingestion Location",
            )
        )
        return organization.id, location.id


@pytest.fixture
def ingestion_setup(
    reviews_session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[tuple[async_sessionmaker[AsyncSession], UUID, UUID]]:
    organization_id, location_id = asyncio.run(_seed_review_location(reviews_session_factory))
    yield reviews_session_factory, organization_id, location_id


@pytest.mark.integration
def test_review_ingestion_imports_90_reviews_and_is_idempotent(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup
    raw_reviews = _raw_reviews(90)
    service = ReviewIngestionService(
        adapter=cast(GBPAdapter, FakeReviewsAdapter(raw_reviews)),
        connection=FakeConnectionService(),
        reviews=ReviewService(),
    )
    settings = Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )

    async def scenario() -> tuple[
        dict[str, object], dict[str, object], int, int, list[dict[str, Any]]
    ]:
        async with factory() as session, session.begin():
            first = await service.ingest_for_location(
                session,
                settings,
                organization_id,
                location_id,
                actor_id=None,
                correlation_id="reviews-ingest-first",
            )
        async with factory() as session, session.begin():
            second = await service.ingest_for_location(
                session,
                settings,
                organization_id,
                location_id,
                actor_id=None,
                correlation_id="reviews-ingest-second",
            )
        async with factory() as session:
            review_count = int(
                await session.scalar(
                    select(func.count(Review.id)).where(Review.organization_id == organization_id)
                )
                or 0
            )
            revision_count = int(
                await session.scalar(
                    select(func.count(ReviewRevision.id)).where(
                        ReviewRevision.organization_id == organization_id
                    )
                )
                or 0
            )
            audit_rows = list(
                await session.scalars(
                    select(AuditEvent)
                    .where(
                        AuditEvent.organization_id == organization_id,
                        AuditEvent.event_type == "reviews.ingest.completed",
                    )
                    .order_by(AuditEvent.occurred_at)
                )
            )
            summaries = [dict(row.event_metadata) for row in audit_rows]
        return first, second, review_count, revision_count, summaries

    first, second, review_count, revision_count, summaries = asyncio.run(scenario())

    assert first == {"total": 90, "ingested": 90, "updated": 0}
    assert second == {"total": 90, "ingested": 0, "updated": 90}
    assert review_count == 90
    assert revision_count == 90
    assert summaries == [
        {"total": 90, "ingested": 90, "updated": 0},
        {"total": 90, "ingested": 0, "updated": 90},
    ]


@pytest.mark.integration
def test_approved_provider_reply_is_imported_without_lilos_publication_history(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup

    async def scenario() -> tuple[Review, ReviewResponseRevision, dict[str, Any]]:
        await _sync(
            factory,
            _settings(postgresql_test_url),
            organization_id,
            location_id,
            [_raw_review(reply=_reply())],
            "approved-provider-reply",
        )
        async with factory() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            response = (
                await session.scalars(
                    select(ReviewResponseRevision).where(
                        ReviewResponseRevision.review_id == review.id
                    )
                )
            ).one()
            event = (
                await session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.resource_id == response.id,
                        AuditEvent.event_type == "reviews.response.provider_observed",
                    )
                )
            ).one()
            return review, response, dict(event.event_metadata)

    review, response, metadata = asyncio.run(scenario())

    assert review.status == "responded"
    assert response.status == "published"
    assert response.generated_by_type == "imported"
    assert response.response_text == "Thank you for choosing us!"
    assert (
        response.external_response_id == "accounts/123/locations/456/reviews/review-provider-reply"
    )
    assert response.published_at == datetime(2026, 1, 2, tzinfo=UTC)
    assert response.approved_by_user_id is None
    assert response.approval_reference_id is None
    assert response.approved_at is None
    assert response.ai_execution_id is None
    assert response.idempotency_key is None
    assert metadata["provider_reply_state"] == "APPROVED"
    assert metadata["policy_violation"] is None


@pytest.mark.integration
def test_reply_appears_with_unchanged_review_and_repeated_sync_is_idempotent_and_fresh(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup
    settings = _settings(postgresql_test_url)

    async def scenario() -> tuple[str, datetime, datetime, int, int, int, dict[str, object]]:
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review()],
            "reply-absent",
        )
        async with factory() as session:
            first_synced = (
                (
                    await session.scalars(
                        select(Review).where(Review.organization_id == organization_id)
                    )
                )
                .one()
                .last_synced_at
            )

        provider_review = _raw_review(reply=_reply())
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [provider_review],
            "reply-appeared",
        )
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [provider_review],
            "reply-identical",
        )
        async with factory() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            response_count = int(
                await session.scalar(
                    select(func.count(ReviewResponseRevision.id)).where(
                        ReviewResponseRevision.review_id == review.id
                    )
                )
                or 0
            )
            revision_count = int(
                await session.scalar(
                    select(func.count(ReviewRevision.id)).where(
                        ReviewRevision.review_id == review.id
                    )
                )
                or 0
            )
            provider_audits = int(
                await session.scalar(
                    select(func.count(AuditEvent.id)).where(
                        AuditEvent.organization_id == organization_id,
                        AuditEvent.event_type == "reviews.response.provider_observed",
                    )
                )
                or 0
            )
            summary = await ReviewService().summary(session, organization_id, location_id)
            return (
                review.status,
                first_synced,
                review.last_synced_at,
                response_count,
                revision_count,
                provider_audits,
                summary,
            )

    (
        status,
        first_synced,
        last_synced,
        response_count,
        revision_count,
        provider_audits,
        summary,
    ) = asyncio.run(scenario())

    assert status == "responded"
    assert last_synced > first_synced
    assert response_count == 1
    assert revision_count == 1
    assert provider_audits == 1
    assert summary["by_status"] == {"responded": 1}


@pytest.mark.integration
def test_changed_reply_text_and_state_preserve_immutable_provider_history(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup
    settings = _settings(postgresql_test_url)

    async def scenario() -> tuple[Review, list[ReviewResponseRevision], int]:
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review(reply=_reply("Original Google response"))],
            "reply-original",
        )
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [
                _raw_review(
                    reply=_reply(
                        "Edited Google response",
                        update_time="2026-01-03T00:00:00Z",
                    )
                )
            ],
            "reply-edited",
        )
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [
                _raw_review(
                    reply=_reply(
                        "Edited Google response",
                        state="PENDING",
                        update_time="2026-01-03T00:00:00Z",
                    )
                )
            ],
            "reply-pending",
        )
        async with factory() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            responses = list(
                await session.scalars(
                    select(ReviewResponseRevision)
                    .where(ReviewResponseRevision.review_id == review.id)
                    .order_by(ReviewResponseRevision.revision_number)
                )
            )
            revision_count = int(
                await session.scalar(
                    select(func.count(ReviewRevision.id)).where(
                        ReviewRevision.review_id == review.id
                    )
                )
                or 0
            )
            return review, responses, revision_count

    review, responses, revision_count = asyncio.run(scenario())

    assert review.status == "publishing"
    assert revision_count == 1
    assert [item.response_text for item in responses] == [
        "Original Google response",
        "Edited Google response",
        "Edited Google response",
    ]
    assert [item.status for item in responses] == ["superseded", "superseded", "publishing"]


@pytest.mark.integration
@pytest.mark.parametrize(
    ("reply", "expected_review_status", "expected_response_status", "expected_error"),
    [
        (_reply(state="PENDING"), "publishing", "publishing", None),
        (
            _reply(state="REJECTED", policy_violation="OFF_TOPIC"),
            "publication_failed",
            "rejected",
            "GOOGLE_REVIEW_REPLY_REJECTED",
        ),
        (_reply(state=None), "responded", "published", None),
        (
            _reply(comment="", state=None),
            "publication_failed",
            "reconciliation_required",
            "GOOGLE_REVIEW_REPLY_STATE_UNRESOLVED",
        ),
    ],
)
def test_provider_moderation_states_map_truthfully(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
    reply: dict[str, Any],
    expected_review_status: str,
    expected_response_status: str,
    expected_error: str | None,
) -> None:
    factory, organization_id, location_id = ingestion_setup

    async def scenario() -> tuple[Review, ReviewResponseRevision, dict[str, Any]]:
        await _sync(
            factory,
            _settings(postgresql_test_url),
            organization_id,
            location_id,
            [_raw_review(reply=reply)],
            f"provider-state-{expected_response_status}",
        )
        async with factory() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            response = (
                await session.scalars(
                    select(ReviewResponseRevision).where(
                        ReviewResponseRevision.review_id == review.id
                    )
                )
            ).one()
            event = (
                await session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.resource_id == response.id,
                        AuditEvent.event_type == "reviews.response.provider_observed",
                    )
                )
            ).one()
            return review, response, dict(event.event_metadata)

    review, response, metadata = asyncio.run(scenario())

    assert review.status == expected_review_status
    assert response.status == expected_response_status
    assert response.safe_error_code == expected_error
    assert metadata["provider_reply_state"] == (
        reply.get("reviewReplyState") or "REVIEW_REPLY_STATE_UNSPECIFIED"
    )
    assert metadata["policy_violation"] == reply.get("policyViolation")


@pytest.mark.integration
def test_identical_google_reply_confirms_lilos_publication_without_import_duplicate(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup
    settings = _settings(postgresql_test_url)

    async def scenario() -> tuple[
        Review,
        ReviewResponseRevision,
        UUID,
        datetime,
        int,
        int,
    ]:
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review()],
            "lilos-publication-review",
        )
        response_id, approval_reference_id, published_at = await _seed_lilos_published_response(
            factory,
            organization_id,
            location_id,
            generated_by_type="template",
        )
        provider_review = _raw_review(reply=_reply("LILOs-published response"))
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [provider_review],
            "lilos-publication-confirmed",
        )
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [provider_review],
            "lilos-publication-confirmed-repeat",
        )
        async with factory() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            responses = list(
                await session.scalars(
                    select(ReviewResponseRevision).where(
                        ReviewResponseRevision.review_id == review.id
                    )
                )
            )
            confirmation_audits = int(
                await session.scalar(
                    select(func.count(AuditEvent.id)).where(
                        AuditEvent.resource_id == response_id,
                        AuditEvent.event_type == "reviews.response.provider_confirmed",
                    )
                )
                or 0
            )
            imported_count = sum(response.generated_by_type == "imported" for response in responses)
            return (
                review,
                responses[0],
                approval_reference_id,
                published_at,
                confirmation_audits,
                imported_count,
            )

    (
        review,
        response,
        approval_reference_id,
        published_at,
        confirmation_audits,
        imported_count,
    ) = asyncio.run(scenario())

    assert review.status == "responded"
    assert response.status == "published"
    assert response.generated_by_type == "template"
    assert response.approval_reference_id == approval_reference_id
    assert response.approved_at == datetime(2026, 1, 1, 12, tzinfo=UTC)
    assert response.approved_fact_revision_ids
    assert response.published_at == published_at
    assert response.idempotency_key == "lilos-published-response"
    assert confirmation_audits == 1
    assert imported_count == 0


@pytest.mark.integration
@pytest.mark.parametrize(
    ("state", "expected_response_status", "expected_review_status", "expected_error"),
    [
        (
            "PENDING",
            "reconciliation_required",
            "publishing",
            "GOOGLE_REVIEW_REPLY_PENDING_MODERATION",
        ),
        (
            "REJECTED",
            "rejected",
            "publication_failed",
            "GOOGLE_REVIEW_REPLY_REJECTED",
        ),
    ],
)
def test_google_moderation_reconciles_onto_lilos_publication_without_import(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
    state: str,
    expected_response_status: str,
    expected_review_status: str,
    expected_error: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup
    settings = _settings(postgresql_test_url)

    async def scenario() -> tuple[Review, ReviewResponseRevision, UUID, datetime, int]:
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review()],
            f"lilos-publication-{state.casefold()}",
        )
        _response_id, approval_reference_id, published_at = await _seed_lilos_published_response(
            factory, organization_id, location_id
        )
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [
                _raw_review(
                    reply=_reply(
                        "LILOs-published response",
                        state=state,
                        policy_violation="OFF_TOPIC" if state == "REJECTED" else None,
                    )
                )
            ],
            f"lilos-publication-{state.casefold()}-observed",
        )
        async with factory() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            responses = list(
                await session.scalars(
                    select(ReviewResponseRevision).where(
                        ReviewResponseRevision.review_id == review.id
                    )
                )
            )
            return review, responses[0], approval_reference_id, published_at, len(responses)

    review, response, approval_reference_id, published_at, response_count = asyncio.run(scenario())

    assert review.status == expected_review_status
    assert response.status == expected_response_status
    assert response.safe_error_code == expected_error
    assert response.generated_by_type == "user"
    assert response.approval_reference_id == approval_reference_id
    assert response.published_at == published_at
    assert response_count == 1


@pytest.mark.integration
def test_external_google_edit_preserves_lilos_history_and_imports_only_current_truth(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup
    settings = _settings(postgresql_test_url)

    async def scenario() -> tuple[Review, list[ReviewResponseRevision], UUID]:
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review()],
            "lilos-publication-before-external-edit",
        )
        _response_id, approval_reference_id, _published_at = await _seed_lilos_published_response(
            factory, organization_id, location_id
        )
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [
                _raw_review(
                    reply=_reply(
                        "Response edited directly in Google",
                        update_time="2026-01-03T00:00:00Z",
                    )
                )
            ],
            "lilos-publication-externally-edited",
        )
        async with factory() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            responses = list(
                await session.scalars(
                    select(ReviewResponseRevision)
                    .where(ReviewResponseRevision.review_id == review.id)
                    .order_by(ReviewResponseRevision.revision_number)
                )
            )
            return review, responses, approval_reference_id

    review, responses, approval_reference_id = asyncio.run(scenario())

    assert review.status == "responded"
    assert len(responses) == 2
    assert responses[0].generated_by_type == "user"
    assert responses[0].status == "superseded"
    assert responses[0].response_text == "LILOs-published response"
    assert responses[0].approval_reference_id == approval_reference_id
    assert responses[0].published_at == datetime(2026, 1, 2, tzinfo=UTC)
    assert responses[1].generated_by_type == "imported"
    assert responses[1].status == "published"
    assert responses[1].response_text == "Response edited directly in Google"
    assert responses[1].approval_reference_id is None
    assert responses[1].approved_at is None
    assert responses[1].idempotency_key is None
    assert sum(response.status != "superseded" for response in responses) == 1


@pytest.mark.integration
def test_removed_provider_reply_restores_actionable_state_and_preserves_history(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup
    settings = _settings(postgresql_test_url)

    async def scenario() -> tuple[Review, ReviewResponseRevision, int]:
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review(reply=_reply())],
            "reply-before-removal",
        )
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review()],
            "reply-removed",
        )
        async with factory() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            response = (
                await session.scalars(
                    select(ReviewResponseRevision).where(
                        ReviewResponseRevision.review_id == review.id
                    )
                )
            ).one()
            removal_audits = int(
                await session.scalar(
                    select(func.count(AuditEvent.id)).where(
                        AuditEvent.resource_id == response.id,
                        AuditEvent.event_type == "reviews.response.provider_removed",
                    )
                )
                or 0
            )
            return review, response, removal_audits

    review, response, removal_audits = asyncio.run(scenario())

    assert review.status == "classified"
    assert response.status == "superseded"
    assert response.response_text == "Thank you for choosing us!"
    assert removal_audits == 1


@pytest.mark.integration
def test_externally_deleted_lilos_publication_requires_reconciliation(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup
    settings = _settings(postgresql_test_url)

    async def scenario() -> tuple[Review, ReviewResponseRevision]:
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review()],
            "published-review",
        )
        async with factory() as session, session.begin():
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
            review.status = "responded"
            session.add(
                ReviewResponseRevision(
                    organization_id=organization_id,
                    location_id=location_id,
                    review_id=review.id,
                    review_revision_id=revision.id,
                    revision_number=1,
                    response_text="LILOs-published response",
                    content_hash="a" * 64,
                    status="published",
                    generated_by_type="user",
                    approved_fact_revision_ids=[],
                    external_response_id=(
                        "accounts/123/locations/456/reviews/review-provider-reply"
                    ),
                    published_at=datetime(2026, 1, 2, tzinfo=UTC),
                    idempotency_key="lilos-published-response",
                )
            )
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review()],
            "published-reply-removed",
        )
        async with factory() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            response = (
                await session.scalars(
                    select(ReviewResponseRevision).where(
                        ReviewResponseRevision.review_id == review.id
                    )
                )
            ).one()
            return review, response

    review, response = asyncio.run(scenario())

    assert review.status == "classified"
    assert response.status == "reconciliation_required"
    assert response.safe_error_code == "GOOGLE_REVIEW_REPLY_MISSING"
    assert response.published_at == datetime(2026, 1, 2, tzinfo=UTC)


@pytest.mark.integration
def test_provider_reply_supersedes_local_draft_without_fabricating_approval(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup
    settings = _settings(postgresql_test_url)

    async def scenario() -> tuple[Review, list[ReviewResponseRevision], int]:
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review()],
            "local-draft-review",
        )
        async with factory() as session, session.begin():
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
            await ReviewService().draft(
                session,
                organization_id=organization_id,
                location_id=location_id,
                review_id=review.id,
                review_revision_id=revision.id,
                text="Unpublished local work",
                generated_by_type="user",
                fact_ids=[uuid4()],
                actor_id=None,
                correlation_id="local-draft",
            )
        await _sync(
            factory,
            settings,
            organization_id,
            location_id,
            [_raw_review(reply=_reply("Response already on Google"))],
            "provider-reply-after-draft",
        )
        async with factory() as session:
            review = (
                await session.scalars(
                    select(Review).where(Review.organization_id == organization_id)
                )
            ).one()
            responses = list(
                await session.scalars(
                    select(ReviewResponseRevision)
                    .where(ReviewResponseRevision.review_id == review.id)
                    .order_by(ReviewResponseRevision.revision_number)
                )
            )
            superseded_audits = int(
                await session.scalar(
                    select(func.count(AuditEvent.id)).where(
                        AuditEvent.resource_id == responses[0].id,
                        AuditEvent.event_type == "reviews.response.superseded_by_provider",
                    )
                )
                or 0
            )
            return review, responses, superseded_audits

    review, responses, superseded_audits = asyncio.run(scenario())

    assert review.status == "responded"
    assert len(responses) == 2
    assert responses[0].generated_by_type == "user"
    assert responses[0].status == "superseded"
    assert responses[0].response_text == "Unpublished local work"
    assert responses[1].generated_by_type == "imported"
    assert responses[1].status == "published"
    assert responses[1].approved_by_user_id is None
    assert responses[1].approval_reference_id is None
    assert responses[1].approved_at is None
    assert responses[1].idempotency_key is None
    assert superseded_audits == 1


@pytest.mark.integration
def test_ingestion_keeps_tenant_and_location_mapping_boundaries(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, _organization_id, location_id = ingestion_setup

    async def scenario() -> int:
        with pytest.raises(LookupError, match="No active GBP location mapping"):
            await _sync(
                factory,
                _settings(postgresql_test_url),
                uuid4(),
                location_id,
                [_raw_review(reply=_reply())],
                "cross-tenant-reply",
            )
        async with factory() as session:
            return int(await session.scalar(select(func.count(Review.id))) or 0)

    assert asyncio.run(scenario()) == 0


@pytest.mark.integration
def test_90_approved_provider_replies_keep_collection_complete_and_fully_responded(
    ingestion_setup: tuple[async_sessionmaker[AsyncSession], UUID, UUID],
    postgresql_test_url: str,
) -> None:
    factory, organization_id, location_id = ingestion_setup
    raw_reviews = [
        {
            **review,
            "name": f"accounts/123/locations/456/reviews/{review['reviewId']}",
            "reviewReply": _reply(f"Google response {index}"),
        }
        for index, review in enumerate(_raw_reviews(90))
    ]

    async def scenario() -> tuple[dict[str, object], dict[str, object], int, dict[str, object]]:
        first = await _sync(
            factory,
            _settings(postgresql_test_url),
            organization_id,
            location_id,
            raw_reviews,
            "ninety-replied-first",
        )
        second = await _sync(
            factory,
            _settings(postgresql_test_url),
            organization_id,
            location_id,
            raw_reviews,
            "ninety-replied-second",
        )
        async with factory() as session:
            summary = await ReviewService().summary(session, organization_id, location_id)
            response_count = int(
                await session.scalar(select(func.count(ReviewResponseRevision.id))) or 0
            )
            return first, second, response_count, summary

    first, second, response_count, summary = asyncio.run(scenario())

    assert first == {"total": 90, "ingested": 90, "updated": 0}
    assert second == {"total": 90, "ingested": 0, "updated": 90}
    assert response_count == 90
    assert summary["by_status"] == {"responded": 90}
