"""Seeding for the monthly report tests: clients, locations and stored Google data."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from gbp.test_performance_sync import seed_client
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.insights.models import InsightSource, MetricDefinition, MetricObservation
from apps.api.app.integrations.models import ProviderResourceMapping
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.gbp.performance_enums import (
    GBPPerformanceMetric,
    GBPPerformanceSyncMode,
    GBPPerformanceSyncStatus,
)
from apps.api.app.products.gbp.performance_models import (
    GBPPerformanceDailyMetric,
    GBPPerformanceKeywordImpression,
    GBPPerformanceSyncRun,
)
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision, ReviewRevision
from apps.api.app.products.seo.models import SEOSearchObservation, SEOSearchProperty, SEOWebsite
from apps.api.app.reporting_periods import calendar_month_window

Factory = async_sessionmaker[AsyncSession]
IMPRESSIONS = (
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_DESKTOP_MAPS,
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_DESKTOP_SEARCH,
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_MAPS,
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_SEARCH,
)
CORE = (
    *IMPRESSIONS,
    GBPPerformanceMetric.CALL_CLICKS,
    GBPPerformanceMetric.WEBSITE_CLICKS,
    GBPPerformanceMetric.BUSINESS_DIRECTION_REQUESTS,
)
# The moment the monthly report job runs: 8:00 AM Pacific on the 1st.
OCTOBER_FIRST = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
SEPTEMBER = date(2026, 9, 1)
AUGUST = date(2026, 8, 1)
SEPTEMBER_LAST_YEAR = date(2025, 9, 1)


def days_of(month: date) -> list[date]:
    start, following = calendar_month_window(month)
    return [start.date() + timedelta(days=i) for i in range((following - start).days)]


async def seed_org(factory: Factory, name: str = "Client") -> tuple[UUID, UUID, UUID]:
    """(organization id, GBP location id, platform location id), one mapped active location."""
    return await seed_client(factory, name)


async def add_location(
    factory: Factory,
    organization_id: UUID,
    name: str,
    *,
    status: LocationStatus = LocationStatus.ACTIVE,
    mapped: bool = True,
) -> tuple[UUID, UUID | None]:
    """Another location of the organization, mapped to its own Business Profile or not."""
    async with factory.begin() as session:
        existing = await session.scalar(
            select(GBPLocation).where(GBPLocation.organization_id == organization_id).limit(1)
        )
        assert existing is not None
        location = Location(
            organization_id=organization_id,
            name=name,
            slug=f"{name.lower().replace(' ', '-')}-{uuid4().hex[:5]}",
            location_type=LocationType.VIRTUAL,
            status=status,
            timezone="UTC",
            country_code="US",
            website_url="https://example.invalid",
            is_primary=False,
            version=1,
            archived_at=datetime.now(UTC) if status is LocationStatus.ARCHIVED else None,
        )
        session.add(location)
        await session.flush()
        if not mapped:
            return location.id, None
        account = await session.get(GBPAccount, existing.account_id)
        assert account is not None
        external = f"locations/{uuid4().int % 10**9}"
        mapping = ProviderResourceMapping(
            organization_id=organization_id,
            connection_id=existing.connection_id,
            resource_type="location",
            external_resource_id=external,
            platform_resource_id=location.id,
            status="active",
        )
        session.add(mapping)
        await session.flush()
        gbp = GBPLocation(
            organization_id=organization_id,
            location_id=location.id,
            connection_id=existing.connection_id,
            account_id=account.id,
            integration_resource_id=mapping.id,
            external_location_id=external,
            business_name=name,
            mapping_status="confirmed",
            write_enabled=False,
        )
        session.add(gbp)
        await session.flush()
        return location.id, gbp.id


async def set_location_status(
    factory: Factory, organization_id: UUID, location_id: UUID, status: LocationStatus
) -> None:
    async with factory.begin() as session:
        location = await session.get(Location, location_id)
        assert location is not None and location.organization_id == organization_id
        location.status = status
        location.archived_at = datetime.now(UTC) if status is LocationStatus.ARCHIVED else None


async def store_metrics(
    factory: Factory,
    organization_id: UUID,
    gbp_location_id: UUID,
    month: date,
    value_for: Callable[[GBPPerformanceMetric, date], int | None] | int = 5,
    *,
    metrics: Iterable[GBPPerformanceMetric] = CORE,
    skip_days: Iterable[date] = (),
) -> None:
    """Daily rows for a month as a sync would have stored them, plus the run that wrote them."""
    skipped = set(skip_days)
    chosen = tuple(metrics)
    async with factory.begin() as session:
        run = GBPPerformanceSyncRun(
            organization_id=organization_id,
            gbp_location_id=gbp_location_id,
            mode=GBPPerformanceSyncMode.RESYNC.value,
            status=GBPPerformanceSyncStatus.SUCCEEDED.value,
            window_start=month,
            window_end=days_of(month)[-1],
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        session.add(run)
        await session.flush()
        for day in days_of(month):
            if day in skipped:
                continue
            for metric in chosen:
                value = value_for(metric, day) if callable(value_for) else value_for
                if value is None:
                    continue
                session.add(
                    GBPPerformanceDailyMetric(
                        organization_id=organization_id,
                        gbp_location_id=gbp_location_id,
                        metric=metric.value,
                        metric_date=day,
                        value=value,
                        sync_run_id=run.id,
                    )
                )


async def store_terms(
    factory: Factory,
    organization_id: UUID,
    gbp_location_id: UUID,
    month: date,
    terms: dict[str, int | tuple[str, int]],
) -> None:
    """Search terms: an int is an exact count, ("below", n) is Google's "fewer than n"."""
    async with factory.begin() as session:
        run = await session.scalar(
            select(GBPPerformanceSyncRun.id).where(
                GBPPerformanceSyncRun.gbp_location_id == gbp_location_id
            )
        )
        assert run is not None
        for keyword, count in terms.items():
            exact = isinstance(count, int)
            session.add(
                GBPPerformanceKeywordImpression(
                    organization_id=organization_id,
                    gbp_location_id=gbp_location_id,
                    month=month,
                    keyword=keyword,
                    value=count if isinstance(count, int) else None,
                    threshold=None if exact else count[1],  # type: ignore[index]
                    sync_run_id=run,
                )
            )


async def add_review(
    factory: Factory,
    organization_id: UUID,
    location_id: UUID,
    *,
    rating: float | None,
    created: datetime,
    status: str = "new",
    responded_at: datetime | None = None,
) -> UUID:
    async with factory.begin() as session:
        mapping_id = await session.scalar(
            select(ProviderResourceMapping.id)
            .where(
                ProviderResourceMapping.organization_id == organization_id,
                ProviderResourceMapping.platform_resource_id == location_id,
            )
            .limit(1)
        )
        assert mapping_id is not None
        review = Review(
            organization_id=organization_id,
            location_id=location_id,
            integration_resource_id=mapping_id,
            external_review_id=f"review-{uuid4().hex}",
            provider="google_business_profile",
            rating=rating,
            status=status,
            review_created_at=created,
            last_synced_at=created,
        )
        session.add(review)
        await session.flush()
        revision = ReviewRevision(
            organization_id=organization_id,
            review_id=review.id,
            revision_number=1,
            rating=rating,
            body="Great.",
            content_hash=uuid4().hex + uuid4().hex,
        )
        session.add(revision)
        await session.flush()
        if responded_at is not None:
            session.add(
                ReviewResponseRevision(
                    organization_id=organization_id,
                    location_id=location_id,
                    review_id=review.id,
                    review_revision_id=revision.id,
                    revision_number=1,
                    response_text="Thank you!",
                    content_hash=uuid4().hex + uuid4().hex,
                    status="published",
                    generated_by_type="user",
                    approved_fact_revision_ids=[],
                    published_at=responded_at,
                )
            )
        return review.id


async def connect_search_console(factory: Factory, organization_id: UUID) -> tuple[UUID, UUID]:
    """A mapped Search Console property on a website. Returns (property id, website id)."""
    async with factory.begin() as session:
        connection_id = await session.scalar(
            select(GBPLocation.connection_id)
            .where(GBPLocation.organization_id == organization_id)
            .limit(1)
        )
        assert connection_id is not None
        website = SEOWebsite(
            organization_id=organization_id,
            key=f"site-{uuid4().hex[:6]}",
            name="Site",
            canonical_origin="https://example.com/",
            status="active",
            ownership_status="verified",
            version=1,
        )
        session.add(website)
        await session.flush()
        prop = SEOSearchProperty(
            organization_id=organization_id,
            website_id=website.id,
            connection_id=connection_id,
            provider="google_search_console",
            external_property_id="sc-domain:example.com",
            property_type="domain",
            mapping_status="mapped",
            freshness_status="fresh",
        )
        session.add(prop)
        await session.flush()
        return prop.id, website.id


async def store_search_month(
    factory: Factory,
    organization_id: UUID,
    property_id: UUID,
    website_id: UUID,
    month: date,
    *,
    clicks: int,
    impressions: int,
    position: float,
    queries: dict[str, tuple[int, int]] | None = None,
    pages: dict[str, tuple[int, int]] | None = None,
    partial: bool = False,
) -> None:
    from apps.api.app.products.seo.month_observations import (
        MONTH_SITE_SUMMARY,
        MONTH_TOP_PAGE,
        MONTH_TOP_QUERY,
        dimension_hash,
    )

    start, following = calendar_month_window(month)

    def observation(kind: str, key: str | None, c: int, i: int) -> SEOSearchObservation:
        dims: dict[str, object] = {"observation_type": kind, "website_id": str(website_id)}
        if key is not None:
            dims["query" if kind == MONTH_TOP_QUERY else "page"] = key
        return SEOSearchObservation(
            organization_id=organization_id,
            search_property_id=property_id,
            website_id=website_id,
            query=key if kind == MONTH_TOP_QUERY else None,
            date_start=start,
            date_end=following,
            dimensions=dims,
            dimension_hash=dimension_hash(dims),
            clicks=c,
            impressions=i,
            ctr=Decimal(c) / Decimal(i) if i else None,
            position=Decimal(str(position)),
            quality_status="valid",
            partial=partial,
        )

    async with factory.begin() as session:
        session.add(observation(MONTH_SITE_SUMMARY, None, clicks, impressions))
        for key, (c, i) in (queries or {}).items():
            session.add(observation(MONTH_TOP_QUERY, key, c, i))
        for key, (c, i) in (pages or {}).items():
            session.add(observation(MONTH_TOP_PAGE, key, c, i))


async def connect_analytics(factory: Factory, organization_id: UUID, website_id: UUID) -> UUID:
    async with factory.begin() as session:
        connection_id = await session.scalar(
            select(GBPLocation.connection_id)
            .where(GBPLocation.organization_id == organization_id)
            .limit(1)
        )
        assert connection_id is not None
        prop = AnalyticsProperty(
            organization_id=organization_id,
            connection_id=connection_id,
            website_id=website_id,
            provider="google_analytics",
            external_property_id="properties/123",
            property_number="123",
            display_name="Site",
            mapping_status="mapped",
            freshness_status="fresh",
        )
        session.add(prop)
        await session.flush()
        return prop.id


async def store_organic_month(
    factory: Factory,
    organization_id: UUID,
    website_id: UUID,
    month: date,
    sessions: int,
    *,
    partial: bool = False,
) -> None:
    from apps.api.app.products.analytics.month_observations import (
        ORGANIC_SESSIONS_KEY,
        month_dimensions,
    )
    from apps.api.app.products.analytics.month_observations import dimension_hash as ga_hash

    start, following = calendar_month_window(month)
    async with factory.begin() as session:
        source = await session.scalar(
            select(InsightSource).where(
                InsightSource.organization_id == organization_id,
                InsightSource.key == "properties/123",
            )
        )
        if source is None:
            source = InsightSource(
                organization_id=organization_id,
                key="properties/123",
                source_type="analytics_property",
                product_key="insights",
                provider="google_analytics",
                status="active",
                authority_scope="organization",
            )
            session.add(source)
        definition = await session.scalar(
            select(MetricDefinition).where(
                MetricDefinition.key == ORGANIC_SESSIONS_KEY, MetricDefinition.version == 1
            )
        )
        if definition is None:
            definition = MetricDefinition(
                key=ORGANIC_SESSIONS_KEY,
                version=1,
                name="GA4 Organic Landing sessions",
                description="Organic Search sessions.",
                source_product="insights",
                unit="count",
                data_type="integer",
                aggregation_behavior="sum",
                supported_dimensions=[],
                required_filters=[],
                freshness_seconds=86_400,
                partial_period_behavior="mark_partial",
                missing_data_behavior="mark_missing",
                status="active",
            )
            session.add(definition)
        await session.flush()
        dims = month_dimensions(website_id)
        session.add(
            MetricObservation(
                organization_id=organization_id,
                source_id=source.id,
                metric_definition_id=definition.id,
                website_id=website_id,
                period_start=start,
                period_end=following,
                dimensions=dims,
                dimension_hash=ga_hash(dims),
                value=Decimal(sessions),
                quality_state="partial" if partial else "valid",
                completeness=Decimal("1.0"),
                provenance={},
            )
        )


async def seed_complete_month(
    factory: Factory,
    organization_id: UUID,
    gbp_location_id: UUID,
    location_id: UUID,
    *,
    month: date = SEPTEMBER,
) -> None:
    """Every source fully stored for the month, its predecessor and the year before."""
    previous = date(month.year - (month.month == 1), (month.month - 2) % 12 + 1, 1)
    last_year = date(month.year - 1, month.month, 1)
    for stored, per_day in ((month, 6), (previous, 5), (last_year, 4)):
        await store_metrics(factory, organization_id, gbp_location_id, stored, per_day)
    await store_terms(
        factory,
        organization_id,
        gbp_location_id,
        month,
        {"pizza near me": 40, "best pizza": 22, "rare term": ("below", 15)},
    )
    created = datetime(month.year, month.month, 10, 12, tzinfo=UTC)
    await add_review(
        factory,
        organization_id,
        location_id,
        rating=5,
        created=created,
        status="responded",
        responded_at=created + timedelta(days=1),
    )
    await add_review(factory, organization_id, location_id, rating=4, created=created)
    prop, website = await connect_search_console(factory, organization_id)
    await store_search_month(
        factory,
        organization_id,
        prop,
        website,
        month,
        clicks=120,
        impressions=3000,
        position=8.4,
        queries={"pizza": (60, 1000), "menu": (30, 800)},
        pages={"https://example.com/": (70, 1500)},
    )
    await store_search_month(
        factory,
        organization_id,
        prop,
        website,
        previous,
        clicks=100,
        impressions=2800,
        position=9.1,
        queries={"pizza": (50, 900)},
        pages={"https://example.com/": (60, 1400)},
    )
    await connect_analytics(factory, organization_id, website)
    await store_organic_month(factory, organization_id, website, month, 900)
    await store_organic_month(factory, organization_id, website, previous, 800)
