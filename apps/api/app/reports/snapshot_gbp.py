"""The Business Profile sections of a report, built from stored sync rows.

Everything comes from ``read_performance``; no provider is called and no table is read a second
way. The period is read once with its comparison and the same months a year earlier, and once
more per location when the client has several.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.gbp.performance_enums import (
    ACTION_METRICS,
    IMPRESSION_METRICS,
    GBPPerformanceAvailability,
    GBPPerformanceMetric,
    GBPPerformanceSyncStatus,
)
from apps.api.app.products.gbp.performance_read import (
    NOT_CONNECTED_TOTAL,
    DateRange,
    MonthlySums,
    PerformancePeriod,
    PerformanceRead,
    RangeWindows,
    Total,
    read_performance,
)
from apps.api.app.reports.contracts import (
    Availability,
    ComparisonBasis,
    NoteCode,
    ReportActionRow,
    ReportComparison,
    ReportCountComparison,
    ReportDailyPoint,
    ReportDailySeries,
    ReportDataNote,
    ReportGbpSection,
    ReportLocationRow,
    ReportMonthlySeries,
    ReportMonthPoint,
    ReportPeriod,
    ReportProfileActions,
    ReportProfileViews,
    ReportRange,
    ReportSearchTerm,
    ReportSearchTerms,
    ReportSourceRow,
    ReportSplit,
    ReportSplitPart,
    SeriesKey,
    SplitKey,
    UnavailableReason,
    note,
)
from apps.api.app.reports.figures import (
    Basis,
    combine,
    count_figure,
    rate_comparison,
    rate_figure,
    total_comparison,
)

SEARCH_TERMS_KEPT = 50
OPTIONAL_METRICS: tuple[GBPPerformanceMetric, ...] = (
    GBPPerformanceMetric.BUSINESS_CONVERSATIONS,
    GBPPerformanceMetric.BUSINESS_BOOKINGS,
    GBPPerformanceMetric.BUSINESS_FOOD_ORDERS,
    GBPPerformanceMetric.BUSINESS_FOOD_MENU_CLICKS,
)
_MAPS = (
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_DESKTOP_MAPS,
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_MAPS,
)
_SEARCH = (
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_DESKTOP_SEARCH,
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_SEARCH,
)
_DESKTOP = (
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_DESKTOP_MAPS,
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_DESKTOP_SEARCH,
)
_MOBILE = (
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_MAPS,
    GBPPerformanceMetric.BUSINESS_IMPRESSIONS_MOBILE_SEARCH,
)


@dataclass(frozen=True, slots=True)
class MappedLocation:
    """A reportable platform location and the Business Profile location mapped to it, if any."""

    location_id: UUID
    name: str
    gbp_location_id: UUID | None


@dataclass(frozen=True, slots=True)
class GbpResult:
    section: ReportGbpSection
    notes: list[ReportDataNote]
    # Whether the period's profile views are fully synced; readiness reads this.
    views_availability: GBPPerformanceAvailability
    series: list[ReportMonthlySeries]
    last_synced: date | None


def month_end(month: date) -> date:
    return month.replace(day=calendar.monthrange(month.year, month.month)[1])


def window_of(period: ReportPeriod) -> DateRange:
    """The days of a period of whole months."""
    return DateRange(period.start_month, month_end(period.end_month))


def range_windows(period: ReportPeriod, comparison: ReportComparison) -> RangeWindows:
    current = window_of(period)
    compared = window_of(comparison.compared)
    if comparison.basis is ComparisonBasis.PREVIOUS_PERIOD and period.span == 1:
        # A single month keeps its established comparison: the same number of days of the month
        # before, never past its end (a 31-day month meets all of a 28-day February).
        compared = DateRange(
            compared.start,
            min(compared.start + timedelta(days=current.days - 1), compared.end),
        )
    return RangeWindows(
        current=current,
        compared=compared,
        year_ago=window_of(comparison.year_ago) if comparison.year_ago else None,
        months=tuple(period.months),
    )


def basis_of(period: ReportPeriod, comparison: ReportComparison) -> Basis:
    return Basis(comparison.compared_as, period.span, comparison.compared.span)


def _range(window: DateRange) -> ReportRange:
    return ReportRange(start=window.start, end=window.end, days=window.days)


def _total(read: PerformanceRead, metric: GBPPerformanceMetric) -> Total:
    return read.metrics[metric].current


def _compared(read: PerformanceRead, metric: GBPPerformanceMetric) -> Total:
    return read.metrics[metric].previous


def _sum(
    read: PerformanceRead, metrics: Sequence[GBPPerformanceMetric], *, compared: bool
) -> Total:
    pick = _compared if compared else _total
    return combine([pick(read, metric) for metric in metrics])


def _split(
    read: PerformanceRead,
    first: tuple[SplitKey, Sequence[GBPPerformanceMetric]],
    second: tuple[SplitKey, Sequence[GBPPerformanceMetric]],
) -> ReportSplit:
    totals = [(key, _sum(read, metrics, compared=False)) for key, metrics in (first, second)]
    whole = combine([total for _, total in totals])
    complete = all(
        total.availability is GBPPerformanceAvailability.AVAILABLE for _, total in totals
    )
    parts: list[ReportSplitPart] = []
    for key, total in totals:
        share = (
            round((total.value or 0) / whole.value * 100, 1) if complete and whole.value else None
        )
        parts.append(ReportSplitPart(key=key, figure=count_figure(total), share_percent=share))
    return ReportSplit(parts=parts)


def _year_total(read: PerformanceRead, metric: GBPPerformanceMetric) -> Total | None:
    return read.year_ago.metrics[metric] if read.year_ago else None


def _year_sum(read: PerformanceRead, metrics: Sequence[GBPPerformanceMetric]) -> Total | None:
    return combine([read.year_ago.metrics[metric] for metric in metrics]) if read.year_ago else None


def _views(read: PerformanceRead, basis: Basis) -> ReportCountComparison:
    return total_comparison(
        read.profile_views.current,
        read.profile_views.previous,
        read.year_ago.profile_views if read.year_ago else None,
        basis,
    )


def _optional_row(
    read: PerformanceRead, metric: GBPPerformanceMetric, basis: Basis
) -> tuple[ReportActionRow, ReportDataNote | None] | None:
    """A row for an optional figure, only when this period or the comparison has a nonzero total.

    Google stops reporting some of these (bookings, conversations, food orders). A stored zero
    after a period with some is more likely a change in what Google reports than lower demand,
    so it is not a headline and its change is "not comparable".
    """
    current, compared = _total(read, metric), _compared(read, metric)
    if not ((current.value or 0) > 0 or (compared.value or 0) > 0):
        return None
    comparison = total_comparison(
        current, compared, _year_total(read, metric), basis, optional=True
    )
    if (current.value or 0) == 0:
        # Not reported now: no change is drawn, and the comparison's own figure explains why.
        comparison = comparison.model_copy(update={"change": None, "change_percent": None})
        return (
            ReportActionRow(
                metric=metric,
                comparison=comparison,
                reported=True,
                comparable=False,
                note=NoteCode.OPTIONAL_FIGURE_NOT_REPORTED,
            ),
            note(NoteCode.OPTIONAL_FIGURE_NOT_REPORTED, count=compared.value, metric=metric),
        )
    return ReportActionRow(metric=metric, comparison=comparison, reported=True), None


def _actions(
    read: PerformanceRead, basis: Basis
) -> tuple[ReportProfileActions, list[ReportDataNote]]:
    current = _sum(read, ACTION_METRICS, compared=False)
    compared = _sum(read, ACTION_METRICS, compared=True)
    year_actions = _year_sum(read, ACTION_METRICS)
    year_views = read.year_ago.profile_views if read.year_ago else None
    year_rate = rate_figure(year_actions, year_views) if year_actions and year_views else None
    rows = [
        ReportActionRow(
            metric=metric,
            comparison=total_comparison(
                _total(read, metric), _compared(read, metric), _year_total(read, metric), basis
            ),
            reported=count_figure(_total(read, metric)).availability
            is not Availability.UNAVAILABLE,
        )
        for metric in ACTION_METRICS
    ]
    optional: list[ReportActionRow] = []
    notes: list[ReportDataNote] = []
    for metric in OPTIONAL_METRICS:
        found = _optional_row(read, metric, basis)
        if found is None:
            continue
        optional.append(found[0])
        if found[1] is not None:
            notes.append(found[1])
    return (
        ReportProfileActions(
            total=total_comparison(current, compared, year_actions, basis),
            action_rate=rate_comparison(
                rate_figure(current, read.profile_views.current),
                rate_figure(compared, read.profile_views.previous),
                year_rate,
            ),
            actions=rows,
            optional=optional,
        ),
        notes,
    )


def _daily(read: PerformanceRead, window: DateRange) -> ReportDailySeries:
    days = [window.start + timedelta(days=offset) for offset in range(window.days)]
    points = [
        ReportDailyPoint(day=point.day, views=point.impressions, actions=point.actions)
        for point in read.series
        if window.start <= point.day <= window.end
    ]
    synced = {point.day for point in points}
    return ReportDailySeries(
        availability=(
            Availability.UNAVAILABLE
            if not synced
            else Availability.AVAILABLE
            if len(synced) == len(days)
            else Availability.PARTIAL
        ),
        days_expected=len(days),
        days_synced=len(synced),
        missing_days=[day for day in days if day not in synced],
        points=points,
    )


def _search_terms(read: PerformanceRead) -> ReportSearchTerms:
    terms = read.search_terms
    if terms.availability is not GBPPerformanceAvailability.AVAILABLE:
        reason = {
            GBPPerformanceAvailability.NOT_CONNECTED: UnavailableReason.NOT_CONNECTED,
            GBPPerformanceAvailability.NOT_SYNCED: UnavailableReason.NOT_SYNCED,
        }.get(terms.availability, UnavailableReason.NO_DATA)
        return ReportSearchTerms(availability=Availability.UNAVAILABLE, reason=reason, terms=[])
    whole = terms.months_covered == terms.months_expected
    return ReportSearchTerms(
        availability=Availability.AVAILABLE if whole else Availability.PARTIAL,
        terms=[
            ReportSearchTerm(
                keyword=term.keyword,
                value=term.value,
                below_threshold=term.below_threshold,
                is_exact=term.is_exact,
            )
            for term in terms.terms
        ],
        total_terms=terms.total_terms,
        months_covered=terms.months_covered,
        months_expected=terms.months_expected,
    )


def _location_row(
    location: MappedLocation, read: PerformanceRead | None, basis: Basis
) -> ReportLocationRow:
    if read is None:
        missing = total_comparison(
            NOT_CONNECTED_TOTAL, NOT_CONNECTED_TOTAL, None, basis, with_year=False
        )
        return ReportLocationRow(
            location_id=location.location_id,
            name=location.name,
            mapped=False,
            profile_views=missing,
            calls=missing,
            website_clicks=missing,
            direction_requests=missing,
        )

    def one(metric: GBPPerformanceMetric) -> ReportCountComparison:
        comparison = read.metrics[metric]
        return total_comparison(
            comparison.current, comparison.previous, None, basis, with_year=False
        )

    return ReportLocationRow(
        location_id=location.location_id,
        name=location.name,
        mapped=True,
        profile_views=total_comparison(
            read.profile_views.current, read.profile_views.previous, None, basis, with_year=False
        ),
        calls=one(GBPPerformanceMetric.CALL_CLICKS),
        website_clicks=one(GBPPerformanceMetric.WEBSITE_CLICKS),
        direction_requests=one(GBPPerformanceMetric.BUSINESS_DIRECTION_REQUESTS),
    )


def _point(
    month: date, sums: MonthlySums, metrics: Sequence[GBPPerformanceMetric], locations: int
) -> ReportMonthPoint:
    """One month of a figure: partial when some of its location-days were not synced."""
    stored = sums.get(month, {})
    rows = sum(stored.get(metric, (0, 0))[1] for metric in metrics)
    if not rows:
        return ReportMonthPoint(month=month, availability=Availability.UNAVAILABLE)
    expected = month_end(month).day * locations * len(metrics)
    return ReportMonthPoint(
        month=month,
        availability=Availability.AVAILABLE if rows >= expected else Availability.PARTIAL,
        value=sum(stored.get(metric, (0, 0))[0] for metric in metrics),
    )


def _series(
    read: PerformanceRead, period: ReportPeriod, comparison: ReportComparison, locations: int
) -> list[ReportMonthlySeries]:
    groups: tuple[tuple[SeriesKey, Sequence[GBPPerformanceMetric]], ...] = (
        (SeriesKey.PROFILE_VIEWS, IMPRESSION_METRICS),
        (SeriesKey.PROFILE_ACTIONS, ACTION_METRICS),
        (SeriesKey.CALLS, (GBPPerformanceMetric.CALL_CLICKS,)),
        (SeriesKey.WEBSITE_CLICKS, (GBPPerformanceMetric.WEBSITE_CLICKS,)),
        (SeriesKey.DIRECTION_REQUESTS, (GBPPerformanceMetric.BUSINESS_DIRECTION_REQUESTS,)),
    )
    current = read.monthly or {}
    compared = read.compared_monthly or {}
    return [
        ReportMonthlySeries(
            key=key,
            period=[_point(month, current, metrics, locations) for month in period.months],
            compared=[
                _point(month, compared, metrics, locations) for month in comparison.compared.months
            ],
        )
        for key, metrics in groups
    ]


def _notes(
    read: PerformanceRead,
    locations: Sequence[MappedLocation],
    section: ReportGbpSection,
) -> list[ReportDataNote]:
    notes: list[ReportDataNote] = []
    views = read.profile_views.current
    mapped = [item for item in locations if item.gbp_location_id is not None]
    if not mapped:
        return [note(NoteCode.GBP_NOT_CONNECTED)]
    notes.extend(
        note(NoteCode.GBP_LOCATION_NOT_MAPPED, location_id=item.location_id)
        for item in locations
        if item.gbp_location_id is None
    )
    if views.value is None:
        notes.append(note(NoteCode.GBP_PERIOD_NOT_SYNCED))
    elif views.availability is GBPPerformanceAvailability.PARTIAL:
        missing = section.daily.days_expected - section.daily.days_synced
        notes.append(note(NoteCode.GBP_PERIOD_PARTIAL, count=missing or None))
    if (
        views.availability is not GBPPerformanceAvailability.AVAILABLE
        and read.source.last_status is GBPPerformanceSyncStatus.FAILED
    ):
        notes.append(note(NoteCode.GBP_SYNC_FAILED))
    if views.value is not None and section.search_terms.availability is Availability.UNAVAILABLE:
        notes.append(note(NoteCode.GBP_SEARCH_TERMS_UNAVAILABLE))
    compared = read.profile_views.previous
    if (
        views.value is not None
        and compared.availability is not GBPPerformanceAvailability.AVAILABLE
    ):
        notes.append(note(NoteCode.GBP_COMPARED_PERIOD_INCOMPLETE))
    if (
        views.value is not None
        and read.year_ago is not None
        and read.year_ago.profile_views.availability is not GBPPerformanceAvailability.AVAILABLE
    ):
        notes.append(note(NoteCode.GBP_YEAR_AGO_UNAVAILABLE))
    return notes


async def build_gbp(
    session: AsyncSession,
    organization_id: UUID,
    period: ReportPeriod,
    comparison: ReportComparison,
    locations: Sequence[MappedLocation],
    *,
    now: datetime,
) -> GbpResult:
    """The Business Profile half of the report for ``period`` across ``locations``."""
    gbp_ids = [item.gbp_location_id for item in locations if item.gbp_location_id is not None]
    windows = range_windows(period, comparison)
    basis = basis_of(period, comparison)
    read = await read_performance(
        session,
        organization_id,
        gbp_ids,
        PerformancePeriod.RANGE,
        now=now,
        search_term_limit=SEARCH_TERMS_KEPT,
        range_windows=windows,
    )
    rows: list[ReportLocationRow] = []
    if len(locations) > 1:
        for item in locations:
            single = (
                await read_performance(
                    session,
                    organization_id,
                    [item.gbp_location_id],
                    PerformancePeriod.RANGE,
                    now=now,
                    search_term_limit=0,
                    range_windows=RangeWindows(
                        windows.current, windows.compared, None, windows.months
                    ),
                )
                if item.gbp_location_id
                else None
            )
            rows.append(_location_row(item, single, basis))
    daily = _daily(read, windows.current)
    views = read.profile_views.current
    actions, optional_notes = _actions(read, basis)
    section = ReportGbpSection(
        availability=(
            Availability.UNAVAILABLE
            if views.value is None
            else Availability.AVAILABLE
            if views.availability is GBPPerformanceAvailability.AVAILABLE
            else Availability.PARTIAL
        ),
        reason=count_figure(views).reason,
        current_range=_range(windows.current),
        compared_range=_range(windows.compared),
        year_ago_range=_range(windows.year_ago) if windows.year_ago else None,
        through_date=max((point.day for point in daily.points), default=None),
        profile_views=ReportProfileViews(
            total=_views(read, basis),
            sources=[
                ReportSourceRow(
                    metric=metric,
                    comparison=total_comparison(
                        _total(read, metric),
                        _compared(read, metric),
                        _year_total(read, metric),
                        basis,
                    ),
                )
                for metric in IMPRESSION_METRICS
            ],
            maps_search=_split(read, (SplitKey.MAPS, _MAPS), (SplitKey.SEARCH, _SEARCH)),
            desktop_mobile=_split(read, (SplitKey.DESKTOP, _DESKTOP), (SplitKey.MOBILE, _MOBILE)),
        ),
        actions=actions,
        daily=daily,
        search_terms=_search_terms(read),
        locations=rows,
    )
    return GbpResult(
        section,
        [*_notes(read, locations, section), *optional_notes],
        views.availability,
        _series(read, period, comparison, max(len(gbp_ids), 1)),
        read.source.last_synced_at.date() if read.source.last_synced_at else None,
    )
