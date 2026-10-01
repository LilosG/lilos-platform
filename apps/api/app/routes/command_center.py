"""Additive SEO reference projections. All writes remain in canonical SEO routes."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationRequest
from apps.api.app.authorization.service import AuthorizationService
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.products.seo.change_quality import QualityCode, quality_problems
from apps.api.app.products.seo.change_set import SiteChangeItem, SiteChangeSet
from apps.api.app.products.seo.decision import (
    GROWTH_TYPES,
    SEOEvidenceInvalidError,
    resolve_decision,
)
from apps.api.app.products.seo.models import SEOImplementationTask, SEOOpportunity, SEOPage
from apps.api.app.routes.seo import Session, meta, no_store, policy, recommendation_row, service

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center",
    tags=["command-center"],
    dependencies=[Depends(no_store)],
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


class OpportunityView(DTO):
    id: str
    source_kind: Literal["seo_opportunity"] = "seo_opportunity"
    source_id: UUID
    organization_id: UUID
    location_id: UUID | None
    website_id: UUID
    page_id: UUID | None
    classification: Literal["Issue", "Growth Opportunity", "Optimization", "Data & Tracking"]
    source_type: str
    status: str
    priority: float | None
    evidence: dict[str, object]
    score_explanation: dict[str, object]
    observed_at: datetime
    evidence_context: EvidenceContext


class OpportunityList(DTO):
    data: list[OpportunityView]
    next_offset: int | None


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


class OpportunityDetail(DTO):
    data: OpportunityView
    page_url: str | None
    recommendations: list[RecommendationView]
    runs: list[RunView]
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


@router.get("/opportunities", response_model=OpportunityList)
async def opportunities(
    organization_id: UUID,
    session: Session,
    _: Annotated[object, policy("seo.read")],
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> OpportunityList:
    rows, more = await service.list_opportunities(
        session, organization_id, limit=limit, offset=offset
    )
    return OpportunityList(
        data=[project(row) for row in rows], next_offset=offset + limit if more else None
    )


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
async def detail(
    request: Request,
    organization_id: UUID,
    opportunity_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[object, policy("seo.read")],
) -> OpportunityDetail:
    item = await service.get_opportunity(session, organization_id, opportunity_id)
    projected = project(item)
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
    return OpportunityDetail(
        data=projected,
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
        correlation_id=str(meta(request)["correlation_id"]),
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
