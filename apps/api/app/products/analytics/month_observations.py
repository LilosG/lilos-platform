"""GA4 Organic Search sessions for whole calendar months, one total per month.

The rolling windows keep sessions per landing page. A month needs only the total, but it needs it
to be able to say "zero" truthfully, so a month with no organic rows still stores a total of 0
that was read from Google. The total has its own observation type and can never be mistaken for a
rolling-window row.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.insights.models import InsightSource, MetricObservation
from apps.api.app.products.analytics.adapter import AnalyticsReportRow, GoogleAnalyticsAdapter
from apps.api.app.reporting_periods import (
    GA4_SYNC_TAIL_EXCLUSION_DAYS,
    calendar_month_window,
    completed_months,
    month_is_final,
    provider_end_date,
    provider_start_date,
)

ORGANIC_MONTH_TOTAL = "organic_month_total"
ORGANIC_SESSIONS_KEY = "ga4.organicLanding.sessions"
MONTHS_KEPT = 2
# A one-time backfill reaches back this far, for reports over a long period and its comparison.
BACKFILL_MONTHS = 16
PARTIAL_STATE = "partial"


def month_dimensions(website_id: UUID) -> dict[str, object]:
    return {"observation_type": ORGANIC_MONTH_TOTAL, "website_id": str(website_id)}


def dimension_hash(dimensions: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(dimensions, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(slots=True)
class OrganicMonthFetch:
    month: date
    rows: list[AnalyticsReportRow] | Exception


async def months_to_fetch(
    session: AsyncSession,
    organization_id: UUID,
    external_property_id: str,
    today: date,
    *,
    backfill: bool = False,
) -> list[date]:
    """Recent months with no total yet, or one stored before the provider settled the month.

    A backfill looks 16 months back and asks only for months the provider has settled; months it
    already stored are left alone, so running it again fetches only what failed before.
    """
    months = completed_months(today, BACKFILL_MONTHS if backfill else MONTHS_KEPT)
    if backfill:
        months = [m for m in months if month_is_final(m, today, GA4_SYNC_TAIL_EXCLUSION_DAYS)]
    source_id = await session.scalar(
        select(InsightSource.id).where(
            InsightSource.organization_id == organization_id,
            InsightSource.key == external_property_id,
        )
    )
    if source_id is None:
        return months
    wanted: list[date] = []
    for month in months:
        start, following = calendar_month_window(month)
        state = await session.scalar(
            select(MetricObservation.quality_state).where(
                MetricObservation.organization_id == organization_id,
                MetricObservation.source_id == source_id,
                MetricObservation.period_start == start,
                MetricObservation.period_end == following,
                MetricObservation.dimensions["observation_type"].astext == ORGANIC_MONTH_TOTAL,
            )
        )
        if state is None or state == PARTIAL_STATE:
            wanted.append(month)
    return wanted


async def fetch_months(
    adapter: GoogleAnalyticsAdapter,
    token: str,
    property_number: str,
    hostname: str,
    months: list[date],
) -> list[OrganicMonthFetch]:
    """Read each month's Organic Search landing rows. A failed month carries its exception.

    The caller has already established that the property can produce the organic report.
    """
    fetched: list[OrganicMonthFetch] = []
    for month in months:
        start, following = calendar_month_window(month)
        try:
            rows: list[AnalyticsReportRow] | Exception = await adapter.run_organic_page_report(
                token,
                property_number,
                start_date=provider_start_date(start),
                end_date=provider_end_date(following),
                hostname=hostname,
            )
        except Exception as exc:
            rows = exc
        fetched.append(OrganicMonthFetch(month, rows))
    return fetched


def total_sessions(rows: list[AnalyticsReportRow], hostname: str) -> int:
    """Sum organic sessions, refusing the foreign hosts and channels the rolling reports refuse."""
    total = 0
    for row in rows:
        if row.dimension_values.get("hostName", "").lower() != hostname:
            raise ValueError("Organic report returned a foreign hostname.")
        if row.dimension_values.get("sessionDefaultChannelGroup") != "Organic Search":
            raise ValueError("Organic report returned a foreign channel.")
        sessions = row.metric_values.get("sessions")
        if type(sessions) is not int or sessions < 0:
            raise ValueError("Invalid Organic Search sessions.")
        total += sessions
    return total


async def store_month(
    session: AsyncSession,
    *,
    organization_id: UUID,
    source: InsightSource,
    definition_id: UUID,
    website_id: UUID,
    location_id: UUID | None,
    property_label: str,
    hostname: str,
    fetch: OrganicMonthFetch,
    today: date,
) -> bool:
    """Persist one month's total; False when the month could not be read or did not validate."""
    if isinstance(fetch.rows, Exception):
        return False
    try:
        total = total_sessions(fetch.rows, hostname)
    except ValueError:
        return False
    start, following = calendar_month_window(fetch.month)
    final = month_is_final(fetch.month, today, GA4_SYNC_TAIL_EXCLUSION_DAYS)
    dimensions = month_dimensions(website_id)
    values = {
        "organization_id": organization_id,
        "source_id": source.id,
        "metric_definition_id": definition_id,
        "period_start": start,
        "period_end": following,
        "dimension_hash": dimension_hash(dimensions),
        "website_id": website_id,
        "location_id": location_id,
        "page_id": None,
        "dimensions": dimensions,
        "value": Decimal(total),
        "quality_state": (("valid" if total else "zero") if final else PARTIAL_STATE),
        "completeness": Decimal("1.0") if final else Decimal("0.9"),
        "provenance": {
            "report": "organic_month_total",
            "property": property_label,
            "month": fetch.month.isoformat(),
        },
    }
    statement = pg_insert(MetricObservation).values(values)
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_metric_observation_identity",
            set_={
                key: getattr(statement.excluded, key)
                for key in ("value", "quality_state", "completeness", "provenance", "dimensions")
            },
        )
    )
    return True
