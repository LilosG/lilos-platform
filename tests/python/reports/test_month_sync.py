"""The syncs also store whole calendar months for the monthly report, apart from rolling windows."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from insights.test_analytics import (
    PageFakeAnalyticsAdapter,
    _freeze_analytics_clock,
    make_connected_connection,
    make_organization,
    make_seo_page,
    make_settings,
    make_website,
)
from seo.scope import SharedSessionScope
from seo.test_search_console import (
    FakeSearchConsoleAdapter,
    _freeze_search_console_clock,
    make_connected_google_connection,
    token_handler,
)
from seo.test_search_console import make_organization as make_sc_organization
from seo.test_search_console import make_settings as make_sc_settings
from seo.test_search_console import make_website as make_sc_website
from sqlalchemy import select

from apps.api.app.insights.models import MetricObservation
from apps.api.app.products.analytics.adapter import AnalyticsReportRow
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.seo.models import SEOSearchObservation
from apps.api.app.products.seo.month_observations import (
    MONTH_SITE_SUMMARY,
    MONTH_TOP_PAGE,
    MONTH_TOP_QUERY,
)
from apps.api.app.products.seo.search_console_adapter import (
    DiscoveredSearchProperty,
    SearchAnalyticsRow,
)
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from apps.api.app.reporting_periods import calendar_month_window
from reports.support import Factory

pytestmark = pytest.mark.integration
FIRST = datetime(2026, 10, 1, 15, 0, tzinfo=UTC)
THIRD = datetime(2026, 10, 3, 15, 0, tzinfo=UTC)
FOURTH = datetime(2026, 10, 4, 15, 0, tzinfo=UTC)


def month_calls(fake: FakeSearchConsoleAdapter) -> list[tuple[str, str, tuple[str, ...]]]:
    """Requests whose window is a whole calendar month (it starts on the 1st)."""
    return [
        (start, end, dims)
        for _, start, end, dims in fake.query_calls
        if start.endswith("-01")
        and dims != ("date",)
        and dims != ("page", "query")
        and start in ("2026-09-01", "2026-08-01")
    ]


@pytest.mark.anyio
async def test_search_console_stores_the_last_two_months_and_stops_once_they_are_final(
    factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_search_console_clock(monkeypatch, FIRST)
    fake = FakeSearchConsoleAdapter(
        properties=[DiscoveredSearchProperty("sc-domain:example.com", "domain", "owner")],
        summary_rows=[SearchAnalyticsRow((), 1, 10, 0.1, 5.0)],
        summary_by_start={
            "2026-09-01": [SearchAnalyticsRow((), 120, 3000, 0.04, 8.4)],
            "2026-08-01": [SearchAnalyticsRow((), 100, 2500, 0.04, 9.0)],
        },
        query_by_start={"2026-09-01": [SearchAnalyticsRow(("pizza",), 60, 1000, 0.06, 3.0)]},
        page_by_start={
            "2026-09-01": [SearchAnalyticsRow(("https://example.com/",), 70, 900, 0.07, 4.0)]
        },
    )
    async with factory.begin() as session:
        org = await make_sc_organization(session)
        settings = make_sc_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        website = await make_sc_website(session, org.id, "https://example.com/")
        service = SearchConsoleService(adapter=fake)
        prop = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id="sc-domain:example.com",
            property_type="domain",
            actor_id=None,
            correlation_id="map",
        )

        async def sync() -> None:
            await service.sync_observations(
                SharedSessionScope(session),
                settings,
                org.id,
                prop.id,
                actor_id=None,
                correlation_id="sync",
            )

        async def months() -> dict[tuple[str, str], SEOSearchObservation]:
            rows = await session.scalars(
                select(SEOSearchObservation)
                .where(
                    SEOSearchObservation.search_property_id == prop.id,
                    SEOSearchObservation.dimensions["observation_type"].astext.in_(
                        (MONTH_SITE_SUMMARY, MONTH_TOP_QUERY, MONTH_TOP_PAGE)
                    ),
                )
                # The upsert is a core statement: re-read what it wrote.
                .execution_options(populate_existing=True)
            )
            return {
                (r.date_start.date().isoformat(), str(r.dimensions["observation_type"])): r
                for r in rows
            }

        await sync()
        stored = await months()
        sept = stored[("2026-09-01", MONTH_SITE_SUMMARY)]
        august = stored[("2026-08-01", MONTH_SITE_SUMMARY)]
        # The whole month, exactly: September 1 to September 30, never a rolling window.
        assert (sept.date_start, sept.date_end) == calendar_month_window(
            datetime(2026, 9, 1).date()
        )
        assert (sept.clicks, sept.impressions) == (120, 3000) and (
            august.clicks,
            august.impressions,
        ) == (100, 2500)
        # Google had not settled September's last days yet; August is final.
        assert sept.partial is True and august.partial is False
        assert stored[("2026-09-01", MONTH_TOP_QUERY)].query == "pizza"
        assert stored[("2026-09-01", MONTH_TOP_PAGE)].dimensions["page"] == "https://example.com/"
        assert {c[0] for c in month_calls(fake)} == {"2026-09-01", "2026-08-01"}

        _freeze_search_console_clock(monkeypatch, THIRD)
        fake.query_calls.clear()
        await sync()
        assert {c[0] for c in month_calls(fake)} == {"2026-09-01"}  # only the unsettled month
        again = await months()
        assert again[("2026-09-01", MONTH_SITE_SUMMARY)].partial is False
        assert len(again) == len(stored)  # updated in place, nothing duplicated

        _freeze_search_console_clock(monkeypatch, FOURTH)
        fake.query_calls.clear()
        await sync()
        assert month_calls(fake) == []  # both months are final: nothing more to ask Google

        # The rolling windows never saw a month row, and the months never changed a rolling row.
        rolling = await session.scalars(
            select(SEOSearchObservation).where(
                SEOSearchObservation.search_property_id == prop.id,
                SEOSearchObservation.dimensions["observation_type"].astext == "site_summary",
            )
        )
        assert all((r.date_end - r.date_start).days in (7, 28, 90) for r in rolling)


@pytest.mark.anyio
async def test_a_failed_month_never_fails_the_rolling_windows(
    factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_search_console_clock(monkeypatch, FIRST)
    fake = FakeSearchConsoleAdapter(
        properties=[DiscoveredSearchProperty("sc-domain:example.com", "domain", "owner")],
        summary_rows=[SearchAnalyticsRow((), 1, 10, 0.1, 5.0)],
        fail_on_start={"2026-09-01"},
    )
    async with factory.begin() as session:
        org = await make_sc_organization(session)
        settings = make_sc_settings()
        await make_connected_google_connection(
            session,
            settings,
            org.id,
            http_handler=token_handler("https://www.googleapis.com/auth/webmasters.readonly"),
        )
        website = await make_sc_website(session, org.id, "https://example.com/")
        service = SearchConsoleService(adapter=fake)
        prop = await service.map_property(
            session,
            settings,
            org.id,
            website.id,
            external_property_id="sc-domain:example.com",
            property_type="domain",
            actor_id=None,
            correlation_id="map",
        )
        result = await service.sync_observations(
            SharedSessionScope(session),
            settings,
            org.id,
            prop.id,
            actor_id=None,
            correlation_id="sync",
        )
        stored = {
            r.date_start.date().isoformat()
            for r in await session.scalars(
                select(SEOSearchObservation).where(
                    SEOSearchObservation.dimensions["observation_type"].astext == MONTH_SITE_SUMMARY
                )
            )
        }

    assert result["periods_synced"] == [7, 28, 90]
    assert stored == {"2026-08-01"}  # September failed and will be tried again; August stored


class MonthAnalyticsAdapter(PageFakeAnalyticsAdapter):
    """Serves organic sessions per calendar month and records which windows were asked for."""

    def __init__(self, sessions: dict[str, list[int]]) -> None:
        super().__init__()
        self.sessions = sessions
        self.asked: list[str] = []

    async def run_organic_page_report(
        self,
        access_token: str,
        property_number: str,
        *,
        start_date: str,
        end_date: str,
        hostname: str,
    ) -> list[AnalyticsReportRow]:
        self.asked.append(start_date)
        return [
            AnalyticsReportRow(
                {"sessions": count, "totalUsers": 1, "keyEvents": 0},
                {
                    "landingPagePlusQueryString": f"/p{index}",
                    "hostName": "example.com",
                    "sessionDefaultChannelGroup": "Organic Search",
                },
            )
            for index, count in enumerate(self.sessions.get(start_date, []))
        ]


@pytest.mark.anyio
async def test_analytics_stores_one_organic_total_per_month_including_a_real_zero(
    factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_analytics_clock(monkeypatch, FIRST)
    adapter = MonthAnalyticsAdapter({"2026-09-01": [500, 400], "2026-08-01": []})
    async with factory.begin() as session:
        org = await make_organization(session)
        settings = make_settings()
        await make_connected_connection(
            session, settings, org.id, "https://www.googleapis.com/auth/analytics.readonly"
        )
        website = await make_website(session, org.id, "https://example.com/")
        await make_seo_page(session, org.id, website.id)
        service = AnalyticsService(adapter=adapter)
        prop = await service.map_property(
            session,
            settings,
            org.id,
            external_property_id="properties/123",
            property_number="123",
            display_name="Example",
            website_id=website.id,
            actor_id=None,
            correlation_id="map",
        )

        async def sync() -> None:
            await service.sync_metrics(
                SharedSessionScope(session),
                settings,
                org.id,
                prop.id,
                actor_id=None,
                correlation_id="sync",
            )

        async def totals() -> dict[str, MetricObservation]:
            rows = await session.scalars(
                select(MetricObservation)
                .where(
                    MetricObservation.organization_id == org.id,
                    MetricObservation.dimensions["observation_type"].astext
                    == "organic_month_total",
                )
                .execution_options(populate_existing=True)
            )
            return {r.period_start.date().isoformat(): r for r in rows}

        await sync()
        stored = await totals()
        # September: the sum over landing pages. August: Google returned no rows, a real zero.
        assert (
            stored["2026-09-01"].value == Decimal(900)
            and stored["2026-09-01"].quality_state == "valid"
        )
        assert (
            stored["2026-08-01"].value == Decimal(0)
            and stored["2026-08-01"].quality_state == "zero"
        )
        assert {"2026-09-01", "2026-08-01"} <= set(adapter.asked)

        adapter.asked.clear()
        await sync()
        # Both months are final, so the next sync does not ask for them again.
        assert "2026-09-01" not in adapter.asked and "2026-08-01" not in adapter.asked
        assert len(await totals()) == 2
