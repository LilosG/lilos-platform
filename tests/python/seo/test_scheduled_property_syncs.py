"""A scheduled Search Console / GA4 sync covers every mapped property in the schedule's scope."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.execution import provider_sync_handlers
from apps.api.app.execution.contracts import JobOutcome, ScheduleCreate
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.seo.models import SEOSearchProperty, SEOWebsite


async def _seed(
    session: AsyncSession,
) -> tuple[UUID, UUID, UUID, dict[str, UUID], dict[str, UUID]]:
    org = Organization(
        name="Scheduled sync",
        slug=f"scheduled-sync-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()
    locations = []
    for slug in ("north", "south"):
        location = Location(
            organization_id=org.id,
            name=slug,
            slug=slug,
            location_type=LocationType.VIRTUAL,
            status=LocationStatus.ACTIVE,
            timezone="UTC",
            country_code="US",
            website_url=f"https://{slug}.example.invalid",
            is_primary=slug == "north",
            version=1,
        )
        session.add(location)
        locations.append(location)
    provider = Provider(
        key=f"google-{uuid4().hex[:6]}",
        name="Google",
        status="active",
        capabilities=[],
        manifest_version=1,
    )
    session.add(provider)
    await session.flush()
    connection = IntegrationConnection(
        organization_id=org.id,
        provider_id=provider.id,
        external_account_reference="google",
        status="connected",
        version=1,
    )
    session.add(connection)
    await session.flush()
    websites: dict[str, SEOWebsite] = {}
    for key, location_id in (
        ("north", locations[0].id),
        ("south", locations[1].id),
        ("shared", None),
    ):
        website = SEOWebsite(
            organization_id=org.id,
            location_id=location_id,
            key=key,
            name=key,
            canonical_origin=f"https://{key}.example.invalid",
            status="active",
            ownership_status="verified",
            version=1,
        )
        session.add(website)
        websites[key] = website
    await session.flush()
    search: dict[str, UUID] = {}
    analytics: dict[str, UUID] = {}
    for key, website in websites.items():
        gsc = SEOSearchProperty(
            organization_id=org.id,
            website_id=website.id,
            connection_id=connection.id,
            provider="google_search_console",
            external_property_id=f"sc-domain:{key}.example.invalid",
            property_type="domain",
            mapping_status="mapped",
            freshness_status="fresh",
        )
        ga4 = AnalyticsProperty(
            organization_id=org.id,
            connection_id=connection.id,
            website_id=website.id,
            provider="google_analytics",
            external_property_id=f"properties/{key}",
            property_number=str(abs(hash(key)) % 10**6),
            display_name=key,
            mapping_status="mapped",
            freshness_status="never_synced",
        )
        session.add_all([gsc, ga4])
        await session.flush()
        search[key] = gsc.id
        analytics[key] = ga4.id
    # A stale mapping is never synced.
    session.add(
        SEOSearchProperty(
            organization_id=org.id,
            website_id=websites["shared"].id,
            connection_id=connection.id,
            provider="google_search_console",
            external_property_id="sc-domain:old.example.invalid",
            property_type="domain",
            mapping_status="stale",
            freshness_status="stale",
        )
    )
    await session.flush()
    return org.id, locations[0].id, locations[1].id, search, analytics


async def _schedule(
    session: AsyncSession, org_id: UUID, workflow_key: str, location_id: UUID | None
) -> UUID:
    schedule = await ExecutionService().create_schedule(
        session,
        org_id,
        ScheduleCreate(
            workflow_key=workflow_key,
            key=f"{workflow_key}:{uuid4().hex[:6]}",
            cron_expression="0 6 * * *",
            timezone="UTC",
            next_run_at=datetime.now(UTC),
            location_id=location_id,
        ),
        correlation_id="scheduled-sync",
    )
    return schedule.id


@pytest.mark.integration
@pytest.mark.anyio
async def test_scheduled_search_console_sync_covers_each_mapped_property_in_scope(
    seo_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    synced: list[UUID] = []

    async def fake_sync(
        session: AsyncSession, organization_id: UUID, property_id: UUID, **kwargs: Any
    ) -> JobOutcome:
        synced.append(property_id)
        return JobOutcome(result="succeeded", result_reference=f"seo-search-property:{property_id}")

    monkeypatch.setattr(provider_sync_handlers, "_sync_search_property", fake_sync)
    async with seo_session_factory.begin() as session:
        org_id, north, _south, search, _analytics = await _seed(session)
        org_wide = await _schedule(session, org_id, "seo.sync_search_console", None)
        scoped = await _schedule(session, org_id, "seo.sync_search_console", north)

    async def run(schedule_id: UUID) -> JobOutcome:
        async with seo_session_factory() as session:
            return await provider_sync_handlers.handle_search_console_sync(
                session,
                organization_id=org_id,
                location_id=None,
                input_document={"schedule_id": str(schedule_id)},
                correlation_id="scheduled",
                workflow_run_id=uuid4(),
            )

    outcome = await run(org_wide)
    assert outcome.result == "succeeded"
    assert sorted(synced) == sorted(search.values())

    synced.clear()
    assert (await run(scoped)).result == "succeeded"
    # The north location's schedule covers its own website and the shared one, not south's.
    assert sorted(synced) == sorted([search["north"], search["shared"]])


@pytest.mark.integration
@pytest.mark.anyio
async def test_scheduled_analytics_sync_covers_each_mapped_property_and_isolates_failures(
    seo_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    attempted: list[UUID] = []
    failing: list[UUID] = []

    async def fake_sync(
        session: AsyncSession, organization_id: UUID, property_id: UUID, **kwargs: Any
    ) -> JobOutcome:
        attempted.append(property_id)
        if property_id in failing:
            return JobOutcome(result="retryable_failure", safe_error="ANALYTICS_SYNC_FAILED")
        return JobOutcome(result="succeeded", result_reference=f"analytics-property:{property_id}")

    monkeypatch.setattr(provider_sync_handlers, "_sync_analytics_property", fake_sync)
    async with seo_session_factory.begin() as session:
        org_id, _north, _south, _search, analytics = await _seed(session)
        schedule_id = await _schedule(session, org_id, "insights.sync_analytics", None)
        failing.append(analytics["north"])

    async with seo_session_factory() as session:
        outcome = await provider_sync_handlers.handle_analytics_sync(
            session,
            organization_id=org_id,
            location_id=None,
            input_document={"schedule_id": str(schedule_id)},
            correlation_id="scheduled",
            workflow_run_id=uuid4(),
        )

    # One property failing does not stop the others, and the run reports the failure.
    assert sorted(attempted) == sorted(analytics.values())
    assert (outcome.result, outcome.safe_error) == ("retryable_failure", "ANALYTICS_SYNC_FAILED")


@pytest.mark.integration
@pytest.mark.anyio
async def test_scheduled_sync_without_a_mapped_property_fails_with_a_typed_code(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org = Organization(
            name="No mapping",
            slug=f"no-mapping-{uuid4().hex[:8]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()
        gsc = await _schedule(session, org.id, "seo.sync_search_console", None)
        ga4 = await _schedule(session, org.id, "insights.sync_analytics", None)

    async with seo_session_factory() as session:
        search = await provider_sync_handlers.handle_search_console_sync(
            session,
            organization_id=org.id,
            location_id=None,
            input_document={"schedule_id": str(gsc)},
            correlation_id="scheduled",
            workflow_run_id=uuid4(),
        )
        analytics = await provider_sync_handlers.handle_analytics_sync(
            session,
            organization_id=org.id,
            location_id=None,
            input_document={"schedule_id": str(ga4)},
            correlation_id="scheduled",
            workflow_run_id=uuid4(),
        )
    assert (search.result, search.safe_error) == (
        "permanent_failure",
        "SEARCH_PROPERTY_NOT_FOUND",
    )
    assert (analytics.result, analytics.safe_error) == (
        "permanent_failure",
        "ANALYTICS_PROPERTY_NOT_FOUND",
    )
