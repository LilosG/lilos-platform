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
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import ColumnElement, Text, and_, cast, exists, func, or_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, aliased

from apps.api.app.execution.automations import automation_attention_counts
from apps.api.app.execution.models import Schedule, WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.growth.models import GrowthInitiative
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
from apps.api.app.products.content.models import (
    ContentOpportunity,
    ContentPublication,
    PublishingTarget,
)
from apps.api.app.products.gbp.performance_read import (
    PerformancePeriod,
    read_actions_by_organization,
)
from apps.api.app.products.leads.models import Lead, LeadSource
from apps.api.app.products.reviews.models import Review
from apps.api.app.products.seo.models import (
    SEOOpportunity,
    SEOPage,
    SEORecommendationRevision,
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.products.seo.site_change_service import (
    organization_mapping_limitation,
    page_mapping_limitation,
)
from apps.api.app.reporting_periods import comparison_window
from apps.api.app.routes.opportunity_subjects import (
    content_subjects,
    evidence_subject,
    growth_headline,
    url_path,
)

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
PERMISSIONS = (
    "seo.read",
    "content.read",
    "insights.read",
    "leads.read",
    "reviews.read",
    "workflows.read",
    "gbp.read",
)
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
    gbp_actions: dict[UUID, MetricRead] = field(default_factory=dict)
    last_completed: dict[UUID, RunRead] = field(default_factory=dict)
    unresolved: dict[UUID, list[RunRead]] = field(default_factory=dict)
    activity: dict[UUID, list[RunRead]] = field(default_factory=dict)
    next_work: dict[UUID, tuple[str, datetime]] = field(default_factory=dict)
    # Scheduled automations needing attention per client: the Automations screen's own rule.
    automations_needing_attention: dict[UUID, int] = field(default_factory=dict)


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
    async with timer.section("gbp_performance"):
        facts.gbp_actions = await gbp_actions(session, ids, allowed["gbp.read"], days)
    async with timer.section("workflows"):
        (
            facts.last_completed,
            facts.unresolved,
            facts.activity,
            facts.next_work,
        ) = await workflows(session, ids, allowed["workflows.read"], start)
        facts.automations_needing_attention = await automation_attention_counts(
            session, [i for i in ids if i in allowed["workflows.read"]]
        )
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
    # The Opportunities screen's rule: one finding is (organization, type, query or page), the
    # newest observation stands for it, and a change that is live and verified is not open work.
    open_filter = and_(
        SEOOpportunity.organization_id.in_(readable),
        SEOOpportunity.status.in_(OPEN_OPPORTUNITY_STATUSES),
        ~seo_is_live(),
    )
    newest = (
        select(
            SEOOpportunity.id.label("id"),
            SEOOpportunity.organization_id.label("organization_id"),
            SEOOpportunity.opportunity_type.label("opportunity_type"),
            SEOOpportunity.status.label("status"),
            SEOOpportunity.priority_score.label("priority"),
            SEOOpportunity.evidence.label("evidence"),
            func.row_number()
            .over(
                partition_by=seo_dedupe_columns(),
                order_by=(SEOOpportunity.updated_at.desc(), SEOOpportunity.id.desc()),
            )
            .label("recency"),
        )
        .where(open_filter)
        .subquery()
    )
    for organization_id, total in await session.execute(
        select(newest.c.organization_id, func.count())
        .where(newest.c.recency == 1)
        .group_by(newest.c.organization_id)
    ):
        counts[organization_id] = int(total)
    for organization_id in readable:
        counts.setdefault(organization_id, 0)
    ranked = (
        select(
            newest.c.id,
            newest.c.organization_id,
            newest.c.opportunity_type,
            newest.c.status,
            newest.c.priority,
            newest.c.evidence,
            func.row_number()
            .over(
                partition_by=newest.c.organization_id,
                order_by=newest.c.priority.desc().nulls_last(),
            )
            .label("rank"),
        )
        .where(newest.c.recency == 1)
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


async def gbp_actions(
    session: AsyncSession, ids: list[UUID], permitted: set[UUID], days: int
) -> dict[UUID, MetricRead]:
    """Calls, website clicks and direction requests for every readable client, in one pass."""
    readable = [i for i in ids if i in permitted]
    rows = await read_actions_by_organization(session, readable, PerformancePeriod(f"{days}d"))
    state = {"partial": "available", "not_synced": "no_data"}
    return {
        organization_id: MetricRead(
            state.get(read.availability.value, read.availability.value),
            float(read.current) if read.current is not None else None,
            float(read.previous) if read.previous is not None else None,
            read.freshness_at,
        )
        for organization_id, read in rows.items()
    }


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


# ---------------------------------------------------------------------------------------------
# Opportunities: one list across every kind. Deterministic, set-based, no per-item queries.
# ---------------------------------------------------------------------------------------------

OpportunityKind = Literal["seo", "content", "growth"]
OPPORTUNITY_KINDS: tuple[OpportunityKind, ...] = ("seo", "content", "growth")
KIND_PERMISSION: dict[OpportunityKind, str] = {
    "seo": "seo.read",
    "content": "content.read",
    "growth": "workflows.read",
}
# The open list: work that still needs a decision or is in flight. Everything else, and an
# SEO change that is verified live, is "done".
OPEN_STATUSES: dict[OpportunityKind, tuple[str, ...]] = {
    "seo": OPEN_OPPORTUNITY_STATUSES,
    "content": ("identified", "validated"),
    "growth": ("proposed", "approved", "executing"),
}
OpportunityState = Literal["open", "done"]
Lifecycle = Literal["open", "live", "done"]
ImportanceReason = Literal["KEY_EVENTS_INFERRED"]
PriorityBand = Literal["high", "medium", "low"]
BAND_FLOOR: dict[PriorityBand, float] = {"high": 70, "medium": 40, "low": 0}
SiteChangeAvailability = Literal["configured", "not_configured", "not_applicable"]
EARLIER_OBSERVATIONS_PER_ITEM = 20


def priority_band(priority: float | None) -> PriorityBand | None:
    if priority is None:
        return None
    return "high" if priority >= 70 else "medium" if priority >= 40 else "low"


@dataclass(frozen=True)
class Observation:
    """An older sighting of the same finding, rolled into the newest one's evidence history."""

    id: UUID
    observed_at: datetime
    status: str
    priority: float | None


@dataclass(frozen=True)
class OpportunityListRow:
    kind: OpportunityKind
    id: UUID
    organization_id: UUID
    location_id: UUID | None
    website_id: UUID | None
    page_id: UUID | None
    source_type: str
    status: str
    priority: float | None
    evidence: dict[str, object]
    score_explanation: dict[str, object]
    observed_at: datetime
    headline: str | None
    confidence: float | None
    source_count: int | None
    latest_revision_status: str | None
    site_change: SiteChangeAvailability
    summary: str | None = None
    subject_query: str | None = None
    subject_path: str | None = None
    lifecycle: Lifecycle = "open"
    verified_at: datetime | None = None
    importance_reason: ImportanceReason | None = None
    earlier: tuple[Observation, ...] = ()
    target_reference: str | None = None


def seo_row(row: SEOOpportunity) -> OpportunityListRow:
    subject = evidence_subject(row.evidence or {}, None)
    explanation = row.score_explanation or {}
    return OpportunityListRow(
        kind="seo",
        id=row.id,
        organization_id=row.organization_id,
        location_id=row.location_id,
        website_id=row.website_id,
        page_id=row.page_id,
        source_type=row.opportunity_type,
        status=row.status,
        priority=float(row.priority_score),
        evidence=row.evidence or {},
        score_explanation=explanation,
        observed_at=row.updated_at,
        headline=None,
        confidence=None,
        source_count=None,
        latest_revision_status=None,
        site_change="not_configured",
        subject_query=subject.query,
        subject_path=subject.path,
        lifecycle="open" if row.status in OPEN_STATUSES["seo"] else "done",
        importance_reason="KEY_EVENTS_INFERRED"
        if explanation.get("business_importance_state") == "inferred"
        else None,
    )


def content_row(row: ContentOpportunity) -> OpportunityListRow:
    return OpportunityListRow(
        kind="content",
        id=row.id,
        organization_id=row.organization_id,
        location_id=row.location_id,
        website_id=None,
        page_id=None,
        source_type=row.opportunity_type,
        status=row.status,
        priority=float(row.priority_score),
        evidence=row.evidence_document or {},
        score_explanation={},
        observed_at=row.updated_at,
        headline=None,
        confidence=None,
        source_count=None,
        latest_revision_status=None,
        site_change="not_applicable",
        lifecycle="open" if row.status in OPEN_STATUSES["content"] else "done",
        target_reference=row.target_reference,
    )


def growth_row(row: GrowthInitiative) -> OpportunityListRow:
    return OpportunityListRow(
        kind="growth",
        id=row.id,
        organization_id=row.organization_id,
        location_id=row.location_id,
        website_id=None,
        page_id=None,
        source_type="growth_plan",
        status=row.status,
        priority=float(row.priority_score),
        evidence={},
        score_explanation={},
        observed_at=row.updated_at,
        headline=growth_headline(row.objective),
        confidence=float(row.confidence),
        source_count=len(row.source_references or []),
        latest_revision_status=None,
        site_change="not_applicable",
        summary=row.objective,
        lifecycle="open" if row.status in OPEN_STATUSES["growth"] else "done",
    )


def band_clause(
    column: ColumnElement[float] | InstrumentedAttribute[int], band: PriorityBand | None
) -> list[ColumnElement[bool]]:
    if band is None:
        return []
    clauses: list[ColumnElement[bool]] = [column >= BAND_FLOOR[band]]
    if band == "medium":
        clauses.append(column < BAND_FLOOR["high"])
    if band == "low":
        clauses.append(column < BAND_FLOOR["medium"])
    return clauses


def seo_is_live() -> ColumnElement[bool]:
    """A site change for this opportunity was applied and its live read-back verified."""
    return exists(
        select(1)
        .select_from(ContentPublication)
        .join(
            SEORecommendationRevision,
            SEORecommendationRevision.id == ContentPublication.seo_recommendation_revision_id,
        )
        .where(
            SEORecommendationRevision.opportunity_id == SEOOpportunity.id,
            ContentPublication.organization_id == SEOOpportunity.organization_id,
            ContentPublication.publication_kind == "site_change",
            ContentPublication.verification_status == "verified",
        )
    )


def seo_dedupe_columns() -> list[Any]:
    """One finding is (organization, type, query or page)."""
    return [
        SEOOpportunity.organization_id,
        SEOOpportunity.opportunity_type,
        func.coalesce(
            SEOOpportunity.evidence["query"].astext, cast(SEOOpportunity.page_id, Text), ""
        ),
    ]


def seo_dedupe_key(row: SEOOpportunity) -> tuple[object, ...]:
    query = (row.evidence or {}).get("query")
    return (
        row.organization_id,
        row.opportunity_type,
        query if isinstance(query, str) else (str(row.page_id) if row.page_id else ""),
    )


def content_dedupe_columns() -> list[Any]:
    return [
        ContentOpportunity.organization_id,
        ContentOpportunity.opportunity_type,
        ContentOpportunity.target_reference,
    ]


def content_dedupe_key(row: ContentOpportunity) -> tuple[object, ...]:
    return (row.organization_id, row.opportunity_type, row.target_reference)


def growth_dedupe_columns() -> list[Any]:
    return [GrowthInitiative.organization_id, GrowthInitiative.objective]


def growth_dedupe_key(row: GrowthInitiative) -> tuple[object, ...]:
    return (row.organization_id, row.objective)


async def newest_per_finding(
    session: AsyncSession,
    model: type[Any],
    dedupe: list[Any],
    conditions: list[ColumnElement[bool]],
    band: PriorityBand | None,
    *,
    limit: int,
) -> list[Any]:
    """The newest row of each finding among ``conditions``, best priority first."""
    ranked = (
        select(
            model,
            func.row_number()
            .over(partition_by=dedupe, order_by=(model.updated_at.desc(), model.id.desc()))
            .label("recency"),
        )
        .where(*conditions)
        .subquery()
    )
    newest = aliased(model, ranked)
    statement = (
        select(newest)
        .where(ranked.c.recency == 1, *band_clause(newest.priority_score, band))
        .order_by(newest.priority_score.desc(), newest.id.asc())
        .limit(limit)
    )
    return list(await session.scalars(statement))


async def earlier_observations(
    session: AsyncSession,
    model: type[Any],
    dedupe: list[Any],
    key_of: Callable[[Any], tuple[object, ...]],
    rows: list[Any],
) -> dict[tuple[object, ...], tuple[Observation, ...]]:
    """Older sightings of each row's finding, any status, newest first. Nothing is deleted."""
    keys = {key_of(row) for row in rows}
    if not keys:
        return {}
    newest = {key_of(row): (row.updated_at, row.id) for row in rows}
    found: dict[tuple[object, ...], list[Observation]] = defaultdict(list)
    for other in await session.scalars(
        select(model)
        .where(tuple_(*dedupe).in_(keys))
        .order_by(model.updated_at.desc(), model.id.desc())
    ):
        key = key_of(other)
        if key not in newest or other.id == newest[key][1] or other.updated_at > newest[key][0]:
            continue
        if len(found[key]) < EARLIER_OBSERVATIONS_PER_ITEM:
            found[key].append(
                Observation(
                    id=other.id,
                    observed_at=other.updated_at,
                    status=other.status,
                    priority=float(other.priority_score),
                )
            )
    return {key: tuple(value) for key, value in found.items()}


async def opportunity_rows(
    session: AsyncSession,
    permitted: dict[OpportunityKind, set[UUID]],
    *,
    organization_id: UUID | None = None,
    kind: OpportunityKind | None = None,
    band: PriorityBand | None = None,
    state: OpportunityState = "open",
    limit: int,
    offset: int,
) -> tuple[list[OpportunityListRow], bool]:
    """The page of opportunities across every permitted kind, ranked by priority.

    One row per finding: the newest observation, with older ones rolled into its evidence
    history. ``state`` selects open work or done work. Each kind is one query bounded by
    ``offset + limit + 1``; history, latest SEO revision, page rows and publishing targets are
    a handful more. The count of queries never depends on the number of opportunities.
    """
    window = offset + limit + 1

    def scope(current: OpportunityKind) -> set[UUID]:
        orgs = permitted.get(current, set())
        if organization_id is not None:
            orgs = orgs & {organization_id}
        return set() if kind is not None and kind != current else orgs

    gathered: list[OpportunityListRow] = []
    if orgs := scope("seo"):
        open_seo = and_(SEOOpportunity.status.in_(OPEN_STATUSES["seo"]), ~seo_is_live())
        seo = await newest_per_finding(
            session,
            SEOOpportunity,
            seo_dedupe_columns(),
            [SEOOpportunity.organization_id.in_(orgs), open_seo if state == "open" else ~open_seo],
            band,
            limit=window,
        )
        history = await earlier_observations(
            session, SEOOpportunity, seo_dedupe_columns(), seo_dedupe_key, seo
        )
        gathered += [replace(seo_row(r), earlier=history.get(seo_dedupe_key(r), ())) for r in seo]
    if orgs := scope("content"):
        open_content = ContentOpportunity.status.in_(OPEN_STATUSES["content"])
        content = await newest_per_finding(
            session,
            ContentOpportunity,
            content_dedupe_columns(),
            [
                ContentOpportunity.organization_id.in_(orgs),
                open_content if state == "open" else ~open_content,
            ],
            band,
            limit=window,
        )
        history = await earlier_observations(
            session, ContentOpportunity, content_dedupe_columns(), content_dedupe_key, content
        )
        gathered += [
            replace(content_row(r), earlier=history.get(content_dedupe_key(r), ())) for r in content
        ]
    if orgs := scope("growth"):
        open_growth = GrowthInitiative.status.in_(OPEN_STATUSES["growth"])
        growth = await newest_per_finding(
            session,
            GrowthInitiative,
            growth_dedupe_columns(),
            [
                GrowthInitiative.organization_id.in_(orgs),
                open_growth if state == "open" else ~open_growth,
            ],
            band,
            limit=window,
        )
        history = await earlier_observations(
            session, GrowthInitiative, growth_dedupe_columns(), growth_dedupe_key, growth
        )
        gathered += [
            replace(growth_row(r), earlier=history.get(growth_dedupe_key(r), ())) for r in growth
        ]
    gathered.sort(key=lambda r: (-(r.priority or 0), r.kind, str(r.id)))
    page = gathered[offset : offset + limit]
    more = len(gathered) > offset + limit
    return await enrich(session, page), more


async def enrich(session: AsyncSession, rows: list[OpportunityListRow]) -> list[OpportunityListRow]:
    """Subjects for content rows, then lifecycle and site-change availability for SEO rows."""
    return await with_seo_state(session, await with_content_subjects(session, rows))


async def with_content_subjects(
    session: AsyncSession, rows: list[OpportunityListRow]
) -> list[OpportunityListRow]:
    """The query or page a content opportunity is about, resolved from its typed reference."""
    content = [r for r in rows if r.kind == "content" and r.target_reference]
    if not content:
        return rows
    subjects = await content_subjects(
        session, [(r.organization_id, r.target_reference or "") for r in content]
    )
    result: list[OpportunityListRow] = []
    for row in rows:
        subject = subjects.get((row.organization_id, row.target_reference or ""))
        result.append(
            replace(row, subject_query=subject.query, subject_path=subject.path)
            if row.kind == "content" and subject is not None
            else row
        )
    return result


async def with_seo_state(
    session: AsyncSession, rows: list[OpportunityListRow]
) -> list[OpportunityListRow]:
    """Latest recommendation, live state and site-change availability for the SEO rows.

    Availability reads the organization's publishing target and page map. A page that is
    known is checked against the map; an opportunity not tied to one page is available when
    the client's target maps pages at all.
    """
    seo = [r for r in rows if r.kind == "seo"]
    if not seo:
        return rows
    ids = [r.id for r in seo]
    latest: dict[UUID, str] = {}
    for opportunity_id, status in await session.execute(
        select(SEORecommendationRevision.opportunity_id, SEORecommendationRevision.status)
        .where(SEORecommendationRevision.opportunity_id.in_(ids))
        .distinct(SEORecommendationRevision.opportunity_id)
        .order_by(
            SEORecommendationRevision.opportunity_id,
            SEORecommendationRevision.revision_number.desc(),
        )
    ):
        latest[opportunity_id] = status
    verified: dict[UUID, datetime | None] = {}
    for opportunity_id, verified_at in await session.execute(
        select(SEORecommendationRevision.opportunity_id, func.max(ContentPublication.verified_at))
        .join(
            ContentPublication,
            ContentPublication.seo_recommendation_revision_id == SEORecommendationRevision.id,
        )
        .where(
            SEORecommendationRevision.opportunity_id.in_(ids),
            ContentPublication.publication_kind == "site_change",
            ContentPublication.verification_status == "verified",
        )
        .group_by(SEORecommendationRevision.opportunity_id)
    ):
        verified[opportunity_id] = verified_at
    org_ids = {r.organization_id for r in seo}
    page_ids = {r.page_id for r in seo if r.page_id}
    urls = (
        {
            page_id: url
            for page_id, url in await session.execute(
                select(SEOPage.id, SEOPage.normalized_url).where(
                    SEOPage.organization_id.in_(org_ids), SEOPage.id.in_(page_ids)
                )
            )
        }
        if page_ids
        else {}
    )
    by_org: dict[UUID, list[PublishingTarget]] = defaultdict(list)
    for active in await session.scalars(
        select(PublishingTarget).where(
            PublishingTarget.organization_id.in_(org_ids), PublishingTarget.status == "active"
        )
    ):
        by_org[active.organization_id].append(active)
    result: list[OpportunityListRow] = []
    for row in rows:
        if row.kind != "seo":
            result.append(row)
            continue
        targets = by_org.get(row.organization_id, [])
        target: PublishingTarget | None = targets[0] if len(targets) == 1 else None
        page_url = urls.get(row.page_id) if row.page_id else None
        limitation = (
            page_mapping_limitation(target, page_url)
            if page_url
            else organization_mapping_limitation(target)
        )
        live_at = verified.get(row.id)
        live = row.id in verified
        result.append(
            replace(
                row,
                latest_revision_status=latest.get(row.id),
                site_change="not_configured" if limitation else "configured",
                subject_path=url_path(page_url) if page_url else row.subject_path,
                lifecycle="live" if live else row.lifecycle,
                verified_at=live_at,
            )
        )
    return result
