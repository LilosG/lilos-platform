"""The Business Profile sections of a monthly report, built from stored sync rows.

Everything comes from ``read_performance``; no provider is called and no table is read a second
way. The month is read three times at most: the month itself (with its previous month), the same
month a year earlier, and once per location when the client has several.
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
    PerformancePeriod,
    PerformanceRead,
    Total,
    read_performance,
)
from apps.api.app.products.gbp.performance_service import months_before
from apps.api.app.reports.contracts import (
    Availability,
    NoteCode,
    ReportActionRow,
    ReportCountComparison,
    ReportDailyPoint,
    ReportDailySeries,
    ReportDataNote,
    ReportGbpSection,
    ReportLocationRow,
    ReportProfileActions,
    ReportProfileViews,
    ReportRange,
    ReportSearchTerm,
    ReportSearchTerms,
    ReportSourceRow,
    ReportSplit,
    ReportSplitPart,
    SplitKey,
    UnavailableReason,
    note,
)
from apps.api.app.reports.figures import (
    combine,
    comparison_of,
    count_comparison,
    count_figure,
    rate_comparison,
    rate_figure,
)

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
    # Whether the month's profile views are fully synced; readiness reads this.
    views_availability: GBPPerformanceAvailability


def month_end(month: date) -> date:
    return month.replace(day=calendar.monthrange(month.year, month.month)[1])


def _range(start: date, end: date) -> ReportRange:
    return ReportRange(start=start, end=end, days=(end - start).days + 1)


def _total(read: PerformanceRead, metric: GBPPerformanceMetric) -> Total:
    return read.metrics[metric].current


def _previous(read: PerformanceRead, metric: GBPPerformanceMetric) -> Total:
    return read.metrics[metric].previous


def _sum(
    read: PerformanceRead, metrics: Sequence[GBPPerformanceMetric], *, previous: bool
) -> Total:
    pick = _previous if previous else _total
    return combine([pick(read, metric) for metric in metrics])


def _split(
    read: PerformanceRead,
    first: tuple[SplitKey, Sequence[GBPPerformanceMetric]],
    second: tuple[SplitKey, Sequence[GBPPerformanceMetric]],
) -> ReportSplit:
    totals = [(key, _sum(read, metrics, previous=False)) for key, metrics in (first, second)]
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


def _year_total(year: PerformanceRead | None, metric: GBPPerformanceMetric) -> Total | None:
    return year.metrics[metric].current if year else None


def _year_sum(
    year: PerformanceRead | None, metrics: Sequence[GBPPerformanceMetric]
) -> Total | None:
    return combine([year.metrics[metric].current for metric in metrics]) if year else None


def _views(read: PerformanceRead, year: PerformanceRead | None) -> ReportCountComparison:
    return count_comparison(
        read.profile_views.current,
        read.profile_views.previous,
        year.profile_views.current if year else None,
    )


def _actions(read: PerformanceRead, year: PerformanceRead | None) -> ReportProfileActions:
    current = _sum(read, ACTION_METRICS, previous=False)
    previous = _sum(read, ACTION_METRICS, previous=True)
    year_actions = _year_sum(year, ACTION_METRICS)
    views_current = read.profile_views.current
    views_previous = read.profile_views.previous
    views_year = year.profile_views.current if year else None
    year_rate = rate_figure(year_actions, views_year) if year_actions and views_year else None
    rows = [
        ReportActionRow(
            metric=metric,
            comparison=comparison_of(read.metrics[metric], _year_total(year, metric)),
            reported=count_figure(_total(read, metric)).availability
            is not Availability.UNAVAILABLE,
        )
        for metric in ACTION_METRICS
    ]
    optional: list[ReportActionRow] = []
    for metric in OPTIONAL_METRICS:
        comparison = comparison_of(read.metrics[metric], _year_total(year, metric), optional=True)
        # Only a metric the profile reports gets a tile; "not reported" is never drawn as 0.
        if comparison.current.availability is not Availability.UNAVAILABLE:
            optional.append(ReportActionRow(metric=metric, comparison=comparison, reported=True))
    return ReportProfileActions(
        total=count_comparison(current, previous, year_actions),
        action_rate=rate_comparison(
            rate_figure(current, views_current),
            rate_figure(previous, views_previous),
            year_rate,
        ),
        actions=rows,
        optional=optional,
    )


def _daily(read: PerformanceRead, month: date) -> ReportDailySeries:
    days = [month + timedelta(days=offset) for offset in range(month_end(month).day)]
    points = [
        ReportDailyPoint(day=point.day, views=point.impressions, actions=point.actions)
        for point in read.series
        if month <= point.day <= month_end(month)
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
    return ReportSearchTerms(
        availability=Availability.AVAILABLE,
        terms=[
            ReportSearchTerm(
                keyword=term.keyword,
                value=term.value,
                below_threshold=term.below_threshold,
                is_exact=term.is_exact,
            )
            for term in terms.terms
        ],
    )


def _location_row(location: MappedLocation, read: PerformanceRead | None) -> ReportLocationRow:
    if read is None:
        missing = count_comparison(NOT_CONNECTED_TOTAL, NOT_CONNECTED_TOTAL, None, with_year=False)
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
        return count_comparison(comparison.current, comparison.previous, None, with_year=False)

    return ReportLocationRow(
        location_id=location.location_id,
        name=location.name,
        mapped=True,
        profile_views=count_comparison(
            read.profile_views.current, read.profile_views.previous, None, with_year=False
        ),
        calls=one(GBPPerformanceMetric.CALL_CLICKS),
        website_clicks=one(GBPPerformanceMetric.WEBSITE_CLICKS),
        direction_requests=one(GBPPerformanceMetric.BUSINESS_DIRECTION_REQUESTS),
    )


def _notes(
    read: PerformanceRead,
    year: PerformanceRead | None,
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
        notes.append(note(NoteCode.GBP_MONTH_NOT_SYNCED))
    elif views.availability is GBPPerformanceAvailability.PARTIAL:
        notes.append(
            note(NoteCode.GBP_MONTH_PARTIAL, count=len(section.daily.missing_days) or None)
        )
    if (
        views.availability is not GBPPerformanceAvailability.AVAILABLE
        and read.source.last_status is GBPPerformanceSyncStatus.FAILED
    ):
        notes.append(note(NoteCode.GBP_SYNC_FAILED))
    if views.value is not None and section.search_terms.availability is Availability.UNAVAILABLE:
        notes.append(note(NoteCode.GBP_SEARCH_TERMS_UNAVAILABLE))
    previous = read.profile_views.previous
    if (
        views.value is not None
        and previous.availability is not GBPPerformanceAvailability.AVAILABLE
    ):
        notes.append(note(NoteCode.GBP_PREVIOUS_MONTH_INCOMPLETE))
    if views.value is not None and (
        year is None
        or year.profile_views.current.availability is not GBPPerformanceAvailability.AVAILABLE
    ):
        notes.append(note(NoteCode.GBP_YEAR_AGO_UNAVAILABLE))
    return notes


async def build_gbp(
    session: AsyncSession,
    organization_id: UUID,
    month: date,
    locations: Sequence[MappedLocation],
    *,
    now: datetime,
) -> GbpResult:
    """The Business Profile half of the report for ``month`` across ``locations``."""
    gbp_ids = [item.gbp_location_id for item in locations if item.gbp_location_id is not None]
    read = await read_performance(
        session,
        organization_id,
        gbp_ids,
        PerformancePeriod.MONTH,
        month=month,
        now=now,
        search_term_limit=None,
    )
    year_month = months_before(month, 12)
    year = (
        await read_performance(
            session, organization_id, gbp_ids, PerformancePeriod.MONTH, month=year_month, now=now
        )
        if gbp_ids
        else None
    )
    rows: list[ReportLocationRow] = []
    if len(locations) > 1:
        for item in locations:
            single = (
                await read_performance(
                    session,
                    organization_id,
                    [item.gbp_location_id],
                    PerformancePeriod.MONTH,
                    month=month,
                    now=now,
                )
                if item.gbp_location_id
                else None
            )
            rows.append(_location_row(item, single))
    series = _daily(read, month)
    views = read.profile_views.current
    section = ReportGbpSection(
        availability=(
            Availability.UNAVAILABLE
            if views.value is None
            else Availability.AVAILABLE
            if views.availability is GBPPerformanceAvailability.AVAILABLE
            else Availability.PARTIAL
        ),
        reason=count_figure(views).reason,
        current_range=_range(read.windows.current.start, read.windows.current.end),
        previous_range=_range(read.windows.previous.start, read.windows.previous.end),
        year_ago_range=_range(year_month, month_end(year_month)),
        through_date=max((point.day for point in series.points), default=None),
        profile_views=ReportProfileViews(
            total=_views(read, year),
            sources=[
                ReportSourceRow(
                    metric=metric,
                    comparison=comparison_of(read.metrics[metric], _year_total(year, metric)),
                )
                for metric in IMPRESSION_METRICS
            ],
            maps_search=_split(read, (SplitKey.MAPS, _MAPS), (SplitKey.SEARCH, _SEARCH)),
            desktop_mobile=_split(read, (SplitKey.DESKTOP, _DESKTOP), (SplitKey.MOBILE, _MOBILE)),
        ),
        actions=_actions(read, year),
        daily=series,
        search_terms=_search_terms(read),
        locations=rows,
    )
    return GbpResult(section, _notes(read, year, locations, section), views.availability)
