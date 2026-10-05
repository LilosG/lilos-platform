"""Portfolio read projection for the Command Center dashboard.

Aggregates canonical persisted evidence for every organization the caller belongs to.
No provider I/O, no writes. Each value carries its source and availability so the
frontend never shows missing data as zero.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Literal, TypedDict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import AuthenticatedPrincipal
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authorization.service import assurance_satisfies
from apps.api.app.errors import request_correlation_id
from apps.api.app.insights.aggregation_service import InsightsService
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.platform_admin.repository import PlatformAdministratorRepository
from apps.api.app.products.seo.decision import GROWTH_TYPES
from apps.api.app.routes.command_center import (
    OpportunityList,
    OpportunityView,
    authorization,
    project_row,
)
from apps.api.app.routes.command_center_reads import (
    KIND_PERMISSION,
    PERMISSIONS,
    Facts,
    MetricRead,
    OpportunityKind,
    OpportunityState,
    PriorityBand,
    SectionTimer,
    load_facts,
    opportunity_rows,
)
from apps.api.app.routes.seo import Session, no_store

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
    average_local_rank: MetricValue
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
    # Typed cause for workflow attention, so the UI shows what failed without parsing text.
    workflow_key: str | None = None
    failure_code: str | None = None


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


class ClientSystem(DTO):
    """One integration or workflow family for a single client."""

    key: Literal["google", "analytics", "search_console", "automations"]
    status: Literal["healthy", "needs_attention", "error", "not_connected", "not_permitted"]


class VisibleClient(DTO):
    organization_id: UUID
    slug: str
    name: str
    status: str
    access: Literal["member", "platform_administrator"]


class VisibleClients(DTO):
    platform_administrator: bool
    data: list[VisibleClient]


class InsightsSummary(DTO):
    """The former Insights summary, folded into the client overview."""

    availability: Availability
    workflow_runs: dict[str, int]
    growth_outcomes: dict[str, int]
    seo_opportunities: dict[str, int]
    seo_opportunities_blocked: int | None
    content_publications: dict[str, int]
    reviews: dict[str, int]


class ClientOverview(DTO):
    generated_at: datetime
    days: int
    period_start: datetime
    period_end: datetime
    access: Literal["member", "platform_administrator"]
    client: ClientRow
    attention: list[AttentionItem]
    opportunities: list[OpportunityItem]
    activity: list["ActivityItem"]
    upcoming: list["UpcomingItem"]
    systems: list[ClientSystem]
    insights: InsightsSummary


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
ClientOverview.model_rebuild()


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


def shaped(source: str, read: MetricRead | None) -> MetricValue:
    """An absent read means the caller may not read that source; it is never zero."""
    if read is None:
        return metric(source, "not_permitted")
    return metric(source, read.availability, read.current, read.previous, read.freshness_at)


class Owner(TypedDict):
    organization_id: UUID
    organization_name: str
    organization_slug: str


@dataclass
class ClientBundle:
    """Everything one organization contributes to the portfolio and its own overview."""

    row: ClientRow
    locations: int
    attention: list[AttentionItem] = field(default_factory=list)
    opportunities: list[OpportunityItem] = field(default_factory=list)
    activity: list[ActivityItem] = field(default_factory=list)
    upcoming: list[UpcomingItem] = field(default_factory=list)
    systems: list[ClientSystem] = field(default_factory=list)


@dataclass(frozen=True)
class Scope:
    """Organizations the caller may see, decided on the server from the principal alone."""

    organizations: list[Organization]
    members: frozenset[UUID]
    platform_administrator: bool

    def access(self, organization_id: UUID) -> Literal["member", "platform_administrator"]:
        return "member" if organization_id in self.members else "platform_administrator"


platform_administrators = PlatformAdministratorRepository()


async def visible_scope(session: Session, principal: AuthenticatedPrincipal) -> Scope:
    """A client user sees their own organizations; an active AAL2 platform administrator sees all.

    Platform-administrator elevation never consults the request, so a client cannot widen it.
    """
    pairs = await access_service.list_my_organizations(session, principal.platform_user_id)
    owned = [
        (membership, organization)
        for membership, organization in pairs
        if membership.status == "active" and organization.status.value == "active"
    ]
    members = frozenset(organization.id for _, organization in owned)
    administrator = (
        principal.user_status is UserStatus.ACTIVE
        and assurance_satisfies(principal.assurance_level, AssuranceLevel.AAL2)
        and await platform_administrators.get_active_by_user_profile_id(
            session, principal.platform_user_id
        )
        is not None
    )
    if not administrator:
        ordered = sorted(owned, key=lambda pair: pair[1].name.lower())
        return Scope([organization for _, organization in ordered], members, False)
    everyone = list(
        await session.scalars(
            select(Organization)
            .where(Organization.status == OrganizationStatus.ACTIVE)
            .order_by(func.lower(Organization.name))
        )
    )
    return Scope(everyone, members, True)


async def permitted_organizations(
    session: Session,
    principal: AuthenticatedPrincipal,
    scope: Scope,
    organizations: list[Organization],
    correlation_id: str,
) -> dict[str, set[UUID]]:
    """Which of ``organizations`` the caller may read, per permission, in constant queries."""
    ids = {organization.id for organization in organizations}
    if scope.platform_administrator:
        # An administrator reads every client's evidence; writes stay behind the
        # per-organization gate and are not reachable from these read projections.
        return {permission: set(ids) for permission in PERMISSIONS}
    decisions = await authorization.evaluate_many(
        session,
        principal,
        list(ids),
        PERMISSIONS,
        correlation_id=correlation_id,
    )
    return {
        permission: {i for i in ids if decisions[(i, permission)].allowed}
        for permission in PERMISSIONS
    }


def impressions_of(evidence: dict[str, object]) -> float | None:
    value = evidence.get("impressions")
    return float(value) if isinstance(value, (int, float)) else None


def assemble(org: Organization, facts: Facts, allowed: dict[str, set[UUID]]) -> ClientBundle:
    """Shape one client from already-loaded facts. No I/O."""
    oid = org.id
    locations = facts.locations.get(oid, [])
    primary = locations[0] if locations else None
    place = ", ".join(part for part in (primary.city, primary.region) if part) if primary else ""

    def read(table: dict[UUID, MetricRead], permission: str) -> MetricRead | None:
        return table.get(oid) if oid in allowed[permission] else None

    search_clicks = shaped("search_console", read(facts.clicks, "seo.read"))
    position = shaped("search_console", read(facts.position, "seo.read"))
    sessions = shaped("ga4", read(facts.sessions, "insights.read"))
    leads = shaped("leads", read(facts.leads, "leads.read"))
    reviews = facts.reviews.get(oid)
    review_summary = (
        ReviewSummary(
            availability=reviews.availability,  # type: ignore[arg-type]
            total=reviews.total,
            new_in_period=reviews.new_in_period,
            average_rating=reviews.average_rating,
        )
        if reviews is not None
        else ReviewSummary(
            availability="not_permitted", total=None, new_in_period=None, average_rating=None
        )
    )
    owner: Owner = {
        "organization_id": oid,
        "organization_name": org.name,
        "organization_slug": org.slug,
    }
    reasons: list[str] = []
    attention: list[AttentionItem] = []
    google = facts.google.get(oid)
    if google is None:
        reasons.append("GOOGLE_NOT_CONNECTED")
    elif google != "connected":
        reasons.append("GOOGLE_RECONNECT_REQUIRED")
        attention.append(
            AttentionItem(
                **owner,
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
    failures = facts.unresolved.get(oid, [])
    for run in failures:
        reasons.append("WORKFLOW_ATTENTION")
        attention.append(
            AttentionItem(
                **owner,
                code=f"WORKFLOW_{run.status.upper()}",
                severity="high" if run.status != "retry_scheduled" else "medium",
                occurred_at=run.at,
                reference=f"{run.workflow_key}:{run.failure_code or ''}".rstrip(":"),
                workflow_key=run.workflow_key,
                failure_code=run.failure_code,
            )
        )
    last = facts.last_completed.get(oid)
    scheduled = facts.next_work.get(oid)
    health: Literal["healthy", "needs_attention", "not_configured"] = (
        "not_configured"
        if "GOOGLE_NOT_CONNECTED" in reasons
        else "needs_attention"
        if reasons
        else "healthy"
    )

    def status_of(read_metric: MetricValue) -> Literal["healthy", "not_connected", "not_permitted"]:
        if read_metric.availability == "not_permitted":
            return "not_permitted"
        if read_metric.availability == "not_connected":
            return "not_connected"
        return "healthy"

    systems = [
        ClientSystem(
            key="google",
            status="not_connected"
            if google is None
            else "healthy"
            if google == "connected"
            else "needs_attention",
        ),
        ClientSystem(key="analytics", status=status_of(sessions)),
        ClientSystem(key="search_console", status=status_of(search_clicks)),
        ClientSystem(key="automations", status="error" if failures else "healthy"),
    ]
    row = ClientRow(
        organization_id=oid,
        slug=org.slug,
        name=org.name,
        location=place or None,
        category=facts.industries.get(oid),
        location_count=len(locations),
        organic_sessions=sessions,
        search_clicks=search_clicks,
        average_position=position,
        average_local_rank=metric("rank_scan", "not_tracked"),
        leads=leads,
        local_visibility=metric("rank_scan", "not_tracked"),
        reviews=review_summary,
        open_opportunities=facts.open_counts.get(oid),
        health=health,
        health_reasons=sorted(set(reasons)),
        last_activity=WorkItem(workflow_key=last.workflow_key, status="completed", at=last.at)
        if last
        else None,
        next_work=WorkItem(workflow_key=scheduled[0], status="scheduled", at=scheduled[1])
        if scheduled
        else None,
    )
    return ClientBundle(
        row=row,
        locations=len(locations),
        attention=attention,
        opportunities=[
            OpportunityItem(
                id=item.id,
                **owner,
                opportunity_type=item.opportunity_type,
                classification="Growth Opportunity"
                if item.opportunity_type in GROWTH_TYPES
                else "Issue",
                status=item.status,
                priority=item.priority,
                query=str(item.evidence["query"]) if item.evidence.get("query") else None,
                page=str(item.evidence["page"]) if item.evidence.get("page") else None,
                impressions=impressions_of(item.evidence),
            )
            for item in facts.opportunities.get(oid, [])
        ],
        activity=[
            ActivityItem(**owner, workflow_key=run.workflow_key, completed_at=run.at)
            for run in facts.activity.get(oid, [])
            if run.at is not None
        ],
        upcoming=[UpcomingItem(**owner, workflow_key=scheduled[0], next_run_at=scheduled[1])]
        if scheduled
        else [],
        systems=systems,
    )


def validate_days(days: int) -> None:
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


@router.get("/clients", response_model=VisibleClients)
async def visible_clients(session: Session, principal: Authenticated) -> VisibleClients:
    """The clients the caller may open, with how they may open them."""
    scope = await visible_scope(session, principal)
    return VisibleClients(
        platform_administrator=scope.platform_administrator,
        data=[
            VisibleClient(
                organization_id=org.id,
                slug=org.slug,
                name=org.name,
                status=org.status.value,
                access=scope.access(org.id),
            )
            for org in scope.organizations
        ],
    )


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2}


@router.get("/opportunities", response_model=OpportunityList)
async def portfolio_opportunities(
    request: Request,
    session: Session,
    principal: Authenticated,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    organization_id: UUID | None = None,
    kind: OpportunityKind | None = None,
    priority: PriorityBand | None = None,
    state: OpportunityState = "open",
) -> OpportunityList:
    """Every opportunity kind across the clients the caller may open, one set-based read."""
    timer = SectionTimer()
    async with timer.section("scope"):
        scope = await visible_scope(session, principal)
        allowed = await permitted_organizations(
            session, principal, scope, scope.organizations, str(request_correlation_id(request))
        )
    permitted: dict[OpportunityKind, set[UUID]] = {
        k: allowed[permission] for k, permission in KIND_PERMISSION.items()
    }
    if organization_id is not None and all(o.id != organization_id for o in scope.organizations):
        raise HTTPException(status_code=404, detail="Not found")
    async with timer.section("opportunities"):
        rows, more = await opportunity_rows(
            session,
            permitted,
            organization_id=organization_id,
            kind=kind,
            band=priority,
            state=state,
            limit=limit,
            offset=offset,
        )
    owners = {o.id: o for o in scope.organizations}
    timer.log("opportunities", len(scope.organizations), str(request_correlation_id(request)))
    data: list[OpportunityView] = [project_row(row, owners[row.organization_id]) for row in rows]
    return OpportunityList(
        data=data,
        next_offset=offset + limit if more else None,
        kinds_unavailable=[k for k in KIND_PERMISSION if not permitted[k]],
    )


@router.get("/portfolio", response_model=PortfolioOverview)
async def portfolio_overview(
    request: Request,
    session: Session,
    principal: Authenticated,
    days: int = Query(28),
) -> PortfolioOverview:
    validate_days(days)
    timer = SectionTimer()
    now = datetime.now(UTC)
    start = now - timedelta(days=days)
    async with timer.section("scope"):
        scope = await visible_scope(session, principal)
        allowed = await permitted_organizations(
            session, principal, scope, scope.organizations, str(request_correlation_id(request))
        )
    facts = await load_facts(session, scope.organizations, allowed, days=days, now=now, timer=timer)
    async with timer.section("assemble"):
        bundles = [assemble(org, facts, allowed) for org in scope.organizations]
    timer.log("portfolio", len(bundles), str(request_correlation_id(request)))
    clients = [bundle.row for bundle in bundles]
    attention = [item for bundle in bundles for item in bundle.attention]
    opportunities = [item for bundle in bundles for item in bundle.opportunities[:3]]
    activity = [item for bundle in bundles for item in bundle.activity]
    upcoming = [item for bundle in bundles for item in bundle.upcoming]
    location_total = sum(bundle.locations for bundle in bundles)

    def summed(field_name: str, source: str) -> MetricValue:
        rows = [
            getattr(c, field_name)
            for c in clients
            if getattr(c, field_name).availability == "available"
        ]
        if not rows:
            states = {getattr(c, field_name).availability for c in clients}
            if len(states) == 1 and states <= {"not_connected", "not_permitted"}:
                return metric(source, states.pop())
            return metric(source, "no_data" if clients else "not_connected")
        current = sum(r.current or 0 for r in rows)
        previous_rows = [r.previous for r in rows if r.previous is not None]
        previous = sum(previous_rows) if len(previous_rows) == len(rows) else None
        return metric(source, "available", current, previous)

    rated = [c.reviews for c in clients if c.reviews.average_rating is not None]
    new_reviews = [c.reviews.new_in_period for c in clients if c.reviews.new_in_period is not None]
    attention.sort(
        key=lambda a: (
            SEVERITY_ORDER[a.severity],
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


def count_map(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(k): int(v) for k, v in value.items() if isinstance(v, int)}


@router.get("/clients/{organization_id}/overview", response_model=ClientOverview)
async def client_overview(
    organization_id: UUID,
    request: Request,
    session: Session,
    principal: Authenticated,
    days: int = Query(28),
) -> ClientOverview:
    validate_days(days)
    timer = SectionTimer()
    async with timer.section("scope"):
        scope = await visible_scope(session, principal)
        org = next((o for o in scope.organizations if o.id == organization_id), None)
        if org is None:
            # Same answer for "does not exist" and "not yours": no tenant disclosure.
            raise HTTPException(status_code=404, detail="Not found")
        allowed = await permitted_organizations(
            session, principal, scope, [org], str(request_correlation_id(request))
        )
    now = datetime.now(UTC)
    facts = await load_facts(session, [org], allowed, days=days, now=now, timer=timer)
    bundle = assemble(org, facts, allowed)
    insights = InsightsSummary(
        availability="not_permitted",
        workflow_runs={},
        growth_outcomes={},
        seo_opportunities={},
        seo_opportunities_blocked=None,
        content_publications={},
        reviews={},
    )
    if organization_id in allowed["insights.read"]:
        async with timer.section("insights"):
            summary = await InsightsService().summary(session, organization_id)
        seo = summary.get("seo")
        growth = summary.get("growth")
        blocked = seo.get("opportunities_blocked") if isinstance(seo, dict) else None
        insights = InsightsSummary(
            availability="available",
            workflow_runs=count_map(summary.get("workflow_runs")),
            growth_outcomes=count_map(
                growth.get("outcome_counts") if isinstance(growth, dict) else None
            ),
            seo_opportunities=count_map(
                seo.get("opportunities") if isinstance(seo, dict) else None
            ),
            seo_opportunities_blocked=blocked if isinstance(blocked, int) else None,
            content_publications=count_map(summary.get("content_publications")),
            reviews=count_map(summary.get("reviews")),
        )
    timer.log("overview", 1, str(request_correlation_id(request)))
    bundle.attention.sort(
        key=lambda a: (
            SEVERITY_ORDER[a.severity],
            -(a.occurred_at.timestamp() if a.occurred_at else now.timestamp()),
        )
    )
    return ClientOverview(
        generated_at=now,
        days=days,
        period_start=now - timedelta(days=days),
        period_end=now,
        access=scope.access(organization_id),
        client=bundle.row,
        attention=bundle.attention,
        opportunities=bundle.opportunities,
        activity=bundle.activity,
        upcoming=bundle.upcoming,
        systems=bundle.systems,
        insights=insights,
    )
