"""The Search Console and Analytics sections of a report, read from stored whole months.

Both come from whole calendar months stored by the syncs (``month_observations``). A rolling
28-day window is never substituted for a month. Months are summed across the period: clicks,
impressions and sessions add up, CTR is derived from the sums and the average position is
weighted by impressions. If any month of the period or of the comparison is not synced, or was
stored before the provider settled it, the figure is partial and says how many months it covers.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.insights.models import InsightSource, MetricDefinition, MetricObservation
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.analytics.month_observations import (
    ORGANIC_MONTH_TOTAL,
    ORGANIC_SESSIONS_KEY,
    PARTIAL_STATE,
)
from apps.api.app.products.seo.models import SEOSearchObservation, SEOSearchProperty
from apps.api.app.products.seo.month_observations import (
    MONTH_SITE_SUMMARY,
    MONTH_TOP_PAGE,
    MONTH_TOP_QUERY,
)
from apps.api.app.reporting_periods import (
    GSC_SYNC_TAIL_EXCLUSION_DAYS,
    calendar_month_window,
)
from apps.api.app.reports.contracts import (
    Availability,
    ComparedAs,
    NoteCode,
    ReportAnalyticsSection,
    ReportComparison,
    ReportCountComparison,
    ReportCountFigure,
    ReportDataNote,
    ReportMonthlySeries,
    ReportMovementQuery,
    ReportPeriod,
    ReportRateComparison,
    ReportRateFigure,
    ReportSearchConsoleSection,
    ReportSearchMovement,
    ReportSearchPageRow,
    ReportSearchQueryRow,
    SeriesKey,
    UnavailableReason,
    note,
)
from apps.api.app.reports.figures import (
    Basis,
    MonthValue,
    compare_counts,
    month_points,
    months_figure,
    rate_comparison,
    unavailable_count,
    unavailable_rate,
)

TOP_ROWS = 50
# A search needs this many impressions in a window to count as ranking there.
MOVEMENT_MIN_IMPRESSIONS = 20
MOVEMENT_ROWS = 400
PROVIDER_MAPPED = "mapped"
SEARCH_PROVIDER = "google_search_console"
ORGANIC_SESSIONS_VERSION = 1
_APOSTROPHES = re.compile(r"['‘’ʼ`]")
_PUNCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalize_text(text: str) -> str:
    """Lowercase, apostrophes removed, other punctuation made a space, spaces collapsed."""
    return " ".join(_PUNCTUATION.sub(" ", _APOSTROPHES.sub("", text.lower())).split())


def is_branded(query: str, brand_terms: Sequence[str]) -> bool:
    """A search is branded when it contains the organization's or a location's name."""
    text = normalize_text(query)
    return any(term and term in text for term in map(normalize_text, brand_terms))


@dataclass(frozen=True, slots=True)
class SearchResult:
    section: ReportSearchConsoleSection
    notes: list[ReportDataNote]
    series: list[ReportMonthlySeries]
    last_synced: date | None
    movement: ReportSearchMovement | None = None


@dataclass(frozen=True, slots=True)
class AnalyticsResult:
    section: ReportAnalyticsSection
    notes: list[ReportDataNote]
    series: list[ReportMonthlySeries]
    last_synced: date | None


def _no_counts(reason: UnavailableReason) -> ReportCountComparison:
    return ReportCountComparison(
        current=unavailable_count(reason), compared=unavailable_count(reason)
    )


def _no_rates(reason: UnavailableReason) -> ReportRateComparison:
    return ReportRateComparison(current=unavailable_rate(reason), compared=unavailable_rate(reason))


def _empty_series(
    keys: Sequence[SeriesKey], period: ReportPeriod, comparison: ReportComparison
) -> list[ReportMonthlySeries]:
    return [
        ReportMonthlySeries(
            key=key,
            period=month_points(period.months, []),
            compared=month_points(comparison.compared.months, []),
        )
        for key in keys
    ]


def _search_unavailable(reason: UnavailableReason) -> ReportSearchConsoleSection:
    return ReportSearchConsoleSection(
        availability=Availability.UNAVAILABLE,
        reason=reason,
        clicks=_no_counts(reason),
        impressions=_no_counts(reason),
        ctr_percent=_no_rates(reason),
        average_position=_no_rates(reason),
        top_queries=[],
        top_pages=[],
    )


def _window(months: Sequence[date]) -> tuple[object, object]:
    return calendar_month_window(months[0])[0], calendar_month_window(months[-1])[1]


async def _observations(
    session: AsyncSession, property_id: UUID, months: Sequence[date], kind: str
) -> list[SEOSearchObservation]:
    start, following = _window(months)
    rows = await session.scalars(
        select(SEOSearchObservation).where(
            SEOSearchObservation.search_property_id == property_id,
            SEOSearchObservation.date_start >= start,
            SEOSearchObservation.date_end <= following,
            SEOSearchObservation.dimensions["observation_type"].astext == kind,
            SEOSearchObservation.quality_status.in_(("valid", "zero")),
        )
    )
    return list(rows)


NO_DATA_STATUS = "zero"


async def _first_data_month(session: AsyncSession, property_id: UUID) -> date | None:
    """The first stored month in which Google reported any impressions, over the whole history."""
    first = await session.scalar(
        select(func.min(SEOSearchObservation.date_start)).where(
            SEOSearchObservation.search_property_id == property_id,
            SEOSearchObservation.dimensions["observation_type"].astext == MONTH_SITE_SUMMARY,
            SEOSearchObservation.quality_status.in_(("valid", "zero")),
            SEOSearchObservation.impressions > 0,
        )
    )
    return first.date() if first else None


@dataclass(slots=True)
class SearchMonths:
    """The stored site summaries of some months, summed the way the report needs them.

    ``no_data`` are months stored as zero before the property's first month with impressions:
    Google had no data yet, which is not a measured zero. They are in neither ``rows`` nor any
    sum, average or plotted point. ``gaps_ok`` lets a side whose only gaps are those months be
    set against another as a monthly average over the months that have data.
    """

    expected: list[date]
    rows: dict[date, SEOSearchObservation]
    no_data: list[date] = field(default_factory=list)
    gaps_ok: bool = False

    @property
    def present(self) -> list[date]:
        return [month for month in self.expected if month in self.rows]

    @property
    def complete(self) -> bool:
        return len(self.rows) == len(self.expected) and not any(
            row.partial for row in self.rows.values()
        )

    @property
    def gapped(self) -> bool:
        """Every month is settled data or no data yet, with at least one month of data."""
        return (
            bool(self.rows)
            and bool(self.no_data)
            and len(self.rows) + len(self.no_data) == len(self.expected)
            and not any(row.partial for row in self.rows.values())
        )

    @property
    def settled(self) -> bool:
        return self.complete or (self.gaps_ok and self.gapped)

    def values(self, attribute: str) -> list[MonthValue]:
        return [
            MonthValue(
                month,
                int(getattr(self.rows[month], attribute) or 0),
                bool(self.rows[month].partial),
            )
            for month in self.present
        ]

    def _figure(self, attribute: str) -> ReportCountFigure:
        values = self.values(attribute)
        if not values:
            return unavailable_count(
                UnavailableReason.NO_SEARCH_DATA_YET
                if self.no_data
                else UnavailableReason.NOT_SYNCED
            )
        figure = months_figure(self.expected, values)
        if self.gapped:
            # Months with no data yet make the total a monthly average over the rest, or nothing.
            if not self.gaps_ok:
                return unavailable_count(UnavailableReason.NO_SEARCH_DATA_YET)
            return figure.model_copy(update={"availability": Availability.AVAILABLE})
        return figure

    def clicks(self) -> ReportCountFigure:
        return self._figure("clicks")

    def impressions(self) -> ReportCountFigure:
        return self._figure("impressions")

    def ctr(self) -> ReportRateFigure:
        """Clicks over impressions of the summed months: derived, never averaged."""
        clicks, impressions = self.clicks(), self.impressions()
        if clicks.value is None or not impressions.value:
            return unavailable_rate(UnavailableReason.NO_DATA)
        return ReportRateFigure(
            availability=Availability.AVAILABLE if self.settled else Availability.PARTIAL,
            value=round(clicks.value / impressions.value * 100, 2),
        )

    def position(self) -> ReportRateFigure:
        """Average position weighted by each month's impressions."""
        weighted = 0.0
        impressions = 0
        for row in self.rows.values():
            if row.position is None or not row.impressions:
                continue
            weighted += float(row.position) * int(row.impressions)
            impressions += int(row.impressions)
        if not impressions:
            return unavailable_rate(UnavailableReason.NO_DATA)
        return ReportRateFigure(
            availability=Availability.AVAILABLE if self.settled else Availability.PARTIAL,
            value=round(weighted / impressions, 1),
        )


async def _search_months(
    session: AsyncSession,
    property_id: UUID,
    months: Sequence[date],
    first_data: date | None,
    *,
    gaps_ok: bool = False,
    baseline: bool = False,
) -> SearchMonths:
    """``baseline`` sides are compared against: the first data month is often a partial month,
    so it is no data there, exactly like the months before it. It stays in the current period."""
    found = await _observations(session, property_id, months, MONTH_SITE_SUMMARY)
    rows: dict[date, SEOSearchObservation] = {}
    no_data: list[date] = []
    for row in found:
        month = row.date_start.date()
        before_first = row.quality_status == NO_DATA_STATUS and (
            first_data is None or month < first_data
        )
        if before_first or (baseline and first_data is not None and month == first_data):
            no_data.append(month)
        else:
            rows[month] = row
    return SearchMonths(list(months), rows, sorted(no_data), gaps_ok)


@dataclass(slots=True)
class Aggregate:
    clicks: int = 0
    impressions: int = 0
    weighted_position: float = 0.0

    def add(self, row: SEOSearchObservation) -> None:
        self.clicks += int(row.clicks or 0)
        impressions = int(row.impressions or 0)
        self.impressions += impressions
        if row.position is not None:
            self.weighted_position += float(row.position) * impressions

    @property
    def ctr(self) -> float | None:
        return round(self.clicks / self.impressions * 100, 2) if self.impressions else None

    @property
    def position(self) -> float | None:
        return round(self.weighted_position / self.impressions, 1) if self.impressions else None


def _aggregate(rows: Sequence[SEOSearchObservation], label: str) -> dict[str, Aggregate]:
    """Each query or page summed across the stored top rows of the months."""
    totals: dict[str, Aggregate] = {}
    for row in rows:
        name = str(row.query if label == "query" else row.dimensions.get(label) or "")
        if name:
            totals.setdefault(name, Aggregate()).add(row)
    return totals


def _ranked(totals: dict[str, Aggregate]) -> list[tuple[str, Aggregate]]:
    return sorted(totals.items(), key=lambda item: (-item[1].clicks, -item[1].impressions, item[0]))


def _compared_clicks(totals: dict[str, Aggregate], name: str, basis: Basis) -> int | None:
    found = totals.get(name)
    return basis.compared_value(found.clicks) if found else None


def build_movement(
    period_rows: Sequence[SEOSearchObservation],
    compared_rows: Sequence[SEOSearchObservation],
    now: SearchMonths,
    before: SearchMonths,
    brand_terms: Sequence[str],
    same_length: bool,
) -> ReportSearchMovement | None:
    """Every non-branded search over the period and over the comparison, from the stored rows.

    Added up from the highest-ranking searches Google reports each month, so a search missing from
    a window is unknown there, not zero. The two windows are set against each other only when both
    have every month stored and settled and are the same length.
    """
    if not period_rows:
        return None
    comparable = now.complete and before.complete and same_length and bool(compared_rows)
    after_totals = _aggregate(period_rows, "query")
    before_totals = _aggregate(compared_rows, "query") if comparable else {}
    rows: list[ReportMovementQuery] = []
    for name in sorted(after_totals.keys() | before_totals.keys()):
        if is_branded(name, brand_terms):
            continue
        after, earlier = after_totals.get(name), before_totals.get(name)
        if (
            max(after.impressions if after else 0, earlier.impressions if earlier else 0)
            < MOVEMENT_MIN_IMPRESSIONS
        ):
            continue
        rows.append(
            ReportMovementQuery(
                query=name,
                before_position=earlier.position if earlier else None,
                after_position=after.position if after else None,
                before_impressions=earlier.impressions if earlier else None,
                after_impressions=after.impressions if after else 0,
                before_clicks=earlier.clicks if earlier else None,
                after_clicks=after.clicks if after else 0,
            )
        )
    rows.sort(key=lambda row: (-max(row.after_impressions, row.before_impressions or 0), row.query))
    return ReportSearchMovement(
        comparable=comparable,
        months_covered=len(now.present),
        months_expected=len(now.expected),
        compared_months_covered=len(before.present),
        compared_months_expected=len(before.expected),
        queries=rows[:MOVEMENT_ROWS],
    )


async def build_search_console(
    session: AsyncSession,
    organization_id: UUID,
    period: ReportPeriod,
    comparison: ReportComparison,
    brand_terms: Sequence[str],
    basis: Basis,
) -> SearchResult:
    keys = (SeriesKey.SEARCH_CLICKS, SeriesKey.SEARCH_IMPRESSIONS)
    prop = await session.scalar(
        select(SEOSearchProperty)
        .where(
            SEOSearchProperty.organization_id == organization_id,
            SEOSearchProperty.provider == SEARCH_PROVIDER,
            SEOSearchProperty.mapping_status == PROVIDER_MAPPED,
        )
        .order_by(SEOSearchProperty.created_at, SEOSearchProperty.id)
        .limit(1)
    )
    if prop is None:
        return SearchResult(
            _search_unavailable(UnavailableReason.NOT_CONNECTED),
            [note(NoteCode.SEARCH_CONSOLE_NOT_CONNECTED)],
            _empty_series(keys, period, comparison),
            None,
        )
    first_data = await _first_data_month(session, prop.id)
    current = await _search_months(session, prop.id, period.months, first_data, gaps_ok=True)
    if not current.present:
        if current.no_data:
            return SearchResult(
                _search_unavailable(UnavailableReason.NO_SEARCH_DATA_YET),
                [note(NoteCode.SEARCH_CONSOLE_NO_DATA_YET)],
                _empty_series(keys, period, comparison),
                prop.last_synced_at.date() if prop.last_synced_at else None,
            )
        return SearchResult(
            _search_unavailable(UnavailableReason.NOT_SYNCED),
            [note(NoteCode.SEARCH_CONSOLE_NOT_SYNCED)],
            _empty_series(keys, period, comparison),
            None,
        )
    compared = await _search_months(
        session, prop.id, comparison.compared.months, first_data, gaps_ok=True, baseline=True
    )
    year = (
        await _search_months(
            session, prop.id, comparison.year_ago.months, first_data, baseline=True
        )
        if comparison.year_ago
        else None
    )
    if current.gapped or compared.gapped:
        # Months before Google's first data are left out of both sides, so the sides are compared
        # as monthly averages over the months that have data.
        basis = Basis(
            ComparedAs.MONTHLY_AVERAGE, len(current.present), max(1, len(compared.present))
        )
    notes: list[ReportDataNote] = []
    lag_days: int | None = None
    last = current.rows.get(period.end_month)
    if last is not None and last.partial:
        # The lag is how many days of the last month the provider had not settled when stored.
        _, following = calendar_month_window(period.end_month)
        settled_through = last.updated_at.date() - timedelta(days=GSC_SYNC_TAIL_EXCLUSION_DAYS)
        lag_days = max(1, (following.date() - timedelta(days=1) - settled_through).days)
        notes.append(note(NoteCode.SEARCH_CONSOLE_LAG_DAYS, count=lag_days))
    if first_data is not None and first_data in {
        *period.months,
        *comparison.compared.months,
        *(comparison.year_ago.months if comparison.year_ago else ()),
    }:
        notes.append(note(NoteCode.SEARCH_CONSOLE_FIRST_MONTH_PARTIAL, month=first_data))
    missing = len(current.expected) - len(current.rows) - len(current.no_data)
    if missing:
        notes.append(note(NoteCode.SEARCH_CONSOLE_MONTHS_MISSING, count=missing))
    if compared.gapped:
        notes.append(
            note(
                NoteCode.SEARCH_CONSOLE_COMPARED_AS_AVERAGE,
                covered_months=compared.present,
                missing_months=compared.no_data,
            )
        )
    elif not compared.complete:
        notes.append(note(NoteCode.SEARCH_CONSOLE_COMPARED_PERIOD_UNAVAILABLE))

    def counts(read: str) -> ReportCountComparison:
        pick = SearchMonths.clicks if read == "clicks" else SearchMonths.impressions
        return compare_counts(pick(current), pick(compared), pick(year) if year else None, basis)

    def rates(pick: str) -> ReportRateComparison:
        now_value, before = getattr(current, pick)(), getattr(compared, pick)()
        return rate_comparison(now_value, before, getattr(year, pick)() if year else None)

    async def baseline_rows(kind: str) -> list[SEOSearchObservation]:
        found = await _observations(session, prop.id, comparison.compared.months, kind)
        return [row for row in found if row.date_start.date() != first_data]

    compared_query_rows = await baseline_rows(MONTH_TOP_QUERY)
    queries = _aggregate(
        await _observations(session, prop.id, period.months, MONTH_TOP_QUERY), "query"
    )
    before_queries = _aggregate(compared_query_rows, "query")
    movement = build_movement(
        await _observations(session, prop.id, period.months, MONTH_TOP_QUERY),
        compared_query_rows,
        current,
        compared,
        brand_terms,
        period.span == comparison.compared.span,
    )
    pages = _aggregate(await _observations(session, prop.id, period.months, MONTH_TOP_PAGE), "page")
    before_pages = _aggregate(await baseline_rows(MONTH_TOP_PAGE), "page")
    # A change is only stated between two settled periods.
    settled = current.settled and compared.settled

    def change(clicks: int, before: int | None) -> int | None:
        if not settled or before is None:
            return None
        average = basis.current_average(clicks)
        return (clicks if average is None else average) - before

    ranked_queries = _ranked(queries)
    branded_clicks = sum(
        item.clicks for name, item in ranked_queries if is_branded(name, brand_terms)
    )
    all_clicks = sum(item.clicks for _, item in ranked_queries)
    query_rows = [
        ReportSearchQueryRow(
            query=name,
            is_branded=is_branded(name, brand_terms),
            clicks=item.clicks,
            impressions=item.impressions,
            ctr=item.ctr,
            position=item.position,
            compared_clicks=(before := _compared_clicks(before_queries, name, basis)),
            clicks_change=change(item.clicks, before),
        )
        for name, item in ranked_queries[:TOP_ROWS]
    ]
    page_rows = [
        ReportSearchPageRow(
            page=name,
            clicks=item.clicks,
            impressions=item.impressions,
            ctr=item.ctr,
            position=item.position,
            compared_clicks=(before := _compared_clicks(before_pages, name, basis)),
            clicks_change=change(item.clicks, before),
        )
        for name, item in _ranked(pages)[:TOP_ROWS]
    ]
    # The first data month is no baseline, but it is real data and stays on the chart.
    plotted = await _search_months(
        session, prop.id, comparison.compared.months, first_data, gaps_ok=True
    )
    series = [
        ReportMonthlySeries(
            key=key,
            period=month_points(period.months, source.values(attribute)),
            compared=month_points(comparison.compared.months, other.values(attribute)),
        )
        for key, attribute, source, other in (
            (SeriesKey.SEARCH_CLICKS, "clicks", current, plotted),
            (SeriesKey.SEARCH_IMPRESSIONS, "impressions", current, plotted),
        )
    ]
    return SearchResult(
        ReportSearchConsoleSection(
            availability=Availability.AVAILABLE if current.settled else Availability.PARTIAL,
            clicks=counts("clicks"),
            impressions=counts("impressions"),
            ctr_percent=rates("ctr"),
            average_position=rates("position"),
            top_queries=query_rows,
            top_pages=page_rows,
            branded_share_percent=(
                round(branded_clicks / all_clicks * 100, 1) if all_clicks else None
            ),
            lag_days=lag_days,
        ),
        notes,
        series,
        prop.last_synced_at.date() if prop.last_synced_at else None,
        movement,
    )


def _analytics_unavailable(reason: UnavailableReason) -> ReportAnalyticsSection:
    return ReportAnalyticsSection(
        availability=Availability.UNAVAILABLE, reason=reason, organic_sessions=_no_counts(reason)
    )


async def _organic_months(
    session: AsyncSession,
    organization_id: UUID,
    source_id: UUID,
    definition_id: UUID,
    months: Sequence[date],
) -> list[MetricObservation]:
    start, following = _window(months)
    rows = await session.scalars(
        select(MetricObservation).where(
            MetricObservation.organization_id == organization_id,
            MetricObservation.source_id == source_id,
            MetricObservation.metric_definition_id == definition_id,
            MetricObservation.period_start >= start,
            MetricObservation.period_end <= following,
            MetricObservation.dimensions["observation_type"].astext == ORGANIC_MONTH_TOTAL,
        )
    )
    return [row for row in rows if row.value is not None]


def _month_values(rows: Sequence[MetricObservation], months: Sequence[date]) -> list[MonthValue]:
    by_month = {row.period_start.date(): row for row in rows}
    return [
        MonthValue(
            month, int(by_month[month].value or 0), by_month[month].quality_state == PARTIAL_STATE
        )
        for month in months
        if month in by_month
    ]


async def build_analytics(
    session: AsyncSession,
    organization_id: UUID,
    period: ReportPeriod,
    comparison: ReportComparison,
    basis: Basis,
) -> AnalyticsResult:
    keys = (SeriesKey.ORGANIC_SESSIONS,)
    prop = await session.scalar(
        select(AnalyticsProperty)
        .where(
            AnalyticsProperty.organization_id == organization_id,
            AnalyticsProperty.mapping_status == PROVIDER_MAPPED,
        )
        .order_by(AnalyticsProperty.created_at, AnalyticsProperty.id)
        .limit(1)
    )
    if prop is None:
        return AnalyticsResult(
            _analytics_unavailable(UnavailableReason.NOT_CONNECTED),
            [note(NoteCode.ANALYTICS_NOT_CONNECTED)],
            _empty_series(keys, period, comparison),
            None,
        )
    source_id = await session.scalar(
        select(InsightSource.id).where(
            InsightSource.organization_id == organization_id,
            InsightSource.key == prop.external_property_id,
        )
    )
    definition_id = await session.scalar(
        select(MetricDefinition.id).where(
            MetricDefinition.key == ORGANIC_SESSIONS_KEY,
            MetricDefinition.version == ORGANIC_SESSIONS_VERSION,
        )
    )
    if not (source_id and definition_id):
        current_rows: list[MetricObservation] = []
    else:
        current_rows = await _organic_months(
            session, organization_id, source_id, definition_id, period.months
        )
    current = _month_values(current_rows, period.months)
    if not current:
        # A property with no confirmed website cannot report Organic Search at all.
        if prop.website_id is None or prop.page_evidence_status == "unavailable":
            return AnalyticsResult(
                _analytics_unavailable(UnavailableReason.SOURCE_UNAVAILABLE),
                [note(NoteCode.ANALYTICS_ORGANIC_UNAVAILABLE)],
                _empty_series(keys, period, comparison),
                None,
            )
        return AnalyticsResult(
            _analytics_unavailable(UnavailableReason.NOT_SYNCED),
            [note(NoteCode.ANALYTICS_NOT_SYNCED)],
            _empty_series(keys, period, comparison),
            None,
        )
    assert source_id is not None and definition_id is not None
    compared_rows = await _organic_months(
        session, organization_id, source_id, definition_id, comparison.compared.months
    )
    compared = _month_values(compared_rows, comparison.compared.months)
    year = (
        _month_values(
            await _organic_months(
                session, organization_id, source_id, definition_id, comparison.year_ago.months
            ),
            comparison.year_ago.months,
        )
        if comparison.year_ago
        else None
    )
    now_figure = months_figure(period.months, current)
    before_figure = months_figure(comparison.compared.months, compared)
    notes: list[ReportDataNote] = []
    missing = len(period.months) - len(current)
    if missing:
        notes.append(note(NoteCode.ANALYTICS_MONTHS_MISSING, count=missing))
    if before_figure.availability is not Availability.AVAILABLE:
        notes.append(note(NoteCode.ANALYTICS_COMPARED_PERIOD_UNAVAILABLE))
    return AnalyticsResult(
        ReportAnalyticsSection(
            availability=now_figure.availability,
            organic_sessions=compare_counts(
                now_figure,
                before_figure,
                months_figure(comparison.year_ago.months, year)
                if comparison.year_ago and year is not None
                else None,
                basis,
            ),
        ),
        notes,
        [
            ReportMonthlySeries(
                key=SeriesKey.ORGANIC_SESSIONS,
                period=month_points(period.months, current),
                compared=month_points(comparison.compared.months, compared),
            )
        ],
        prop.last_synced_at.date() if prop.last_synced_at else None,
    )
