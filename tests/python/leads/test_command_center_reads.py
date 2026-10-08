"""Set-based Command Center reads agree with the canonical per-organization services."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from authorization.fixtures import add_effective_product_entitlement
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.insights.models import InsightSource, MetricObservation
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.leads.models import LeadSource
from apps.api.app.products.seo.models import SEOSearchObservation, SEOSearchProperty, SEOWebsite
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from apps.api.app.reporting_periods import comparison_window
from leads import test_leads_api as canonical

HEADERS = canonical.HEADERS
run_db = canonical.run_db
canonical_leads_client = canonical.leads_client
PORTFOLIO = "/api/v1/command-center/portfolio"
OVERVIEW = "/api/v1/command-center/clients/{}/overview"
KEYS = ("seo.read", "insights.read", "leads.read", "reviews.read", "workflows.read")


def portfolio_row(client: TestClient, org: UUID) -> dict[str, object]:
    body = client.get(PORTFOLIO + "?days=28", headers=HEADERS).json()
    return next(row for row in body["clients"] if row["organization_id"] == str(org))


def test_search_console_and_ga4_match_the_canonical_reports(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    org = ids["organization"]
    expected: dict[str, object] = {}

    async def seed(session: AsyncSession) -> None:
        await add_effective_product_entitlement(session, org, "seo", correlation_id="reads-seo")
        await add_effective_product_entitlement(
            session, org, "insights", correlation_id="reads-insights"
        )
        await ProviderCatalogSeeder().run(session)
        provider = await session.scalar(
            select(Provider).where(Provider.key == "google_business_profile")
        )
        assert provider is not None
        connection = IntegrationConnection(
            organization_id=org,
            location_id=None,
            provider_id=provider.id,
            external_account_reference="google-reads",
            status="connected",
            granted_capabilities=[],
            version=1,
        )
        session.add(connection)
        await session.flush()
        website = SEOWebsite(
            organization_id=org,
            location_id=None,
            key="primary",
            name="Primary",
            canonical_origin="https://example.invalid/",
            status="active",
            ownership_status="verified",
            version=1,
        )
        session.add(website)
        await session.flush()
        now = datetime.now(UTC)
        end = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=28)
        comp_start, comp_end = comparison_window(start, 28)
        prop = SEOSearchProperty(
            organization_id=org,
            website_id=website.id,
            connection_id=connection.id,
            provider="google_search_console",
            external_property_id="sc-domain:reads.example",
            property_type="domain",
            mapping_status="mapped",
            freshness_status="fresh",
            last_synced_at=now,
        )
        ga4 = AnalyticsProperty(
            organization_id=org,
            connection_id=connection.id,
            website_id=website.id,
            provider="google_analytics",
            external_property_id="properties/777",
            property_number="777",
            display_name="GA4",
            mapping_status="mapped",
            freshness_status="fresh",
            last_synced_at=now,
        )
        source = InsightSource(
            organization_id=org,
            key="properties/777",
            source_type="analytics_property",
            product_key="insights",
            provider="google_analytics",
            status="active",
            authority_scope="organization",
        )
        session.add_all([prop, ga4, source])
        await session.flush()
        for window_start, window_end, clicks, position in (
            (start, end, 321, Decimal("7.5")),
            (comp_start, comp_end, 300, Decimal("8.25")),
        ):
            session.add(
                SEOSearchObservation(
                    organization_id=org,
                    search_property_id=prop.id,
                    website_id=website.id,
                    page_id=None,
                    query=None,
                    date_start=window_start,
                    date_end=window_end,
                    dimensions={"observation_type": "site_summary"},
                    dimension_hash=uuid4().hex,
                    clicks=clicks,
                    impressions=9000,
                    ctr=Decimal("0.03"),
                    position=position,
                    quality_status="valid",
                    partial=False,
                )
            )
        definitions = await AnalyticsService()._ensure_metric_definitions(session)
        for window_start, window_end, value in ((start, end, 640), (comp_start, comp_end, 500)):
            dims: dict[str, object] = {"observation_type": "aggregate"}
            session.add(
                MetricObservation(
                    organization_id=org,
                    website_id=website.id,
                    location_id=None,
                    page_id=None,
                    source_id=source.id,
                    metric_definition_id=definitions["ga4.sessions"].id,
                    period_start=window_start,
                    period_end=window_end,
                    dimensions=dims,
                    dimension_hash=uuid4().hex,
                    value=Decimal(value),
                    quality_state="valid",
                    completeness=Decimal("1.0"),
                    provenance={},
                )
            )
        await session.flush()
        gsc = await SearchConsoleService().performance_report(session, org, website.id, days=28)
        analytics = await AnalyticsService().performance_report(session, org, days=28)
        expected["gsc"] = gsc["metrics"]
        expected["ga4"] = analytics["metrics"]
        await session.commit()

    run_db(postgresql_test_url, seed)
    row = portfolio_row(client, org)
    gsc = expected["gsc"]
    ga4 = expected["ga4"]
    assert isinstance(gsc, dict) and isinstance(ga4, dict)
    for field, key in (("search_clicks", "clicks"), ("average_position", "position")):
        value = row[field]
        assert isinstance(value, dict)
        assert value["availability"] == "available"
        assert value["current"] == gsc[key]["current"]
        assert value["previous"] == gsc[key]["previous"]
    sessions = row["organic_sessions"]
    assert isinstance(sessions, dict)
    assert sessions["current"] == ga4["ga4.sessions"]["current"] == 640
    assert sessions["previous"] == ga4["ga4.sessions"]["previous"] == 500
    assert sessions["freshness_at"] is not None


def test_leads_are_not_connected_without_an_active_source_and_never_zero(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    org = ids["organization"]
    row = portfolio_row(client, org)
    assert row["leads"] == {
        **row["leads"],  # type: ignore[dict-item]
        "availability": "available",
        "current": 0,
    }

    async def pause(session: AsyncSession) -> None:
        await session.execute(
            update(LeadSource).where(LeadSource.organization_id == org).values(status="paused")
        )
        await session.commit()

    run_db(postgresql_test_url, pause)
    row = portfolio_row(client, org)
    leads = row["leads"]
    assert isinstance(leads, dict)
    assert leads["availability"] == "not_connected"
    assert leads["current"] is None and leads["previous"] is None
    body = client.get(PORTFOLIO + "?days=28", headers=HEADERS).json()
    assert body["totals"]["website_leads"]["availability"] == "not_connected"
    assert body["totals"]["website_leads"]["current"] is None
    overview = client.get(OVERVIEW.format(org), headers=HEADERS).json()
    assert overview["client"]["leads"]["availability"] == "not_connected"


def test_only_unresolved_failures_count_as_attention(
    canonical_leads_client: tuple[TestClient, dict[str, UUID]],
    postgresql_test_url: str,
) -> None:
    client, ids = canonical_leads_client
    org = ids["organization"]
    location = ids["location"]
    base = datetime.now(UTC) - timedelta(days=2)

    async def seed(session: AsyncSession) -> None:
        run = await session.get(WorkflowRun, ids["workflow_run"])
        assert run is not None
        version_id = run.workflow_version_id
        other_definition = WorkflowDefinition(key="reviews.ingest", name="Reviews", owner="t")
        session.add(other_definition)
        await session.flush()
        other_version = WorkflowVersion(
            definition_id=other_definition.id,
            version=1,
            status="approved",
            input_schema={},
            output_schema={},
            step_specification=[],
            retry_policy={},
            timeout_seconds=60,
        )
        session.add(other_version)
        await session.flush()

        def make(
            version: UUID,
            status: str,
            at: datetime,
            code: str | None = None,
            place: UUID | None = location,
        ) -> WorkflowRun:
            return WorkflowRun(
                organization_id=org,
                location_id=place,
                workflow_version_id=version,
                product_key="leads",
                trigger_type="manual",
                idempotency_key=f"unresolved-{uuid4().hex}",
                request_hash="h",
                input_document={},
                correlation_id="unresolved",
                status=status,
                failure_code=code,
                completed_at=at if status == "completed" else None,
                updated_at=at,
            )

        # Resolved: failed, then the same definition and scope completed later.
        session.add(make(version_id, "failed", base, "RESOLVED_LATER"))
        session.add(make(version_id, "completed", base + timedelta(hours=1)))
        # Unresolved: another definition failed and never completed afterwards.
        session.add(make(other_version.id, "failed", base, "PROVIDER_REJECTED"))
        # A completed run in a different scope (no location) does not resolve a located failure.
        session.add(make(other_version.id, "completed", base + timedelta(hours=1), place=None))
        # A later failure does not resolve an earlier one either.
        session.add(make(other_version.id, "escalated", base + timedelta(hours=2), "ESCALATED"))
        run.status = "completed"
        run.completed_at = base - timedelta(days=1)
        await session.commit()

    run_db(postgresql_test_url, seed)
    body = client.get(PORTFOLIO + "?days=28", headers=HEADERS).json()
    items = [item for item in body["attention"] if item["code"].startswith("WORKFLOW_")]
    typed = sorted((item["code"], item["workflow_key"], item["failure_code"]) for item in items)
    assert typed == [
        ("WORKFLOW_ESCALATED", "reviews.ingest", "ESCALATED"),
        ("WORKFLOW_FAILED", "reviews.ingest", "PROVIDER_REJECTED"),
    ]
    assert all("RESOLVED_LATER" not in str(item) for item in items)
    row = next(c for c in body["clients"] if c["organization_id"] == str(org))
    assert "WORKFLOW_ATTENTION" in row["health_reasons"]
    overview = client.get(OVERVIEW.format(org), headers=HEADERS).json()
    assert len(overview["attention"]) == len(items) == 2
    automations = next(s for s in overview["systems"] if s["key"] == "automations")
    # Automations health counts scheduled automations only (the Automations screen's rule);
    # these on-demand failures stay in the attention list above but have no schedule.
    assert automations["status"] == "healthy"

    async def resolve(session: AsyncSession) -> None:
        version = await session.scalar(
            select(WorkflowVersion.id)
            .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
            .where(WorkflowDefinition.key == "reviews.ingest")
        )
        assert version is not None
        session.add(
            WorkflowRun(
                organization_id=org,
                location_id=location,
                workflow_version_id=version,
                product_key="leads",
                trigger_type="manual",
                idempotency_key=f"resolver-{uuid4().hex}",
                request_hash="h",
                input_document={},
                correlation_id="resolver",
                status="completed",
                completed_at=datetime.now(UTC),
            )
        )
        await session.commit()

    run_db(postgresql_test_url, resolve)
    body = client.get(PORTFOLIO + "?days=28", headers=HEADERS).json()
    assert [i for i in body["attention"] if i["code"].startswith("WORKFLOW_")] == []
    row = next(c for c in body["clients"] if c["organization_id"] == str(org))
    assert "WORKFLOW_ATTENTION" not in row["health_reasons"]
    assert body["totals"]["reporting_attention"] == 1  # Google is still not connected
