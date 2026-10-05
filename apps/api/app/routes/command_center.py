"""Additive SEO reference projections. All writes remain in canonical SEO routes."""

from dataclasses import replace
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationRequest
from apps.api.app.authorization.service import AuthorizationService
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.growth.models import GrowthInitiative
from apps.api.app.growth.service import GrowthService
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.models import ContentItem, ContentOpportunity
from apps.api.app.products.seo.change_quality import QualityCode, quality_problems
from apps.api.app.products.seo.change_set import SiteChangeItem, SiteChangeSet
from apps.api.app.products.seo.decision import (
    GROWTH_TYPES,
    SEOEvidenceInvalidError,
    resolve_decision,
)
from apps.api.app.products.seo.models import SEOImplementationTask, SEOOpportunity, SEOPage
from apps.api.app.routes.command_center_reads import (
    KIND_PERMISSION,
    ImportanceReason,
    Lifecycle,
    OpportunityKind,
    OpportunityListRow,
    OpportunityState,
    PriorityBand,
    SiteChangeAvailability,
    content_row,
    earlier_observations,
    enrich,
    growth_row,
    opportunity_rows,
    priority_band,
    seo_dedupe_columns,
    seo_dedupe_key,
    seo_row,
    with_seo_state,
)
from apps.api.app.routes.seo import Session, meta, no_store, policy, recommendation_row, service

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(no_store)],
)
authorization = AuthorizationService()


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceContext(DTO):
    source: str | None
    quality: str | None
    freshness_at: str | None
    period_start: str | None
    period_end: str | None
    limitation_code: str | None = None


class OpportunityClient(DTO):
    organization_id: UUID
    name: str
    slug: str


class EvidenceMetric(DTO):
    key: str
    value: float


class EvidenceSummary(DTO):
    """What the evidence says, as codes and numbers. Labels are the frontend's job."""

    source: str | None
    signal: str
    metrics: list[EvidenceMetric]
    source_count: int | None = None


NextAction = Literal[
    "request_recommendation",
    "review_recommendation",
    "monitor_publication",
    "measure_impact",
    "review_opportunity",
    "review_growth_plan",
    "monitor_execution",
    "none",
]


class EarlierObservation(DTO):
    """An older sighting of the same finding. Rolled up in the read; never deleted."""

    id: UUID
    observed_at: datetime
    status: str
    priority: float | None


class OpportunitySubject(DTO):
    """What the opportunity is about: the titles are built from these, never from keys."""

    query: str | None = None
    path: str | None = None


class OpportunityView(DTO):
    id: str
    source_kind: Literal["seo_opportunity", "content_opportunity", "growth_initiative"] = (
        "seo_opportunity"
    )
    kind: OpportunityKind = "seo"
    source_id: UUID
    organization_id: UUID
    client: OpportunityClient | None = None
    location_id: UUID | None
    website_id: UUID | None
    page_id: UUID | None
    classification: Literal["Issue", "Growth Opportunity", "Optimization", "Data & Tracking"]
    source_type: str
    status: str
    priority: float | None
    evidence: dict[str, object]
    score_explanation: dict[str, object]
    observed_at: datetime
    evidence_context: EvidenceContext
    priority_band: PriorityBand | None = None
    headline: str | None = None
    confidence: float | None = None
    evidence_summary: EvidenceSummary | None = None
    next_action: NextAction = "none"
    latest_revision_status: str | None = None
    site_change: SiteChangeAvailability = "not_applicable"
    # Typed reason the site-change action is disabled; the frontend owns the sentence.
    site_change_reason: Literal["SITE_CHANGES_NOT_CONFIGURED"] | None = None
    subject: OpportunitySubject = OpportunitySubject()
    # The full text of a growth plan; `headline` is its short title.
    summary: str | None = None
    lifecycle: Lifecycle = "open"
    # When the approved change was verified on the live site.
    verified_at: datetime | None = None
    # Typed reason the opportunity matters; None means there is nothing to say.
    importance_reason: ImportanceReason | None = None
    earlier_observations: list[EarlierObservation] = []


class OpportunityList(DTO):
    data: list[OpportunityView]
    next_offset: int | None
    # Kinds the caller may not read: labeled, never shown as an empty list of zero.
    kinds_unavailable: list[OpportunityKind] = []


class QualityResult(DTO):
    field: str
    code: QualityCode
    reason: str


class QualityView(DTO):
    state: Literal["passed", "blocked", "unavailable"]
    problems: list[QualityResult]
    target_query: str | None
    top_queries: list[str]
    location_terms: list[str]
    repository_verification: Literal["executor_rechecks_before_write"] = (
        "executor_rechecks_before_write"
    )


class LiveCheck(DTO):
    field: str | None
    expected: object = None
    observed: object = None
    state: str | None


class PublicationView(DTO):
    publication_id: UUID | None
    workflow_run_id: UUID | None
    deployment_status: str | None
    approved_head_sha: str | None
    external_revision_id: str | None
    published_url: str | None
    verified_at: datetime | None
    mapping_state: str | None
    blocked_code: str | None
    publication_status: str | None
    pull_request_url: str | None
    build_gate: str | None
    build_state: str | None
    verification_state: str | None
    live_checks: list[LiveCheck]


class RecommendationView(DTO):
    id: UUID
    created_at: datetime
    revision_number: int
    proposed_action: str
    expected_result_hypothesis: str
    risk: str
    effort: str
    status: str
    change_set: list[SiteChangeItem]
    change_set_limitation_code: str | None
    decision_context: dict[str, object] | None
    site_change: PublicationView | None
    approved_fingerprint: str | None
    quality: QualityView


class RunView(DTO):
    id: UUID
    task_id: UUID
    task_status: str
    status: str
    correlation_id: str
    output_reference: str | None


class StatusEvent(DTO):
    event_type: str
    action: str
    result: str
    occurred_at: datetime
    actor_type: str


class GrowthActionView(DTO):
    id: UUID
    action_key: str
    product_key: str
    action_type: str
    execution_mode: str
    status: str
    risk: str
    effort: str
    expected_result_hypothesis: str
    safe_error_code: str | None


class GrowthPlanView(DTO):
    objective: str
    rationale: str
    confidence: float
    actions: list[GrowthActionView]


class ContentItemView(DTO):
    id: UUID
    content_type: str
    title: str
    status: str


class ContentOpportunityView(DTO):
    target_reference: str
    opportunity_type: str
    items: list[ContentItemView]


class LiveCheckResult(DTO):
    """The verification of the live site against the approved change, as persisted."""

    state: str | None
    verified_at: datetime | None
    checks: list[LiveCheck]


class OpportunityDetail(DTO):
    kind: OpportunityKind = "seo"
    data: OpportunityView
    page_url: str | None
    recommendations: list[RecommendationView]
    runs: list[RunView]
    growth: GrowthPlanView | None = None
    content: ContentOpportunityView | None = None
    # None: the caller may not read audit history. An empty list is a real "no events".
    history: list[StatusEvent] | None = None
    live_check: LiveCheckResult | None = None
    can_recommend: bool
    can_approve: bool
    correlation_id: str


class AttentionView(DTO):
    id: str
    source_id: UUID
    opportunity_id: UUID
    reason: Literal[
        "waiting_approval",
        "publication_blocked",
        "workflow_failure",
        "retry_scheduled",
        "waiting",
        "missing_mapping",
    ]
    status: str
    code: str | None = None


class AttentionList(DTO):
    data: list[AttentionView]
    next_offset: int | None


def project(item: SEOOpportunity) -> OpportunityView:
    # Classification uses canonical structured detector types, never presentation prose.
    return OpportunityView(
        id=f"seo_opportunity:{item.id}",
        source_id=item.id,
        organization_id=item.organization_id,
        location_id=item.location_id,
        website_id=item.website_id,
        page_id=item.page_id,
        classification="Growth Opportunity" if item.opportunity_type in GROWTH_TYPES else "Issue",
        source_type=item.opportunity_type,
        status=item.status,
        priority=item.priority_score,
        evidence=item.evidence,
        score_explanation=item.score_explanation,
        observed_at=item.updated_at,
        evidence_context=EvidenceContext(
            source=str(item.evidence["source"])
            if item.evidence.get("source")
            else "crawl"
            if "crawl.v1" in item.source_versions
            else None,
            quality=None,
            freshness_at=None,
            period_start=str(item.evidence["date_start"])
            if item.evidence.get("date_start")
            else None,
            period_end=str(item.evidence["date_end"]) if item.evidence.get("date_end") else None,
        ),
    )


def next_action_for(
    kind: OpportunityKind, status: str, revision_status: str | None, live: bool = False
) -> NextAction:
    """One typed next step per state; the frontend maps it to wording."""
    if kind == "seo":
        if live:
            return "measure_impact"
        if revision_status is None or revision_status in {"rejected", "superseded", "withdrawn"}:
            return "request_recommendation" if status not in {"archived", "implemented"} else "none"
        if revision_status == "awaiting_approval":
            return "review_recommendation"
        return "monitor_publication" if revision_status == "approved" else "none"
    if kind == "content":
        return "review_opportunity" if status in {"identified", "validated"} else "none"
    if status == "proposed":
        return "review_growth_plan"
    return "monitor_execution" if status in {"approved", "executing"} else "none"


EVIDENCE_NUMBERS = ("clicks", "impressions", "ctr", "position", "http_status")


def evidence_summary(row: OpportunityListRow) -> EvidenceSummary:
    metrics = [
        EvidenceMetric(key=key, value=float(value))
        for key in EVIDENCE_NUMBERS
        if isinstance((value := row.evidence.get(key)), (int, float))
        and not isinstance(value, bool)
    ]
    issue = row.evidence.get("issue")
    source = row.evidence.get("source")
    return EvidenceSummary(
        source=str(source) if source else ("crawl" if row.kind == "seo" else None),
        signal=str(issue) if isinstance(issue, str) else row.source_type,
        metrics=metrics,
        source_count=row.source_count,
    )


def project_row(row: OpportunityListRow, organization: Organization) -> OpportunityView:
    classification: Literal["Issue", "Growth Opportunity", "Optimization", "Data & Tracking"] = (
        "Growth Opportunity" if row.kind == "growth" or row.source_type in GROWTH_TYPES else "Issue"
    )
    return OpportunityView(
        id=f"{SOURCE_KINDS[row.kind]}:{row.id}",
        source_kind=SOURCE_KINDS[row.kind],
        kind=row.kind,
        source_id=row.id,
        organization_id=row.organization_id,
        client=OpportunityClient(
            organization_id=organization.id, name=organization.name, slug=organization.slug
        ),
        location_id=row.location_id,
        website_id=row.website_id,
        page_id=row.page_id,
        classification=classification,
        source_type=row.source_type,
        status=row.status,
        priority=row.priority,
        evidence=row.evidence,
        score_explanation=row.score_explanation,
        observed_at=row.observed_at,
        evidence_context=EvidenceContext(
            source=None, quality=None, freshness_at=None, period_start=None, period_end=None
        ),
        priority_band=priority_band(row.priority),
        headline=row.headline,
        confidence=row.confidence,
        evidence_summary=evidence_summary(row),
        next_action=next_action_for(
            row.kind, row.status, row.latest_revision_status, row.lifecycle == "live"
        ),
        latest_revision_status=row.latest_revision_status,
        site_change=row.site_change,
        site_change_reason="SITE_CHANGES_NOT_CONFIGURED"
        if row.site_change == "not_configured"
        else None,
        subject=OpportunitySubject(query=row.subject_query, path=row.subject_path),
        summary=row.summary,
        lifecycle=row.lifecycle,
        verified_at=row.verified_at,
        importance_reason=row.importance_reason,
        earlier_observations=[
            EarlierObservation(
                id=o.id, observed_at=o.observed_at, status=o.status, priority=o.priority
            )
            for o in row.earlier
        ],
    )


SOURCE_KINDS: dict[
    OpportunityKind, Literal["seo_opportunity", "content_opportunity", "growth_initiative"]
] = {
    "seo": "seo_opportunity",
    "content": "content_opportunity",
    "growth": "growth_initiative",
}


async def capability(
    session: Session,
    principal: Authenticated,
    organization_id: UUID,
    permission: str,
    aal: AssuranceLevel,
    request: Request,
) -> bool:
    result = await authorization.evaluate(
        session,
        principal,
        AuthorizationRequest(
            platform_user_id=principal.platform_user_id,
            organization_id=organization_id,
            permission_key=permission,
            resource_scope=ScopeType.ORGANIZATION,
            minimum_assurance_level=aal,
        ),
        correlation_id=str(meta(request)["correlation_id"]),
    )
    return result.allowed


async def readable_kinds(
    session: Session,
    principal: Authenticated,
    organization_id: UUID,
    request: Request,
) -> dict[OpportunityKind, set[UUID]]:
    """Which opportunity kinds the caller may read for one client, in one set-based decision."""
    decisions = await authorization.evaluate_many(
        session,
        principal,
        [organization_id],
        list(KIND_PERMISSION.values()),
        correlation_id=str(meta(request)["correlation_id"]),
    )
    return {
        kind: {organization_id} if decisions[(organization_id, permission)].allowed else set()
        for kind, permission in KIND_PERMISSION.items()
    }


@router.get("/opportunities", response_model=OpportunityList)
async def opportunities(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    kind: OpportunityKind | None = None,
    priority: PriorityBand | None = None,
    state: OpportunityState = "open",
) -> OpportunityList:
    permitted = await readable_kinds(session, principal, organization_id, request)
    if not any(permitted.values()):
        # Same answer for "does not exist" and "not yours": no tenant disclosure.
        raise HTTPException(status_code=404, detail="Not found")
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Not found")
    rows, more = await opportunity_rows(
        session,
        permitted,
        kind=kind,
        band=priority,
        state=state,
        limit=limit,
        offset=offset,
    )
    return OpportunityList(
        data=[project_row(row, organization) for row in rows],
        next_offset=offset + limit if more else None,
        kinds_unavailable=[k for k, orgs in permitted.items() if not orgs],
    )


async def resolve_kind(
    session: Session, organization_id: UUID, opportunity_id: UUID
) -> tuple[OpportunityKind, SEOOpportunity | ContentOpportunity | GrowthInitiative] | None:
    """Which kind a tenant-scoped id belongs to. At most three primary-key lookups."""
    seo = await session.scalar(
        select(SEOOpportunity).where(
            SEOOpportunity.organization_id == organization_id,
            SEOOpportunity.id == opportunity_id,
        )
    )
    if seo is not None:
        return "seo", seo
    content = await session.scalar(
        select(ContentOpportunity).where(
            ContentOpportunity.organization_id == organization_id,
            ContentOpportunity.id == opportunity_id,
        )
    )
    if content is not None:
        return "content", content
    growth = await session.scalar(
        select(GrowthInitiative).where(
            GrowthInitiative.organization_id == organization_id,
            GrowthInitiative.id == opportunity_id,
        )
    )
    return ("growth", growth) if growth is not None else None


HISTORY_RESOURCE: dict[OpportunityKind, str] = {
    "seo": "seo_opportunity",
    "content": "content_opportunity",
    "growth": "growth_initiative",
}
growth_service = GrowthService()


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
async def detail(
    request: Request,
    organization_id: UUID,
    opportunity_id: UUID,
    session: Session,
    principal: Authenticated,
) -> OpportunityDetail:
    found = await resolve_kind(session, organization_id, opportunity_id)
    if found is None:
        raise HTTPException(status_code=404, detail="Not found")
    kind, entity = found
    if not await capability(
        session, principal, organization_id, KIND_PERMISSION[kind], AssuranceLevel.AAL1, request
    ):
        # Same answer for "does not exist" and "not yours": no tenant disclosure.
        raise HTTPException(status_code=404, detail="Not found")
    organization = await session.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(status_code=404, detail="Not found")
    history: list[StatusEvent] | None = None
    if await capability(
        session, principal, organization_id, "audit.read", AssuranceLevel.AAL1, request
    ):
        history = [
            StatusEvent(
                event_type=event.event_type,
                action=event.action,
                result=event.result,
                occurred_at=event.occurred_at,
                actor_type=event.actor_type,
            )
            for event in await service.audit_repository.list_for_resource(
                session,
                organization_id=organization_id,
                resource_type=HISTORY_RESOURCE[kind],
                resource_id=opportunity_id,
                limit=50,
            )
        ]
    correlation = str(meta(request)["correlation_id"])
    if kind == "growth":
        assert isinstance(entity, GrowthInitiative)
        plan = await growth_service.detail(session, organization_id, opportunity_id)
        actions = plan["actions"] if plan else []
        listed = growth_row(entity)
        return OpportunityDetail(
            kind="growth",
            data=project_row(listed, organization),
            page_url=None,
            recommendations=[],
            runs=[],
            growth=GrowthPlanView(
                objective=entity.objective,
                rationale=entity.rationale,
                confidence=float(entity.confidence),
                actions=[
                    GrowthActionView.model_validate(
                        {key: action[key] for key in GrowthActionView.model_fields if key in action}
                    )
                    for action in actions  # type: ignore[attr-defined]
                ],
            ),
            history=history,
            can_recommend=False,
            can_approve=await capability(
                session,
                principal,
                organization_id,
                "workflows.execute",
                AssuranceLevel.AAL2,
                request,
            ),
            correlation_id=correlation,
        )
    if kind == "content":
        assert isinstance(entity, ContentOpportunity)
        items = await session.scalars(
            select(ContentItem)
            .where(
                ContentItem.organization_id == organization_id,
                ContentItem.opportunity_id == opportunity_id,
            )
            .order_by(ContentItem.created_at)
        )
        return OpportunityDetail(
            kind="content",
            data=project_row((await enrich(session, [content_row(entity)]))[0], organization),
            page_url=None,
            recommendations=[],
            runs=[],
            content=ContentOpportunityView(
                target_reference=entity.target_reference,
                opportunity_type=entity.opportunity_type,
                items=[
                    ContentItemView(
                        id=item.id,
                        content_type=item.content_type,
                        title=item.title,
                        status=item.status,
                    )
                    for item in items
                ],
            ),
            history=history,
            can_recommend=False,
            can_approve=await capability(
                session, principal, organization_id, "content.create", AssuranceLevel.AAL1, request
            ),
            correlation_id=correlation,
        )
    assert isinstance(entity, SEOOpportunity)
    item = entity
    (seo_state,) = await with_seo_state(session, [seo_row(item)])
    seo_state = replace(
        seo_state,
        earlier=(
            await earlier_observations(
                session, SEOOpportunity, seo_dedupe_columns(), seo_dedupe_key, [item]
            )
        ).get(seo_dedupe_key(item), ()),
    )
    projected = project_row(seo_state, organization)
    projected.evidence_context = project(item).evidence_context
    try:
        evidence = await resolve_decision(
            session, organization_id, item, [f"seo-opportunity:{item.id}"]
        )
        projected.evidence_context.quality = (
            str(evidence["evidence_quality"])
            if evidence.get("evidence_quality") is not None
            else None
        )
        projected.evidence_context.freshness_at = (
            str(evidence["evidence_freshness"])
            if evidence.get("evidence_freshness") not in (None, "None")
            else None
        )
    except SEOEvidenceInvalidError as error:
        projected.evidence_context.limitation_code = error.limitation_code
    revisions = await service.list_recommendations(session, organization_id, opportunity_id)
    from apps.api.app.products.seo.site_change_state import load_site_change_states

    states = await load_site_change_states(session, organization_id, revisions)
    quality = await service.site_changes.quality_context(session, organization_id, item)
    recommendations = []
    for revision in revisions:
        row = recommendation_row(revision, states.get(revision.id))
        changes = (
            SiteChangeSet.model_validate(revision.change_set).items if revision.change_set else []
        )
        problems = [
            QualityResult(field=change.field.value, code=problem.code, reason=problem.reason)
            for change in changes
            for problem in quality_problems(
                change.field, change.current_value, change.proposed_value, quality
            )
        ]
        recommendations.append(
            RecommendationView.model_validate(
                {
                    "created_at": revision.created_at,
                    **{
                        key: row[key]
                        for key in (
                            "id",
                            "revision_number",
                            "proposed_action",
                            "expected_result_hypothesis",
                            "risk",
                            "effort",
                            "status",
                            "change_set",
                            "change_set_limitation_code",
                            "decision_context",
                            "site_change",
                        )
                    },
                    "approved_fingerprint": revision.change_set_fingerprint,
                    "quality": QualityView(
                        state="blocked" if problems else "passed" if changes else "unavailable",
                        problems=problems,
                        target_query=quality.target_query,
                        top_queries=list(quality.top_queries),
                        location_terms=list(quality.location_terms),
                    ),
                },
            )
        )
    pairs = (
        (
            await session.execute(
                select(SEOImplementationTask, WorkflowRun)
                .join(
                    WorkflowRun,
                    (WorkflowRun.id == SEOImplementationTask.workflow_run_id)
                    & (WorkflowRun.organization_id == organization_id),
                )
                .where(
                    SEOImplementationTask.organization_id == organization_id,
                    SEOImplementationTask.recommendation_revision_id.in_(
                        [revision.id for revision in revisions]
                    ),
                )
            )
        ).all()
        if revisions
        else []
    )
    page = (
        await session.scalar(
            select(SEOPage).where(
                SEOPage.organization_id == organization_id, SEOPage.id == item.page_id
            )
        )
        if item.page_id
        else None
    )
    # The newest revision's persisted publication is the live check; nothing is re-derived here.
    latest_site_change = recommendations[0].site_change if recommendations else None
    return OpportunityDetail(
        kind="seo",
        data=projected,
        history=history,
        live_check=LiveCheckResult(
            state=latest_site_change.verification_state,
            verified_at=latest_site_change.verified_at,
            checks=latest_site_change.live_checks,
        )
        if latest_site_change
        else None,
        page_url=page.normalized_url if page else None,
        recommendations=recommendations,
        runs=[
            RunView(
                id=run.id,
                task_id=task.id,
                task_status=task.status,
                status=run.status,
                correlation_id=run.correlation_id,
                output_reference=run.output_reference,
            )
            for task, run in pairs
        ],
        can_recommend=await capability(
            session, principal, organization_id, "seo.recommend", AssuranceLevel.AAL1, request
        ),
        can_approve=await capability(
            session, principal, organization_id, "seo.approve", AssuranceLevel.AAL2, request
        ),
        correlation_id=correlation,
    )


@router.get("/attention", response_model=AttentionList)
async def attention(
    organization_id: UUID,
    session: Session,
    _: Annotated[object, policy("seo.read")],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> AttentionList:
    # Page canonical opportunities first, then derive attention; no independent writable lifecycle.
    rows, more = await service.list_opportunities(
        session, organization_id, limit=limit, offset=offset
    )
    from apps.api.app.products.seo.models import SEORecommendationRevision
    from apps.api.app.products.seo.site_change_state import load_site_change_states

    revisions = (
        list(
            await session.scalars(
                select(SEORecommendationRevision).where(
                    SEORecommendationRevision.organization_id == organization_id,
                    SEORecommendationRevision.opportunity_id.in_([row.id for row in rows]),
                    SEORecommendationRevision.status.not_in(
                        ["superseded", "withdrawn", "rejected"]
                    ),
                )
            )
        )
        if rows
        else []
    )
    states = await load_site_change_states(session, organization_id, revisions)
    result = []
    for revision in revisions:
        state = states.get(revision.id)
        reason: Literal["waiting_approval", "publication_blocked", "missing_mapping"] | None = (
            "waiting_approval" if revision.status == "awaiting_approval" else None
        )
        code = state.get("blocked_code") if state else None
        if code:
            reason = "missing_mapping" if code == "SITE_MAPPING_REQUIRED" else "publication_blocked"
        if reason:
            result.append(
                AttentionView(
                    id=f"seo_revision:{revision.id}:{reason}",
                    source_id=revision.id,
                    opportunity_id=revision.opportunity_id,
                    reason=reason,
                    status=revision.status,
                    code=str(code) if code else None,
                )
            )
    pairs = (
        (
            await session.execute(
                select(SEOImplementationTask, WorkflowRun)
                .join(
                    WorkflowRun,
                    (WorkflowRun.id == SEOImplementationTask.workflow_run_id)
                    & (WorkflowRun.organization_id == organization_id),
                )
                .where(
                    SEOImplementationTask.organization_id == organization_id,
                    SEOImplementationTask.recommendation_revision_id.in_(
                        [revision.id for revision in revisions]
                    ),
                    WorkflowRun.status.in_(
                        ["failed", "retry_scheduled", "waiting", "waiting_approval"]
                    ),
                )
            )
        ).all()
        if revisions
        else []
    )
    parent = {revision.id: revision.opportunity_id for revision in revisions}
    for task, run in pairs:
        result.append(
            AttentionView(
                id=f"workflow_run:{run.id}:{run.status}",
                source_id=run.id,
                opportunity_id=parent[task.recommendation_revision_id],
                status=run.status,
                reason="workflow_failure" if run.status == "failed" else run.status,
            )
        )
    return AttentionList(
        data=sorted(result, key=lambda value: value.id),
        next_offset=offset + limit if more else None,
    )
