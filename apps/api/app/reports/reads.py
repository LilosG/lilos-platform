"""Read projections over stored reports: history, the portfolio, and the real schedule.

Reads only ever touch stored revisions, deliveries and schedules. No provider is called and no
number is recomputed: a past month is exactly what was measured then.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.models import Schedule
from apps.api.app.insights.models import ReportDelivery, ReportRevision
from apps.api.app.locations.enums import LocationStatus
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.reports.contracts import (
    PortfolioReportCounts,
    PortfolioReportRow,
    ReportDeliveryView,
    ReportReadiness,
    ReportRevisionRow,
    ReportStatus,
    ReportUpcoming,
    UpcomingKind,
)
from apps.api.app.reports.schedule import REPORT_SCHEDULE_KEY, REPORT_TIMEZONE_NAME
from apps.api.app.reports.service import REVISION_APPROVED

_READINESS = ReportRevision.metric_snapshot["snapshot"]["readiness"].astext


def _status(approved: bool, delivery: ReportDelivery | None) -> ReportStatus:
    if not approved:
        return ReportStatus.DRAFT
    return ReportStatus.SENT if delivery else ReportStatus.READY


async def _deliveries(
    session: AsyncSession, organization_ids: Sequence[UUID], revision_ids: Sequence[UUID]
) -> dict[UUID, ReportDelivery]:
    if not revision_ids:
        return {}
    rows = await session.scalars(
        select(ReportDelivery).where(
            ReportDelivery.organization_id.in_(organization_ids),
            ReportDelivery.report_revision_id.in_(revision_ids),
        )
    )
    return {row.report_revision_id: row for row in rows}


async def revision_rows(session: AsyncSession, organization_id: UUID) -> list[ReportRevisionRow]:
    """Every revision of the client, newest month first, each with its status and delivery."""
    rows = (
        await session.execute(
            select(
                ReportRevision.id,
                ReportRevision.period_month,
                ReportRevision.revision,
                ReportRevision.status,
                ReportRevision.created_at,
                ReportRevision.approved_at,
                _READINESS,
            )
            .where(ReportRevision.organization_id == organization_id)
            .order_by(ReportRevision.period_month.desc(), ReportRevision.revision.desc())
        )
    ).all()
    deliveries = await _deliveries(session, [organization_id], [row[0] for row in rows])
    newest: dict[date, int] = {}
    for _, month, revision, *_rest in rows:
        newest[month] = max(newest.get(month, 0), revision)
    result: list[ReportRevisionRow] = []
    for revision_id, month, revision, status, created_at, approved_at, readiness in rows:
        delivery = deliveries.get(revision_id)
        result.append(
            ReportRevisionRow(
                month=month,
                revision=revision,
                status=_status(status == REVISION_APPROVED, delivery),
                readiness=ReportReadiness(readiness),
                is_current=revision == newest[month],
                created_at=created_at,
                approved_at=approved_at,
                delivery=ReportDeliveryView(
                    sent_on=delivery.sent_on, recorded_at=delivery.created_at
                )
                if delivery
                else None,
            )
        )
    return result


async def portfolio_rows(
    session: AsyncSession, organizations: Sequence[Organization], month: date
) -> tuple[list[PortfolioReportRow], PortfolioReportCounts]:
    """The latest report of ``month`` for every organization, in a fixed number of queries."""
    ids = [organization.id for organization in organizations]
    rows = (
        (
            await session.execute(
                select(
                    ReportRevision.organization_id,
                    ReportRevision.id,
                    ReportRevision.revision,
                    ReportRevision.status,
                    _READINESS,
                )
                .where(
                    ReportRevision.organization_id.in_(ids),
                    ReportRevision.period_month == month,
                )
                .order_by(ReportRevision.organization_id, ReportRevision.revision)
            )
        ).all()
        if ids
        else []
    )
    latest = {row[0]: row for row in rows}
    deliveries = await _deliveries(session, ids, [row[1] for row in rows])
    sent_by_org: dict[UUID, date] = {}
    for row in rows:
        delivery = deliveries.get(row[1])
        if delivery is not None:
            sent_by_org[row[0]] = max(sent_by_org.get(row[0], delivery.sent_on), delivery.sent_on)
    result: list[PortfolioReportRow] = []
    for organization in organizations:
        stored = latest.get(organization.id)
        result.append(
            PortfolioReportRow(
                organization_id=organization.id,
                slug=organization.slug,
                name=organization.name,
                month=month,
                revision=stored[2] if stored else None,
                status=_status(stored[3] == REVISION_APPROVED, deliveries.get(stored[1]))
                if stored
                else None,
                readiness=ReportReadiness(stored[4]) if stored else None,
                sent_on=sent_by_org.get(organization.id),
            )
        )
    return result, counts_of(result)


def counts_of(rows: Sequence[PortfolioReportRow]) -> PortfolioReportCounts:
    def count(readiness: ReportReadiness | None, *, sent: bool | None) -> int:
        return sum(
            1
            for row in rows
            if row.readiness is readiness
            and (sent is None or (row.status is ReportStatus.SENT) is sent)
        )

    return PortfolioReportCounts(
        ready=count(ReportReadiness.READY, sent=False),
        needs_attention=count(ReportReadiness.READY_WITH_NOTE, sent=False),
        missing_data=count(ReportReadiness.MISSING_DATA, sent=False),
        sent=sum(1 for row in rows if row.status is ReportStatus.SENT),
        not_generated=sum(1 for row in rows if row.status is None),
    )


def month_before(moment: datetime) -> date:
    """The calendar month before the Pacific date of ``moment``: what a run then reports on."""
    local = moment.astimezone(ZoneInfo(REPORT_TIMEZONE_NAME)).date().replace(day=1)
    previous = date.fromordinal(local.toordinal() - 1)
    return previous.replace(day=1)


async def upcoming(session: AsyncSession, organization_id: UUID) -> ReportUpcoming | None:
    """The next scheduled report run, read from the schedule itself; None when there is none."""
    schedule = await session.scalar(
        select(Schedule).where(
            Schedule.organization_id == organization_id,
            Schedule.key == REPORT_SCHEDULE_KEY,
            Schedule.status == "active",
        )
    )
    if schedule is None:
        return None
    return ReportUpcoming(
        kind=UpcomingKind.GENERATE_MONTHLY_REPORT,
        next_run_at=schedule.next_run_at,
        month=month_before(schedule.next_run_at),
    )


async def organization_is_reportable(session: AsyncSession, organization_id: UUID) -> bool:
    """An active client with at least one location that still runs a profile."""
    organization = await session.get(Organization, organization_id)
    if organization is None or organization.status != OrganizationStatus.ACTIVE:
        return False
    if organization.removed_at is not None:
        return False
    found = await session.scalar(
        select(Location.id)
        .where(
            Location.organization_id == organization_id,
            Location.status.in_(
                [LocationStatus.ACTIVE.value, LocationStatus.CLOSED_TEMPORARILY.value]
            ),
        )
        .limit(1)
    )
    return found is not None
