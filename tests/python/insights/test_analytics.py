"""GA4 operator journey: discovery, property mapping, real metric sync, and
Insights consumption. No real Google calls -- the Analytics adapter is a
deterministic fake and the Google connection is created directly with the
Analytics scope granted.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import cast
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.insights.models import (
    InsightSource,
    MetricDefinition,
    MetricObservation,
)
from apps.api.app.integrations.connection_service import (
    GBPConnectionService,
)
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.analytics.adapter import (
    AnalyticsReportRow,
    DiscoveredAnalyticsProperty,
    GoogleAnalyticsAdapter,
    GoogleAnalyticsAdminAdapter,
)
from apps.api.app.products.analytics.service import (
    AnalyticsService,
    recommend_property,
)
from apps.api.app.products.seo.models import SEOWebsite
from apps.api.app.reporting_periods import (
    GA4_SYNC_TAIL_EXCLUSION_DAYS,
    comparison_window,
    provider_start_date,
    reporting_window,
)


def make_settings() -> Settings:
    return Settings.model_validate(
        {
            "environment": EnvironmentName.TEST,
            "google_oauth_client_id": "test-client-id",
            "google_oauth_client_secret": "test-client-secret",
            "google_oauth_redirect_uri": "https://api.example.invalid/api/v1/integrations/google/callback",
            "secret_encryption_key": Fernet.generate_key().decode("utf-8"),
        }
    )


def mock_client_factory(
    handler: Callable[[httpx.Request], httpx.Response],
) -> Callable[[], httpx.AsyncClient]:
    return lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))


def state_from_url(url: str) -> str:
    return parse_qs(urlsplit(url).query)["state"][0]


async def make_organization(session: AsyncSession) -> Organization:
    org = Organization(
        name="Analytics Test Org",
        slug=f"analytics-test-org-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()
    return org


async def make_website(session: AsyncSession, organization_id: UUID, origin: str) -> SEOWebsite:
    website = SEOWebsite(
        organization_id=organization_id,
        location_id=None,
        key="primary",
        name="Primary",
        canonical_origin=origin,
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add(website)
    await session.flush()
    return website


async def make_connected_connection(
    session: AsyncSession,
    settings: Settings,
    organization_id: UUID,
    scope: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/token"
        return httpx.Response(
            200,
            json={
                "access_token": "ga-access",
                "refresh_token": "ga-refresh",
                "expires_in": 3600,
                "scope": scope,
            },
        )

    await ProviderCatalogSeeder().run(session)
    svc = GBPConnectionService(http_client_factory=mock_client_factory(handler))
    url = await svc.begin_connection(
        session, settings, organization_id, actor_id=None, correlation_id="c1"
    )
    await svc.complete_connection(
        session,
        settings,
        organization_id,
        state=state_from_url(url),
        code="code",
        correlation_id="c2",
    )


class FakeAnalyticsAdapter(GoogleAnalyticsAdapter):
    def __init__(
        self,
        properties: list[DiscoveredAnalyticsProperty],
        aggregate_rows: list[AnalyticsReportRow] | None = None,
        daily_rows: list[AnalyticsReportRow] | None = None,
        aggregate_by_start: dict[str, list[AnalyticsReportRow]] | None = None,
    ) -> None:
        self._properties = properties
        self._aggregate_rows = aggregate_rows or []
        self._daily_rows = daily_rows or []
        self._aggregate_by_start = aggregate_by_start or {}
        # (start_date, end_date, dimensions)
        self.report_calls: list[tuple[str, str, tuple[str, ...]]] = []

    async def list_account_summaries(self, access_token: str) -> list[DiscoveredAnalyticsProperty]:
        return self._properties

    async def run_report(
        self,
        access_token: str,
        property_number: str,
        *,
        start_date: str,
        end_date: str,
        metrics: Sequence[str] = (
            "sessions",
            "totalUsers",
            "screenPageViews",
            "conversions",
        ),
        dimensions: Sequence[str] = (),
    ) -> list[AnalyticsReportRow]:
        del access_token, property_number, metrics
        self.report_calls.append((start_date, end_date, tuple(dimensions)))
        if dimensions == ("date",):
            return self._daily_rows
        return self._aggregate_by_start.get(start_date, self._aggregate_rows)


def test_recommend_property_matches_display_name_to_website_domain() -> None:
    properties = [
        DiscoveredAnalyticsProperty("properties/111", "111", "Wheyland Electric", "Wheyland"),
        DiscoveredAnalyticsProperty("properties/222", "222", "Other Site", "Other"),
    ]
    site = SEOWebsite(
        organization_id=uuid4(),
        location_id=None,
        key="primary",
        name="Primary",
        canonical_origin="https://wheylandelectric.com/",
        status="active",
        ownership_status="verified",
        version=1,
    )
    recommended = recommend_property(properties, site)
    assert recommended is not None
    assert recommended.external_property_id == "properties/111"


@pytest.mark.anyio
async def test_adapter_parses_account_summary_resource_name_shape() -> None:
    """The Admin API returns ``account`` as a string, not a nested document."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/accountSummaries"
        return httpx.Response(
            200,
            json={
                "accountSummaries": [
                    {
                        "name": "accountSummaries/123",
                        "account": "accounts/123",
                        "displayName": "Wheyland Group",
                        "propertySummaries": [
                            {
                                "property": "properties/456",
                                "displayName": "Wheyland Electric",
                            }
                        ],
                    }
                ]
            },
        )

    adapter = GoogleAnalyticsAdminAdapter(http_client_factory=mock_client_factory(handler))
    properties = await adapter.list_account_summaries("access-token")

    assert properties == [
        DiscoveredAnalyticsProperty(
            external_property_id="properties/456",
            property_number="456",
            display_name="Wheyland Electric",
            account_display_name="Wheyland Group",
        )
    ]


@pytest.mark.anyio
async def test_adapter_paginates_all_account_summaries() -> None:
    requests: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/accountSummaries"
        assert request.url.params["pageSize"] == "200"
        page_token = request.url.params.get("pageToken")
        requests.append(page_token)
        account_id = "123" if page_token is None else "456"
        payload: dict[str, object] = {
            "accountSummaries": [
                {
                    "displayName": f"Account {account_id}",
                    "propertySummaries": [
                        {
                            "property": f"properties/{account_id}",
                            "displayName": f"Property {account_id}",
                        }
                    ],
                }
            ]
        }
        if page_token is None:
            payload["nextPageToken"] = "account-page-2"
        return httpx.Response(200, json=payload)

    adapter = GoogleAnalyticsAdminAdapter(http_client_factory=mock_client_factory(handler))
    properties = await adapter.list_account_summaries("access-token")

    assert [item.property_number for item in properties] == ["123", "456"]
    assert requests == [None, "account-page-2"]


@pytest.mark.anyio
async def test_adapter_rejects_repeated_account_summary_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1beta/accountSummaries"
        return httpx.Response(
            200,
            json={"accountSummaries": [], "nextPageToken": "same-token"},
        )

    adapter = GoogleAnalyticsAdminAdapter(http_client_factory=mock_client_factory(handler))

    with pytest.raises(RuntimeError, match="token repeated"):
        await adapter.list_account_summaries("access-token")


@pytest.mark.integration
@pytest.mark.anyio
async def test_ga4_discover_map_sync_and_insights_consumption(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_connection(
            session, settings, org.id, "https://www.googleapis.com/auth/analytics.readonly"
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")

        fake = FakeAnalyticsAdapter(
            properties=[
                DiscoveredAnalyticsProperty(
                    "properties/123456", "123456", "Wheyland Electric", "Wheyland"
                ),
                DiscoveredAnalyticsProperty("properties/999", "999", "Other", "Other"),
            ],
            aggregate_rows=[
                AnalyticsReportRow(
                    {
                        "sessions": 5400,
                        "totalUsers": 3100,
                        "screenPageViews": 12000,
                        "conversions": 42,
                    }
                )
            ],
            daily_rows=[
                AnalyticsReportRow(
                    {"sessions": 200, "totalUsers": 120, "screenPageViews": 450, "conversions": 2},
                    {"date": "2026-07-20"},
                ),
                AnalyticsReportRow(
                    {"sessions": 180, "totalUsers": 110, "screenPageViews": 420, "conversions": 1},
                    {"date": "2026-07-21"},
                ),
            ],
        )
        service = AnalyticsService(adapter=fake)

        discovery = await service.discover_properties(
            session,
            settings,
            org.id,
            website_id=website.id,
            actor_id=None,
            correlation_id="d1",
        )
        assert discovery.recommended is not None
        assert discovery.recommended.external_property_id == "properties/123456"

        mapped = await service.map_property(
            session,
            settings,
            org.id,
            external_property_id="properties/123456",
            property_number="123456",
            display_name="Wheyland Electric",
            website_id=website.id,
            actor_id=None,
            correlation_id="m1",
        )
        assert mapped.mapping_status == "mapped"
        assert mapped.freshness_status == "never_synced"

        # Idempotent re-map (no duplicate).
        again = await service.map_property(
            session,
            settings,
            org.id,
            external_property_id="properties/123456",
            property_number="123456",
            display_name="Wheyland Electric",
            website_id=website.id,
            actor_id=None,
            correlation_id="m2",
        )
        assert again.id == mapped.id

        result = await service.sync_metrics(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )
        # 3 periods × (4 current aggregate + 4 prior aggregate + 2 daily × 4) = 48 upserts
        assert result["metrics_synced"] == 48
        assert result["periods_synced"] == [7, 28, 90]

        # MetricDefinition catalog was created idempotently.
        defs = list(
            await session.scalars(select(MetricDefinition).where(MetricDefinition.version == 1))
        )
        ga4_keys = {d.key for d in defs if d.key.startswith("ga4.")}
        assert ga4_keys == {
            "ga4.sessions",
            "ga4.totalUsers",
            "ga4.screenPageViews",
            "ga4.conversions",
        }

        # MetricObservation rows were persisted with real values across periods.
        observations = list(
            await session.scalars(
                select(MetricObservation).where(MetricObservation.organization_id == org.id)
            )
        )
        # 3 periods × 4 current aggregate + 3 periods × 4 prior aggregate
        #   + 2 dates × 4 daily = 24 + 8 = 32 observations
        assert len(observations) == 32
        aggregate_obs = [
            o for o in observations if o.dimensions.get("observation_type") == "aggregate"
        ]
        daily_obs = [o for o in observations if o.dimensions.get("observation_type") == "daily"]
        assert len(aggregate_obs) == 24
        assert len(daily_obs) == 8
        # Aggregate observations contain real provider values
        agg_values = {int(o.value) for o in aggregate_obs if o.value is not None}
        assert 5400 in agg_values

        # Insights summary consumes the synced GA4 metrics from latest period.
        summary = await service.summary(session, org.id)
        assert summary["connected"] is True
        metrics = cast(dict[str, int], summary["metrics"])
        assert metrics["ga4.sessions"] == 5400
        assert metrics["ga4.conversions"] == 42

        # Repeat sync is idempotent (upsert, not duplicate).
        await service.sync_metrics(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s2"
        )
        await session.flush()
        observations2 = list(
            await session.scalars(
                select(MetricObservation).where(MetricObservation.organization_id == org.id)
            )
        )
        assert len(observations2) == 32


@pytest.mark.integration
@pytest.mark.anyio
async def test_ga4_requires_analytics_scope(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from apps.api.app.products.analytics.errors import AnalyticsScopeRequiredError

    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        # GBP-only connection (no analytics scope).
        await make_connected_connection(
            session,
            settings,
            org.id,
            "https://www.googleapis.com/auth/business.manage",
        )
        service = AnalyticsService(adapter=FakeAnalyticsAdapter(properties=[]))
        with pytest.raises(AnalyticsScopeRequiredError):
            await service.discover_properties(
                session, settings, org.id, website_id=None, actor_id=None, correlation_id="d1"
            )


@pytest.mark.integration
@pytest.mark.anyio
async def test_insights_summary_stays_usable_without_ga4(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        service = AnalyticsService(adapter=FakeAnalyticsAdapter(properties=[]))
        summary = await service.summary(session, org.id)
        assert summary["connected"] is False
        assert cast(dict[str, int], summary["metrics"]) == {}


def _inclusive_span(start_date: str, end_date: str) -> int:
    """Count inclusive provider dates between two YYYY-MM-DD strings."""
    return (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_ga4_sync_sends_exact_inclusive_provider_dates(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_connection(
            session, settings, org.id, "https://www.googleapis.com/auth/analytics.readonly"
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")
        fake = FakeAnalyticsAdapter(
            properties=[
                DiscoveredAnalyticsProperty(
                    "properties/123456", "123456", "Wheyland Electric", "Wheyland"
                )
            ],
            aggregate_rows=[AnalyticsReportRow({"sessions": 10})],
        )
        service = AnalyticsService(adapter=fake)
        mapped = await service.map_property(
            session,
            settings,
            org.id,
            external_property_id="properties/123456",
            property_number="123456",
            display_name="Wheyland Electric",
            website_id=website.id,
            actor_id=None,
            correlation_id="m1",
        )
        await service.sync_metrics(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )

        aggregate_calls = [c for c in fake.report_calls if c[2] == ()]
        # 3 periods × (current + prior) = 6 aggregate calls
        assert len(aggregate_calls) == 6
        spans = sorted(_inclusive_span(s, e) for s, e, _ in aggregate_calls)
        assert spans == [7, 7, 28, 28, 90, 90]

        # GA4 tail exclusion = 1 day: current windows end at (today - 1)
        today = datetime.now(UTC).date()
        expected_last = today - timedelta(days=GA4_SYNC_TAIL_EXCLUSION_DAYS)
        assert any(e == expected_last.isoformat() for s, e, _ in aggregate_calls)

        # Current and prior windows never overlap.
        current_calls = [c for c in aggregate_calls if c[1] == expected_last.isoformat()]
        prior_calls = [c for c in aggregate_calls if c[1] != expected_last.isoformat()]
        assert len(current_calls) == 3
        assert len(prior_calls) == 3


@pytest.mark.integration
@pytest.mark.anyio
async def test_ga4_performance_report_current_and_prior_from_single_sync(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_connection(
            session, settings, org.id, "https://www.googleapis.com/auth/analytics.readonly"
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")

        now = datetime.now(UTC)
        aggregate_by_start: dict[str, list[AnalyticsReportRow]] = {}
        for days in (7, 28, 90):
            cur_start, _ = reporting_window(now, days, GA4_SYNC_TAIL_EXCLUSION_DAYS)
            comp_start, _ = comparison_window(cur_start, days)
            aggregate_by_start[provider_start_date(cur_start)] = [
                AnalyticsReportRow(
                    {
                        "sessions": 1200,
                        "totalUsers": 800,
                        "screenPageViews": 3000,
                        "conversions": 10,
                    }
                )
            ]
            aggregate_by_start[provider_start_date(comp_start)] = [
                AnalyticsReportRow(
                    {"sessions": 1000, "totalUsers": 700, "screenPageViews": 2500, "conversions": 8}
                )
            ]

        fake = FakeAnalyticsAdapter(
            properties=[
                DiscoveredAnalyticsProperty(
                    "properties/123456", "123456", "Wheyland Electric", "Wheyland"
                )
            ],
            aggregate_by_start=aggregate_by_start,
            daily_rows=[
                AnalyticsReportRow(
                    {"sessions": 200, "totalUsers": 120, "screenPageViews": 450, "conversions": 2},
                    {"date": "2026-07-20"},
                ),
            ],
        )
        service = AnalyticsService(adapter=fake)
        mapped = await service.map_property(
            session,
            settings,
            org.id,
            external_property_id="properties/123456",
            property_number="123456",
            display_name="Wheyland Electric",
            website_id=website.id,
            actor_id=None,
            correlation_id="m1",
        )
        await service.sync_metrics(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )

        for days in (7, 28, 90):
            report = await service.performance_report(session, org.id, days=days)
            assert report["connected"] is True
            assert cast(dict[str, object], report["range"])["days"] == days
            assert cast(dict[str, object], report["comparison_range"])["days"] == days
            metrics = cast(dict[str, dict[str, object]], report["metrics"])
            sessions = metrics["ga4.sessions"]
            assert sessions["current"] == 1200
            assert sessions["previous"] == 1000
            assert sessions["delta"] == 200
            assert sessions["percent_delta"] == pytest.approx(20.0)
            assert sessions["quality"] == "valid"
            # totalUsers is stored from aggregate rows (not summed daily)
            assert metrics["ga4.totalUsers"]["current"] == 800
            assert metrics["ga4.totalUsers"]["previous"] == 700


@pytest.mark.integration
@pytest.mark.anyio
async def test_ga4_missing_current_remains_none_not_zero(
    insights_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A metric with no current observation must report null (missing), not 0."""
    async with insights_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_connection(
            session, settings, org.id, "https://www.googleapis.com/auth/analytics.readonly"
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")

        # Sync with real zero for the current window so definitions/source exist.
        now = datetime.now(UTC)
        aggregate_by_start: dict[str, list[AnalyticsReportRow]] = {}
        for days in (7, 28, 90):
            cur_start, _ = reporting_window(now, days, GA4_SYNC_TAIL_EXCLUSION_DAYS)
            comp_start, _ = comparison_window(cur_start, days)
            aggregate_by_start[provider_start_date(cur_start)] = [
                AnalyticsReportRow(
                    {"sessions": 0, "totalUsers": 0, "screenPageViews": 0, "conversions": 0}
                )
            ]
            aggregate_by_start[provider_start_date(comp_start)] = [
                AnalyticsReportRow(
                    {"sessions": 100, "totalUsers": 50, "screenPageViews": 200, "conversions": 1}
                )
            ]

        fake = FakeAnalyticsAdapter(
            properties=[
                DiscoveredAnalyticsProperty(
                    "properties/123456", "123456", "Wheyland Electric", "Wheyland"
                )
            ],
            aggregate_by_start=aggregate_by_start,
        )
        service = AnalyticsService(adapter=fake)
        mapped = await service.map_property(
            session,
            settings,
            org.id,
            external_property_id="properties/123456",
            property_number="123456",
            display_name="Wheyland Electric",
            website_id=website.id,
            actor_id=None,
            correlation_id="m1",
        )
        await service.sync_metrics(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )

        # A real provider zero must remain numeric 0 (not missing).
        report = await service.performance_report(session, org.id, days=7)
        sessions = cast(dict[str, dict[str, object]], report["metrics"])["ga4.sessions"]
        assert sessions["current"] == 0
        assert sessions["previous"] == 100
        assert sessions["delta"] == -100
        assert sessions["quality"] == "valid"

        # Remove the current aggregate observation to simulate genuinely missing
        # data; the report must now return null (not 0).
        cur_start, cur_end = reporting_window(now, 7, GA4_SYNC_TAIL_EXCLUSION_DAYS)
        session_source = await session.scalar(
            select(InsightSource).where(
                InsightSource.organization_id == org.id,
                InsightSource.key == "properties/123456",
            )
        )
        assert session_source is not None
        session_def = await session.scalar(
            select(MetricDefinition).where(
                MetricDefinition.key == "ga4.sessions",
                MetricDefinition.version == 1,
            )
        )
        assert session_def is not None
        current_obs = await session.scalar(
            select(MetricObservation).where(
                MetricObservation.organization_id == org.id,
                MetricObservation.source_id == session_source.id,
                MetricObservation.metric_definition_id == session_def.id,
                MetricObservation.period_start == cur_start,
                MetricObservation.period_end == cur_end,
            )
        )
        assert current_obs is not None
        await session.delete(current_obs)
        await session.flush()

        report_missing = await service.performance_report(session, org.id, days=7)
        sessions_missing = cast(dict[str, dict[str, object]], report_missing["metrics"])[
            "ga4.sessions"
        ]
        assert sessions_missing["current"] is None
        assert sessions_missing["delta"] is None
        assert sessions_missing["percent_delta"] is None
        assert sessions_missing["quality"] == "missing"
