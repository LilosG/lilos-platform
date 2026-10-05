"""Pure window arithmetic: backfill, re-sync, chunking, keyword months and comparison periods."""

from datetime import date

import pytest

from apps.api.app.products.gbp.performance_enums import (
    GBPPerformanceAvailability,
    GBPPerformanceSyncMode,
)
from apps.api.app.products.gbp.performance_read import (
    PerformancePeriod,
    Total,
    compare,
    period_windows,
    total_of,
)
from apps.api.app.products.gbp.performance_service import (
    day_chunks,
    keyword_months,
    months_before,
    plan_window,
)

TODAY = date(2026, 10, 5)


def test_months_before_clamps_to_the_shorter_month() -> None:
    assert months_before(date(2026, 10, 5), 18) == date(2025, 4, 5)
    assert months_before(date(2026, 8, 31), 6) == date(2026, 2, 28)
    assert months_before(date(2026, 1, 15), 1) == date(2025, 12, 15)
    assert months_before(date(2026, 12, 1), -1) == date(2027, 1, 1)


def test_the_first_run_backfills_and_later_runs_resync_ten_days() -> None:
    first = plan_window(TODAY, backfilled=False)
    later = plan_window(TODAY, backfilled=True)

    assert (first.mode, first.start, first.end) == (
        GBPPerformanceSyncMode.BACKFILL,
        date(2025, 4, 5),
        date(2026, 10, 4),
    )
    assert (later.mode, later.start, later.end) == (
        GBPPerformanceSyncMode.RESYNC,
        date(2026, 9, 25),
        date(2026, 10, 4),
    )
    assert (later.end - later.start).days + 1 == 10


def test_day_chunks_tile_the_range_without_gaps_or_overlap() -> None:
    chunks = day_chunks(date(2025, 4, 5), date(2026, 10, 4))

    assert chunks[0][0] == date(2025, 4, 5) and chunks[-1][1] == date(2026, 10, 4)
    assert all((end - start).days + 1 <= 186 for start, end in chunks)
    assert all(
        b[0].toordinal() == a[1].toordinal() + 1 for a, b in zip(chunks, chunks[1:], strict=False)
    )
    assert day_chunks(TODAY, TODAY) == [(TODAY, TODAY)]


def test_keyword_months_are_completed_months_only() -> None:
    backfill = keyword_months(plan_window(TODAY, backfilled=False), TODAY)
    resync = keyword_months(plan_window(TODAY, backfilled=True), TODAY)

    assert backfill[0] == date(2025, 4, 1) and backfill[-1] == date(2026, 9, 1)
    assert len(backfill) == 18
    assert resync == [date(2026, 8, 1), date(2026, 9, 1)]
    assert date(2026, 10, 1) not in backfill + resync


@pytest.mark.parametrize(("period", "days"), [("7d", 7), ("28d", 28), ("90d", 90)])
def test_rolling_periods_end_yesterday_and_compare_with_the_equal_period_before(
    period: str, days: int
) -> None:
    windows = period_windows(PerformancePeriod(period), today=TODAY)

    assert windows.current.end == date(2026, 10, 4)
    assert windows.current.days == windows.previous.days == days
    assert windows.previous.end.toordinal() == windows.current.start.toordinal() - 1


def test_a_running_month_is_compared_with_the_same_days_of_the_month_before() -> None:
    windows = period_windows(PerformancePeriod.MONTH, today=TODAY, month=date(2026, 10, 17))

    assert (windows.current.start, windows.current.end) == (date(2026, 10, 1), date(2026, 10, 4))
    assert (windows.previous.start, windows.previous.end) == (date(2026, 9, 1), date(2026, 9, 4))


def test_a_finished_month_is_compared_with_the_whole_month_before() -> None:
    windows = period_windows(PerformancePeriod.MONTH, today=TODAY, month=date(2026, 3, 9))

    assert (windows.current.start, windows.current.end) == (date(2026, 3, 1), date(2026, 3, 31))
    assert (windows.previous.start, windows.previous.end) == (date(2026, 2, 1), date(2026, 3, 3))


def test_totals_say_how_far_to_trust_them() -> None:
    assert total_of(rows=0, expected=28, value=0, ever_synced=False).availability is (
        GBPPerformanceAvailability.NOT_SYNCED
    )
    empty = total_of(rows=0, expected=28, value=0, ever_synced=True)
    assert (empty.availability, empty.value) == (GBPPerformanceAvailability.NO_DATA, None)
    partial = total_of(rows=20, expected=28, value=90, ever_synced=True)
    assert (partial.availability, partial.value) == (GBPPerformanceAvailability.PARTIAL, 90)
    full = total_of(rows=28, expected=28, value=0, ever_synced=True)
    assert (full.availability, full.value) == (GBPPerformanceAvailability.AVAILABLE, 0)


def test_comparison_needs_both_sides_complete_and_never_divides_by_zero() -> None:
    def available(value: int) -> Total:
        return Total(GBPPerformanceAvailability.AVAILABLE, value, 28, 28)

    up = compare(available(150), available(100))
    assert (up.change, up.change_percent) == (50, 50.0)
    from_zero = compare(available(5), available(0))
    assert (from_zero.change, from_zero.change_percent) == (5, None)
    partial = Total(GBPPerformanceAvailability.PARTIAL, 10, 10, 28)
    assert compare(partial, available(100)).change is None
    missing = Total(GBPPerformanceAvailability.NOT_SYNCED, None, 0, 28)
    assert compare(available(5), missing).change is None
