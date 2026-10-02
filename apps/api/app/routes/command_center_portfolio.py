"""Portfolio read projection for the Command Center dashboard.

Aggregates canonical persisted evidence for every organization the caller belongs to.
No provider I/O, no writes. Each value carries its source and availability so the
frontend never shows missing data as zero.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Select, func, select

from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.execution.models import Schedule, WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.industries.models import Industry
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.models import Location
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.leads.models import Lead
from apps.api.app.products.reviews.models import Review
from apps.api.app.products.seo.decision import GROWTH_TYPES
from apps.api.app.products.seo.models import SEOOpportunity
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from apps.api.app.routes.command_center_search import allowed
from apps.api.app.routes.seo import Session, no_store, service

router = APIRouter(
    prefix="/api/v1/command-center",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(no_store)],
)
access_service = AccessControlService()

Availability = Literal["available", "no_data", "not_connected", "not_tracked", "not_permitted"]
REPORTING_DAYS = (7, 28, 90)
OPEN_OPPORTUNITY_STATUSES = ("identified", "recommended", "approved")
ATTENTION_RUN_STATUSES = ("failed", "escalated", "retry_scheduled")


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MetricValue(DTO):
    current: float | None
    previous: float | None
    percent_delta: float | None
    source: Literal["ga4", "search_console", "leads", "reviews", "rank_scan"]
    availability: Availability
    freshness_at: datetime | None = None


class ReviewSummary(DTO):
    availability: Availability
    total: int | None
    new_in_period: int | None
    average_rating: float | None


class WorkItem(DTO):
    workflow_key: str
    status: str
    at: datetime | None
    failure_code: str | None = None


class ClientRow(DTO):
    organization_id: UUID
    slug: str
    name: str
    location: str | None
    category: str | None
    location_count: int
    organic_sessions: MetricValue
    search_clicks: MetricValue
    average_position: MetricValue
    leads: MetricValue
    local_visibility: MetricValue
    reviews: ReviewSummary
    open_opportunities: int | None
    health: Literal["healthy", "needs_attention", "not_configured"]
    health_reasons: list[str]
    last_activity: WorkItem | None
    next_work: WorkItem | None


class AttentionItem(DTO):
    organization_id: UUID
    organization_name: str
    organization_slug: str
    code: str
    severity: Literal["critical", "high", "medium"]
    occurred_at: datetime | None
    reference: str | None


class OpportunityItem(DTO):
    id: UUID
    organization_id: UUID
    organization_name: str
    organization_slug: str
    opportunity_type: str
    classification: Literal["Issue", "Growth Opportunity"]
    status: str
    priority: float | None
    query: str | None
    page: str | None
    impressions: float | None


class SystemHealth(DTO):
    key: Literal["google", "analytics", "automations"]
    status: Literal["healthy", "needs_attention", "error", "not_connected"]
    affected_clients: int


class PortfolioTotals(DTO):
    website_leads: MetricValue
    organic_sessions: MetricValue
    new_reviews: int | None
    average_rating: float | None
    reporting_attention: int
    local_visibility: MetricValue


class PortfolioOverview(DTO):
    generated_at: datetime
    days: int
    period_start: datetime
    period_end: datetime
    client_count: int
    location_count: int
    totals: PortfolioTotals
    clients: list[ClientRow]
    attention: list[AttentionItem]
    opportunities: list[OpportunityItem]
    activity: list["ActivityItem"]
    upcoming: list["UpcomingItem"]
    systems: list[SystemHealth]


class ActivityItem(DTO):
    organization_id: UUID
    organization_name: str
    organization_slug: str
    workflow_key: str
    completed_at: datetime


class UpcomingItem(DTO):
    organization_id: UUID
    organization_name: str
    organization_slug: str
    workflow_key: str
    next_run_at: datetime


PortfolioOverview.model_rebuild()

MEANINGFUL_ACTIVITY = (
    "gbp.publish_post",
    "reviews.publish_response",
    "content.publish",
    "seo.apply_site_change",
    "seo.crawl_or_analysis",
)


def percent(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def metric(
    source: str,
    availability: str,
    current: float | None = None,
    previous: float | None = None,
    freshness_at: datetime | None = None,
) -> MetricValue:
    return MetricValue.model_validate(
        {
            "current": current,
            "previous": previous,
            "percent_delta": percent(current, previous),
            "source": source,
            "availability": availability,
            "freshness_at": freshness_at,
        }
    )


def report_metric(report: dict[str, object], key: str, source: str) -> MetricValue:
    """Read one comparison from a canonical performance report without inventing zeros."""
    if not report.get("connected"):
        return metric(source, "not_connected")
    freshness = report.get("freshness") or {}
    synced = freshness.get("last_synced_at") if isinstance(freshness, dict) else None
    synced_at = datetime.fromisoformat(synced) if isinstance(synced, str) else None
    metrics = report.get("metrics") or {}
    value = metrics.get(key) if isinstance(metrics, dict) else None
    if not isinstance(value, dict) or value.get("current") is None:
        return metric(source, "no_data", freshness_at=synced_at)
    return metric(
        source,
        "available",
        float(value["current"]),
        float(value["previous"]) if value.get("previous") is not None else None,
        synced_at,
    )


def workflow_keyed(organization_id: UUID) -> Select[tuple[WorkflowRun, str]]:
    return (
        select(WorkflowRun, WorkflowDefinition.key)
        .join(WorkflowVersion, WorkflowVersion.id == WorkflowRun.workflow_version_id)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
        .where(WorkflowRun.organization_id == organization_id)
    )


@router.get("/portfolio", response_model=PortfolioOverview)
async def portfolio_overview(
    request: Request,
    session: Session,
    principal: Authenticated,
    days: int = Query(28),
) -> PortfolioOverview:
    if days not in REPORTING_DAYS:
        raise RequestValidationError(
            [
                {
                    "loc": ("query", "days"),
                    "type": "literal_error",
                    "msg": "Input should be 7, 28 or 90",
                    "input": days,
                }
            ]
        )
    now = datetime.now(UTC)
    start = now - timedelta(days=days)
    previous_start = start - timedelta(days=days)
    pairs = await access_service.list_my_organizations(session, principal.platform_user_id)
    organizations = [
        organization
        for membership, organization in pairs
        if membership.status == "active" and organization.status.value == "active"
    ]
    clients: list[ClientRow] = []
    attention: list[AttentionItem] = []
    opportunities: list[OpportunityItem] = []
    activity: list[ActivityItem] = []
    upcoming: list[UpcomingItem] = []
    location_total = 0

    for org in organizations:
        oid = org.id

        async def can(permission: str, organization_id: UUID = oid) -> bool:
            return await allowed(session, principal, organization_id, request, permission)

        locations = list(
            await session.scalars(
                select(Location)
                .where(Location.organization_id == oid, Location.status == "active")
                .order_by(Location.is_primary.desc(), Location.created_at)
            )
        )
        location_total += len(locations)
        primary = locations[0] if locations else None
        place = (
            ", ".join(part for part in (primary.city, primary.region) if part) if primary else ""
        )
        industry = (
            await session.scalar(select(Industry.name).where(Industry.id == org.industry_id))
            if org.industry_id
            else None
        )

        # Search Console and GA4 come from their canonical reporting services.
        search_clicks = metric("search_console", "not_permitted")
        position = metric("search_console", "not_permitted")
        open_count: int | None = None
        if await can("seo.read"):
            websites = [
                w for w in await service.list_websites(session, oid) if w.status == "active"
            ]
            if websites:
                report = await SearchConsoleService().performance_report(
                    session, oid, websites[0].id, days=days
                )
                search_clicks = report_metric(report, "clicks", "search_console")
                position = report_metric(report, "position", "search_console")
            else:
                search_clicks = metric("search_console", "not_connected")
                position = metric("search_console", "not_connected")
            open_count = int(
                await session.scalar(
                    select(func.count())
                    .select_from(SEOOpportunity)
                    .where(
                        SEOOpportunity.organization_id == oid,
                        SEOOpportunity.status.in_(OPEN_OPPORTUNITY_STATUSES),
                    )
                )
                or 0
            )
            for item in await session.scalars(
                select(SEOOpportunity)
                .where(
                    SEOOpportunity.organization_id == oid,
                    SEOOpportunity.status.in_(OPEN_OPPORTUNITY_STATUSES),
                )
                .order_by(SEOOpportunity.priority_score.desc().nulls_last())
                .limit(3)
            ):
                evidence = item.evidence or {}
                impressions = evidence.get("impressions")
                opportunities.append(
                    OpportunityItem(
                        id=item.id,
                        organization_id=oid,
                        organization_name=org.name,
                        organization_slug=org.slug,
                        opportunity_type=item.opportunity_type,
                        classification="Growth Opportunity"
                        if item.opportunity_type in GROWTH_TYPES
                        else "Issue",
                        status=item.status,
                        priority=item.priority_score,
                        query=str(evidence["query"]) if evidence.get("query") else None,
                        page=str(evidence["page"]) if evidence.get("page") else None,
                        impressions=float(impressions)
                        if isinstance(impressions, (int, float))
                        else None,
                    )
                )

        sessions = metric("ga4", "not_permitted")
        if await can("insights.read"):
            ga4 = await AnalyticsService().performance_report(session, oid, days=days)
            sessions = report_metric(ga4, "ga4.sessions", "ga4")

        leads = metric("leads", "not_permitted")
        if await can("leads.read"):

            async def lead_count(
                lower: datetime, upper: datetime, organization_id: UUID = oid
            ) -> int:
                return int(
                    await session.scalar(
                        select(func.count())
                        .select_from(Lead)
                        .where(
                            Lead.organization_id == organization_id,
                            Lead.duplicate_of_lead_id.is_(None),
                            Lead.received_at >= lower,
                            Lead.received_at < upper,
                        )
                    )
                    or 0
                )

            leads = metric(
                "leads",
                "available",
                await lead_count(start, now),
                await lead_count(previous_start, start),
            )

        reviews = ReviewSummary(
            availability="not_permitted", total=None, new_in_period=None, average_rating=None
        )
        if await can("reviews.read"):
            total, average, recent = (
                await session.execute(
                    select(
                        func.count(Review.id),
                        func.avg(Review.rating),
                        func.count(Review.id).filter(Review.review_created_at >= start),
                    ).where(Review.organization_id == oid)
                )
            ).one()
            reviews = ReviewSummary(
                availability="available" if total else "no_data",
                total=int(total) if total else None,
                new_in_period=int(recent) if total else None,
                average_rating=round(float(average), 1) if average is not None else None,
            )

        # Integration health: the best connection per provider is what counts, so an
        # old disconnected record next to a working reconnection is not an alert.
        reasons: list[str] = []
        best: dict[str, str] = {}
        rank = {"connected": 4, "degraded": 3, "pending": 2, "reconnect_required": 1}
        for key, status in await session.execute(
            select(Provider.key, IntegrationConnection.status)
            .join(Provider, Provider.id == IntegrationConnection.provider_id)
            .where(IntegrationConnection.organization_id == oid)
        ):
            if rank.get(status, 0) >= rank.get(best.get(key, ""), -1):
                best[key] = status
        google = best.get("google_business_profile")
        if google is None:
            reasons.append("GOOGLE_NOT_CONNECTED")
        elif google != "connected":
            reasons.append("GOOGLE_RECONNECT_REQUIRED")
            attention.append(
                AttentionItem(
                    organization_id=oid,
                    organization_name=org.name,
                    organization_slug=org.slug,
                    code="GOOGLE_RECONNECT_REQUIRED",
                    severity="critical",
                    occurred_at=None,
                    reference=None,
                )
            )
        if search_clicks.availability == "not_connected":
            reasons.append("SEARCH_CONSOLE_NOT_CONNECTED")
        if sessions.availability == "not_connected":
            reasons.append("GA4_NOT_CONNECTED")

        last_activity: WorkItem | None = None
        next_work: WorkItem | None = None
        if await can("workflows.read"):
            base = workflow_keyed(oid)
            latest = (
                await session.execute(
                    base.where(WorkflowRun.status == "completed")
                    .order_by(WorkflowRun.completed_at.desc().nulls_last())
                    .limit(1)
                )
            ).first()
            if latest:
                run, key = latest
                last_activity = WorkItem(workflow_key=key, status=run.status, at=run.completed_at)
            for run, key in await session.execute(
                base.where(
                    WorkflowRun.status.in_(ATTENTION_RUN_STATUSES),
                    WorkflowRun.updated_at >= start,
                ).order_by(WorkflowRun.updated_at.desc())
            ):
                reasons.append("WORKFLOW_ATTENTION")
                attention.append(
                    AttentionItem(
                        organization_id=oid,
                        organization_name=org.name,
                        organization_slug=org.slug,
                        code=f"WORKFLOW_{run.status.upper()}",
                        severity="high" if run.status != "retry_scheduled" else "medium",
                        occurred_at=run.updated_at,
                        reference=f"{key}:{run.failure_code or ''}".rstrip(":"),
                    )
                )
            for run, key in await session.execute(
                base.where(
                    WorkflowRun.status == "completed",
                    WorkflowRun.completed_at >= start,
                    WorkflowDefinition.key.in_(MEANINGFUL_ACTIVITY),
                )
                .order_by(WorkflowRun.completed_at.desc())
                .limit(5)
            ):
                activity.append(
                    ActivityItem(
                        organization_id=oid,
                        organization_name=org.name,
                        organization_slug=org.slug,
                        workflow_key=key,
                        completed_at=run.completed_at or run.updated_at,
                    )
                )
            schedule = await session.scalar(
                select(Schedule)
                .where(Schedule.organization_id == oid, Schedule.status == "active")
                .order_by(Schedule.next_run_at)
                .limit(1)
            )
            if schedule:
                next_work = WorkItem(
                    workflow_key=schedule.key, status="scheduled", at=schedule.next_run_at
                )
                upcoming.append(
                    UpcomingItem(
                        organization_id=oid,
                        organization_name=org.name,
                        organization_slug=org.slug,
                        workflow_key=schedule.key,
                        next_run_at=schedule.next_run_at,
                    )
                )

        health: Literal["healthy", "needs_attention", "not_configured"] = (
            "not_configured"
            if "GOOGLE_NOT_CONNECTED" in reasons
            else "needs_attention"
            if reasons
            else "healthy"
        )
        clients.append(
            ClientRow(
                organization_id=oid,
                slug=org.slug,
                name=org.name,
                location=place or None,
                category=industry,
                location_count=len(locations),
                organic_sessions=sessions,
                search_clicks=search_clicks,
                average_position=position,
                leads=leads,
                local_visibility=metric("rank_scan", "not_tracked"),
                reviews=reviews,
                open_opportunities=open_count,
                health=health,
                health_reasons=sorted(set(reasons)),
                last_activity=last_activity,
                next_work=next_work,
            )
        )

    def summed(field: str, source: str) -> MetricValue:
        rows = [getattr(c, field) for c in clients if getattr(c, field).availability == "available"]
        if not rows:
            return metric(source, "no_data" if clients else "not_connected")
        current = sum(r.current or 0 for r in rows)
        previous_rows = [r.previous for r in rows if r.previous is not None]
        previous = sum(previous_rows) if len(previous_rows) == len(rows) else None
        return metric(source, "available", current, previous)

    rated = [c.reviews for c in clients if c.reviews.average_rating is not None]
    new_reviews = [c.reviews.new_in_period for c in clients if c.reviews.new_in_period is not None]
    severity_order = {"critical": 0, "high": 1, "medium": 2}
    attention.sort(
        key=lambda a: (
            severity_order[a.severity],
            -(a.occurred_at.timestamp() if a.occurred_at else now.timestamp()),
        )
    )
    opportunities.sort(key=lambda o: -(o.priority or 0))
    activity.sort(key=lambda a: a.completed_at, reverse=True)
    upcoming.sort(key=lambda u: u.next_run_at)
    google_issue = sum(1 for c in clients if "GOOGLE_RECONNECT_REQUIRED" in c.health_reasons)
    analytics_issue = sum(1 for c in clients if "GA4_NOT_CONNECTED" in c.health_reasons)
    automation_issue = len({a.organization_id for a in attention if a.code.startswith("WORKFLOW_")})
    return PortfolioOverview(
        generated_at=now,
        days=days,
        period_start=start,
        period_end=now,
        client_count=len(clients),
        location_count=location_total,
        totals=PortfolioTotals(
            website_leads=summed("leads", "leads"),
            organic_sessions=summed("organic_sessions", "ga4"),
            new_reviews=sum(new_reviews) if new_reviews else None,
            average_rating=round(sum(r.average_rating or 0 for r in rated) / len(rated), 1)
            if rated
            else None,
            reporting_attention=sum(1 for c in clients if c.health != "healthy"),
            local_visibility=metric("rank_scan", "not_tracked"),
        ),
        clients=clients,
        attention=attention[:50],
        opportunities=opportunities[:10],
        activity=activity[:10],
        upcoming=upcoming[:10],
        systems=[
            SystemHealth(
                key="google",
                status="needs_attention" if google_issue else "healthy",
                affected_clients=google_issue,
            ),
            SystemHealth(
                key="analytics",
                status="needs_attention" if analytics_issue else "healthy",
                affected_clients=analytics_issue,
            ),
            SystemHealth(
                key="automations",
                status="error" if automation_issue else "healthy",
                affected_clients=automation_issue,
            ),
        ],
    )
