"""Set-based evidence reads for the Command Center portfolio and client overview.

One query per metric family for every visible organization, grouped by ``organization_id``,
instead of per-organization and per-metric round trips. Each loader returns plain dictionaries
keyed by organization; assembling a client row from them does no I/O.

Semantics deliberately match the canonical per-organization services these replace:
``SearchConsoleService.performance_report`` (exact-window site summary, authoritative mapped
property, active website), ``AnalyticsService.performance_report`` (exact-window aggregate
sessions across mapped properties) and the lead, review, integration and workflow reads.
Reads are independent of one another, so each section is timed separately.
"""

import logging
import time
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from apps.api.app.execution.models import Schedule, WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.industries.models import Industry
from apps.api.app.insights.models import InsightSource, MetricDefinition, MetricObservation
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.models import Location
from apps.api.app.organizations.models import Organization
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.analytics.service import (
    ANALYTICS_PROVIDER_KEY,
    METRIC_DEFINITION_VERSION,
)
from apps.api.app.products.leads.models import Lead, LeadSource
from apps.api.app.products.reviews.models import Review
from apps.api.app.products.seo.models import (
    SEOOpportunity,
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.reporting_periods import comparison_window

logger = logging.getLogger("lilos.api.command_center")

OPEN_OPPORTUNITY_STATUSES = ("identified", "recommended", "approved")
ATTENTION_RUN_STATUSES = ("failed", "escalated", "retry_scheduled")
MEANINGFUL_ACTIVITY = (
    "gbp.publish_post",
    "reviews.publish_response",
    "content.publish",
    "seo.apply_site_change",
    "seo.crawl_or_analysis",
)
OPPORTUNITIES_PER_ORGANIZATION = 5
ACTIVITY_PER_ORGANIZATION = 5
PERMISSIONS = ("seo.read", "insights.read", "leads.read", "reviews.read", "workflows.read")
RANK = {"connected": 4, "degraded": 3, "pending": 2, "reconnect_required": 1}


class SectionTimer:
    """Wall time per read section, logged once so slow sections are visible."""

    def __init__(self) -> None:
        self.sections: dict[str, float] = {}
        self.started = time.perf_counter()

    @asynccontextmanager
    async def section(self, name: str) -> AsyncIterator[None]:
        began = time.perf_counter()
        try:
            yield
        finally:
            self.sections[name] = round(
                self.sections.get(name, 0.0) + (time.perf_counter() - began) * 1000, 1
            )

    def log(self, route: str, organizations: int, correlation_id: str) -> None:
        logger.info(
            "Command Center read timed",
            extra={
                "event_name": "command_center.read.timings",
                "correlation_id": correlation_id,
                "route": route,
                "organization_count": organizations,
                "total_ms": round((time.perf_counter() - self.started) * 1000, 1),
                "sections_ms": dict(self.sections),
            },
        )


@dataclass(frozen=True, slots=True)
class MetricRead:
    """One metric before it is shaped into the response contract."""

    availability: str
    current: float | None = None
    previous: float | None = None
    freshness_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ReviewRead:
    availability: str
    total: int | None = None
    new_in_period: int | None = None
    average_rating: float | None = None


@dataclass(frozen=True, slots=True)
class OpportunityRead:
    id: UUID
    organization_id: UUID
    opportunity_type: str
    status: str
    priority: float | None
    evidence: dict[str, object]


@dataclass(frozen=True, slots=True)
class RunRead:
    organization_id: UUID
    workflow_key: str
    status: str
    at: datetime | None
    failure_code: str | None


@dataclass(frozen=True, slots=True)
class LocationRead:
    organization_id: UUID
    city: str | None
    region: str | None


@dataclass
class Facts:
    """Everything the projections need, keyed by organization id."""

    locations: dict[UUID, list[LocationRead]] = field(default_factory=dict)
    industries: dict[UUID, str] = field(default_factory=dict)
    clicks: dict[UUID, MetricRead] = field(default_factory=dict)
    position: dict[UUID, MetricRead] = field(default_factory=dict)
    sessions: dict[UUID, MetricRead] = field(default_factory=dict)
    leads: dict[UUID, MetricRead] = field(default_factory=dict)
    reviews: dict[UUID, ReviewRead] = field(default_factory=dict)
    open_counts: dict[UUID, int] = field(default_factory=dict)
    opportunities: dict[UUID, list[OpportunityRead]] = field(default_factory=dict)
    google: dict[UUID, str] = field(default_factory=dict)
    last_completed: dict[UUID, RunRead] = field(default_factory=dict)
    unresolved: dict[UUID, list[RunRead]] = field(default_factory=dict)
    activity: dict[UUID, list[RunRead]] = field(default_factory=dict)
    next_work: dict[UUID, tuple[str, datetime]] = field(default_factory=dict)


async def load_facts(
    session: AsyncSession,
    organizations: list[Organization],
    allowed: dict[str, set[UUID]],
    *,
    days: int,
    now: datetime,
    timer: SectionTimer,
) -> Facts:
    """Load every fact for ``organizations``; ``allowed[permission]`` names who may be read."""
    facts = Facts()
    ids = [organization.id for organization in organizations]
    if not ids:
        return facts
    start = now - timedelta(days=days)
    async with timer.section("locations"):
        facts.locations = await locations(session, ids)
        facts.industries = await industries(session, organizations)
    async with timer.section("search_console"):
        facts.clicks, facts.position = await search_console(session, ids, allowed["seo.read"], days)
    async with timer.section("analytics"):
        facts.sessions = await analytics_sessions(session, ids, allowed["insights.read"], days)
    async with timer.section("leads"):
        facts.leads = await lead_counts(session, ids, allowed["leads.read"], start, now, days)
    async with timer.section("reviews"):
        facts.reviews = await review_summary(session, ids, allowed["reviews.read"], start)
    async with timer.section("opportunities"):
        facts.open_counts, facts.opportunities = await opportunities(
            session, ids, allowed["seo.read"]
        )
    async with timer.section("integrations"):
        facts.google = await google_connections(session, ids)
    async with timer.section("workflows"):
        (
            facts.last_completed,
            facts.unresolved,
            facts.activity,
            facts.next_work,
        ) = await workflows(session, ids, allowed["workflows.read"], start)
    return facts


async def locations(session: AsyncSession, ids: list[UUID]) -> dict[UUID, list[LocationRead]]:
    grouped: dict[UUID, list[LocationRead]] = defaultdict(list)
    for organization_id, city, region in await session.execute(
        select(Location.organization_id, Location.city, Location.region)
        .where(Location.organization_id.in_(ids), Location.status == "active")
        .order_by(Location.organization_id, Location.is_primary.desc(), Location.created_at)
    ):
        grouped[organization_id].append(LocationRead(organization_id, city, region))
    return grouped


async def industries(session: AsyncSession, organizations: list[Organization]) -> dict[UUID, str]:
    industry_ids = {o.industry_id for o in organizations if o.industry_id}
    if not industry_ids:
        return {}
    names = {
        row_id: name
        for row_id, name in await session.execute(
            select(Industry.id, Industry.name).where(Industry.id.in_(industry_ids))
        )
    }
    return {o.id: names[o.industry_id] for o in organizations if o.industry_id in names}


async def search_console(
    session: AsyncSession, ids: list[UUID], permitted: set[UUID], days: int
) -> tuple[dict[UUID, MetricRead], dict[UUID, MetricRead]]:
    """Clicks and average position from the exact-window site summary of the active website."""
    clicks: dict[UUID, MetricRead] = {}
    position: dict[UUID, MetricRead] = {}
    readable = [i for i in ids if i in permitted]
    if not readable:
        return clicks, position
    # The newest active website per organization (the canonical list is newest first).
    websites: dict[UUID, UUID] = {}
    for website_id, organization_id in await session.execute(
        select(SEOWebsite.id, SEOWebsite.organization_id)
        .where(SEOWebsite.organization_id.in_(readable), SEOWebsite.status == "active")
        .order_by(SEOWebsite.organization_id, SEOWebsite.created_at.desc())
        .distinct(SEOWebsite.organization_id)
    ):
        websites[organization_id] = website_id
    for organization_id in readable:
        if organization_id not in websites:
            clicks[organization_id] = position[organization_id] = MetricRead("not_connected")
    if not websites:
        return clicks, position
    # The earliest-created mapped property per (organization, website) is authoritative.
    properties: dict[UUID, tuple[UUID, UUID, datetime | None]] = {}
    for prop_id, organization_id, last_synced in await session.execute(
        select(
            SEOSearchProperty.id,
            SEOSearchProperty.organization_id,
            SEOSearchProperty.last_synced_at,
        )
        .where(
            SEOSearchProperty.organization_id.in_(websites),
            SEOSearchProperty.website_id.in_(websites.values()),
            SEOSearchProperty.provider == "google_search_console",
            SEOSearchProperty.mapping_status == "mapped",
        )
        .order_by(
            SEOSearchProperty.organization_id,
            SEOSearchProperty.website_id,
            SEOSearchProperty.created_at.asc(),
            SEOSearchProperty.id.asc(),
        )
        .distinct(SEOSearchProperty.organization_id, SEOSearchProperty.website_id)
    ):
        properties[organization_id] = (prop_id, websites[organization_id], last_synced)
    for organization_id in websites:
        if organization_id not in properties:
            clicks[organization_id] = position[organization_id] = MetricRead("not_connected")
    if not properties:
        return clicks, position
    prop_ids = [prop_id for prop_id, _, _ in properties.values()]
    site_of = {prop_id: website_id for prop_id, website_id, _ in properties.values()}
    summary = (
        SEOSearchObservation.dimensions["observation_type"].astext == "site_summary",
        SEOSearchObservation.quality_status.in_(["valid", "zero"]),
        or_(
            SEOSearchObservation.website_id.is_(None),
            SEOSearchObservation.website_id.in_(site_of.values()),
        ),
    )
    windows: dict[UUID, tuple[datetime, datetime]] = {}
    for prop_id, date_start, date_end in await session.execute(
        select(
            SEOSearchObservation.search_property_id,
            SEOSearchObservation.date_start,
            SEOSearchObservation.date_end,
        )
        .where(
            SEOSearchObservation.search_property_id.in_(prop_ids),
            *summary,
            func.extract("epoch", SEOSearchObservation.date_end - SEOSearchObservation.date_start)
            == days * 86_400,
        )
        .order_by(SEOSearchObservation.search_property_id, SEOSearchObservation.date_end.desc())
        .distinct(SEOSearchObservation.search_property_id)
    ):
        windows[prop_id] = (date_start, date_end)
    wanted: list[tuple[datetime, datetime, UUID]] = []
    for prop_id, (date_start, date_end) in windows.items():
        comp_start, comp_end = comparison_window(date_start, days)
        wanted.append((date_start, date_end, prop_id))
        wanted.append((comp_start, comp_end, prop_id))
    found: dict[tuple[UUID, datetime, datetime], tuple[float | None, float | None]] = {}
    if wanted:
        rows = await session.execute(
            select(
                SEOSearchObservation.search_property_id,
                SEOSearchObservation.website_id,
                SEOSearchObservation.date_start,
                SEOSearchObservation.date_end,
                SEOSearchObservation.clicks,
                SEOSearchObservation.position,
            )
            .where(
                tuple_(
                    SEOSearchObservation.date_start,
                    SEOSearchObservation.date_end,
                    SEOSearchObservation.search_property_id,
                ).in_(wanted),
                *summary,
            )
            .order_by(SEOSearchObservation.date_end.desc())
        )
        for prop_id, row_site, date_start, date_end, row_clicks, row_position in rows:
            key = (prop_id, date_start, date_end)
            own = row_site == site_of[prop_id]
            if key not in found or own:
                found[key] = (
                    float(row_clicks) if row_clicks is not None else None,
                    float(row_position) if row_position is not None else None,
                )
    for organization_id, (prop_id, _, last_synced) in properties.items():
        window = windows.get(prop_id)
        if window is None:
            clicks[organization_id] = position[organization_id] = MetricRead(
                "no_data", freshness_at=last_synced
            )
            continue
        comp = comparison_window(window[0], days)
        now_values = found.get((prop_id, *window), (None, None))
        before_values = found.get((prop_id, *comp), (None, None))
        for target, index in ((clicks, 0), (position, 1)):
            current, previous = now_values[index], before_values[index]
            target[organization_id] = (
                MetricRead("available", current, previous, last_synced)
                if current is not None
                else MetricRead("no_data", freshness_at=last_synced)
            )
    return clicks, position


async def analytics_sessions(
    session: AsyncSession, ids: list[UUID], permitted: set[UUID], days: int
) -> dict[UUID, MetricRead]:
    """GA4 sessions: the exact-window aggregate summed across mapped properties."""
    result: dict[UUID, MetricRead] = {}
    readable = [i for i in ids if i in permitted]
    if not readable:
        return result
    props: dict[UUID, list[tuple[str, datetime | None]]] = defaultdict(list)
    for organization_id, external_id, synced in await session.execute(
        select(
            AnalyticsProperty.organization_id,
            AnalyticsProperty.external_property_id,
            AnalyticsProperty.last_synced_at,
        ).where(
            AnalyticsProperty.organization_id.in_(readable),
            AnalyticsProperty.provider == ANALYTICS_PROVIDER_KEY,
            AnalyticsProperty.mapping_status == "mapped",
        )
    ):
        props[organization_id].append((external_id, synced))
    for organization_id in readable:
        if organization_id not in props:
            result[organization_id] = MetricRead("not_connected")
    if not props:
        return result
    external_ids = {external for rows in props.values() for external, _ in rows}
    source_of: dict[tuple[UUID, str], UUID] = {}
    for source_id, organization_id, key in await session.execute(
        select(InsightSource.id, InsightSource.organization_id, InsightSource.key).where(
            InsightSource.organization_id.in_(props), InsightSource.key.in_(external_ids)
        )
    ):
        source_of[(organization_id, key)] = source_id
    org_of_source = {source_id: org for (org, _), source_id in source_of.items()}
    definition_id = await session.scalar(
        select(MetricDefinition.id).where(
            MetricDefinition.key == "ga4.sessions",
            MetricDefinition.version == METRIC_DEFINITION_VERSION,
        )
    )
    aggregate = (
        MetricObservation.dimensions["observation_type"].astext == "aggregate",
        MetricObservation.quality_state.in_(["valid", "zero"]),
    )
    windows: dict[UUID, tuple[datetime, datetime]] = {}
    if source_of:
        for organization_id, period_start, period_end in await session.execute(
            select(
                MetricObservation.organization_id,
                MetricObservation.period_start,
                MetricObservation.period_end,
            )
            .where(
                MetricObservation.organization_id.in_(props),
                MetricObservation.source_id.in_(source_of.values()),
                *aggregate,
                func.extract("epoch", MetricObservation.period_end - MetricObservation.period_start)
                == days * 86_400,
            )
            .order_by(MetricObservation.organization_id, MetricObservation.period_end.desc())
            .distinct(MetricObservation.organization_id)
        ):
            windows[organization_id] = (period_start, period_end)
    sums: dict[tuple[UUID, datetime, datetime], Decimal | None] = {}
    if windows and definition_id is not None:
        wanted: list[tuple[UUID, datetime, datetime]] = []
        for organization_id, (period_start, period_end) in windows.items():
            comp_start, comp_end = comparison_window(period_start, days)
            wanted.append((organization_id, period_start, period_end))
            wanted.append((organization_id, comp_start, comp_end))
        seen: set[tuple[UUID, UUID, datetime, datetime]] = set()
        for source_id, period_start, period_end, value in await session.execute(
            select(
                MetricObservation.source_id,
                MetricObservation.period_start,
                MetricObservation.period_end,
                MetricObservation.value,
            )
            .where(
                tuple_(
                    MetricObservation.organization_id,
                    MetricObservation.period_start,
                    MetricObservation.period_end,
                ).in_(wanted),
                MetricObservation.source_id.in_(source_of.values()),
                MetricObservation.metric_definition_id == definition_id,
                *aggregate,
            )
            .order_by(MetricObservation.period_end.desc())
        ):
            organization_id = org_of_source[source_id]
            marker = (organization_id, source_id, period_start, period_end)
            if marker in seen or value is None:
                continue
            seen.add(marker)  # one observation per property and window, as the report takes
            key = (organization_id, period_start, period_end)
            sums[key] = (sums.get(key) or Decimal(0)) + value
    for organization_id, rows in props.items():
        synced_values = [synced for _, synced in rows if synced is not None]
        freshness = max(synced_values) if synced_values else None
        window = windows.get(organization_id)
        current = previous = None
        if window is not None:
            current = sums.get((organization_id, *window))
            previous = sums.get((organization_id, *comparison_window(window[0], days)))
        result[organization_id] = (
            MetricRead(
                "available",
                float(current),
                float(previous) if previous is not None else None,
                freshness,
            )
            if current is not None
            else MetricRead("no_data", freshness_at=freshness)
        )
    return result


async def lead_counts(
    session: AsyncSession,
    ids: list[UUID],
    permitted: set[UUID],
    start: datetime,
    now: datetime,
    days: int,
) -> dict[UUID, MetricRead]:
    """Lead counts; an organization with no active lead source is not connected, never zero."""
    readable = [i for i in ids if i in permitted]
    result: dict[UUID, MetricRead] = {}
    if not readable:
        return result
    connected = set(
        await session.scalars(
            select(LeadSource.organization_id)
            .where(LeadSource.organization_id.in_(readable), LeadSource.status == "active")
            .distinct()
        )
    )
    previous_start = start - timedelta(days=days)
    counts: dict[UUID, tuple[int, int]] = {}
    if connected:
        for organization_id, current, previous in await session.execute(
            select(
                Lead.organization_id,
                func.count().filter(and_(Lead.received_at >= start, Lead.received_at < now)),
                func.count().filter(
                    and_(Lead.received_at >= previous_start, Lead.received_at < start)
                ),
            )
            .where(
                Lead.organization_id.in_(connected),
                Lead.duplicate_of_lead_id.is_(None),
                Lead.received_at >= previous_start,
                Lead.received_at < now,
            )
            .group_by(Lead.organization_id)
        ):
            counts[organization_id] = (int(current), int(previous))
    for organization_id in readable:
        if organization_id not in connected:
            result[organization_id] = MetricRead("not_connected")
        else:
            current, previous = counts.get(organization_id, (0, 0))
            result[organization_id] = MetricRead("available", float(current), float(previous))
    return result


async def review_summary(
    session: AsyncSession, ids: list[UUID], permitted: set[UUID], start: datetime
) -> dict[UUID, ReviewRead]:
    readable = [i for i in ids if i in permitted]
    result: dict[UUID, ReviewRead] = {}
    if not readable:
        return result
    for organization_id, total, average, recent in await session.execute(
        select(
            Review.organization_id,
            func.count(Review.id),
            func.avg(Review.rating),
            func.count(Review.id).filter(Review.review_created_at >= start),
        )
        .where(Review.organization_id.in_(readable))
        .group_by(Review.organization_id)
    ):
        result[organization_id] = ReviewRead(
            "available",
            int(total),
            int(recent),
            round(float(average), 1) if average is not None else None,
        )
    for organization_id in readable:
        result.setdefault(organization_id, ReviewRead("no_data"))
    return result


async def opportunities(
    session: AsyncSession, ids: list[UUID], permitted: set[UUID]
) -> tuple[dict[UUID, int], dict[UUID, list[OpportunityRead]]]:
    readable = [i for i in ids if i in permitted]
    counts: dict[UUID, int] = {}
    top: dict[UUID, list[OpportunityRead]] = defaultdict(list)
    if not readable:
        return counts, top
    open_filter = and_(
        SEOOpportunity.organization_id.in_(readable),
        SEOOpportunity.status.in_(OPEN_OPPORTUNITY_STATUSES),
    )
    for organization_id, total in await session.execute(
        select(SEOOpportunity.organization_id, func.count())
        .where(open_filter)
        .group_by(SEOOpportunity.organization_id)
    ):
        counts[organization_id] = int(total)
    for organization_id in readable:
        counts.setdefault(organization_id, 0)
    ranked = (
        select(
            SEOOpportunity.id.label("id"),
            SEOOpportunity.organization_id.label("organization_id"),
            SEOOpportunity.opportunity_type.label("opportunity_type"),
            SEOOpportunity.status.label("status"),
            SEOOpportunity.priority_score.label("priority"),
            SEOOpportunity.evidence.label("evidence"),
            func.row_number()
            .over(
                partition_by=SEOOpportunity.organization_id,
                order_by=SEOOpportunity.priority_score.desc().nulls_last(),
            )
            .label("rank"),
        )
        .where(open_filter)
        .subquery()
    )
    for row in await session.execute(
        select(ranked)
        .where(ranked.c.rank <= OPPORTUNITIES_PER_ORGANIZATION)
        .order_by(ranked.c.organization_id, ranked.c.rank)
    ):
        top[row.organization_id].append(
            OpportunityRead(
                row.id,
                row.organization_id,
                row.opportunity_type,
                row.status,
                float(row.priority) if row.priority is not None else None,
                row.evidence or {},
            )
        )
    return counts, top


async def google_connections(session: AsyncSession, ids: list[UUID]) -> dict[UUID, str]:
    """The best connection state per organization: a working reconnection beats an old one."""
    best: dict[UUID, str] = {}
    for organization_id, status in await session.execute(
        select(IntegrationConnection.organization_id, IntegrationConnection.status)
        .join(Provider, Provider.id == IntegrationConnection.provider_id)
        .where(
            IntegrationConnection.organization_id.in_(ids),
            Provider.key == "google_business_profile",
        )
    ):
        if RANK.get(status, 0) >= RANK.get(best.get(organization_id, ""), -1):
            best[organization_id] = status
    return best


async def workflows(
    session: AsyncSession, ids: list[UUID], permitted: set[UUID], start: datetime
) -> tuple[
    dict[UUID, RunRead],
    dict[UUID, list[RunRead]],
    dict[UUID, list[RunRead]],
    dict[UUID, tuple[str, datetime]],
]:
    readable = [i for i in ids if i in permitted]
    last: dict[UUID, RunRead] = {}
    unresolved: dict[UUID, list[RunRead]] = defaultdict(list)
    activity: dict[UUID, list[RunRead]] = defaultdict(list)
    upcoming: dict[UUID, tuple[str, datetime]] = {}
    if not readable:
        return last, unresolved, activity, upcoming
    joined = (
        select(WorkflowRun, WorkflowDefinition.key)
        .join(WorkflowVersion, WorkflowVersion.id == WorkflowRun.workflow_version_id)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
    )

    def read(run: WorkflowRun, key: str, at: datetime | None) -> RunRead:
        return RunRead(run.organization_id, key, run.status, at, run.failure_code)

    for run, key in await session.execute(
        joined.where(WorkflowRun.organization_id.in_(readable), WorkflowRun.status == "completed")
        .order_by(WorkflowRun.organization_id, WorkflowRun.completed_at.desc().nulls_last())
        .distinct(WorkflowRun.organization_id)
    ):
        last[run.organization_id] = read(run, key, run.completed_at)
    # A failure is unresolved only while no later run of the same definition and scope
    # (organization and location) has completed.
    later = aliased(WorkflowRun)
    later_version = aliased(WorkflowVersion)
    superseded = exists().where(
        later.organization_id == WorkflowRun.organization_id,
        later.workflow_version_id == later_version.id,
        later_version.definition_id == WorkflowVersion.definition_id,
        later.status == "completed",
        later.location_id.is_not_distinct_from(WorkflowRun.location_id),
        later.completed_at > WorkflowRun.updated_at,
    )
    for run, key in await session.execute(
        joined.where(
            WorkflowRun.organization_id.in_(readable),
            WorkflowRun.status.in_(ATTENTION_RUN_STATUSES),
            WorkflowRun.updated_at >= start,
            ~superseded,
        ).order_by(WorkflowRun.updated_at.desc())
    ):
        unresolved[run.organization_id].append(read(run, key, run.updated_at))
    ranked = (
        select(
            WorkflowRun.id.label("id"),
            func.row_number()
            .over(
                partition_by=WorkflowRun.organization_id,
                order_by=WorkflowRun.completed_at.desc(),
            )
            .label("rank"),
        )
        .join(WorkflowVersion, WorkflowVersion.id == WorkflowRun.workflow_version_id)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
        .where(
            WorkflowRun.organization_id.in_(readable),
            WorkflowRun.status == "completed",
            WorkflowRun.completed_at >= start,
            WorkflowDefinition.key.in_(MEANINGFUL_ACTIVITY),
        )
        .subquery()
    )
    for run, key in await session.execute(
        joined.join(ranked, ranked.c.id == WorkflowRun.id)
        .where(ranked.c.rank <= ACTIVITY_PER_ORGANIZATION)
        .order_by(WorkflowRun.completed_at.desc())
    ):
        activity[run.organization_id].append(read(run, key, run.completed_at))
    for organization_id, key, next_run_at in await session.execute(
        select(Schedule.organization_id, WorkflowDefinition.key, Schedule.next_run_at)
        .join(WorkflowVersion, WorkflowVersion.id == Schedule.workflow_version_id)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
        .where(Schedule.organization_id.in_(readable), Schedule.status == "active")
        .order_by(Schedule.organization_id, Schedule.next_run_at)
        .distinct(Schedule.organization_id)
    ):
        upcoming[organization_id] = (key, next_run_at)
    return last, unresolved, activity, upcoming


__all__ = [
    "ATTENTION_RUN_STATUSES",
    "Facts",
    "LocationRead",
    "MetricRead",
    "OpportunityRead",
    "PERMISSIONS",
    "ReviewRead",
    "RunRead",
    "SectionTimer",
    "load_facts",
]
