"""scripts.ensure_client_schedules: idempotent, dry-run-first, tenant-safe schedule creation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.contracts import ScheduleCreate
from apps.api.app.execution.models import Schedule
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.seo.models import SEOSearchProperty, SEOWebsite
from scripts.ensure_client_schedules import (
    Action,
    SkipReason,
    ensure_client_schedules,
    format_report,
)

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)  # a Friday


async def _organization(
    session: AsyncSession,
    name: str,
    *,
    status: OrganizationStatus = OrganizationStatus.ACTIVE,
    timezone: str = "America/Los_Angeles",
) -> Organization:
    organization = Organization(
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{uuid4().hex[:6]}",
        organization_type=OrganizationType.TEST,
        status=status,
        timezone=timezone,
        default_currency="USD",
        version=1,
    )
    if status is OrganizationStatus.ARCHIVED:
        organization.archived_at = NOW
    session.add(organization)
    await session.flush()
    return organization


async def _fully_mapped(
    session: AsyncSession, organization: Organization, locations: int
) -> list[UUID]:
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
        organization_id=organization.id,
        provider_id=provider.id,
        external_account_reference="google",
        status="connected",
        version=1,
    )
    session.add(connection)
    await session.flush()
    account = GBPAccount(
        organization_id=organization.id,
        connection_id=connection.id,
        external_account_id="accounts/1",
        display_name="Account",
        status="selected",
    )
    website = SEOWebsite(
        organization_id=organization.id,
        location_id=None,
        key="primary",
        name="Primary",
        canonical_origin=f"https://{uuid4().hex[:8]}.example.invalid",
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add_all([account, website])
    await session.flush()
    session.add_all(
        [
            SEOSearchProperty(
                organization_id=organization.id,
                website_id=website.id,
                connection_id=connection.id,
                provider="google_search_console",
                external_property_id=f"sc-domain:{uuid4().hex[:6]}",
                property_type="domain",
                mapping_status="mapped",
                freshness_status="fresh",
            ),
            AnalyticsProperty(
                organization_id=organization.id,
                connection_id=connection.id,
                website_id=website.id,
                provider="google_analytics",
                external_property_id=f"properties/{uuid4().hex[:6]}",
                property_number="123",
                display_name="GA4",
                mapping_status="mapped",
                freshness_status="never_synced",
            ),
        ]
    )
    location_ids: list[UUID] = []
    for index in range(locations):
        location = Location(
            organization_id=organization.id,
            name=f"Location {index}",
            slug=f"location-{index}",
            location_type=LocationType.VIRTUAL,
            status=LocationStatus.ACTIVE,
            timezone="UTC",
            country_code="US",
            website_url="https://example.invalid",
            is_primary=index == 0,
            version=1,
        )
        session.add(location)
        await session.flush()
        mapping = ProviderResourceMapping(
            organization_id=organization.id,
            connection_id=connection.id,
            resource_type="location",
            external_resource_id=f"locations/{index}",
            platform_resource_id=location.id,
            status="active",
        )
        session.add(mapping)
        await session.flush()
        session.add(
            GBPLocation(
                organization_id=organization.id,
                location_id=location.id,
                connection_id=connection.id,
                account_id=account.id,
                integration_resource_id=mapping.id,
                external_location_id=f"locations/{index}",
                business_name=f"Business {index}",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        location_ids.append(location.id)
    await session.flush()
    return location_ids


async def _schedules(
    factory: async_sessionmaker[AsyncSession], organization_id: UUID
) -> list[Schedule]:
    async with factory() as session:
        return list(
            await session.scalars(
                select(Schedule)
                .where(Schedule.organization_id == organization_id)
                .order_by(Schedule.key)
            )
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_dry_run_changes_nothing_and_apply_creates_each_schedule_once(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        client = await _organization(session, "Client")
        locations = await _fully_mapped(session, client, 2)
        client_id = client.id

    dry = await ensure_client_schedules(
        workflows_session_factory, apply=False, organization_id=client_id, now=NOW
    )
    assert not dry.applied
    assert [c.action for c in dry.changes] == [Action.CREATE] * 8
    assert await _schedules(workflows_session_factory, client_id) == []

    applied = await ensure_client_schedules(
        workflows_session_factory, apply=True, organization_id=client_id, now=NOW
    )
    assert [c.action for c in applied.changes] == [Action.CREATE] * 8
    schedules = await _schedules(workflows_session_factory, client_id)
    by_key = {schedule.key: schedule for schedule in schedules}
    assert len(by_key) == 8
    assert {schedule.timezone for schedule in schedules} == {"America/Los_Angeles"}
    assert {schedule.status for schedule in schedules} == {"active"}
    assert all(schedule.next_run_at > NOW for schedule in schedules)
    for location_id in locations:
        review = by_key[f"ensure:reviews.ingest:{location_id}"]
        assert (review.cron_expression, review.location_id) == ("0 */6 * * *", location_id)
        performance = by_key[f"ensure:gbp.sync_performance:{location_id}"]
        # Daily, after the 05:00 gbp.sync, one schedule per mapped GBP location.
        assert (performance.cron_expression, performance.location_id) == ("15 5 * * *", location_id)
    assert by_key["ensure:gbp.sync"].cron_expression == "0 5 * * *"
    assert by_key["ensure:gbp.sync"].location_id == locations[0]
    assert by_key["ensure:seo.sync_search_console"].cron_expression == "30 5 * * *"
    assert by_key["ensure:insights.sync_analytics"].cron_expression == "0 6 * * *"
    crawl = by_key["ensure:seo.crawl_or_analysis"]
    assert crawl.cron_expression == "0 7 * * 1"
    # Mondays at 07:00 Pacific, i.e. the Monday after the Friday we ran on.
    assert crawl.next_run_at == datetime(2026, 10, 5, 14, 0, tzinfo=UTC)
    async with workflows_session_factory() as session:
        audited = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.organization_id == client_id,
                AuditEvent.event_type == "workflow.schedule.created",
            )
        )
    assert audited == 8


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_second_apply_is_a_no_op_and_drift_is_corrected(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        client = await _organization(session, "Client")
        await _fully_mapped(session, client, 1)
        client_id = client.id
    await ensure_client_schedules(
        workflows_session_factory, apply=True, organization_id=client_id, now=NOW
    )
    before = {s.key: s.id for s in await _schedules(workflows_session_factory, client_id)}

    again = await ensure_client_schedules(
        workflows_session_factory, apply=True, organization_id=client_id, now=NOW
    )
    assert {c.action for c in again.changes} == {Action.UNCHANGED}
    assert {s.key: s.id for s in await _schedules(workflows_session_factory, client_id)} == before

    # Someone paused one schedule and edited another's cron.
    async with workflows_session_factory.begin() as session:
        schedules = {
            s.key: s
            for s in await session.scalars(
                select(Schedule).where(Schedule.organization_id == client_id)
            )
        }
        schedules["ensure:gbp.sync"].status = "paused"
        schedules["ensure:insights.sync_analytics"].cron_expression = "0 0 1 * *"
    fixed = await ensure_client_schedules(
        workflows_session_factory, apply=True, organization_id=client_id, now=NOW
    )
    updated = {
        c.wanted.workflow_key: c.differences for c in fixed.changes if c.action is Action.UPDATE
    }
    assert updated == {"gbp.sync": ("status",), "insights.sync_analytics": ("cron",)}
    repaired = {s.key: s for s in await _schedules(workflows_session_factory, client_id)}
    assert repaired["ensure:gbp.sync"].status == "active"
    assert repaired["ensure:insights.sync_analytics"].cron_expression == "0 6 * * *"
    assert {key: s.id for key, s in repaired.items()} == before


@pytest.mark.integration
@pytest.mark.anyio
async def test_missing_mappings_are_skipped_and_reported_not_scheduled(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        bare = await _organization(session, "Bare")
        bare_id = bare.id

    report = await ensure_client_schedules(
        workflows_session_factory, apply=True, organization_id=bare_id, now=NOW
    )

    assert report.changes == []
    assert {(s.workflow_key, s.reason) for s in report.skipped} == {
        ("reviews.ingest", SkipReason.NO_MAPPED_GBP_LOCATION),
        ("gbp.sync", SkipReason.NO_MAPPED_GBP_LOCATION),
        ("gbp.sync_performance", SkipReason.NO_MAPPED_GBP_LOCATION),
        ("seo.sync_search_console", SkipReason.NO_MAPPED_SEARCH_PROPERTY),
        ("insights.sync_analytics", SkipReason.NO_MAPPED_ANALYTICS_PROPERTY),
        ("seo.crawl_or_analysis", SkipReason.NO_ACTIVE_WEBSITE),
    }
    assert await _schedules(workflows_session_factory, bare_id) == []
    assert any("NO_MAPPED_GBP_LOCATION" in line for line in format_report(report))


@pytest.mark.integration
@pytest.mark.anyio
async def test_archived_organizations_wheyland_and_foreign_schedules_are_never_touched(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        archived = await _organization(session, "Old Client", status=OrganizationStatus.ARCHIVED)
        await _fully_mapped(session, archived, 1)
        wheyland = await _organization(session, "Wheyland Electric")
        await _fully_mapped(session, wheyland, 1)
        client = await _organization(session, "Client")
        client_locations = await _fully_mapped(session, client, 1)
        # A schedule somebody else owns on the same organization (like gbp.generate_post).
        foreign = await ExecutionService().create_schedule(
            session,
            client.id,
            ScheduleCreate(
                workflow_key="gbp.generate_post",
                key="weekly-gbp-post",
                cron_expression="0 9 * * 2",
                timezone="UTC",
                next_run_at=NOW,
                location_id=client_locations[0],
            ),
            correlation_id="foreign",
        )
        ids = (archived.id, wheyland.id, client.id, foreign.id)
    archived_id, wheyland_id, client_id, foreign_id = ids

    report = await ensure_client_schedules(workflows_session_factory, apply=True, now=NOW)

    assert {c.organization_id for c in report.changes} == {client_id}
    assert await _schedules(workflows_session_factory, archived_id) == []
    assert await _schedules(workflows_session_factory, wheyland_id) == []
    keys = [s.key for s in await _schedules(workflows_session_factory, client_id)]
    assert "weekly-gbp-post" in keys and len(keys) == 7  # six ensure:* plus the foreign one
    async with workflows_session_factory() as session:
        untouched = await session.get(Schedule, foreign_id)
        assert untouched is not None
        assert (untouched.cron_expression, untouched.status) == ("0 9 * * 2", "active")


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_schedule_bound_to_another_workflow_is_reported_not_overwritten(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        client = await _organization(session, "Client")
        await _fully_mapped(session, client, 1)
        await ExecutionService().create_schedule(
            session,
            client.id,
            ScheduleCreate(
                workflow_key="reviews.ingest",
                key="ensure:seo.sync_search_console",
                cron_expression="0 1 * * *",
                timezone="UTC",
                next_run_at=NOW,
            ),
            correlation_id="conflict",
        )
        client_id = client.id

    report = await ensure_client_schedules(
        workflows_session_factory, apply=True, organization_id=client_id, now=NOW
    )

    conflicts = [c for c in report.changes if c.action is Action.CONFLICT]
    assert [c.wanted.workflow_key for c in conflicts] == ["seo.sync_search_console"]
    assert conflicts[0].differences == ("workflow",)
    stored = {s.key: s for s in await _schedules(workflows_session_factory, client_id)}
    assert stored["ensure:seo.sync_search_console"].cron_expression == "0 1 * * *"
