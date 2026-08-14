"""Canonical reporting-period math regression tests.

Proves exactly 7/28/90 provider calendar dates, non-overlapping comparison
windows, and correct provider-inclusive date translation.
"""

from datetime import UTC, datetime

from apps.api.app.reporting_periods import (
    GA4_SYNC_TAIL_EXCLUSION_DAYS,
    GSC_SYNC_TAIL_EXCLUSION_DAYS,
    comparison_window,
    format_range_label,
    provider_end_date,
    provider_start_date,
    reporting_window,
)


def _now() -> datetime:
    return datetime(2026, 8, 13, 15, 30, 0, tzinfo=UTC)


def _inclusive_date_count(start: datetime, end: datetime) -> int:
    """Count calendar dates in a half-open [start, end) window."""
    return (end - start).days


def test_7_day_ga4_window_has_exactly_7_dates() -> None:
    start, end = reporting_window(_now(), 7, GA4_SYNC_TAIL_EXCLUSION_DAYS)
    assert _inclusive_date_count(start, end) == 7
    # tail exclusion = 1 -> last data date is Aug 12; 7 dates = Aug 6..12
    assert provider_start_date(start) == "2026-08-06"
    assert provider_end_date(end) == "2026-08-12"


def test_28_day_ga4_window_has_exactly_28_dates() -> None:
    start, end = reporting_window(_now(), 28, GA4_SYNC_TAIL_EXCLUSION_DAYS)
    assert _inclusive_date_count(start, end) == 28
    assert provider_start_date(start) == "2026-07-16"
    assert provider_end_date(end) == "2026-08-12"


def test_90_day_ga4_window_has_exactly_90_dates() -> None:
    start, end = reporting_window(_now(), 90, GA4_SYNC_TAIL_EXCLUSION_DAYS)
    assert _inclusive_date_count(start, end) == 90
    assert provider_start_date(start) == "2026-05-15"
    assert provider_end_date(end) == "2026-08-12"


def test_7_day_gsc_window_has_exactly_7_dates() -> None:
    start, end = reporting_window(_now(), 7, GSC_SYNC_TAIL_EXCLUSION_DAYS)
    assert _inclusive_date_count(start, end) == 7
    # tail exclusion = 2 -> last data date is Aug 11; 7 dates = Aug 5..11
    assert provider_start_date(start) == "2026-08-05"
    assert provider_end_date(end) == "2026-08-11"


def test_28_day_gsc_window_has_exactly_28_dates() -> None:
    start, end = reporting_window(_now(), 28, GSC_SYNC_TAIL_EXCLUSION_DAYS)
    assert _inclusive_date_count(start, end) == 28


def test_90_day_gsc_window_has_exactly_90_dates() -> None:
    start, end = reporting_window(_now(), 90, GSC_SYNC_TAIL_EXCLUSION_DAYS)
    assert _inclusive_date_count(start, end) == 90


def test_comparison_window_has_equal_duration_and_no_overlap() -> None:
    for days in (7, 28, 90):
        current_start, current_end = reporting_window(_now(), days, GA4_SYNC_TAIL_EXCLUSION_DAYS)
        comp_start, comp_end = comparison_window(current_start, days)
        # Equal duration
        assert _inclusive_date_count(comp_start, comp_end) == days
        # No overlap: comparison ends exactly where current begins
        assert comp_end == current_start
        assert _inclusive_date_count(current_start, current_end) == days


def test_comparison_window_ends_before_current_window() -> None:
    current_start, _ = reporting_window(_now(), 28, GA4_SYNC_TAIL_EXCLUSION_DAYS)
    comp_start, comp_end = comparison_window(current_start, 28)
    assert comp_end <= current_start
    # The last comparison date is the day before the first current date
    assert provider_end_date(comp_end) != provider_start_date(current_start)


def test_format_range_label_matches_provider_dates() -> None:
    start, end = reporting_window(_now(), 28, GA4_SYNC_TAIL_EXCLUSION_DAYS)
    label = format_range_label(start, end, 28)
    assert label == {
        "start": "2026-07-16",
        "end": "2026-08-12",
        "days": 28,
    }


def test_previous_period_never_shares_calendar_date() -> None:
    """Current and previous provider date ranges must share zero dates."""
    import datetime as _dt

    for days in (7, 28, 90):
        current_start, current_end = reporting_window(_now(), days, GA4_SYNC_TAIL_EXCLUSION_DAYS)
        comp_start, comp_end = comparison_window(current_start, days)

        current_dates = {(current_start + _dt.timedelta(days=i)).date() for i in range(days)}
        comp_dates = {(comp_start + _dt.timedelta(days=i)).date() for i in range(days)}

        assert current_dates.isdisjoint(comp_dates)
