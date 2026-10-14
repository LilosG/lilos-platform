"""The Search Console and Analytics sections of a monthly report, read from stored months.

Both come from whole calendar months stored by the syncs (``month_observations``). A rolling
28-day window is never substituted for a month: a month that was not synced is reported as not
synced. Data the provider had not settled when it was stored is partial, with the lag in days.
"""

from __future__ import annotations

from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
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
    first_of_month,
)
from apps.api.app.reports.contracts import (
    Availability,
    NoteCode,
    ReportAnalyticsSection,
    ReportCountComparison,
    ReportCountFigure,
    ReportDataNote,
    ReportRateComparison,
    ReportRateFigure,
    ReportSearchConsoleSection,
    ReportSearchPageRow,
    ReportSearchQueryRow,
    UnavailableReason,
    note,
)
from apps.api.app.reports.figures import (
    rate_comparison,
    unavailable_count,
    unavailable_rate,
)

TOP_ROWS = 25
PROVIDER_MAPPED = "mapped"
SEARCH_PROVIDER = "google_search_console"
ORGANIC_SESSIONS_VERSION = 1


def _previous_month(month: date) -> date:
    return first_of_month(month - timedelta(days=1))


def _count(value: int | None, *, partial: bool, reason: UnavailableReason) -> ReportCountFigure:
    if value is None:
        return unavailable_count(reason)
    return ReportCountFigure(
        availability=Availability.PARTIAL if partial else Availability.AVAILABLE, value=value
    )


def _rate(value: float | None, *, partial: bool, reason: UnavailableReason) -> ReportRateFigure:
    if value is None:
        return unavailable_rate(reason)
    return ReportRateFigure(
        availability=Availability.PARTIAL if partial else Availability.AVAILABLE, value=value
    )


def _change(
    current: ReportCountFigure, previous: ReportCountFigure
) -> tuple[int | None, float | None]:
    """A change only between two settled figures; a half-settled month proves nothing."""
    if current.availability is not Availability.AVAILABLE:
        return None, None
    if previous.availability is not Availability.AVAILABLE:
        return None, None
    assert current.value is not None and previous.value is not None
    difference = current.value - previous.value
    percent = round(difference / previous.value * 100, 1) if previous.value else None
    return difference, percent


def _comparison(current: ReportCountFigure, previous: ReportCountFigure) -> ReportCountComparison:
    change, percent = _change(current, previous)
    return ReportCountComparison(
        current=current, previous=previous, change=change, change_percent=percent
    )


def _no_counts(reason: UnavailableReason) -> ReportCountComparison:
    return ReportCountComparison(
        current=unavailable_count(reason), previous=unavailable_count(reason)
    )


def _no_rates(reason: UnavailableReason) -> ReportRateComparison:
    return ReportRateComparison(current=unavailable_rate(reason), previous=unavailable_rate(reason))


def _search_unavailable(
    reason: UnavailableReason,
) -> ReportSearchConsoleSection:
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


async def _month_summary(
    session: AsyncSession, property_id: UUID, month: date
) -> SEOSearchObservation | None:
    start, following = calendar_month_window(month)
    row: SEOSearchObservation | None = await session.scalar(
        select(SEOSearchObservation).where(
            SEOSearchObservation.search_property_id == property_id,
            SEOSearchObservation.date_start == start,
            SEOSearchObservation.date_end == following,
            SEOSearchObservation.dimensions["observation_type"].astext == MONTH_SITE_SUMMARY,
            SEOSearchObservation.quality_status.in_(("valid", "zero")),
        )
    )
    return row


async def _month_rows(
    session: AsyncSession, property_id: UUID, month: date, kind: str
) -> list[SEOSearchObservation]:
    start, following = calendar_month_window(month)
    rows = await session.scalars(
        select(SEOSearchObservation).where(
            SEOSearchObservation.search_property_id == property_id,
            SEOSearchObservation.date_start == start,
            SEOSearchObservation.date_end == following,
            SEOSearchObservation.dimensions["observation_type"].astext == kind,
        )
    )
    return list(rows)


def _ctr_percent(row: SEOSearchObservation | None) -> float | None:
    if row is None or row.ctr is None or not row.impressions:
        return None
    return round(float(row.ctr) * 100, 2)


def _position(row: SEOSearchObservation | None) -> float | None:
    if row is None or row.position is None or not row.impressions:
        return None
    return round(float(row.position), 1)


def _ranked(rows: list[SEOSearchObservation]) -> list[SEOSearchObservation]:
    return sorted(
        rows,
        key=lambda row: (
            -(row.clicks or 0),
            -(row.impressions or 0),
            str(row.dimensions.get("query") or row.dimensions.get("page") or ""),
        ),
    )[:TOP_ROWS]


async def build_search_console(
    session: AsyncSession, organization_id: UUID, month: date
) -> tuple[ReportSearchConsoleSection, list[ReportDataNote]]:
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
        return (
            _search_unavailable(UnavailableReason.NOT_CONNECTED),
            [note(NoteCode.SEARCH_CONSOLE_NOT_CONNECTED)],
        )
    current = await _month_summary(session, prop.id, month)
    if current is None:
        return (
            _search_unavailable(UnavailableReason.NOT_SYNCED),
            [note(NoteCode.SEARCH_CONSOLE_NOT_SYNCED)],
        )
    previous_month = _previous_month(month)
    previous = await _month_summary(session, prop.id, previous_month)
    notes: list[ReportDataNote] = []
    partial = bool(current.partial)
    previous_partial = bool(previous.partial) if previous else False
    lag_days: int | None = None
    if partial:
        # The lag is how many days of the month the provider had not settled when it was stored.
        _, following = calendar_month_window(month)
        settled_through = current.updated_at.date() - timedelta(days=GSC_SYNC_TAIL_EXCLUSION_DAYS)
        lag_days = max(1, (following.date() - timedelta(days=1) - settled_through).days)
        notes.append(note(NoteCode.SEARCH_CONSOLE_LAG_DAYS, count=lag_days))
    if previous is None or previous_partial:
        notes.append(note(NoteCode.SEARCH_CONSOLE_PREVIOUS_MONTH_UNAVAILABLE))

    def figures(attribute: str) -> ReportCountComparison:
        now = _count(getattr(current, attribute), partial=partial, reason=UnavailableReason.NO_DATA)
        before = (
            _count(
                getattr(previous, attribute),
                partial=previous_partial,
                reason=UnavailableReason.NO_DATA,
            )
            if previous
            else unavailable_count(UnavailableReason.NOT_SYNCED)
        )
        return _comparison(now, before)

    ctr_now = _rate(_ctr_percent(current), partial=partial, reason=UnavailableReason.NO_DATA)
    ctr_before = (
        _rate(_ctr_percent(previous), partial=previous_partial, reason=UnavailableReason.NO_DATA)
        if previous
        else unavailable_rate(UnavailableReason.NOT_SYNCED)
    )
    position_now = _rate(_position(current), partial=partial, reason=UnavailableReason.NO_DATA)
    position_before = (
        _rate(_position(previous), partial=previous_partial, reason=UnavailableReason.NO_DATA)
        if previous
        else unavailable_rate(UnavailableReason.NOT_SYNCED)
    )

    queries = _ranked(await _month_rows(session, prop.id, month, MONTH_TOP_QUERY))
    before_queries = {
        row.query: row
        for row in await _month_rows(session, prop.id, previous_month, MONTH_TOP_QUERY)
    }
    pages = _ranked(await _month_rows(session, prop.id, month, MONTH_TOP_PAGE))
    before_pages = {
        str(row.dimensions.get("page")): row
        for row in await _month_rows(session, prop.id, previous_month, MONTH_TOP_PAGE)
    }

    def counted(
        row: SEOSearchObservation, earlier: SEOSearchObservation | None
    ) -> tuple[int, int, int | None, int | None]:
        clicks, impressions = int(row.clicks or 0), int(row.impressions or 0)
        # Without a settled earlier month there is no change to state.
        if earlier is None or previous_partial or partial:
            return clicks, impressions, None, None
        before = int(earlier.clicks or 0)
        return clicks, impressions, before, clicks - before

    query_rows: list[ReportSearchQueryRow] = []
    for row in queries:
        clicks, impressions, before, change = counted(row, before_queries.get(row.query))
        query_rows.append(
            ReportSearchQueryRow(
                query=row.query or "",
                clicks=clicks,
                impressions=impressions,
                ctr=_ctr_percent(row),
                position=_position(row),
                previous_clicks=before,
                clicks_change=change,
            )
        )
    page_rows: list[ReportSearchPageRow] = []
    for row in pages:
        label = str(row.dimensions.get("page") or "")
        clicks, impressions, before, change = counted(row, before_pages.get(label))
        page_rows.append(
            ReportSearchPageRow(
                page=label,
                clicks=clicks,
                impressions=impressions,
                ctr=_ctr_percent(row),
                position=_position(row),
                previous_clicks=before,
                clicks_change=change,
            )
        )
    return (
        ReportSearchConsoleSection(
            availability=Availability.PARTIAL if partial else Availability.AVAILABLE,
            clicks=figures("clicks"),
            impressions=figures("impressions"),
            ctr_percent=rate_comparison(ctr_now, ctr_before),
            average_position=rate_comparison(position_now, position_before),
            top_queries=query_rows,
            top_pages=page_rows,
            lag_days=lag_days,
        ),
        notes,
    )


def _analytics_unavailable(reason: UnavailableReason) -> ReportAnalyticsSection:
    return ReportAnalyticsSection(
        availability=Availability.UNAVAILABLE, reason=reason, organic_sessions=_no_counts(reason)
    )


async def _organic_total(
    session: AsyncSession,
    organization_id: UUID,
    source_id: UUID,
    definition_id: UUID,
    month: date,
) -> MetricObservation | None:
    start, following = calendar_month_window(month)
    row: MetricObservation | None = await session.scalar(
        select(MetricObservation).where(
            MetricObservation.organization_id == organization_id,
            MetricObservation.source_id == source_id,
            MetricObservation.metric_definition_id == definition_id,
            MetricObservation.period_start == start,
            MetricObservation.period_end == following,
            MetricObservation.dimensions["observation_type"].astext == ORGANIC_MONTH_TOTAL,
        )
    )
    return row


async def build_analytics(
    session: AsyncSession, organization_id: UUID, month: date
) -> tuple[ReportAnalyticsSection, list[ReportDataNote]]:
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
        return (
            _analytics_unavailable(UnavailableReason.NOT_CONNECTED),
            [note(NoteCode.ANALYTICS_NOT_CONNECTED)],
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
    current = (
        await _organic_total(session, organization_id, source_id, definition_id, month)
        if source_id and definition_id
        else None
    )
    if current is None or current.value is None:
        # A property with no confirmed website cannot report Organic Search at all.
        if prop.website_id is None or prop.page_evidence_status == "unavailable":
            return (
                _analytics_unavailable(UnavailableReason.SOURCE_UNAVAILABLE),
                [note(NoteCode.ANALYTICS_ORGANIC_UNAVAILABLE)],
            )
        return (
            _analytics_unavailable(UnavailableReason.NOT_SYNCED),
            [note(NoteCode.ANALYTICS_NOT_SYNCED)],
        )
    assert source_id is not None and definition_id is not None
    previous = await _organic_total(
        session, organization_id, source_id, definition_id, _previous_month(month)
    )
    partial = current.quality_state == PARTIAL_STATE
    previous_partial = bool(previous and previous.quality_state == PARTIAL_STATE)
    now = _count(int(current.value), partial=partial, reason=UnavailableReason.NO_DATA)
    before = (
        _count(int(previous.value), partial=previous_partial, reason=UnavailableReason.NO_DATA)
        if previous and previous.value is not None
        else unavailable_count(UnavailableReason.NOT_SYNCED)
    )
    notes = (
        [note(NoteCode.ANALYTICS_PREVIOUS_MONTH_UNAVAILABLE)]
        if before.availability is Availability.UNAVAILABLE
        else []
    )
    return (
        ReportAnalyticsSection(
            availability=Availability.PARTIAL if partial else Availability.AVAILABLE,
            organic_sessions=_comparison(now, before),
        ),
        notes,
    )
