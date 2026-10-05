"""Read side of the Business Profile performance sync: periods, totals, comparison, search terms.

Reads stored rows only; no provider call. A period with no rows is never reported as 0: the
availability says whether nothing was synced, the window had no data, or only part of it did.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.gbp.performance_enums import (
    IMPRESSION_METRICS,
    GBPPerformanceAvailability,
    GBPPerformanceMetric,
    GBPPerformanceSyncStatus,
)
from apps.api.app.products.gbp.performance_models import (
    GBPPerformanceDailyMetric,
    GBPPerformanceKeywordImpression,
    GBPPerformanceSyncRun,
)
from apps.api.app.products.gbp.performance_service import first_of_month, months_before

TOP_SEARCH_TERMS = 25
# The newest complete day: today's and yesterday's values are not final when Google serves them.
LAST_DAY_OFFSET = 1


class PerformancePeriod(StrEnum):
    LAST_7_DAYS = "7d"
    LAST_28_DAYS = "28d"
    LAST_90_DAYS = "90d"
    MONTH = "month"


_DAYS = {
    PerformancePeriod.LAST_7_DAYS: 7,
    PerformancePeriod.LAST_28_DAYS: 28,
    PerformancePeriod.LAST_90_DAYS: 90,
}


@dataclass(frozen=True, slots=True)
class DateRange:
    start: date
    end: date  # inclusive

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True, slots=True)
class PeriodWindows:
    current: DateRange
    previous: DateRange
    month: date | None  # the requested calendar month, for the month period


def period_windows(
    period: PerformancePeriod, *, today: date, month: date | None = None
) -> PeriodWindows:
    """The period and the one before it, of equal length, with no overlap.

    A calendar month that is still running is compared with the same number of days of the
    month before, so a half-finished month is never set against a whole one.
    """
    last_day = today - timedelta(days=LAST_DAY_OFFSET)
    if period is PerformancePeriod.MONTH:
        if month is None:
            raise ValueError("a month period needs a month")
        month = first_of_month(month)
        next_month = months_before(month, -1)
        end = min(next_month - timedelta(days=1), last_day)
        current = DateRange(month, max(end, month))
        previous_start = months_before(month, 1)
        previous = DateRange(previous_start, previous_start + timedelta(days=current.days - 1))
        return PeriodWindows(current, previous, month)
    days = _DAYS[period]
    current = DateRange(last_day - timedelta(days=days - 1), last_day)
    previous_end = current.start - timedelta(days=1)
    return PeriodWindows(
        current, DateRange(previous_end - timedelta(days=days - 1), previous_end), None
    )


@dataclass(frozen=True, slots=True)
class Total:
    availability: GBPPerformanceAvailability
    value: int | None
    days_covered: int
    days_expected: int


@dataclass(frozen=True, slots=True)
class MetricComparison:
    current: Total
    previous: Total
    change: int | None
    change_percent: float | None


@dataclass(frozen=True, slots=True)
class SearchTerm:
    keyword: str
    value: int | None  # sum of the exact counts Google gave; None when it gave none
    below_threshold: int | None  # sum of the "fewer than N" figures, when any location had one

    @property
    def is_exact(self) -> bool:
        return self.below_threshold is None


@dataclass(frozen=True, slots=True)
class SearchTerms:
    availability: GBPPerformanceAvailability
    month: date | None
    terms: list[SearchTerm]


@dataclass(frozen=True, slots=True)
class SourceState:
    last_synced_at: datetime | None
    last_status: GBPPerformanceSyncStatus | None
    last_failure_code: str | None


@dataclass(frozen=True, slots=True)
class PerformanceRead:
    windows: PeriodWindows
    availability: GBPPerformanceAvailability
    profile_views: MetricComparison
    metrics: dict[GBPPerformanceMetric, MetricComparison]
    search_terms: SearchTerms
    source: SourceState


def total_of(*, rows: int, expected: int, value: int, ever_synced: bool) -> Total:
    """Turn what is stored for a window into a number that says how far to trust it."""
    if rows == 0:
        state = (
            GBPPerformanceAvailability.NO_DATA
            if ever_synced
            else GBPPerformanceAvailability.NOT_SYNCED
        )
        return Total(state, None, 0, expected)
    state = (
        GBPPerformanceAvailability.AVAILABLE
        if rows >= expected
        else GBPPerformanceAvailability.PARTIAL
    )
    return Total(state, value, rows, expected)


def compare(current: Total, previous: Total) -> MetricComparison:
    usable = (GBPPerformanceAvailability.AVAILABLE, GBPPerformanceAvailability.PARTIAL)
    if (
        current.value is None
        or previous.value is None
        or current.availability not in usable
        or previous.availability not in usable
        # A half-synced side makes any difference meaningless.
        or current.availability is GBPPerformanceAvailability.PARTIAL
        or previous.availability is GBPPerformanceAvailability.PARTIAL
    ):
        return MetricComparison(current, previous, None, None)
    change = current.value - previous.value
    percent = round(change / previous.value * 100, 1) if previous.value else None
    return MetricComparison(current, previous, change, percent)


async def _sums(
    session: AsyncSession,
    organization_id: UUID,
    gbp_location_ids: Sequence[UUID],
    window: DateRange,
) -> dict[GBPPerformanceMetric, tuple[int, int]]:
    """Per metric: (sum of values, number of stored location-days) inside the window."""
    rows = await session.execute(
        select(
            GBPPerformanceDailyMetric.metric,
            func.coalesce(func.sum(GBPPerformanceDailyMetric.value), 0),
            func.count(),
        )
        .where(
            GBPPerformanceDailyMetric.organization_id == organization_id,
            GBPPerformanceDailyMetric.gbp_location_id.in_(gbp_location_ids),
            GBPPerformanceDailyMetric.metric_date >= window.start,
            GBPPerformanceDailyMetric.metric_date <= window.end,
        )
        .group_by(GBPPerformanceDailyMetric.metric)
    )
    return {GBPPerformanceMetric(metric): (int(total), int(count)) for metric, total, count in rows}


def _totals(
    sums: dict[GBPPerformanceMetric, tuple[int, int]],
    window: DateRange,
    locations: int,
    *,
    ever_synced: bool,
) -> tuple[Total, dict[GBPPerformanceMetric, Total]]:
    expected = window.days * locations
    per_metric = {
        metric: total_of(
            rows=sums.get(metric, (0, 0))[1],
            expected=expected,
            value=sums.get(metric, (0, 0))[0],
            ever_synced=ever_synced,
        )
        for metric in GBPPerformanceMetric
    }
    # Profile views are the four impression metrics together; each day of each must be present.
    views = total_of(
        rows=sum(sums.get(metric, (0, 0))[1] for metric in IMPRESSION_METRICS),
        expected=expected * len(IMPRESSION_METRICS),
        value=sum(sums.get(metric, (0, 0))[0] for metric in IMPRESSION_METRICS),
        ever_synced=ever_synced,
    )
    if views.value is not None:
        views = Total(
            views.availability,
            views.value,
            views.days_covered // len(IMPRESSION_METRICS),
            expected,
        )
    return views, per_metric


async def _search_terms(
    session: AsyncSession,
    organization_id: UUID,
    gbp_location_ids: Sequence[UUID],
    month: date | None,
    *,
    ever_synced: bool,
) -> SearchTerms:
    if month is None:
        latest = await session.scalar(
            select(func.max(GBPPerformanceKeywordImpression.month)).where(
                GBPPerformanceKeywordImpression.organization_id == organization_id,
                GBPPerformanceKeywordImpression.gbp_location_id.in_(gbp_location_ids),
            )
        )
        month = latest
    if month is None:
        state = (
            GBPPerformanceAvailability.NO_DATA
            if ever_synced
            else GBPPerformanceAvailability.NOT_SYNCED
        )
        return SearchTerms(state, None, [])
    rows = await session.execute(
        select(
            GBPPerformanceKeywordImpression.keyword,
            func.sum(GBPPerformanceKeywordImpression.value),
            func.sum(GBPPerformanceKeywordImpression.threshold),
        )
        .where(
            GBPPerformanceKeywordImpression.organization_id == organization_id,
            GBPPerformanceKeywordImpression.gbp_location_id.in_(gbp_location_ids),
            GBPPerformanceKeywordImpression.month == month,
        )
        .group_by(GBPPerformanceKeywordImpression.keyword)
    )
    terms = [
        SearchTerm(
            keyword,
            int(value) if value is not None else None,
            int(threshold) if threshold is not None else None,
        )
        for keyword, value, threshold in rows
    ]
    if not terms:
        state = (
            GBPPerformanceAvailability.NO_DATA
            if ever_synced
            else GBPPerformanceAvailability.NOT_SYNCED
        )
        return SearchTerms(state, month, [])
    # Exact counts first, biggest first; terms Google only bounded follow, by their bound.
    terms.sort(
        key=lambda t: (t.value is None, -(t.value or 0), -(t.below_threshold or 0), t.keyword)
    )
    return SearchTerms(GBPPerformanceAvailability.AVAILABLE, month, terms[:TOP_SEARCH_TERMS])


async def _source(
    session: AsyncSession, organization_id: UUID, gbp_location_ids: Sequence[UUID]
) -> tuple[SourceState, bool]:
    ok = (GBPPerformanceSyncStatus.SUCCEEDED.value, GBPPerformanceSyncStatus.PARTIAL.value)
    last_ok = await session.scalar(
        select(func.max(GBPPerformanceSyncRun.completed_at)).where(
            GBPPerformanceSyncRun.organization_id == organization_id,
            GBPPerformanceSyncRun.gbp_location_id.in_(gbp_location_ids),
            GBPPerformanceSyncRun.status.in_(ok),
        )
    )
    latest = (
        await session.execute(
            select(GBPPerformanceSyncRun.status, GBPPerformanceSyncRun.failure_code)
            .where(
                GBPPerformanceSyncRun.organization_id == organization_id,
                GBPPerformanceSyncRun.gbp_location_id.in_(gbp_location_ids),
                GBPPerformanceSyncRun.status != GBPPerformanceSyncStatus.RUNNING.value,
            )
            .order_by(GBPPerformanceSyncRun.started_at.desc())
            .limit(1)
        )
    ).first()
    status = GBPPerformanceSyncStatus(latest[0]) if latest else None
    return SourceState(last_ok, status, latest[1] if latest else None), last_ok is not None


NOT_CONNECTED_TOTAL = Total(GBPPerformanceAvailability.NOT_CONNECTED, None, 0, 0)


def not_connected(windows: PeriodWindows) -> PerformanceRead:
    """No mapped Business Profile location: every figure is unavailable, not zero."""
    unavailable = MetricComparison(NOT_CONNECTED_TOTAL, NOT_CONNECTED_TOTAL, None, None)
    return PerformanceRead(
        windows=windows,
        availability=GBPPerformanceAvailability.NOT_CONNECTED,
        profile_views=unavailable,
        metrics=dict.fromkeys(GBPPerformanceMetric, unavailable),
        search_terms=SearchTerms(GBPPerformanceAvailability.NOT_CONNECTED, None, []),
        source=SourceState(None, None, None),
    )


async def read_performance(
    session: AsyncSession,
    organization_id: UUID,
    gbp_location_ids: Sequence[UUID],
    period: PerformancePeriod,
    *,
    month: date | None = None,
    now: datetime | None = None,
) -> PerformanceRead:
    today = (now or datetime.now(UTC)).astimezone(UTC).date()
    windows = period_windows(period, today=today, month=month)
    if not gbp_location_ids:
        return not_connected(windows)
    source, ever_synced = await _source(session, organization_id, gbp_location_ids)
    locations = len(gbp_location_ids)
    current_views, current = _totals(
        await _sums(session, organization_id, gbp_location_ids, windows.current),
        windows.current,
        locations,
        ever_synced=ever_synced,
    )
    previous_views, previous = _totals(
        await _sums(session, organization_id, gbp_location_ids, windows.previous),
        windows.previous,
        locations,
        ever_synced=ever_synced,
    )
    terms = await _search_terms(
        session, organization_id, gbp_location_ids, windows.month, ever_synced=ever_synced
    )
    return PerformanceRead(
        windows=windows,
        availability=current_views.availability,
        profile_views=compare(current_views, previous_views),
        metrics={metric: compare(current[metric], previous[metric]) for metric in current},
        search_terms=terms,
        source=source,
    )
