"""Search Console months before Google's first data are "no data yet", never a measured zero."""

from __future__ import annotations

from datetime import date

import pytest

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
    # April has no data: the comparison is May and June, 3,149 clicks over two months.
    assert clicks.compared_as is ComparedAs.MONTHLY_AVERAGE
    assert clicks.compared.value == 1574 and clicks.compared.months_covered == 2
    assert clicks.current_monthly_average == 1837
    assert clicks.change_percent == 16.7  # not +75% from setting 5,512 against two months
    note = next(n for n in result.notes if n.code is NoteCode.SEARCH_CONSOLE_COMPARED_AS_AVERAGE)
    assert note.covered_months == [MAY, JUNE] and note.missing_months == [APRIL]
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
    assert series.compared[0].value is None
    headline = next(h for h in result.headlines if h.count and h.count.change_percent == 16.7)
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


def spec() -> ComparisonSpec:
    return ComparisonSpec()
