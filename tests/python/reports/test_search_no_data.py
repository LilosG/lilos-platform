"""Search Console months before Google's first data are "no data yet", never a measured zero."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from apps.api.app.products.seo.models import SEOSearchProperty
from apps.api.app.reports.contracts import (
    Availability,
    ComparedAs,
    ComparisonSpec,
    NoteCode,
    ReportPeriod,
    SeriesKey,
    UnavailableReason,
)
from apps.api.app.reports.snapshot import build_snapshot
from reports.support import (
    OCTOBER_FIRST,
    Factory,
    connect_search_console,
    seed_org,
    store_metrics,
    store_search_month,
)

pytestmark = pytest.mark.integration
JULY_SEPTEMBER = ReportPeriod(start_month=date(2026, 7, 1), end_month=date(2026, 9, 1))
APRIL, MAY, JUNE = (date(2026, m, 1) for m in (4, 5, 6))


def months(start: date, end: date) -> list[date]:
    found, cursor = [], start
    while cursor <= end:
        found.append(cursor)
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)
    return found


async def seed_miss_bs(factory: Factory, *, august_clicks: int = 1850):  # type: ignore[no-untyped-def]
    """Miss B's: eleven zero months (June 2025 to April 2026), then data from May 2026."""
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, date(2026, 9, 1), 5)
    prop, website = await connect_search_console(factory, org)
    for month in months(date(2025, 6, 1), APRIL):
        await store_search_month(
            factory, org, prop, website, month,
            clicks=0, impressions=0, position=None, quality="zero",
        )  # fmt: skip
    for month, clicks in ((MAY, 1366), (JUNE, 1783), (date(2026, 7, 1), 1800)):
        await store_search_month(
            factory, org, prop, website, month, clicks=clicks, impressions=clicks * 20, position=9.0
        )
    if august_clicks:
        await store_search_month(
            factory, org, prop, website, date(2026, 8, 1),
            clicks=august_clicks, impressions=august_clicks * 20, position=9.0,
        )  # fmt: skip
    else:
        # Months after data started that Google reported as zero are measured zeros.
        await store_search_month(
            factory, org, prop, website, date(2026, 8, 1),
            clicks=0, impressions=0, position=None, quality="zero",
        )  # fmt: skip
    await store_search_month(
        factory, org, prop, website, date(2026, 9, 1), clicks=1862, impressions=37240, position=9.0
    )
    return org


@pytest.mark.anyio
async def test_months_before_the_first_data_compare_as_monthly_averages(factory: Factory) -> None:
    org = await seed_miss_bs(factory)

    async with factory() as session:
        result = await build_snapshot(session, org, JULY_SEPTEMBER, spec(), now=OCTOBER_FIRST)

    clicks = result.search_console.clicks
    assert clicks.current.value == 5512
    # April has no data and May is the first (partial) data month: the baseline is June alone.
    assert clicks.compared_as is ComparedAs.MONTHLY_AVERAGE
    assert clicks.compared.value == 1783 and clicks.compared.months_covered == 1
    assert clicks.current_monthly_average == 1837
    assert clicks.change_percent == 3.0  # 5,512 / 3 = 1,837.3 against June's 1,783
    note = next(n for n in result.notes if n.code is NoteCode.SEARCH_CONSOLE_COMPARED_AS_AVERAGE)
    assert note.covered_months == [JUNE] and note.missing_months == [APRIL, MAY]
    assert NoteCode.SEARCH_CONSOLE_COMPARED_PERIOD_UNAVAILABLE not in {n.code for n in result.notes}


@pytest.mark.anyio
async def test_year_ago_with_no_search_data_is_unavailable_not_zero(factory: Factory) -> None:
    org = await seed_miss_bs(factory)

    async with factory() as session:
        result = await build_snapshot(session, org, JULY_SEPTEMBER, spec(), now=OCTOBER_FIRST)

    year = result.search_console.clicks.year_ago
    assert year is not None and year.availability is Availability.UNAVAILABLE
    assert year.value is None and year.reason is UnavailableReason.NO_SEARCH_DATA_YET
    assert result.search_console.clicks.year_change is None
    assert result.search_console.clicks.year_change_percent is None


@pytest.mark.anyio
async def test_months_with_no_data_are_not_plotted_and_the_headline_uses_the_average(
    factory: Factory,
) -> None:
    org = await seed_miss_bs(factory)

    async with factory() as session:
        result = await build_snapshot(session, org, JULY_SEPTEMBER, spec(), now=OCTOBER_FIRST)

    series = next(s for s in result.monthly if s.key is SeriesKey.SEARCH_CLICKS)
    assert [(p.month, p.availability) for p in series.compared] == [
        (APRIL, Availability.UNAVAILABLE),
        (MAY, Availability.AVAILABLE),
        (JUNE, Availability.AVAILABLE),
    ]
    assert series.compared[0].value is None and series.compared[1].value == 1366
    headline = next(h for h in result.headlines if h.count and h.count.change_percent == 3.0)
    assert headline.count and headline.count.compared_as is ComparedAs.MONTHLY_AVERAGE


@pytest.mark.anyio
async def test_a_zero_after_data_started_is_a_real_zero(factory: Factory) -> None:
    org = await seed_miss_bs(factory, august_clicks=0)
    august = ReportPeriod(start_month=date(2026, 8, 1), end_month=date(2026, 8, 1))

    async with factory() as session:
        result = await build_snapshot(session, org, august, spec(), now=OCTOBER_FIRST)

    clicks = result.search_console.clicks.current
    assert clicks.value == 0 and clicks.availability is Availability.AVAILABLE


@pytest.mark.anyio
async def test_a_period_wholly_before_the_first_data_says_no_search_data_yet(
    factory: Factory,
) -> None:
    org = await seed_miss_bs(factory)
    early = ReportPeriod(start_month=date(2025, 7, 1), end_month=date(2025, 9, 1))

    async with factory() as session:
        result = await build_snapshot(session, org, early, spec(), now=OCTOBER_FIRST)

    assert result.search_console.availability is Availability.UNAVAILABLE
    assert result.search_console.reason is UnavailableReason.NO_SEARCH_DATA_YET
    assert result.search_console.clicks.current.value is None
    assert NoteCode.SEARCH_CONSOLE_NO_DATA_YET in {n.code for n in result.notes}
    assert NoteCode.SEARCH_CONSOLE_NOT_SYNCED not in {n.code for n in result.notes}


async def seed_partial_june(factory: Factory):  # type: ignore[no-untyped-def]
    """Property 3e512b31: June is the first month with impressions (37 clicks), then 700s."""
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, date(2026, 9, 1), 5)
    prop, website = await connect_search_console(factory, org)
    for month in months(date(2025, 6, 1), MAY):
        await store_search_month(
            factory, org, prop, website, month,
            clicks=0, impressions=0, position=None, quality="zero",
        )  # fmt: skip
    queries = {"plumber near me": (20, 400), "water heater repair": (17, 351)}
    await store_search_month(
        factory, org, prop, website, JUNE,
        clicks=37, impressions=751, position=9.0, queries=queries,
    )  # fmt: skip
    for month, clicks in (
        (date(2026, 7, 1), 707),
        (date(2026, 8, 1), 796),
        (date(2026, 9, 1), 667),
    ):
        await store_search_month(
            factory, org, prop, website, month,
            clicks=clicks, impressions=clicks * 20, position=9.0,
            queries={"plumber near me": (clicks // 2, clicks * 10)},
        )  # fmt: skip
    return org


def codes(result) -> set[NoteCode]:  # type: ignore[no-untyped-def]
    return {n.code for n in result.notes}


@pytest.mark.anyio
async def test_a_partial_first_month_is_never_the_only_baseline(factory: Factory) -> None:
    org = await seed_partial_june(factory)

    async with factory() as session:
        result = await build_snapshot(session, org, JULY_SEPTEMBER, spec(), now=OCTOBER_FIRST)

    clicks = result.search_console.clicks
    assert clicks.current.value == 2170
    assert clicks.compared.availability is Availability.UNAVAILABLE
    assert clicks.compared.reason is UnavailableReason.NO_SEARCH_DATA_YET
    assert clicks.change_percent is None and clicks.change is None
    assert NoteCode.SEARCH_CONSOLE_FIRST_MONTH_PARTIAL in codes(result)


@pytest.mark.anyio
async def test_a_period_with_the_first_month_keeps_its_clicks_and_gets_the_note(
    factory: Factory,
) -> None:
    org = await seed_partial_june(factory)
    june_september = ReportPeriod(start_month=JUNE, end_month=date(2026, 9, 1))

    async with factory() as session:
        result = await build_snapshot(session, org, june_september, spec(), now=OCTOBER_FIRST)

    assert result.search_console.clicks.current.value == 37 + 2170
    note = next(n for n in result.notes if n.code is NoteCode.SEARCH_CONSOLE_FIRST_MONTH_PARTIAL)
    assert note.month == JUNE
    series = next(s for s in result.monthly if s.key is SeriesKey.SEARCH_CLICKS)
    assert series.period[0].value == 37


@pytest.mark.anyio
async def test_a_period_clear_of_the_first_month_has_no_note(factory: Factory) -> None:
    org = await seed_miss_bs(factory)
    september = ReportPeriod(start_month=date(2026, 9, 1), end_month=date(2026, 9, 1))

    async with factory() as session:
        result = await build_snapshot(session, org, september, spec(), now=OCTOBER_FIRST)

    assert NoteCode.SEARCH_CONSOLE_FIRST_MONTH_PARTIAL not in codes(result)


@pytest.mark.anyio
async def test_year_ago_over_the_first_data_month_is_unavailable(factory: Factory) -> None:
    org = await seed_partial_june(factory)
    async with factory() as session:
        found = (await session.scalars(select(SEOSearchProperty))).one()
        prop, website = found.id, found.website_id
    assert website is not None
    await store_search_month(
        factory, org, prop, website, date(2027, 6, 1), clicks=800, impressions=16000, position=9.0
    )
    june_2027 = ReportPeriod(start_month=date(2027, 6, 1), end_month=date(2027, 6, 1))

    async with factory() as session:
        result = await build_snapshot(
            session, org, june_2027, spec(), now=datetime(2027, 7, 1, 12, tzinfo=UTC)
        )

    year = result.search_console.clicks.year_ago
    assert year is not None and year.value is None
    assert year.reason is UnavailableReason.NO_SEARCH_DATA_YET
    assert NoteCode.SEARCH_CONSOLE_FIRST_MONTH_PARTIAL in codes(result)


@pytest.mark.anyio
async def test_topics_and_gains_are_not_set_against_a_first_month_baseline(
    factory: Factory,
) -> None:
    org = await seed_partial_june(factory)
    july_september_vs_june = ComparisonSpec()

    async with factory() as session:
        result = await build_snapshot(
            session, org, ReportPeriod(start_month=date(2026, 7, 1), end_month=date(2026, 7, 1)),
            july_september_vs_june, now=OCTOBER_FIRST,
        )  # fmt: skip

    movement = result.search_movement
    assert movement is not None and movement.comparable is False
    assert all(q.before_clicks is None and q.before_position is None for q in movement.queries)
    assert result.search_console.top_queries
    assert all(q.compared_clicks is None for q in result.search_console.top_queries)


def spec() -> ComparisonSpec:
    return ComparisonSpec()
