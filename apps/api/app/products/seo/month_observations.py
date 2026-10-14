"""Search Console observations for whole calendar months, kept apart from the rolling windows.

A month window can have the same length as a 7/28/90-day window (February has 28 days), so a month
is stored under its own observation types. Nothing that reads the rolling windows can ever pick
a month up, and no rolling sync can overwrite one.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.seo.models import SEOSearchObservation, SEOSearchProperty
from apps.api.app.products.seo.search_console_adapter import SearchAnalyticsRow
from apps.api.app.reporting_periods import (
    GSC_SYNC_TAIL_EXCLUSION_DAYS,
    calendar_month_window,
    completed_months,
    month_is_final,
)

MONTH_SITE_SUMMARY = "month_site_summary"
MONTH_TOP_QUERY = "month_top_query"
MONTH_TOP_PAGE = "month_top_page"
# Months the sync keeps: the one just ended and the one before it, for the change between them.
MONTHS_KEPT = 2
STORED_ROWS_PER_DIMENSION = 100


def dimension_hash(dimensions: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(dimensions, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(slots=True)
class MonthFetch:
    """One calendar month's provider responses, or the exception a request raised."""

    month: date
    summary: list[SearchAnalyticsRow] | Exception
    queries: list[SearchAnalyticsRow] | Exception
    pages: list[SearchAnalyticsRow] | Exception

    @property
    def failed(self) -> bool:
        return any(isinstance(item, Exception) for item in (self.summary, self.queries, self.pages))


async def months_to_fetch(session: AsyncSession, property_id: UUID, today: date) -> list[date]:
    """Recent months whose summary is missing or was stored before the provider settled it."""
    wanted: list[date] = []
    for month in completed_months(today, MONTHS_KEPT):
        start, following = calendar_month_window(month)
        stored = await session.scalar(
            select(SEOSearchObservation.partial).where(
                SEOSearchObservation.search_property_id == property_id,
                SEOSearchObservation.date_start == start,
                SEOSearchObservation.date_end == following,
                SEOSearchObservation.dimensions["observation_type"].astext == MONTH_SITE_SUMMARY,
            )
        )
        if stored is None or stored:
            wanted.append(month)
    return wanted


CHUNK_SIZE = 200


def _row(
    property_row: SEOSearchProperty,
    *,
    start: datetime,
    end: datetime,
    dimensions: dict[str, object],
    query: str | None,
    clicks: int,
    impressions: int,
    ctr: float | None,
    position: float | None,
    quality: str,
    partial: bool,
) -> dict[str, object]:
    return {
        "organization_id": property_row.organization_id,
        "search_property_id": property_row.id,
        "website_id": property_row.website_id,
        "page_id": None,
        "query": query,
        "date_start": start,
        "date_end": end,
        "dimensions": dimensions,
        "dimension_hash": dimension_hash(dimensions),
        "clicks": clicks,
        "impressions": impressions,
        "ctr": ctr,
        "position": position,
        "quality_status": quality,
        "partial": partial,
    }


async def _upsert_many(session: AsyncSession, rows: list[dict[str, object]]) -> None:
    """Bounded multi-row upserts, so a month of queries is a handful of statements."""
    for offset in range(0, len(rows), CHUNK_SIZE):
        statement = pg_insert(SEOSearchObservation).values(rows[offset : offset + CHUNK_SIZE])
        await session.execute(
            statement.on_conflict_do_update(
                constraint="uq_seo_search_observation",
                set_={
                    **{
                        key: getattr(statement.excluded, key)
                        for key in (
                            "query",
                            "dimensions",
                            "clicks",
                            "impressions",
                            "ctr",
                            "position",
                            "quality_status",
                            "partial",
                        )
                    },
                    # Core upserts skip the ORM's onupdate; the read derives the lag from this.
                    "updated_at": func.now(),
                },
            )
        )


async def store_month(
    session: AsyncSession, property_row: SEOSearchProperty, fetch: MonthFetch, today: date
) -> int:
    """Persist one fetched month; the caller has already checked that nothing failed."""
    assert not isinstance(fetch.summary, Exception)
    assert not isinstance(fetch.queries, Exception)
    assert not isinstance(fetch.pages, Exception)
    start, following = calendar_month_window(fetch.month)
    website = str(property_row.website_id)
    partial = not month_is_final(fetch.month, today, GSC_SYNC_TAIL_EXCLUSION_DAYS)
    total = fetch.summary[0] if fetch.summary else None
    rows = [
        _row(
            property_row,
            start=start,
            end=following,
            dimensions={"observation_type": MONTH_SITE_SUMMARY, "website_id": website},
            query=None,
            clicks=total.clicks if total else 0,
            impressions=total.impressions if total else 0,
            ctr=total.ctr if total else None,
            position=total.position if total else None,
            quality="valid" if total else "zero",
            partial=partial,
        )
    ]
    for source, kind, key in (
        (fetch.queries, MONTH_TOP_QUERY, "query"),
        (fetch.pages, MONTH_TOP_PAGE, "page"),
    ):
        unique: dict[str, dict[str, object]] = {}
        for item in source[:STORED_ROWS_PER_DIMENSION]:
            label = item.keys[0] if item.keys else ""
            if not label:
                continue
            row = _row(
                property_row,
                start=start,
                end=following,
                dimensions={"observation_type": kind, key: label, "website_id": website},
                query=label if key == "query" else None,
                clicks=item.clicks,
                impressions=item.impressions,
                ctr=item.ctr,
                position=item.position,
                quality="valid",
                partial=partial,
            )
            unique[str(row["dimension_hash"])] = row
        rows.extend(unique.values())
    await _upsert_many(session, rows)
    return len(rows)
