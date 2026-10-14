"""Build the monthly snapshot of one organization: deterministic, typed, from stored data only.

No provider is called and no model is involved. The snapshot is a pure function of what is stored,
so the same stored data always gives the same snapshot and the same hash.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.locations.enums import LocationStatus
from apps.api.app.locations.models import Location
from apps.api.app.products.gbp.performance_service import mapped_gbp_locations
from apps.api.app.reporting_periods import first_of_month
from apps.api.app.reports.contracts import (
    NOTE_EFFECT,
    NoteEffect,
    ReportDataNote,
    ReportReadiness,
    ReportSnapshot,
)
from apps.api.app.reports.errors import ReportMonthNotEndedError
from apps.api.app.reports.snapshot_gbp import MappedLocation, build_gbp
from apps.api.app.reports.snapshot_reviews import build_reviews
from apps.api.app.reports.snapshot_search import build_analytics, build_search_console
from apps.api.app.reports.snapshot_work import build_work
from apps.api.app.routes.command_center_search import not_tracked

# Locations that still run a profile. Paused, closed for good and archived ones are out.
REPORTABLE_STATUSES: tuple[LocationStatus, ...] = (
    LocationStatus.ACTIVE,
    LocationStatus.CLOSED_TEMPORARILY,
)
# The agency works in Pacific time: a month has ended when it has ended there.
REPORT_TIMEZONE = ZoneInfo("America/Los_Angeles")


def report_today(now: datetime) -> date:
    return now.astimezone(REPORT_TIMEZONE).date()


def last_ended_month(now: datetime) -> date:
    """The most recent calendar month that has ended."""
    first = first_of_month(report_today(now))
    return first_of_month(date.fromordinal(first.toordinal() - 1))


def require_ended(month: date, now: datetime) -> date:
    """A report is for a whole calendar month that has ended; never a running one."""
    if month.day != 1 or month >= first_of_month(report_today(now)):
        raise ReportMonthNotEndedError
    return month


async def reportable_locations(
    session: AsyncSession, organization_id: UUID
) -> list[MappedLocation]:
    mapped = {
        row.location_id: row.id
        for row in await mapped_gbp_locations(session, organization_id)
        if row.location_id is not None
    }
    rows = await session.execute(
        select(Location.id, Location.name)
        .where(
            Location.organization_id == organization_id,
            Location.status.in_([status.value for status in REPORTABLE_STATUSES]),
        )
        .order_by(Location.name, Location.id)
    )
    return [
        MappedLocation(location_id, name, mapped.get(location_id)) for location_id, name in rows
    ]


def readiness_of(notes: list[ReportDataNote]) -> ReportReadiness:
    """The rule, in code: Business Profile data decides; other gaps only flag the report."""
    effects = {NOTE_EFFECT[note.code] for note in notes}
    if NoteEffect.BLOCKING in effects:
        return ReportReadiness.MISSING_DATA
    if NoteEffect.DEGRADING in effects:
        return ReportReadiness.READY_WITH_NOTE
    return ReportReadiness.READY


async def build_snapshot(
    session: AsyncSession, organization_id: UUID, month: date, *, now: datetime | None = None
) -> ReportSnapshot:
    """The snapshot of ``month`` across every reportable location of the organization."""
    now = now or datetime.now(UTC)
    require_ended(month, now)
    locations = await reportable_locations(session, organization_id)
    location_ids = [item.location_id for item in locations]
    gbp = await build_gbp(session, organization_id, month, locations, now=now)
    reviews, review_notes = await build_reviews(session, organization_id, month, location_ids)
    search, search_notes = await build_search_console(session, organization_id, month)
    analytics, analytics_notes = await build_analytics(session, organization_id, month)
    work = await build_work(session, organization_id, month, location_ids)
    notes = [*gbp.notes, *review_notes, *search_notes, *analytics_notes]
    return ReportSnapshot(
        month=month,
        readiness=readiness_of(notes),
        notes=notes,
        gbp=gbp.section,
        reviews=reviews,
        search_console=search,
        analytics=analytics,
        local_rank=not_tracked(),
        work=work,
    )


def canonical_json(document: object) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), default=str)


def data_hash(snapshot: ReportSnapshot) -> str:
    """Identifies the computed numbers alone, so a regeneration can tell whether they changed."""
    return hashlib.sha256(canonical_json(snapshot.model_dump(mode="json")).encode()).hexdigest()
