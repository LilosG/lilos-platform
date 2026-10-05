"""Ensure every active organization has its recurring sync and analysis schedules.

Almost nothing recurs today: reviews are ingested only when someone clicks in the web app,
Search Console and GA4 have never synced as workflows, and GA4 data is weeks old for most
clients. This creates (or corrects) the missing schedules through the canonical
`ExecutionService.create_schedule` / `update_schedule`, so each one is audited and the
scheduler dispatches it like any other.

What each active organization gets (an organization with no mapping for a source is skipped
and reported, never given a schedule that can only fail):

* `reviews.ingest`            every 6 hours, one schedule per mapped GBP location
* `gbp.sync`                  daily, one schedule, bound to the first mapped GBP location
* `gbp.sync_performance`      daily after `gbp.sync`, one schedule per mapped GBP location
* `seo.sync_search_console`   daily, one schedule, needs a mapped Search Console property
* `insights.sync_analytics`   daily, one schedule, needs a mapped GA4 property
* `seo.crawl_or_analysis`     weekly on Mondays, one schedule, needs an active SEO website

Schedules run in the organization's own timezone and carry the key `ensure:<workflow>` (plus
`:<location id>` for reviews), so a re-run finds them again: a matching schedule is left alone,
a drifted one (cron, timezone, paused or cancelled) is corrected, a missing one is created.
Schedules this script did not create (for example Coco Maya's `gbp.generate_post`) are never
touched. Only ACTIVE organizations are considered, which excludes archived ones; Wheyland
Electric is excluded by name as well.

Dry run by default: it prints exactly what `--apply` would do.

Run (Render shell):

    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.ensure_client_schedules
    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.ensure_client_schedules --apply
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import ColumnElement, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import InstrumentedAttribute

from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.execution.contracts import ScheduleCreate, ScheduleUpdate
from apps.api.app.execution.models import Schedule, WorkflowDefinition, WorkflowVersion
from apps.api.app.execution.service import ExecutionService
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.gbp.performance_service import mapped_gbp_locations
from apps.api.app.products.seo.models import SEOSearchProperty, SEOWebsite
from scripts._cli import run_script

EXIT_CONFLICT = 4
EXCLUDED_ORGANIZATION_NAMES = frozenset({"wheyland electric"})
KEY_PREFIX = "ensure:"


class Cadence(StrEnum):
    REVIEWS = "0 */6 * * *"
    GBP_SYNC = "0 5 * * *"
    GBP_PERFORMANCE = "15 5 * * *"
    SEARCH_CONSOLE = "30 5 * * *"
    ANALYTICS = "0 6 * * *"
    CRAWL = "0 7 * * 1"


class SkipReason(StrEnum):
    NO_MAPPED_GBP_LOCATION = "NO_MAPPED_GBP_LOCATION"
    NO_MAPPED_SEARCH_PROPERTY = "NO_MAPPED_SEARCH_PROPERTY"
    NO_MAPPED_ANALYTICS_PROPERTY = "NO_MAPPED_ANALYTICS_PROPERTY"
    NO_ACTIVE_WEBSITE = "NO_ACTIVE_WEBSITE"


class Action(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    UNCHANGED = "unchanged"
    # A script-owned key bound to another workflow or location. A schedule's workflow and
    # location cannot be edited, so this is reported for an operator and never overwritten.
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class Wanted:
    """One schedule an organization should have."""

    workflow_key: str
    key: str
    cron: str
    location_id: UUID | None
    # Locations an existing schedule may already be bound to without needing a change.
    acceptable_locations: tuple[UUID | None, ...] = ()


@dataclass(frozen=True, slots=True)
class Change:
    organization_id: UUID
    organization: str
    wanted: Wanted
    action: Action
    schedule_id: UUID | None
    differences: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Skipped:
    organization_id: UUID
    organization: str
    workflow_key: str
    reason: SkipReason


@dataclass(slots=True)
class Report:
    changes: list[Change] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    organizations: int = 0
    applied: bool = False


def _timezone(organization: Organization) -> str:
    try:
        ZoneInfo(organization.timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return "UTC"
    return organization.timezone


def next_run(cron: str, timezone: str, now: datetime) -> datetime:
    """The next occurrence of ``cron`` in ``timezone`` after ``now``, as an aware UTC time."""
    local = croniter(cron, now.astimezone(ZoneInfo(timezone))).get_next(datetime)
    return local.astimezone(UTC)


async def _mapped_gbp_locations(session: AsyncSession, organization_id: UUID) -> list[UUID]:
    """Platform locations whose GBP location is confirmed and has an active resource mapping.

    That is exactly what `ReviewIngestionService.ingest_for_location` needs to resolve.
    """
    seen: list[UUID] = []
    for row in await mapped_gbp_locations(session, organization_id):
        if row.location_id is not None and row.location_id not in seen:
            seen.append(row.location_id)
    return seen


async def _has(
    session: AsyncSession, column: InstrumentedAttribute[UUID], *conditions: ColumnElement[bool]
) -> bool:
    return (await session.scalar(select(column).where(*conditions).limit(1))) is not None


async def wanted_schedules(
    session: AsyncSession, organization: Organization
) -> tuple[list[Wanted], list[Skipped]]:
    """What this organization should have, and which sources it has no mapping for."""
    org_id = organization.id
    wanted: list[Wanted] = []
    skipped: list[Skipped] = []

    def skip(workflow_key: str, reason: SkipReason) -> None:
        skipped.append(Skipped(org_id, organization.name, workflow_key, reason))

    locations = await _mapped_gbp_locations(session, org_id)
    if locations:
        for location_id in locations:
            wanted.append(
                Wanted(
                    "reviews.ingest",
                    f"{KEY_PREFIX}reviews.ingest:{location_id}",
                    Cadence.REVIEWS,
                    location_id,
                )
            )
        for location_id in locations:
            wanted.append(
                Wanted(
                    "gbp.sync_performance",
                    f"{KEY_PREFIX}gbp.sync_performance:{location_id}",
                    Cadence.GBP_PERFORMANCE,
                    location_id,
                )
            )
        # The sync covers the whole organization, so any mapped location will do.
        wanted.append(
            Wanted(
                "gbp.sync",
                f"{KEY_PREFIX}gbp.sync",
                Cadence.GBP_SYNC,
                locations[0],
                tuple(locations),
            )
        )
    else:
        skip("reviews.ingest", SkipReason.NO_MAPPED_GBP_LOCATION)
        skip("gbp.sync", SkipReason.NO_MAPPED_GBP_LOCATION)
        skip("gbp.sync_performance", SkipReason.NO_MAPPED_GBP_LOCATION)

    if await _has(
        session,
        SEOSearchProperty.id,
        SEOSearchProperty.organization_id == org_id,
        SEOSearchProperty.mapping_status == "mapped",
    ):
        wanted.append(
            Wanted(
                "seo.sync_search_console",
                f"{KEY_PREFIX}seo.sync_search_console",
                Cadence.SEARCH_CONSOLE,
                None,
            )
        )
    else:
        skip("seo.sync_search_console", SkipReason.NO_MAPPED_SEARCH_PROPERTY)

    if await _has(
        session,
        AnalyticsProperty.id,
        AnalyticsProperty.organization_id == org_id,
        AnalyticsProperty.mapping_status == "mapped",
    ):
        wanted.append(
            Wanted(
                "insights.sync_analytics",
                f"{KEY_PREFIX}insights.sync_analytics",
                Cadence.ANALYTICS,
                None,
            )
        )
    else:
        skip("insights.sync_analytics", SkipReason.NO_MAPPED_ANALYTICS_PROPERTY)

    if await _has(
        session,
        SEOWebsite.id,
        SEOWebsite.organization_id == org_id,
        SEOWebsite.status == "active",
    ):
        wanted.append(
            Wanted(
                "seo.crawl_or_analysis", f"{KEY_PREFIX}seo.crawl_or_analysis", Cadence.CRAWL, None
            )
        )
    else:
        skip("seo.crawl_or_analysis", SkipReason.NO_ACTIVE_WEBSITE)
    return wanted, skipped


async def _workflow_key_of(session: AsyncSession, schedule: Schedule) -> str | None:
    key = await session.scalar(
        select(WorkflowDefinition.key)
        .join(WorkflowVersion, WorkflowVersion.definition_id == WorkflowDefinition.id)
        .where(WorkflowVersion.id == schedule.workflow_version_id)
    )
    return str(key) if key is not None else None


async def plan_organization(
    session: AsyncSession, organization: Organization
) -> tuple[list[Change], list[Skipped]]:
    """Compare what the organization should have with what it has. Nothing is written."""
    wanted, skipped = await wanted_schedules(session, organization)
    timezone = _timezone(organization)
    changes: list[Change] = []
    for item in wanted:
        existing = await session.scalar(
            select(Schedule).where(
                Schedule.organization_id == organization.id, Schedule.key == item.key
            )
        )
        if existing is None:
            changes.append(
                Change(organization.id, organization.name, item, Action.CREATE, None, ())
            )
            continue
        conflicts: list[str] = []
        if await _workflow_key_of(session, existing) != item.workflow_key:
            conflicts.append("workflow")
        if existing.location_id not in (item.acceptable_locations or (item.location_id,)):
            conflicts.append("location")
        differences: list[str] = []
        if existing.cron_expression != item.cron:
            differences.append("cron")
        if existing.timezone != timezone:
            differences.append("timezone")
        if existing.status != "active":
            differences.append("status")
        action = (
            Action.CONFLICT if conflicts else Action.UPDATE if differences else Action.UNCHANGED
        )
        changes.append(
            Change(
                organization.id,
                organization.name,
                item,
                action,
                existing.id,
                tuple(conflicts or differences),
            )
        )
    return changes, skipped


async def _apply(
    session: AsyncSession,
    organization: Organization,
    change: Change,
    execution: ExecutionService,
    correlation_id: str,
    now: datetime,
) -> None:
    timezone = _timezone(organization)
    item = change.wanted
    if change.action is Action.CREATE:
        await execution.create_schedule(
            session,
            organization.id,
            ScheduleCreate(
                workflow_key=item.workflow_key,
                key=item.key,
                cron_expression=item.cron,
                timezone=timezone,
                next_run_at=next_run(item.cron, timezone, now),
                location_id=item.location_id,
            ),
            correlation_id=correlation_id,
        )
    elif change.action is Action.UPDATE and change.schedule_id is not None:
        await execution.update_schedule(
            session,
            organization.id,
            change.schedule_id,
            ScheduleUpdate(
                status="active",
                cron_expression=item.cron,
                timezone=timezone,
                next_run_at=next_run(item.cron, timezone, now),
            ),
            correlation_id=correlation_id,
        )


async def ensure_client_schedules(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    apply: bool,
    organization_id: UUID | None = None,
    execution: ExecutionService | None = None,
    now: datetime | None = None,
) -> Report:
    """Plan (and with ``apply`` execute) the schedules of every active organization."""
    execution = execution or ExecutionService()
    now = now or datetime.now(UTC)
    async with session_factory() as session:
        statement = select(Organization).where(Organization.status == OrganizationStatus.ACTIVE)
        if organization_id is not None:
            statement = statement.where(Organization.id == organization_id)
        organizations = [
            organization
            for organization in await session.scalars(
                statement.order_by(Organization.created_at, Organization.id)
            )
            if organization.name.strip().lower() not in EXCLUDED_ORGANIZATION_NAMES
        ]
    report = Report(organizations=len(organizations), applied=apply)
    correlation_id = f"ensure-client-schedules:{uuid4().hex[:12]}"
    for organization in organizations:
        # One transaction per organization: a failure leaves the others untouched.
        async with session_factory.begin() as session:
            changes, skipped = await plan_organization(session, organization)
            if apply:
                for change in changes:
                    await _apply(session, organization, change, execution, correlation_id, now)
            report.changes.extend(changes)
            report.skipped.extend(skipped)
    return report


def format_report(report: Report) -> list[str]:
    lines: list[str] = []
    by_organization: dict[str, list[Change]] = {}
    for change in report.changes:
        by_organization.setdefault(change.organization, []).append(change)
    for name, changes in by_organization.items():
        lines.append(f"organization {name}")
        for change in changes:
            detail = f" ({', '.join(change.differences)})" if change.differences else ""
            where = f" location={change.wanted.location_id}" if change.wanted.location_id else ""
            lines.append(
                f"  {change.action.value:<9} {change.wanted.workflow_key:<24} "
                f"{change.wanted.cron:<12}{where}{detail}"
            )
    for item in report.skipped:
        lines.append(
            f"SKIPPED {item.organization} ({item.organization_id}) {item.workflow_key} "
            f"reason={item.reason.value}"
        )
    counts = Counter(change.action for change in report.changes)
    lines.append(
        f"organizations={report.organizations} create={counts[Action.CREATE]} "
        f"update={counts[Action.UPDATE]} unchanged={counts[Action.UNCHANGED]} "
        f"conflict={counts[Action.CONFLICT]} skipped={len(report.skipped)}"
    )
    return lines


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--organization-id", type=UUID, help="limit to one active organization")
    parser.add_argument(
        "--apply", action="store_true", help="create and correct schedules (default: dry run)"
    )
    return parser.parse_args(argv)


async def main() -> int:
    args = _parse_args()
    runtime = create_database_runtime(Settings())
    try:
        report = await ensure_client_schedules(
            runtime.require_session_factory(),
            apply=args.apply,
            organization_id=args.organization_id,
        )
    finally:
        await runtime.dispose()
    print("APPLIED" if report.applied else "DRY RUN (re-run with --apply to execute)")
    for line in format_report(report):
        print(line)
    return EXIT_CONFLICT if any(c.action is Action.CONFLICT for c in report.changes) else 0


if __name__ == "__main__":
    raise SystemExit(run_script("ensure_client_schedules", main))
