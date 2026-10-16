"""Client reports: generate, review, approve and record as sent.

Reads never call a provider.

A report is a saved snapshot of 1 to 12 whole calendar months set against a comparison. Its
address is ``{period}/{comparison}/{revision}``: ``2026-09`` or ``2026-05_2026-09``, then
``previous``, ``year-ago`` or ``vs-2026-01_2026-03``. Numbers are computed by code from stored data;
a person edits the narrative, approves the exact revision, and records when they sent it. Nothing
here emails or notifies anyone.
"""

from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import select

from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.errors import NotFoundError, request_correlation_id
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.models import GBPLocation
from apps.api.app.reports.cards import edited_cards, figure_table
from apps.api.app.reports.contracts import (
    ComparisonSpec,
    NarrativeOrigin,
    NarrativeOutcome,
    PortfolioReportsView,
    ReportDeliveryView,
    ReportDetailView,
    ReportGenerateRequest,
    ReportGenerateResult,
    ReportListView,
    ReportMarkSentRequest,
    ReportNarrative,
    ReportNarrativeDraftResult,
    ReportNarrativeUpdate,
    ReportPeriod,
    ReportPermissions,
)
from apps.api.app.reports.errors import ReportScopeNotReadableError
from apps.api.app.reports.narrative import NarrativeDrafter
from apps.api.app.reports.reads import portfolio_rows, revision_rows, upcoming
from apps.api.app.reports.search_results import search_results
from apps.api.app.reports.service import ReportService, StoredReport, status_of
from apps.api.app.reports.snapshot import last_ended_month, reportable_locations, require_ended
from apps.api.app.routes.command_center_portfolio import (
    permitted_organizations,
    visible_scope,
)
from apps.api.app.routes.command_center_reviews import private
from apps.api.app.routes.command_center_search import allowed
from apps.api.app.routes.insights import policy
from apps.api.app.routes.reviews import Session

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
# The period and comparison segments are parsed in code, so a malformed one gets a typed error.
PeriodSlug = Annotated[str, Path(max_length=64)]
ComparisonSlug = Annotated[str, Path(max_length=64)]

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center/reports",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(private)],
)
portfolio_router = APIRouter(
    prefix="/api/v1/command-center/reports",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(private)],
)
service = ReportService()


def get_narrative_drafter() -> NarrativeDrafter:
    """The drafter a request uses; tests replace this with one over a fake gateway."""
    return DRAFTER


DRAFTER = NarrativeDrafter()
Drafter = Annotated[NarrativeDrafter, Depends(get_narrative_drafter)]


def month_of(value: str) -> date:
    return date.fromisoformat(f"{value}-01")


def report_of(period: str, comparison: str) -> tuple[ReportPeriod, ComparisonSpec]:
    return ReportPeriod.from_slug(period), ComparisonSpec.from_slug(comparison)


async def permissions_of(
    session: Session, principal: Authenticated, organization_id: UUID, request: Request
) -> ReportPermissions:
    return ReportPermissions(
        can_generate=await allowed(session, principal, organization_id, request, "insights.manage"),
        can_publish=await allowed(session, principal, organization_id, request, "insights.publish"),
    )


async def profile_names(session: Session, organization_id: UUID) -> list[str]:
    """The Google profile names of the locations, only when there is more than one to tell apart.

    The cover uses the business title on the profile, never the internal location name.
    """
    locations = await reportable_locations(session, organization_id)
    if len(locations) < 2:
        return []
    ids = [item.gbp_location_id for item in locations if item.gbp_location_id is not None]
    rows = await session.scalars(
        select(GBPLocation.business_name)
        .where(GBPLocation.organization_id == organization_id, GBPLocation.id.in_(ids))
        .order_by(GBPLocation.business_name)
    )
    return list(dict.fromkeys(rows))


async def detail_of(
    session: Session,
    organization_id: UUID,
    stored: StoredReport,
    permissions: ReportPermissions,
) -> ReportDetailView:
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise NotFoundError
    delivery = await service.delivery(session, organization_id, stored.revision.id)
    count = await service.revision_count(session, organization_id, stored.period, stored.comparison)
    return ReportDetailView(
        organization_id=organization_id,
        client_name=organization.name,
        client_slug=organization.slug,
        period=stored.period,
        comparison=stored.comparison,
        revision=stored.revision.revision,
        revision_count=count,
        status=status_of(stored.revision, delivery),
        readiness=stored.snapshot.readiness,
        is_current=stored.revision.revision == count,
        created_at=stored.revision.created_at,
        approved_at=stored.revision.approved_at,
        delivery=ReportDeliveryView(sent_on=delivery.sent_on, recorded_at=delivery.created_at)
        if delivery
        else None,
        snapshot=stored.snapshot,
        narrative=stored.narrative,
        topics=stored.topics,
        search_results=search_results(stored.snapshot, stored.topics),
        profile_names=await profile_names(session, organization_id),
        permissions=permissions,
    )


async def require_whole_scope(
    session: Session, principal: Authenticated, organization_id: UUID, request: Request
) -> None:
    """A report covers every active location, so the caller must be able to read each of them."""
    for location in await reportable_locations(session, organization_id):
        if not await allowed(
            session,
            principal,
            organization_id,
            request,
            "gbp.read",
            location_id=location.location_id,
        ):
            raise ReportScopeNotReadableError


@router.get("", response_model=ReportListView)
async def list_reports(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("insights.read")],
) -> ReportListView:
    """The client's current report, every stored revision, and the next scheduled run."""
    history = await revision_rows(session, organization_id)
    current_month = last_ended_month(datetime.now(UTC))
    current = next(
        (
            row
            for row in history
            if row.period.start_month == current_month
            and row.period.end_month == current_month
            and row.comparison.basis is ComparisonSpec().basis
            and row.is_current
        ),
        None,
    )
    return ReportListView(
        organization_id=organization_id,
        current_month=current_month,
        current=current,
        history=history,
        upcoming=await upcoming(session, organization_id),
        permissions=await permissions_of(session, principal, organization_id, request),
    )


@router.post("/generate", response_model=ReportGenerateResult)
async def generate_report(
    request: Request,
    organization_id: UUID,
    body: ReportGenerateRequest,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("insights.manage")],
) -> ReportGenerateResult:
    """Compute a period from stored data. Identical data returns the existing draft."""
    period = body.period
    body.comparison.resolve(period)
    require_ended(period.end_month, datetime.now(UTC))
    await require_whole_scope(session, principal, organization_id, request)
    stored, created = await service.generate(
        session,
        organization_id,
        period,
        body.comparison,
        actor_id=principal.platform_user_id,
        correlation_id=str(request_correlation_id(request)),
    )
    permissions = await permissions_of(session, principal, organization_id, request)
    return ReportGenerateResult(
        report=await detail_of(session, organization_id, stored, permissions), created=created
    )


@router.get("/{period}/{comparison}/{revision}", response_model=ReportDetailView)
async def report_detail(
    request: Request,
    organization_id: UUID,
    period: PeriodSlug,
    comparison: ComparisonSlug,
    revision: Annotated[int, Path(ge=1)],
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("insights.read")],
) -> ReportDetailView:
    """One stored revision exactly as it was saved."""
    when, spec = report_of(period, comparison)
    stored = await service.get(session, organization_id, when, spec, revision)
    return await detail_of(
        session,
        organization_id,
        stored,
        await permissions_of(session, principal, organization_id, request),
    )


@router.put("/{period}/{comparison}/{revision}/narrative", response_model=ReportDetailView)
async def update_narrative(
    request: Request,
    organization_id: UUID,
    period: PeriodSlug,
    comparison: ComparisonSlug,
    revision: Annotated[int, Path(ge=1)],
    body: ReportNarrativeUpdate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("insights.manage")],
) -> ReportDetailView:
    """Replace a draft's narrative. An approved revision cannot be edited."""
    when, spec = report_of(period, comparison)
    current = await service.get(session, organization_id, when, spec, revision)
    cards = current.narrative.result_cards
    if body.result_cards is not None:
        table = figure_table(current.snapshot, search_results(current.snapshot, current.topics))
        cards = edited_cards(body.result_cards, table)
    stored = await service.set_narrative(
        session,
        organization_id,
        when,
        spec,
        revision,
        ReportNarrative(
            what_changed=body.what_changed.strip(),
            next_work=body.next_work.strip(),
            origin=NarrativeOrigin.MANUAL,
            result_cards=cards,
        ),
        actor_id=principal.platform_user_id,
        correlation_id=str(request_correlation_id(request)),
    )
    return await detail_of(
        session,
        organization_id,
        stored,
        await permissions_of(session, principal, organization_id, request),
    )


@router.post(
    "/{period}/{comparison}/{revision}/draft-narrative", response_model=ReportNarrativeDraftResult
)
async def draft_narrative(
    request: Request,
    organization_id: UUID,
    period: PeriodSlug,
    comparison: ComparisonSlug,
    revision: Annotated[int, Path(ge=1)],
    session: Session,
    principal: Authenticated,
    drafter: Drafter,
    _: Annotated[AuthorizationDecision, policy("insights.manage")],
) -> ReportNarrativeDraftResult:
    """Ask Hermes for a draft of the narrative. A draft that fails a check is not used."""
    when, spec = report_of(period, comparison)
    stored = await service.get(session, organization_id, when, spec, revision, lock=True)
    # Refuse before any spend: only the current draft has a narrative to draft.
    await service.assert_editable(session, organization_id, stored)
    # Regenerating regroups the searches first; the cards are written from that grouping.
    topics = await drafter.group_topics(
        session,
        organization_id=organization_id,
        revision_id=stored.revision.id,
        snapshot=stored.snapshot,
    )
    if topics is not None:
        stored = await service.set_topics(
            session,
            organization_id,
            when,
            spec,
            revision,
            topics,
            actor_id=principal.platform_user_id,
            correlation_id=str(request_correlation_id(request)),
        )
    result = await drafter.draft(
        session,
        organization_id=organization_id,
        revision_id=stored.revision.id,
        snapshot=stored.snapshot,
        results=search_results(stored.snapshot, stored.topics),
    )
    if result.narrative is not None:
        stored = await service.set_narrative(
            session,
            organization_id,
            when,
            spec,
            revision,
            result.narrative,
            actor_id=principal.platform_user_id,
            correlation_id=str(request_correlation_id(request)),
            event="reports.narrative.drafted",
        )
    permissions = await permissions_of(session, principal, organization_id, request)
    return ReportNarrativeDraftResult(
        report=await detail_of(session, organization_id, stored, permissions),
        outcome=NarrativeOutcome.DRAFTED if result.narrative else NarrativeOutcome.NOT_USED,
        failure=result.failure,
        cards_dropped=result.cards_dropped,
    )


@router.post("/{period}/{comparison}/{revision}/approve", response_model=ReportDetailView)
async def approve_report(
    request: Request,
    organization_id: UUID,
    period: PeriodSlug,
    comparison: ComparisonSlug,
    revision: Annotated[int, Path(ge=1)],
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("insights.publish")],
) -> ReportDetailView:
    """Approve the exact revision shown. Approved revisions are immutable."""
    when, spec = report_of(period, comparison)
    stored, _approved = await service.approve(
        session,
        organization_id,
        when,
        spec,
        revision,
        actor_id=principal.platform_user_id,
        correlation_id=str(request_correlation_id(request)),
    )
    return await detail_of(
        session,
        organization_id,
        stored,
        await permissions_of(session, principal, organization_id, request),
    )


@router.post("/{period}/{comparison}/{revision}/mark-sent", response_model=ReportDetailView)
async def mark_report_sent(
    request: Request,
    organization_id: UUID,
    period: PeriodSlug,
    comparison: ComparisonSlug,
    revision: Annotated[int, Path(ge=1)],
    body: ReportMarkSentRequest,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("insights.publish")],
) -> ReportDetailView:
    """Record that a person sent the approved report on the given day. Sends nothing."""
    when, spec = report_of(period, comparison)
    await service.mark_sent(
        session,
        organization_id,
        when,
        spec,
        revision,
        body.sent_on,
        actor_id=principal.platform_user_id,
        correlation_id=str(request_correlation_id(request)),
    )
    when, spec = report_of(period, comparison)
    stored = await service.get(session, organization_id, when, spec, revision)
    return await detail_of(
        session,
        organization_id,
        stored,
        await permissions_of(session, principal, organization_id, request),
    )


@portfolio_router.get("", response_model=PortfolioReportsView)
async def portfolio_reports(
    request: Request,
    session: Session,
    principal: Authenticated,
    month: Annotated[str | None, Query(pattern=MONTH_PATTERN)] = None,
) -> PortfolioReportsView:
    """Every client the caller may read, with the latest report of one month and its status."""
    scope = await visible_scope(session, principal)
    permitted = await permitted_organizations(
        session, principal, scope, scope.organizations, str(request_correlation_id(request))
    )
    readable = [o for o in scope.organizations if o.id in permitted["insights.read"]]
    when = month_of(month) if month else last_ended_month(datetime.now(UTC))
    rows, counts = await portfolio_rows(session, readable, when)
    return PortfolioReportsView(month=when, counts=counts, clients=rows)
