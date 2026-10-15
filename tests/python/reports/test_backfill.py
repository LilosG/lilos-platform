"""The one-time Search Console and GA4 month backfill: idempotent; failed months stay unsynced."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from insights.test_analytics import (
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
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.seo.models import SEOSearchObservation
from apps.api.app.products.seo.month_observations import MONTH_SITE_SUMMARY
from apps.api.app.products.seo.search_console_adapter import (
    DiscoveredSearchProperty,
    SearchAnalyticsRow,
)
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from reports.support import Factory
from reports.test_month_sync import MonthAnalyticsAdapter

pytestmark = pytest.mark.integration
# October 4th: every month through September is settled for both providers.
SETTLED = datetime(2026, 10, 4, 15, 0, tzinfo=UTC)
SIXTEEN = [
    f"{year}-{month:02d}-01"
    for year, month in [(2025, m) for m in range(6, 13)] + [(2026, m) for m in range(1, 10)]
]


def month_starts(fake: FakeSearchConsoleAdapter) -> set[str]:
    """Starts of the whole-month site summaries that were asked for."""
    return {start for _, start, _end, dims in fake.query_calls if dims == () and start in SIXTEEN}


@pytest.mark.anyio
async def test_search_console_backfills_sixteen_months_once_and_leaves_failures_unsynced(
    factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_search_console_clock(monkeypatch, SETTLED)
    fake = FakeSearchConsoleAdapter(
        properties=[DiscoveredSearchProperty("sc-domain:example.com", "domain", "owner")],
        summary_rows=[SearchAnalyticsRow((), 10, 100, 0.1, 5.0)],
        fail_on_start={"2026-03-01"},
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

        async def sync(*, backfill: bool) -> None:
            await service.sync_observations(
                SharedSessionScope(session),
                settings,
                org.id,
                prop.id,
                actor_id=None,
                correlation_id="sync",
                backfill_months=backfill,
            )

        async def stored() -> set[str]:
            rows = await session.scalars(
                select(SEOSearchObservation)
                .where(
                    SEOSearchObservation.search_property_id == prop.id,
                    SEOSearchObservation.dimensions["observation_type"].astext
                    == MONTH_SITE_SUMMARY,
                )
                .execution_options(populate_existing=True)
            )
            return {row.date_start.date().isoformat() for row in rows}

        # The regular sync keeps only the last 2 months.
        await sync(backfill=False)
        assert await stored() == {"2026-09-01", "2026-08-01"}

        fake.query_calls.clear()
        await sync(backfill=True)
        # Everything settled is asked for except what is already stored; March failed.
        assert month_starts(fake) == set(SIXTEEN) - {"2026-09-01", "2026-08-01"}
        assert await stored() == set(SIXTEEN) - {"2026-03-01"}  # a failed month stays unsynced

        # Again: only the failed month is asked for, and nothing is duplicated.
        fake._fail_on_start.clear()
        fake.query_calls.clear()
        await sync(backfill=True)
        assert month_starts(fake) == {"2026-03-01"}
        assert await stored() == set(SIXTEEN)
        count = len(list(await session.scalars(select(SEOSearchObservation.id))))
        fake.query_calls.clear()
        await sync(backfill=True)
        assert month_starts(fake) == set()
        assert len(list(await session.scalars(select(SEOSearchObservation.id)))) == count

        # And the regular sync is back to its 2-month cadence.
        fake.query_calls.clear()
        await sync(backfill=False)
        assert month_starts(fake) == set()


class FailingMonthAnalytics(MonthAnalyticsAdapter):
    def __init__(self, sessions: dict[str, list[int]], failing: set[str]) -> None:
        super().__init__(sessions)
        self.failing = failing

    async def run_organic_page_report(self, *args, start_date: str, **kwargs):  # type: ignore[no-untyped-def]
        if start_date in self.failing:
            self.asked.append(start_date)
            raise RuntimeError("provider failure")
        return await super().run_organic_page_report(*args, start_date=start_date, **kwargs)


@pytest.mark.anyio
async def test_analytics_backfills_organic_months_once_and_leaves_failures_unsynced(
    factory: Factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _freeze_analytics_clock(monkeypatch, SETTLED)
    adapter = FailingMonthAnalytics(
        dict.fromkeys(SIXTEEN, [30, 20]), failing={"2026-03-01", "2025-07-01"}
    )
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

        async def sync(*, backfill: bool) -> None:
            await service.sync_metrics(
                SharedSessionScope(session),
                settings,
                org.id,
                prop.id,
                actor_id=None,
                correlation_id="sync",
                backfill_months=backfill,
            )

        async def stored() -> dict[str, MetricObservation]:
            rows = await session.scalars(
                select(MetricObservation)
                .where(
                    MetricObservation.organization_id == org.id,
                    MetricObservation.dimensions["observation_type"].astext
                    == "organic_month_total",
                )
                .execution_options(populate_existing=True)
            )
            return {row.period_start.date().isoformat(): row for row in rows}

        await sync(backfill=False)
        assert set(await stored()) == {"2026-09-01", "2026-08-01"}

        adapter.asked.clear()
        await sync(backfill=True)
        months = await stored()
        assert set(months) == set(SIXTEEN) - {"2026-03-01", "2025-07-01"}
        assert all(row.value == 50 and row.quality_state == "valid" for row in months.values())

        adapter.failing.clear()
        adapter.asked.clear()
        await sync(backfill=True)
        assert {m for m in adapter.asked if m in SIXTEEN} == {"2026-03-01", "2025-07-01"}
        assert set(await stored()) == set(SIXTEEN)

        adapter.asked.clear()
        await sync(backfill=True)
        assert not [m for m in adapter.asked if m in SIXTEEN]  # idempotent: nothing left to ask
        assert len(await stored()) == len(SIXTEEN)
