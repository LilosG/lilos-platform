"""Search Console operator journey: discovery, canonical-domain recommendation,
idempotent mapping, real-modeled metric sync, and SEO consumption.

No real Google calls -- the Search Console adapter is replaced with a
deterministic fake and the Google OAuth token is short-circuited by writing a
connected connection with the Search Console scope granted directly.
"""

import json
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta, timezone
from typing import cast
from urllib.parse import parse_qs, urlsplit
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.integrations.connection_service import (
    SEARCH_CONSOLE_SCOPE,
    GBPConnectionService,
    granted_services,
)
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.seo.models import (
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.products.seo.search_console_adapter import (
    DiscoveredSearchProperty,
    GoogleSearchConsoleAdapter,
    SearchAnalyticsRow,
    SearchConsoleAdapter,
)
from apps.api.app.products.seo.search_console_service import (
    SearchConsoleService,
    recommend_property,
)
from apps.api.app.reporting_periods import (
    GSC_SYNC_TAIL_EXCLUSION_DAYS,
    comparison_window,
    provider_end_date,
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


def state_from_authorization_url(url: str) -> str:
    return parse_qs(urlsplit(url).query)["state"][0]


async def make_organization(session: AsyncSession) -> Organization:
    organization = Organization(
        name="Search Console Test Org",
        slug=f"sc-test-org-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(organization)
    await session.flush()
    return organization


async def make_website(
    session: AsyncSession, organization_id: UUID, canonical_origin: str
) -> SEOWebsite:
    website = SEOWebsite(
        organization_id=organization_id,
        location_id=None,
        key="primary",
        name="Primary site",
        canonical_origin=canonical_origin,
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add(website)
    await session.flush()
    return website


async def make_connected_google_connection(
    session: AsyncSession,
    settings: Settings,
    organization_id: UUID,
    *,
    http_handler: Callable[[httpx.Request], httpx.Response],
) -> IntegrationConnection:
    """Create a connected Google connection, bypassing OAuth.

    The granted OAuth scopes are taken from the token response ``scope`` field
    (exactly as in production), so callers control which services are granted
    via the mock token handler.
    """
    await ProviderCatalogSeeder().run(session)
    connection_svc = GBPConnectionService(http_client_factory=mock_client_factory(http_handler))
    url = await connection_svc.begin_connection(
        session, settings, organization_id, actor_id=None, correlation_id="c1"
    )
    state = state_from_authorization_url(url)
    connection = await connection_svc.complete_connection(
        session,
        settings,
        organization_id,
        state=state,
        code="authorization-code",
        correlation_id="c2",
    )
    return connection


class FakeSearchConsoleAdapter(SearchConsoleAdapter):
    def __init__(
        self,
        properties: list[DiscoveredSearchProperty],
        summary_rows: list[SearchAnalyticsRow] | None = None,
        daily_rows: list[SearchAnalyticsRow] | None = None,
        query_rows: list[SearchAnalyticsRow] | None = None,
        page_rows: list[SearchAnalyticsRow] | None = None,
        summary_by_start: dict[str, list[SearchAnalyticsRow]] | None = None,
        fail_on_start: set[str] | None = None,
    ) -> None:
        self._properties = properties
        self._summary_rows = summary_rows or []
        self._daily_rows = daily_rows or []
        self._query_rows = query_rows or []
        self._page_rows = page_rows or []
        self._summary_by_start = summary_by_start or {}
        self._fail_on_start = fail_on_start or set()
        # (site_url, start_date, end_date, dimensions)
        self.query_calls: list[tuple[str, str, str, tuple[str, ...]]] = []

    async def list_sites(self, access_token: str) -> list[DiscoveredSearchProperty]:
        self.query_calls.append(("list", "", "", ()))
        return self._properties

    async def query_search_analytics(
        self,
        access_token: str,
        site_url: str,
        *,
        start_date: str,
        end_date: str,
        dimensions: Sequence[str] = ("query",),
        row_limit: int = 1000,
    ) -> list[SearchAnalyticsRow]:
        self.query_calls.append((site_url, start_date, end_date, tuple(dimensions)))
        if start_date in self._fail_on_start:
            raise RuntimeError(f"Search Console provider unavailable for {start_date}")
        if not dimensions:
            return self._summary_by_start.get(start_date, self._summary_rows)
        if "date" in dimensions:
            return self._daily_rows
        if "query" in dimensions:
            return self._query_rows
        if "page" in dimensions:
            return self._page_rows
        return self._query_rows  # default fallback


def token_handler(scope: str) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/token"
        return httpx.Response(
            200,
            json={
                "access_token": "sc-access-token",
                "refresh_token": "sc-refresh-token",
                "expires_in": 3600,
                "scope": scope,
            },
        )

    return handler


def test_recommend_property_prefers_domain_match_over_url_prefix() -> None:
    properties = [
        DiscoveredSearchProperty("https://wheylandelectric.com/", "url_prefix", "siteOwner"),
        DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "siteOwner"),
        DiscoveredSearchProperty("https://other.example/", "url_prefix", "siteOwner"),
    ]
    recommended = recommend_property(properties, "https://www.wheylandelectric.com/")
    assert recommended is not None
    assert recommended.external_property_id == "sc-domain:wheylandelectric.com"


def test_recommend_property_returns_none_when_no_match() -> None:
    properties = [DiscoveredSearchProperty("https://other.example/", "url_prefix", "siteOwner")]
    assert recommend_property(properties, "https://wheylandelectric.com/") is None


@pytest.mark.anyio
async def test_search_console_adapter_paginates_search_analytics_rows() -> None:
    starts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/searchAnalytics/query")
        parsed = json.loads(request.content)
        starts.append(int(parsed["startRow"]))
        start = int(parsed["startRow"])
        rows = [
            {
                "keys": [f"query-{index}"],
                "clicks": index,
                "impressions": index + 10,
                "ctr": 0.5,
                "position": 2.0,
            }
            for index in range(start, start + (2 if start == 0 else 1))
        ]
        return httpx.Response(200, json={"rows": rows})

    adapter = GoogleSearchConsoleAdapter(http_client_factory=mock_client_factory(handler))
    rows = await adapter.query_search_analytics(
        "access-token",
        "https://example.com/",
        start_date="2026-01-01",
        end_date="2026-01-31",
        row_limit=2,
    )

    assert [row.keys for row in rows] == [("query-0",), ("query-1",), ("query-2",)]
    assert starts == [0, 2]


@pytest.mark.integration
@pytest.mark.anyio
async def test_granted_services_reports_search_console_after_reconsent(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        connection = await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler(
                "https://www.googleapis.com/auth/webmasters.readonly "
                "https://www.googleapis.com/auth/business.manage"
            ),
        )
        services = granted_services(connection)
        assert services == {"gbp": True, "search_console": True, "analytics": False}


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_discover_recommend_map_and_sync(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler(
                "https://www.googleapis.com/auth/webmasters.readonly "
                "https://www.googleapis.com/auth/business.manage"
            ),
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")

        fake = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "siteOwner"),
                DiscoveredSearchProperty(
                    "https://wheylandelectric.com/", "url_prefix", "siteOwner"
                ),
            ],
            summary_rows=[
                SearchAnalyticsRow((), 500, 15000, 0.033, 5.0),
            ],
            daily_rows=[
                SearchAnalyticsRow(("2026-07-20",), 15, 500, 0.030, 5.5),
                SearchAnalyticsRow(("2026-07-21",), 12, 400, 0.030, 4.8),
            ],
            query_rows=[
                SearchAnalyticsRow(("electrician near me",), 120, 3400, 0.035, 4.2),
                SearchAnalyticsRow(("panel upgrade",), 40, 900, 0.044, 6.1),
            ],
            page_rows=[
                SearchAnalyticsRow(("/services",), 80, 2000, 0.040, 3.5),
                SearchAnalyticsRow(("/contact",), 60, 1500, 0.040, 4.0),
            ],
        )
        service = SearchConsoleService(adapter=fake)

        # Discover recommends the domain property matching the canonical host.
        discovery = await service.discover_properties(
            session, settings, org.id, website.id, actor_id=None, correlation_id="d1"
        )
        assert discovery.recommended is not None
        assert discovery.recommended.external_property_id == "sc-domain:wheylandelectric.com"

        # Operator confirms the recommended property; mapping is persisted.
        mapped = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id=discovery.recommended.external_property_id,
            property_type="domain",
            actor_id=None,
            correlation_id="m1",
        )
        assert mapped.mapping_status == "mapped"
        assert mapped.freshness_status == "never_synced"

        # Re-mapping the same property is idempotent (no duplicate row).
        again = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id=discovery.recommended.external_property_id,
            property_type="domain",
            actor_id=None,
            correlation_id="m2",
        )
        assert again.id == mapped.id

        # Sync pulls real modeled metrics into SEOSearchObservation.
        result = await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )
        # 3 × (1 current summary + 1 prior summary + 2 daily + 2 query + 2 page) = 24 upserts;
        # daily rows dedup across periods (same day boundaries) → 20 stored
        assert result["rows_synced"] == 24
        assert result["periods_synced"] == [7, 28, 90]
        await session.flush()
        observations = list(
            await session.scalars(
                select(SEOSearchObservation).where(
                    SEOSearchObservation.search_property_id == mapped.id
                )
            )
        )
        assert len(observations) == 20
        # Verify observation types are present
        obs_types = {o.dimensions.get("observation_type") for o in observations}
        assert obs_types == {"site_summary", "daily", "top_query", "top_page"}
        # 6 site_summary rows: 3 current + 3 prior (exact comparison windows)
        summary_obs = [
            o for o in observations if o.dimensions.get("observation_type") == "site_summary"
        ]
        assert len(summary_obs) == 6
        # The sync queried the mapped domain property (last recorded call).
        assert fake.query_calls[-1][0] == "sc-domain:wheylandelectric.com"

        # SEO summary consumes the latest site_summary observation.
        summary = await service.search_performance_summary(session, org.id, website.id)
        assert summary["connected"] is True
        assert summary["total_clicks"] == 500
        assert summary["total_impressions"] == 15000


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_sync_is_idempotent_on_repeat(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")
        fake = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "owner")
            ],
            summary_rows=[SearchAnalyticsRow((), 10, 100, 0.1, 5.0)],
            query_rows=[SearchAnalyticsRow(("q",), 10, 100, 0.1, 5.0)],
        )
        service = SearchConsoleService(adapter=fake)
        mapped = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id="sc-domain:wheylandelectric.com",
            property_type="domain",
            actor_id=None,
            correlation_id="m1",
        )
        first_result = await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )
        # 3 periods × (1 current summary + 1 prior summary + 1 query) = 9 upserts
        assert first_result["rows_synced"] == 9
        # Second sync upserts in place rather than duplicating rows.
        await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s2"
        )
        await session.flush()
        observations = list(
            await session.scalars(
                select(SEOSearchObservation).where(
                    SEOSearchObservation.search_property_id == mapped.id
                )
            )
        )
        assert len(observations) == 9
        assert observations[0].clicks == 10


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_requires_scope(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from apps.api.app.products.seo.errors import SEOSearchConsoleScopeRequiredError

    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        # GBP-only connection (no search_console scope) -- legacy upgrade case.
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/business.manage"),
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")
        service = SearchConsoleService(adapter=FakeSearchConsoleAdapter(properties=[]))
        with pytest.raises(SEOSearchConsoleScopeRequiredError):
            await service.discover_properties(
                session, settings, org.id, website.id, actor_id=None, correlation_id="d1"
            )


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_zero_properties_is_truthful_not_error(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")
        service = SearchConsoleService(adapter=FakeSearchConsoleAdapter(properties=[]))
        result = await service.discover_properties(
            session, settings, org.id, website.id, actor_id=None, correlation_id="d1"
        )
        assert result.properties == ()
        assert result.recommended is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_existing_gbp_connection_survives_reconsent_without_duplicate(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        # First: GBP-only connection.
        connection1 = await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/business.manage"),
        )
        # Re-consent requesting search_console reuses the SAME connection row.
        connection_svc = GBPConnectionService(
            http_client_factory=mock_client_factory(
                token_handler(
                    "https://www.googleapis.com/auth/business.manage "
                    "https://www.googleapis.com/auth/webmasters.readonly"
                )
            )
        )
        url = await connection_svc.begin_connection(
            session,
            settings,
            org.id,
            actor_id=None,
            correlation_id="r1",
            products=("gbp", "search_console"),
        )
        state = state_from_authorization_url(url)
        connection2 = await connection_svc.complete_connection(
            session,
            settings,
            org.id,
            state=state,
            code="code-2",
            correlation_id="r2",
        )
        assert connection2.id == connection1.id
        # No duplicate Google connection rows for this organization.
        all_connections = list(
            await session.scalars(
                select(IntegrationConnection)
                .join(Provider, Provider.id == IntegrationConnection.provider_id)
                .where(
                    IntegrationConnection.organization_id == org.id,
                    Provider.key == "google_business_profile",
                )
            )
        )
        assert len(all_connections) == 1
        assert SEARCH_CONSOLE_SCOPE in connection2.granted_capabilities


def _inclusive_span(start_date: str, end_date: str) -> int:
    return (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days + 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_sync_sends_exact_inclusive_provider_dates(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")
        fake = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "owner")
            ],
            summary_rows=[SearchAnalyticsRow((), 10, 100, 0.1, 5.0)],
            query_rows=[SearchAnalyticsRow(("q",), 10, 100, 0.1, 5.0)],
        )
        service = SearchConsoleService(adapter=fake)
        mapped = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id="sc-domain:wheylandelectric.com",
            property_type="domain",
            actor_id=None,
            correlation_id="m1",
        )
        await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )

        # Current site-summary windows must each span exactly 7/28/90 inclusive dates.
        summary_calls = [c for c in fake.query_calls if c[3] == ()]
        assert len(summary_calls) == 6  # 3 current + 3 prior
        spans = sorted(_inclusive_span(s, e) for _, s, e, _ in summary_calls)
        assert spans == [7, 7, 28, 28, 90, 90]

        # GSC tail exclusion = 2 days: current windows end at (today - 2).
        today = datetime.now(UTC).date()
        expected_last = (today - timedelta(days=GSC_SYNC_TAIL_EXCLUSION_DAYS)).isoformat()
        current_calls = [c for c in summary_calls if c[2] == expected_last]
        prior_calls = [c for c in summary_calls if c[2] != expected_last]
        assert len(current_calls) == 3
        assert len(prior_calls) == 3

        # Daily/query/page provider requests are also inclusive and exact.
        for dims in (("date",), ("query",), ("page",)):
            typed_calls = [c for c in fake.query_calls if c[3] == dims]
            assert len(typed_calls) == 3  # current only, one per period
            typed_spans = sorted(_inclusive_span(s, e) for _, s, e, _ in typed_calls)
            assert typed_spans == [7, 28, 90]


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_performance_report_current_and_prior_from_single_sync(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")

        now = datetime.now(UTC)
        summary_by_start: dict[str, list[SearchAnalyticsRow]] = {}
        for days in (7, 28, 90):
            cur_start, _ = reporting_window(now, days, GSC_SYNC_TAIL_EXCLUSION_DAYS)
            comp_start, _ = comparison_window(cur_start, days)
            summary_by_start[provider_start_date(cur_start)] = [
                SearchAnalyticsRow((), 500, 15000, 0.033, 5.0)
            ]
            summary_by_start[provider_start_date(comp_start)] = [
                SearchAnalyticsRow((), 400, 12000, 0.033, 5.5)
            ]

        # A daily date within every current window (7/28/90).
        daily_date = (now.date() - timedelta(days=3)).isoformat()
        fake = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "owner")
            ],
            summary_by_start=summary_by_start,
            daily_rows=[SearchAnalyticsRow((daily_date,), 15, 500, 0.030, 5.5)],
            query_rows=[SearchAnalyticsRow(("electrician near me",), 120, 3400, 0.035, 4.2)],
            page_rows=[SearchAnalyticsRow(("/services",), 80, 2000, 0.040, 3.5)],
        )
        service = SearchConsoleService(adapter=fake)
        mapped = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id="sc-domain:wheylandelectric.com",
            property_type="domain",
            actor_id=None,
            correlation_id="m1",
        )
        await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )

        for days in (7, 28, 90):
            report = await service.performance_report(session, org.id, website.id, days=days)
            assert report["connected"] is True
            assert cast(dict[str, object], report["range"])["days"] == days
            assert cast(dict[str, object], report["comparison_range"])["days"] == days
            metrics = cast(dict[str, dict[str, object]], report["metrics"])
            assert metrics["clicks"]["current"] == 500
            assert metrics["clicks"]["previous"] == 400
            assert metrics["clicks"]["delta"] == 100
            assert metrics["impressions"]["current"] == 15000
            assert metrics["impressions"]["previous"] == 12000
            assert metrics["position"]["current"] == 5.0
            assert metrics["position"]["previous"] == 5.5
            # Series, top queries, top pages all resolve from the same property.
            assert len(cast(list[dict[str, object]], report["series"])) == 1
            assert cast(list[dict[str, object]], report["top_queries"])[0]["clicks"] == 120
            assert cast(list[dict[str, object]], report["top_pages"])[0]["clicks"] == 80


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_multi_property_authority_resolves_single_source(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")

        service = SearchConsoleService(
            adapter=FakeSearchConsoleAdapter(properties=[]),
        )
        # Map the first property, then a second. The first must be replaced.
        first = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id="sc-domain:wheylandelectric.com",
            property_type="domain",
            actor_id=None,
            correlation_id="m1",
        )
        second = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id="https://wheylandelectric.com/",
            property_type="url_prefix",
            actor_id=None,
            correlation_id="m2",
        )

        assert first.id != second.id
        properties = list(
            await session.scalars(
                select(SEOSearchProperty).where(
                    SEOSearchProperty.organization_id == org.id,
                    SEOSearchProperty.website_id == website.id,
                )
            )
        )
        by_status = {p.external_property_id: p.mapping_status for p in properties}
        assert by_status["sc-domain:wheylandelectric.com"] == "replaced"
        assert by_status["https://wheylandelectric.com/"] == "mapped"

        report = await service.performance_report(session, org.id, website.id, days=7)
        assert report["connected"] is True
        props = cast(list[dict[str, object]], report["properties"])
        assert len(props) == 1
        assert props[0]["external_property_id"] == "https://wheylandelectric.com/"


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_missing_values_not_converted_to_zero(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Null observation values must stay null; real zeros stay zero."""
    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        website = await make_website(session, org.id, "https://wheylandelectric.com/")
        service = SearchConsoleService(adapter=FakeSearchConsoleAdapter(properties=[]))
        mapped = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id="sc-domain:wheylandelectric.com",
            property_type="domain",
            actor_id=None,
            correlation_id="m1",
        )

        now = datetime.now(UTC)
        start, end = reporting_window(now, 7, GSC_SYNC_TAIL_EXCLUSION_DAYS)

        import hashlib
        import json as _json

        def _dh(dims: dict[str, object]) -> str:
            return hashlib.sha256(
                _json.dumps(dims, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()

        # Insert a current site_summary so the report window can anchor.
        summary_dims: dict[str, object] = {"observation_type": "site_summary"}
        session.add(
            SEOSearchObservation(
                organization_id=org.id,
                search_property_id=mapped.id,
                page_id=None,
                query=None,
                date_start=start,
                date_end=end,
                dimensions=summary_dims,
                dimension_hash=_dh(summary_dims),
                clicks=12,
                impressions=300,
                ctr=0.04,
                position=5.0,
                quality_status="valid",
                partial=False,
            )
        )

        # A daily observation with missing (None) metrics vs a real zero.
        day_dt = date.fromisoformat(provider_start_date(start))
        day_start = datetime(day_dt.year, day_dt.month, day_dt.day, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)

        missing_dims: dict[str, object] = {
            "observation_type": "daily",
            "date": day_start.strftime("%Y-%m-%d"),
        }
        session.add(
            SEOSearchObservation(
                organization_id=org.id,
                search_property_id=mapped.id,
                page_id=None,
                query=None,
                date_start=day_start,
                date_end=day_end,
                dimensions=missing_dims,
                dimension_hash=_dh(missing_dims),
                clicks=None,
                impressions=None,
                ctr=None,
                position=None,
                quality_status="valid",
                partial=True,
            )
        )
        zero_day = day_start + timedelta(days=1)
        zero_end = zero_day + timedelta(days=1)
        zero_dims: dict[str, object] = {
            "observation_type": "daily",
            "date": zero_day.strftime("%Y-%m-%d"),
        }
        session.add(
            SEOSearchObservation(
                organization_id=org.id,
                search_property_id=mapped.id,
                page_id=None,
                query=None,
                date_start=zero_day,
                date_end=zero_end,
                dimensions=zero_dims,
                dimension_hash=_dh(zero_dims),
                clicks=0,
                impressions=0,
                ctr=0.0,
                position=0.0,
                quality_status="zero",
                partial=False,
            )
        )
        await session.flush()

        report = await service.performance_report(session, org.id, website.id, days=7)
        series = cast(list[dict[str, object]], report["series"])
        assert len(series) == 2
        missing_entry = next(s for s in series if s["date"] == day_start.strftime("%Y-%m-%d"))
        zero_entry = next(s for s in series if s["date"] == zero_day.strftime("%Y-%m-%d"))
        assert missing_entry["clicks"] is None
        assert missing_entry["impressions"] is None
        assert zero_entry["clicks"] == 0
        assert zero_entry["impressions"] == 0


class _FrozenDateTime(datetime):
    """Deterministic ``datetime.now`` stub for module-level clock control."""

    frozen_now: datetime | None = None

    @classmethod
    def now(cls, tz: timezone | None = None) -> datetime:  # type: ignore[override]
        if cls.frozen_now is not None:
            return cls.frozen_now
        return datetime.now(tz)


def _freeze_search_console_clock(monkeypatch: pytest.MonkeyPatch, value: datetime) -> None:
    import apps.api.app.products.seo.search_console_service as sc_module

    _FrozenDateTime.frozen_now = value
    monkeypatch.setattr(sc_module, "datetime", _FrozenDateTime)


async def _setup_mapped_gsc(
    session: AsyncSession,
    settings: Settings,
    org: Organization,
    fake: FakeSearchConsoleAdapter,
) -> tuple[SEOSearchProperty, SEOWebsite]:
    website = await make_website(session, org.id, "https://wheylandelectric.com/")
    service = SearchConsoleService(adapter=fake)
    mapped = await service.map_property(
        session,
        settings,
        org.id,
        website.id,
        external_property_id="sc-domain:wheylandelectric.com",
        property_type="domain",
        actor_id=None,
        correlation_id="m1",
    )
    return mapped, website


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_report_anchored_to_stored_window_across_rollover(
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A calendar rollover before the next sync must not shift the report window."""
    day_n = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    day_n1 = datetime(2026, 8, 14, 12, 0, tzinfo=UTC)
    _freeze_search_console_clock(monkeypatch, day_n)

    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )

        summary_by_start: dict[str, list[SearchAnalyticsRow]] = {}
        expected_ranges: dict[int, dict[str, object]] = {}
        for days in (7, 28, 90):
            cur_start, cur_end = reporting_window(day_n, days, GSC_SYNC_TAIL_EXCLUSION_DAYS)
            comp_start, _ = comparison_window(cur_start, days)
            summary_by_start[provider_start_date(cur_start)] = [
                SearchAnalyticsRow((), 500, 15000, 0.033, 5.0)
            ]
            summary_by_start[provider_start_date(comp_start)] = [
                SearchAnalyticsRow((), 400, 12000, 0.033, 5.5)
            ]
            expected_ranges[days] = {
                "start": provider_start_date(cur_start),
                "end": provider_end_date(cur_end),
                "days": days,
            }

        fake = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "owner")
            ],
            summary_by_start=summary_by_start,
            query_rows=[SearchAnalyticsRow(("electrician near me",), 120, 3400, 0.035, 4.2)],
            page_rows=[SearchAnalyticsRow(("/services",), 80, 2000, 0.040, 3.5)],
        )
        service = SearchConsoleService(adapter=fake)
        mapped, website = await _setup_mapped_gsc(session, settings, org, fake)
        await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )

        _FrozenDateTime.frozen_now = day_n1

        for days in (7, 28, 90):
            report = await service.performance_report(session, org.id, website.id, days=days)
            metrics = cast(dict[str, dict[str, object]], report["metrics"])
            assert metrics["clicks"]["current"] == 500
            assert metrics["clicks"]["previous"] == 400
            assert metrics["clicks"]["delta"] == 100
            assert report["range"] == expected_ranges[days]
            assert cast(dict[str, object], report["freshness"])["status"] == "fresh"

        _FrozenDateTime.frozen_now = day_n + timedelta(days=3)
        report = await service.performance_report(session, org.id, website.id, days=28)
        metrics = cast(dict[str, dict[str, object]], report["metrics"])
        assert metrics["clicks"]["current"] == 500
        assert report["range"] == expected_ranges[28]
        assert cast(dict[str, object], report["freshness"])["status"] == "stale"


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_partial_sync_preserves_previous_freshness(
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed required request must not mark fresh nor advance last_synced_at."""
    day_n = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    _freeze_search_console_clock(monkeypatch, day_n)

    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        fake = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "owner")
            ],
            summary_rows=[SearchAnalyticsRow((), 10, 100, 0.1, 5.0)],
            query_rows=[SearchAnalyticsRow(("q",), 10, 100, 0.1, 5.0)],
        )
        service = SearchConsoleService(adapter=fake)
        mapped, website = await _setup_mapped_gsc(session, settings, org, fake)

        first = await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )
        assert first["freshness_status"] == "fresh"
        prop_before = await session.scalar(
            select(SEOSearchProperty).where(SEOSearchProperty.id == mapped.id)
        )
        assert prop_before is not None
        first_last_synced = prop_before.last_synced_at
        assert first_last_synced is not None

        cur90_start, _ = reporting_window(day_n, 90, GSC_SYNC_TAIL_EXCLUSION_DAYS)
        fake._fail_on_start = {provider_start_date(cur90_start)}
        second = await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s2"
        )
        assert second["freshness_status"] == "stale"
        assert second["rows_synced"] == 0
        assert second["periods_synced"] == []

        prop_after = await session.scalar(
            select(SEOSearchProperty).where(SEOSearchProperty.id == mapped.id)
        )
        assert prop_after is not None
        assert prop_after.last_synced_at == first_last_synced
        assert prop_after.freshness_status == "stale"

        report = await service.performance_report(session, org.id, website.id, days=90)
        metrics = cast(dict[str, dict[str, object]], report["metrics"])
        assert metrics["clicks"]["current"] == 10
        assert cast(dict[str, object], report["freshness"])["status"] == "stale"


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_total_first_sync_failure_is_never_synced(
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Total provider failure on first-ever sync must not claim fresh."""
    day_n = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    _freeze_search_console_clock(monkeypatch, day_n)

    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        fake = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "owner")
            ],
            summary_rows=[SearchAnalyticsRow((), 10, 100, 0.1, 5.0)],
        )
        fake._fail_on_start = {
            provider_start_date(reporting_window(day_n, d, GSC_SYNC_TAIL_EXCLUSION_DAYS)[0])
            for d in (7, 28, 90)
        }
        service = SearchConsoleService(adapter=fake)
        mapped, website = await _setup_mapped_gsc(session, settings, org, fake)

        result = await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )
        assert result["freshness_status"] == "never_synced"
        assert result["rows_synced"] == 0

        prop = await session.scalar(
            select(SEOSearchProperty).where(SEOSearchProperty.id == mapped.id)
        )
        assert prop is not None
        assert prop.last_synced_at is None
        assert prop.freshness_status == "never_synced"

        report = await service.performance_report(session, org.id, website.id, days=28)
        assert report["range"] is None
        assert report["comparison_range"] is None
        assert cast(dict[str, object], report["freshness"])["status"] == "never_synced"
        assert report["metrics"] == {}


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_sync_failure_tenant_isolation(
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One tenant's failed sync must not disturb another tenant's dataset."""
    day_n = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    _freeze_search_console_clock(monkeypatch, day_n)

    async with seo_session_factory.begin() as session:
        org_a = await make_organization(session)
        org_b = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org_a.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        await make_connected_google_connection(
            session,
            settings,
            org_b.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )

        fake_a = FakeSearchConsoleAdapter(
            properties=[DiscoveredSearchProperty("sc-domain:a.example", "domain", "owner")],
            summary_rows=[SearchAnalyticsRow((), 30, 300, 0.1, 5.0)],
            query_rows=[SearchAnalyticsRow(("qa",), 10, 100, 0.1, 5.0)],
        )
        service_a = SearchConsoleService(adapter=fake_a)
        website_a = await make_website(session, org_a.id, "https://a.example/")
        mapped_a = await service_a.map_property(
            session,
            settings,
            org_a.id,
            website_a.id,
            external_property_id="sc-domain:a.example",
            property_type="domain",
            actor_id=None,
            correlation_id="ma",
        )
        result_a = await service_a.sync_observations(
            session, settings, org_a.id, mapped_a.id, actor_id=None, correlation_id="sa"
        )
        assert result_a["freshness_status"] == "fresh"

        fake_b = FakeSearchConsoleAdapter(
            properties=[DiscoveredSearchProperty("sc-domain:b.example", "domain", "owner")],
            summary_rows=[SearchAnalyticsRow((), 40, 400, 0.1, 5.0)],
        )
        fake_b._fail_on_start = {
            provider_start_date(reporting_window(day_n, d, GSC_SYNC_TAIL_EXCLUSION_DAYS)[0])
            for d in (7, 28, 90)
        }
        service_b = SearchConsoleService(adapter=fake_b)
        website_b = await make_website(session, org_b.id, "https://b.example/")
        mapped_b = await service_b.map_property(
            session,
            settings,
            org_b.id,
            website_b.id,
            external_property_id="sc-domain:b.example",
            property_type="domain",
            actor_id=None,
            correlation_id="mb",
        )
        result_b = await service_b.sync_observations(
            session, settings, org_b.id, mapped_b.id, actor_id=None, correlation_id="sb"
        )
        assert result_b["freshness_status"] == "never_synced"

        report_a = await service_a.performance_report(session, org_a.id, website_a.id, days=28)
        metrics_a = cast(dict[str, dict[str, object]], report_a["metrics"])
        assert metrics_a["clicks"]["current"] == 30
        assert cast(dict[str, object], report_a["freshness"])["status"] == "fresh"
        report_b = await service_b.performance_report(session, org_b.id, website_b.id, days=28)
        assert report_b["range"] is None
        assert cast(dict[str, object], report_b["freshness"])["status"] == "never_synced"


# -- regression: empty site-summary must establish authoritative zero observation --


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_empty_current_summary_persists_zero_observation(
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """First sync stores real data; second sync returns [] → current window is zero."""
    day_n = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    _freeze_search_console_clock(monkeypatch, day_n)

    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )

        # First sync — real 28‑day data
        cur_start, cur_end = reporting_window(day_n, 28, GSC_SYNC_TAIL_EXCLUSION_DAYS)
        comp_start, _ = comparison_window(cur_start, 28)
        summary_by_start1: dict[str, list[SearchAnalyticsRow]] = {
            provider_start_date(cur_start): [
                SearchAnalyticsRow((), 500, 15000, 0.033, 5.0)
            ],
            provider_start_date(comp_start): [
                SearchAnalyticsRow((), 400, 12000, 0.033, 5.5)
            ],
        }

        fake1 = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "owner")
            ],
            summary_by_start=summary_by_start1,
        )
        service = SearchConsoleService(adapter=fake1)
        mapped, website = await _setup_mapped_gsc(session, settings, org, fake1)
        result = await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )
        assert result["freshness_status"] == "fresh"
        assert result["last_synced_at"] is not None
        first_synced = result["last_synced_at"]

        report = await service.performance_report(session, org.id, website.id, days=28)
        metrics = cast(dict[str, dict[str, object]], report["metrics"])
        assert metrics["clicks"]["current"] == 500
        assert cast(dict[str, object], report["freshness"])["status"] == "fresh"

        # Advance clock so we get a new reporting window
        day_n1 = day_n + timedelta(days=3)
        _FrozenDateTime.frozen_now = day_n1

        new_start, new_end = reporting_window(day_n1, 28, GSC_SYNC_TAIL_EXCLUSION_DAYS)
        new_comp_start, _ = comparison_window(new_start, 28)

        # Second sync — current site_summary returns [], prior returns zero too
        summary_by_start2: dict[str, list[SearchAnalyticsRow]] = {
            provider_start_date(new_start): [],
            provider_start_date(new_comp_start): [],
        }
        fake2 = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "owner")
            ],
            summary_by_start=summary_by_start2,
        )
        service2 = SearchConsoleService(adapter=fake2)
        result2 = await service2.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s2"
        )
        assert result2["freshness_status"] == "fresh"
        assert result2["last_synced_at"] is not None
        assert result2["last_synced_at"] > first_synced

        report2 = await service2.performance_report(session, org.id, website.id, days=28)
        metrics2 = cast(dict[str, dict[str, object]], report2["metrics"])
        assert metrics2["clicks"]["current"] == 0
        assert metrics2["clicks"]["previous"] == 0
        assert metrics2["impressions"]["current"] == 0
        assert metrics2["impressions"]["previous"] == 0
        assert metrics2["ctr"]["current"] is None
        assert metrics2["ctr"]["previous"] is None
        assert metrics2["position"]["current"] is None
        assert metrics2["position"]["previous"] is None
        assert metrics2["clicks"]["quality"] == "valid"
        assert metrics2["ctr"]["quality"] == "missing"

        # Range labels use the new window
        rng = cast(dict[str, object], report2["range"])
        assert rng["start"] == provider_start_date(new_start)
        assert rng["end"] == provider_end_date(new_end)
        assert rng["days"] == 28

        assert cast(dict[str, object], report2["freshness"])["status"] == "fresh"

        # Repeated empty sync is idempotent
        result3 = await service2.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s3"
        )
        assert result3["freshness_status"] == "fresh"
        report3 = await service2.performance_report(session, org.id, website.id, days=28)
        metrics3 = cast(dict[str, dict[str, object]], report3["metrics"])
        assert metrics3["clicks"]["current"] == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_empty_prior_summary_does_not_substitute_stale_prior(
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When prior site_summary returns [] the previous values are 0, not stale."""
    day_n = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    _freeze_search_console_clock(monkeypatch, day_n)

    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )

        cur_start, _ = reporting_window(day_n, 28, GSC_SYNC_TAIL_EXCLUSION_DAYS)
        comp_start, _ = comparison_window(cur_start, 28)

        summary_by_start: dict[str, list[SearchAnalyticsRow]] = {
            provider_start_date(cur_start): [
                SearchAnalyticsRow((), 500, 15000, 0.033, 5.0)
            ],
            provider_start_date(comp_start): [],
        }

        fake = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "owner")
            ],
            summary_by_start=summary_by_start,
        )
        service = SearchConsoleService(adapter=fake)
        mapped, website = await _setup_mapped_gsc(session, settings, org, fake)
        await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )

        report = await service.performance_report(session, org.id, website.id, days=28)
        metrics = cast(dict[str, dict[str, object]], report["metrics"])
        assert metrics["clicks"]["current"] == 500
        assert metrics["clicks"]["previous"] == 0
        assert metrics["impressions"]["current"] == 15000
        assert metrics["impressions"]["previous"] == 0
        assert metrics["ctr"]["current"] == 0.033
        assert metrics["ctr"]["previous"] is None
        assert metrics["position"]["current"] == 5.0
        assert metrics["position"]["previous"] is None


# -- regression: CTR / position deltas must work with Decimal (Numeric) values --


@pytest.mark.integration
@pytest.mark.anyio
async def test_search_console_ctr_position_decimal_deltas(
    seo_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CTR and position deltas are computed correctly from real Numeric columns."""
    day_n = datetime(2026, 8, 13, 12, 0, tzinfo=UTC)
    _freeze_search_console_clock(monkeypatch, day_n)

    async with seo_session_factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )

        cur_start, _ = reporting_window(day_n, 28, GSC_SYNC_TAIL_EXCLUSION_DAYS)
        comp_start, _ = comparison_window(cur_start, 28)

        summary_by_start: dict[str, list[SearchAnalyticsRow]] = {
            provider_start_date(cur_start): [
                SearchAnalyticsRow((), 500, 15000, 0.045, 3.2)
            ],
            provider_start_date(comp_start): [
                SearchAnalyticsRow((), 400, 12000, 0.033, 5.5)
            ],
        }

        fake = FakeSearchConsoleAdapter(
            properties=[
                DiscoveredSearchProperty("sc-domain:wheylandelectric.com", "domain", "owner")
            ],
            summary_by_start=summary_by_start,
        )
        service = SearchConsoleService(adapter=fake)
        mapped, website = await _setup_mapped_gsc(session, settings, org, fake)
        await service.sync_observations(
            session, settings, org.id, mapped.id, actor_id=None, correlation_id="s1"
        )

        report = await service.performance_report(session, org.id, website.id, days=28)
        metrics = cast(dict[str, dict[str, object]], report["metrics"])

        # CTR
        assert metrics["ctr"]["current"] == 0.045
        assert metrics["ctr"]["previous"] == 0.033
        assert metrics["ctr"]["delta"] is not None
        assert isinstance(metrics["ctr"]["delta"], float)
        assert pytest.approx(metrics["ctr"]["delta"], abs=1e-6) == 0.012
        assert metrics["ctr"]["percent_delta"] is not None
        assert isinstance(metrics["ctr"]["percent_delta"], float)
        # (0.045 - 0.033) / 0.033 * 100 ≈ 36.36...
        assert pytest.approx(metrics["ctr"]["percent_delta"], abs=0.1) == 36.36

        # Position
        assert metrics["position"]["current"] == 3.2
        assert metrics["position"]["previous"] == 5.5
        assert metrics["position"]["delta"] is not None
        assert isinstance(metrics["position"]["delta"], float)
        assert pytest.approx(metrics["position"]["delta"], abs=1e-6) == -2.3
        assert metrics["position"]["percent_delta"] is not None
        # (-2.3 / 5.5 * 100) ≈ -41.818...
        assert pytest.approx(metrics["position"]["percent_delta"], abs=0.1) == -41.82
