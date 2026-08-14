"""Search Console operator journey: discovery, canonical-domain recommendation,
idempotent mapping, real-modeled metric sync, and SEO consumption.

No real Google calls -- the Search Console adapter is replaced with a
deterministic fake and the Google OAuth token is short-circuited by writing a
connected connection with the Search Console scope granted directly.
"""

import json
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
    ) -> None:
        self._properties = properties
        self._summary_rows = summary_rows or []
        self._daily_rows = daily_rows or []
        self._query_rows = query_rows or []
        self._page_rows = page_rows or []
        self._summary_by_start = summary_by_start or {}
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

        # A daily observation with missing (None) metrics vs a real zero.
        day_dt = date.fromisoformat(provider_start_date(start))
        day_start = datetime(day_dt.year, day_dt.month, day_dt.day, tzinfo=UTC)
        day_end = day_start + timedelta(days=1)

        import hashlib
        import json as _json

        def _dh(dims: dict[str, object]) -> str:
            return hashlib.sha256(
                _json.dumps(dims, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()

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
