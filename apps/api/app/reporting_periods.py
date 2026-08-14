"""Canonical reporting-period math shared across GA4 and Search Console.

Google Analytics Data API and Search Console Search Analytics both use
INCLUSIVE startDate/endDate semantics. This module guarantees:

- ``days`` means exactly that many provider calendar dates
- Comparison period has exactly the same number of dates
- Comparison window ends before the current window begins (zero overlap)
- Tail-exclusion days are applied before computing boundaries
- Internal representation is half-open [start, end) where end is the midnight
  AFTER the last included day — this matches the existing MetricObservation
  and SEOSearchObservation persistence model
"""

from datetime import UTC, datetime, timedelta

GA4_SYNC_TAIL_EXCLUSION_DAYS = 1
GSC_SYNC_TAIL_EXCLUSION_DAYS = 2
VALID_REPORTING_PERIODS: tuple[int, ...] = (7, 28, 90)


def _days_before(date: datetime, days: int) -> datetime:
    """Return a date `days` calendar days before `date` at midnight UTC."""
    target = date.date() - timedelta(days=days)
    return datetime(target.year, target.month, target.day, tzinfo=UTC)


def _at_midnight(date_val: datetime) -> datetime:
    """Return the given datetime's date at midnight UTC."""
    d = date_val.date()
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def reporting_window(
    now: datetime, days: int, tail_exclusion_days: int
) -> tuple[datetime, datetime]:
    """Return a half-open window [start, end) covering exactly `days` calendar dates.

    ``end`` is midnight on the day AFTER the last included date (half-open).

    With ``tail_exclusion_days=1`` and ``days=28`` on 2026-08-13:
    last_data_date = Aug 12, first_data_date = Aug 12 - 27 = Jul 16.
    Returns (Jul 16 00:00, Aug 13 00:00) covering 28 dates: Jul 16 – Aug 12.
    """
    last_data_date = (now - timedelta(days=tail_exclusion_days)).date()
    last = datetime(last_data_date.year, last_data_date.month, last_data_date.day, tzinfo=UTC)
    # end is midnight AFTER the last included date
    end = last + timedelta(days=1)
    # start is `days` days before end (so we include exactly `days` dates)
    start = end - timedelta(days=days)
    return start, end


def comparison_window(current_start: datetime, days: int) -> tuple[datetime, datetime]:
    """Return the prior period of exactly `days` dates ending before current_start.

    The comparison window has zero overlap with the current window.
    """
    comp_end = current_start
    comp_start = comp_end - timedelta(days=days)
    return comp_start, comp_end


def provider_start_date(window_start: datetime) -> str:
    """Format the first date as an inclusive YYYY-MM-DD for provider APIs."""
    return window_start.strftime("%Y-%m-%d")


def provider_end_date(window_end: datetime) -> str:
    """Format the last included date as YYYY-MM-DD for provider APIs.

    Since our internal representation is half-open [start, end) where end is
    midnight after the last included day, the inclusive end date is end - 1 day.
    """
    last = window_end - timedelta(days=1)
    return last.strftime("%Y-%m-%d")


def format_range_label(
    window_start: datetime, window_end: datetime, days: int
) -> dict[str, object]:
    """Format the window as a range object for API responses."""
    return {
        "start": provider_start_date(window_start),
        "end": provider_end_date(window_end),
        "days": days,
    }
