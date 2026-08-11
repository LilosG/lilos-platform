"""PostgreSQL integration coverage for complete GBP review ingestion."""

import asyncio
from collections.abc import Iterator
from typing import Any, cast
from uuid import UUID

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
from apps.api.app.products.reviews.models import Review, ReviewRevision
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
