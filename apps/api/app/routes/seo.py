"""Protected evidence-driven SEO APIs."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.agents.access import AgentAccessService
from apps.api.app.agents.models import AgentRun
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.execution.service import ExecutionService
from apps.api.app.growth.measurement import (
    METRIC_SPECS,
    parse_verification_plan,
    seo_page_periods,
)
from apps.api.app.growth.models import GrowthAction, GrowthInitiative
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.seo.contracts import (
    CrawlRequest,
    ImplementationTaskCreate,
    ImplementationTaskVerify,
    OutcomeRecord,
    RecommendationCreate,
    RecommendationDecision,
    SearchConsoleSyncRequest,
    SearchPropertyCreate,
    SearchPropertySelect,
    WebsiteCreate,
)
from apps.api.app.products.seo.decision import (
    growth_handoff,
    recommendation_class,
    resolve_decision,
    revision_decision,
)
from apps.api.app.products.seo.errors import (
    SEOCrawlRunNotFoundError,
    SEOOpportunityNotFoundError,
    SEOWebsiteNotFoundError,
)
from apps.api.app.products.seo.models import (
    SEOCrawlPageObservation,
    SEOCrawlRun,
    SEOImplementationTask,
    SEOOpportunity,
    SEOOutcome,
    SEOPage,
    SEORecommendationRevision,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.page_intelligence import read_page_intelligence
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from apps.api.app.products.seo.service import SEOService
from apps.api.app.reporting_periods import (
    GA4_SYNC_TAIL_EXCLUSION_DAYS,
    GSC_SYNC_TAIL_EXCLUSION_DAYS,
)
from apps.api.app.routes.health import settings_from_request

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/seo",
    tags=["seo"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = SEOService()
orchestration = SEOOrchestrationService(seo=service)
search_console = SearchConsoleService()
execution = ExecutionService()
agent_access = AgentAccessService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


async def _opportunity_reasoning_run(
    session: AsyncSession, organization_id: UUID, opportunity_id: UUID
) -> tuple[WorkflowRun, AgentRun | None] | None:
    workflow = await session.scalar(
        select(WorkflowRun)
        .join(WorkflowVersion, WorkflowRun.workflow_version_id == WorkflowVersion.id)
        .join(WorkflowDefinition, WorkflowVersion.definition_id == WorkflowDefinition.id)
        .where(
            WorkflowRun.organization_id == organization_id,
            WorkflowDefinition.key == "agent.seo",
            WorkflowRun.input_document.contains({"seo_opportunity_id": str(opportunity_id)}),
        )
        .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
        .limit(1)
    )
    if workflow is None:
        return None
    agent = await session.scalar(
        select(AgentRun).where(
            AgentRun.organization_id == organization_id,
            AgentRun.workflow_run_id == workflow.id,
        )
    )
    return workflow, agent


def _reasoning_run_row(workflow: WorkflowRun, agent: AgentRun | None) -> dict[str, object]:
    terminal_failure = workflow.status in {"failed", "cancelled", "expired"}
    return {
        "workflow_run_id": str(workflow.id),
        "agent_run_id": str(agent.id) if agent else None,
        "status": workflow.status if terminal_failure or agent is None else agent.status,
        "safe_error_code": (
            (workflow.failure_code or (agent.safe_error_code if agent else None))
            if terminal_failure or agent is None
            else agent.safe_error_code
        ),
        "proposal_references": agent.output_references if agent else [],
    }


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def policy(key: str, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            key, ScopeType.ORGANIZATION, AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1
        )
    )


def meta(request: Request) -> dict[str, object]:
    return {"correlation_id": request_correlation_id(request)}


def website_row(item: SEOWebsite) -> dict[str, object]:
    return {
        "id": str(item.id),
        "location_id": str(item.location_id) if item.location_id else None,
        "key": item.key,
        "name": item.name,
        "canonical_origin": item.canonical_origin,
        "status": item.status,
        "ownership_status": item.ownership_status,
        "verified_at": item.verified_at,
    }


def search_property_row(item: SEOSearchProperty) -> dict[str, object]:
    return {
        "id": str(item.id),
        "provider": item.provider,
        "external_property_id": item.external_property_id,
        "property_type": item.property_type,
        "mapping_status": item.mapping_status,
        "freshness_status": item.freshness_status,
        "last_synced_at": item.last_synced_at,
    }


def opportunity_row(item: SEOOpportunity) -> dict[str, object]:
    return {
        "id": str(item.id),
        "website_id": str(item.website_id),
        "page_id": str(item.page_id) if item.page_id else None,
        "opportunity_type": item.opportunity_type,
        "recommendation_class": recommendation_class(item),
        "priority_score": item.priority_score,
        "score_explanation": item.score_explanation,
        "evidence": item.evidence,
        "status": item.status,
    }


def recommendation_row(item: SEORecommendationRevision) -> dict[str, object]:
    context = revision_decision(item.evidence_references)
    return {
        "id": str(item.id),
        "revision_number": item.revision_number,
        "proposed_action": item.proposed_action,
        "expected_result_hypothesis": item.expected_result_hypothesis,
        "risk": item.risk,
        "effort": item.effort,
        "status": item.status,
        "approved_by_user_id": str(item.approved_by_user_id) if item.approved_by_user_id else None,
        "evidence_references": [ref for ref in item.evidence_references if isinstance(ref, str)],
        "decision_context": context,
        "growth_handoff": (
            growth_handoff(
                item.id,
                item.status,
                item.expected_result_hypothesis,
                item.proposed_action,
                context,
            )
            if context
            else None
        ),
    }


def task_row(item: SEOImplementationTask) -> dict[str, object]:
    return {
        "id": str(item.id),
        "recommendation_revision_id": str(item.recommendation_revision_id),
        "workflow_run_id": str(item.workflow_run_id),
        "target_type": item.target_type,
        "target_reference": item.target_reference,
        "status": item.status,
        "verification_evidence": item.verification_evidence,
        "verified_at": item.verified_at,
    }


def outcome_row(item: SEOOutcome) -> dict[str, object]:
    return {
        "id": str(item.id),
        "implementation_task_id": str(item.implementation_task_id),
        "classification": item.classification,
        "metrics": item.metrics,
        "limitations": item.limitations,
        "baseline_start": item.baseline_start,
        "baseline_end": item.baseline_end,
        "measurement_start": item.measurement_start,
        "measurement_end": item.measurement_end,
    }


@router.get("/workspace", dependencies=[Depends(no_store)])
async def search_intelligence_workspace(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
    website_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> dict[str, object]:
    """Bounded, scoped work projection over existing SEO and integration records."""
    opportunities, has_more = await service.list_opportunities(
        session, organization_id, website_id=website_id, limit=limit, offset=offset
    )
    websites = list(
        await session.scalars(
            select(SEOWebsite)
            .where(SEOWebsite.organization_id == organization_id)
            .order_by(SEOWebsite.name, SEOWebsite.id)
            .limit(101)
        )
    )
    opportunity_site_ids = {item.website_id for item in opportunities}
    additional_sites = (
        list(
            await session.scalars(
                select(SEOWebsite).where(
                    SEOWebsite.organization_id == organization_id,
                    SEOWebsite.id.in_(opportunity_site_ids - {item.id for item in websites}),
                )
            )
        )
        if opportunity_site_ids
        else []
    )
    site_by_id = {item.id: item for item in [*websites, *additional_sites]}
    page_ids = [item.page_id for item in opportunities if item.page_id is not None]
    pages = (
        list(
            await session.scalars(
                select(SEOPage).where(
                    SEOPage.organization_id == organization_id, SEOPage.id.in_(page_ids)
                )
            )
        )
        if page_ids
        else []
    )
    page_by_id = {item.id: item for item in pages}
    opportunity_ids = [item.id for item in opportunities]
    revisions = (
        list(
            await session.scalars(
                select(SEORecommendationRevision)
                .where(
                    SEORecommendationRevision.organization_id == organization_id,
                    SEORecommendationRevision.opportunity_id.in_(opportunity_ids),
                )
                .order_by(
                    SEORecommendationRevision.created_at.desc(), SEORecommendationRevision.id.desc()
                )
                .limit(5001)
            )
        )
        if opportunity_ids
        else []
    )
    latest_revision: dict[UUID, SEORecommendationRevision] = {}
    for candidate_revision in revisions:
        latest_revision.setdefault(candidate_revision.opportunity_id, candidate_revision)
    revision_ids = [item.id for item in revisions]
    revision_by_id = {item.id: item for item in revisions}
    tasks = (
        list(
            await session.scalars(
                select(SEOImplementationTask)
                .where(
                    SEOImplementationTask.organization_id == organization_id,
                    SEOImplementationTask.recommendation_revision_id.in_(revision_ids),
                )
                .order_by(SEOImplementationTask.created_at.desc(), SEOImplementationTask.id.desc())
                .limit(5001)
            )
        )
        if revision_ids
        else []
    )
    latest_task: dict[UUID, SEOImplementationTask] = {}
    for candidate_task in tasks:
        latest_task.setdefault(candidate_task.recommendation_revision_id, candidate_task)
    task_ids = [item.id for item in latest_task.values()]
    outcomes = (
        list(
            await session.scalars(
                select(SEOOutcome)
                .where(
                    SEOOutcome.organization_id == organization_id,
                    SEOOutcome.implementation_task_id.in_(task_ids),
                )
                .order_by(SEOOutcome.created_at.desc(), SEOOutcome.id.desc())
                .limit(5001)
            )
        )
        if task_ids
        else []
    )
    latest_outcome: dict[UUID, SEOOutcome] = {}
    for candidate_outcome in outcomes:
        latest_outcome.setdefault(candidate_outcome.implementation_task_id, candidate_outcome)
    task_by_id = {item.id: item for item in tasks}
    learned_by_opportunity: dict[
        UUID, tuple[SEORecommendationRevision, SEOImplementationTask, SEOOutcome]
    ] = {}
    for candidate_outcome in outcomes:
        measured_task = task_by_id[candidate_outcome.implementation_task_id]
        measured_revision = revision_by_id[measured_task.recommendation_revision_id]
        learned_by_opportunity.setdefault(
            measured_revision.opportunity_id, (measured_revision, measured_task, candidate_outcome)
        )
    target_references = [f"seo-page:{page_id}" for page_id in page_ids]
    growth_pairs = (
        list(
            (
                await session.execute(
                    select(GrowthAction, GrowthInitiative)
                    .join(
                        GrowthInitiative,
                        (GrowthInitiative.organization_id == GrowthAction.organization_id)
                        & (GrowthInitiative.id == GrowthAction.initiative_id),
                    )
                    .where(
                        GrowthAction.organization_id == organization_id,
                        GrowthAction.target_reference.in_(target_references),
                    )
                    .order_by(GrowthAction.created_at.desc())
                    .limit(501)
                )
            ).all()
        )
        if target_references
        else []
    )
    growth_by_revision: dict[UUID, GrowthAction] = {}
    for action, initiative in growth_pairs[:500]:
        for ref in action.evidence_references:
            if not str(ref).startswith("seo-recommendation:"):
                continue
            try:
                revision_id = UUID(str(ref).split(":", 1)[1])
            except ValueError:
                continue
            linked_revision = revision_by_id.get(revision_id)
            linked_opportunity = (
                next(
                    (item for item in opportunities if item.id == linked_revision.opportunity_id),
                    None,
                )
                if linked_revision
                else None
            )
            if (
                linked_opportunity is not None
                and linked_revision is not None
                and initiative.location_id == linked_opportunity.location_id
                and action.target_reference == f"seo-page:{linked_opportunity.page_id}"
                and action.expected_result_hypothesis == linked_revision.expected_result_hypothesis
            ):
                growth_by_revision.setdefault(revision_id, action)
    active_by_page: dict[UUID, dict[str, str]] = {}
    active_history_truncated = False
    if page_ids:
        approved_pairs = list(
            (
                await session.execute(
                    select(SEORecommendationRevision, SEOOpportunity)
                    .join(
                        SEOOpportunity,
                        (
                            SEOOpportunity.organization_id
                            == SEORecommendationRevision.organization_id
                        )
                        & (SEOOpportunity.id == SEORecommendationRevision.opportunity_id),
                    )
                    .where(
                        SEORecommendationRevision.organization_id == organization_id,
                        SEORecommendationRevision.status == "approved",
                        SEOOpportunity.page_id.in_(page_ids),
                    )
                    .order_by(SEORecommendationRevision.created_at.desc())
                    .limit(5001)
                )
            ).all()
        )
        active_history_truncated = len(approved_pairs) > 5000
        active_revision_ids = [revision.id for revision, _ in approved_pairs]
        active_tasks = (
            list(
                await session.scalars(
                    select(SEOImplementationTask)
                    .where(
                        SEOImplementationTask.organization_id == organization_id,
                        SEOImplementationTask.recommendation_revision_id.in_(active_revision_ids),
                    )
                    .order_by(SEOImplementationTask.created_at.desc())
                    .limit(5001)
                )
            )
            if active_revision_ids
            else []
        )
        active_history_truncated = active_history_truncated or len(active_tasks) > 5000
        active_task_by_revision: dict[UUID, SEOImplementationTask] = {}
        for active_task in active_tasks:
            active_task_by_revision.setdefault(active_task.recommendation_revision_id, active_task)
        active_outcome_task_ids = (
            list(
                await session.scalars(
                    select(SEOOutcome.implementation_task_id).where(
                        SEOOutcome.organization_id == organization_id,
                        SEOOutcome.implementation_task_id.in_([item.id for item in active_tasks]),
                    )
                )
            )
            if active_tasks
            else []
        )
        measured_task_ids = set(active_outcome_task_ids)
        for approved_revision, approved_opp in approved_pairs:
            if (
                approved_opp.page_id is None
                or recommendation_class(approved_opp) != "growth_change"
                or approved_opp.page_id in active_by_page
            ):
                continue
            matching_active_task = active_task_by_revision.get(approved_revision.id)
            if matching_active_task and matching_active_task.status in {"failed", "cancelled"}:
                continue
            if matching_active_task and matching_active_task.id in measured_task_ids:
                continue
            state = (
                "approved_awaiting_implementation"
                if matching_active_task is None
                else "implemented_measuring"
                if matching_active_task.verified_at
                else "implementing"
            )
            active_by_page[approved_opp.page_id] = {
                "revision_id": str(approved_revision.id),
                "state": state,
            }
    readiness_site_ids = [item.id for item in websites[:100]]
    gsc = (
        list(
            await session.scalars(
                select(SEOSearchProperty).where(
                    SEOSearchProperty.organization_id == organization_id,
                    SEOSearchProperty.website_id.in_(readiness_site_ids),
                )
            )
        )
        if readiness_site_ids
        else []
    )
    ga4 = (
        list(
            await session.scalars(
                select(AnalyticsProperty).where(
                    AnalyticsProperty.organization_id == organization_id,
                    AnalyticsProperty.website_id.in_(readiness_site_ids),
                )
            )
        )
        if readiness_site_ids
        else []
    )
    inventory_sites = (
        set(
            await session.scalars(
                select(SEOPage.website_id)
                .where(
                    SEOPage.organization_id == organization_id,
                    SEOPage.website_id.in_(readiness_site_ids),
                )
                .distinct()
            )
        )
        if readiness_site_ids
        else set()
    )
    readiness = []
    for readiness_site in websites[:100]:
        site_gsc = [
            item
            for item in gsc
            if item.website_id == readiness_site.id and item.mapping_status == "mapped"
        ]
        site_ga4 = [
            item
            for item in ga4
            if item.website_id == readiness_site.id and item.mapping_status == "mapped"
        ]
        readiness.append(
            {
                "website_id": str(readiness_site.id),
                "website_name": readiness_site.name,
                "location_id": str(readiness_site.location_id)
                if readiness_site.location_id
                else None,
                "gsc": "fresh"
                if any(item.freshness_status == "fresh" for item in site_gsc)
                else "stale"
                if site_gsc
                else "unavailable",
                "ga4": "fresh"
                if any(item.freshness_status == "fresh" for item in site_ga4)
                else "stale"
                if site_ga4
                else "unavailable",
                "page_inventory": "observed"
                if readiness_site.id in inventory_sites
                else "unavailable",
            }
        )
    rows = []
    for opportunity in opportunities:
        site = site_by_id.get(opportunity.website_id)
        page = page_by_id.get(opportunity.page_id) if opportunity.page_id else None
        if (
            site is None
            or site.location_id != opportunity.location_id
            or (opportunity.page_id is not None and (page is None or page.website_id != site.id))
        ):
            continue
        revision = latest_revision.get(opportunity.id)
        task = latest_task.get(revision.id) if revision else None
        outcome = latest_outcome.get(task.id) if task else None
        learned = learned_by_opportunity.get(opportunity.id)
        growth_action = growth_by_revision.get(revision.id) if revision else None
        measurement: dict[str, object] | None = None
        if revision and recommendation_class(opportunity) == "growth_change":
            plan = (
                parse_verification_plan(dict(growth_action.verification_plan or {}))
                if growth_action
                else None
            )
            if task and task.verified_at and plan:
                baseline_start, baseline_end, measurement_start, measurement_end = seo_page_periods(
                    task.verified_at, plan.window_days
                )
                tail = (
                    GSC_SYNC_TAIL_EXCLUSION_DAYS
                    if METRIC_SPECS[plan.metric].family == "gsc"
                    else GA4_SYNC_TAIL_EXCLUSION_DAYS
                )
                measurement = {
                    "metric": plan.metric,
                    "baseline_start": baseline_start,
                    "baseline_end": baseline_end,
                    "measurement_start": measurement_start,
                    "measurement_end": measurement_end,
                    "maturity": "mature"
                    if datetime.now(UTC) >= measurement_end + timedelta(days=tail)
                    else "pending",
                    "limitation": (
                        "Page-level GA4 outcome measurement is unavailable."
                        if METRIC_SPECS[plan.metric].family != "gsc"
                        else None
                    ),
                }
            else:
                context = revision_decision(revision.evidence_references)
                measurement = {
                    "metric": context.get("target_metric") if context else None,
                    "maturity": "unavailable",
                    "limitation": (
                        "Implementation is not verified."
                        if not task or not task.verified_at
                        else "No supported linked Growth measurement plan exists."
                    ),
                }
        rows.append(
            {
                "opportunity": opportunity_row(opportunity),
                "website": website_row(site),
                "page": page_row(page) if page else None,
                "recommendation": recommendation_row(revision) if revision else None,
                "task": task_row(task) if task else None,
                "outcome": outcome_row(outcome) if outcome else None,
                "measurement": measurement,
                "latest_measured": {
                    "recommendation": recommendation_row(learned[0]),
                    "task": task_row(learned[1]),
                    "outcome": outcome_row(learned[2]),
                }
                if learned
                else None,
                "active_change": (
                    active_by_page.get(opportunity.page_id)
                    if opportunity.page_id and recommendation_class(opportunity) == "growth_change"
                    else None
                ),
            }
        )
    return {
        "data": {
            "items": rows,
            "readiness": readiness,
            "readiness_has_more": len(websites) > 100,
            "history_truncated": (
                any(len(history) > 5000 for history in (revisions, tasks, outcomes))
                or len(growth_pairs) > 500
                or active_history_truncated
            ),
            "pagination": {
                "limit": limit,
                "offset": offset,
                "next_offset": offset + limit if has_more else None,
                "has_more": has_more,
            },
        },
        "pagination": {
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if has_more else None,
            "has_more": has_more,
        },
        "meta": meta(request),
    }


@router.get("/websites", dependencies=[Depends(no_store)])
async def list_websites(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    items = await service.list_websites(session, organization_id)
    return {"data": [website_row(item) for item in items], "meta": meta(request)}


@router.post("/websites", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)])
async def create_website(
    request: Request,
    organization_id: UUID,
    command: WebsiteCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.manage")],
) -> dict[str, object]:
    item = await service.create_website(
        session,
        organization_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": website_row(item), "meta": meta(request)}


@router.get("/websites/{website_id}", dependencies=[Depends(no_store)])
async def get_website(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    item = await service.get_website(session, organization_id, website_id)
    return {"data": website_row(item), "meta": meta(request)}


@router.get("/websites/{website_id}/audit", dependencies=[Depends(no_store)])
async def website_audit(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("audit.read")],
) -> dict[str, object]:
    await service.get_website(session, organization_id, website_id)
    history = await service.resource_history(
        session, organization_id, resource_type="seo_website", resource_id=website_id
    )
    return {"data": history, "meta": meta(request)}


@router.get("/websites/{website_id}/search-properties", dependencies=[Depends(no_store)])
async def list_search_properties(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    items = await service.list_search_properties(session, organization_id, website_id)
    return {"data": [search_property_row(item) for item in items], "meta": meta(request)}


@router.post(
    "/websites/{website_id}/search-properties",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def create_search_property(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    command: SearchPropertyCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.manage")],
) -> dict[str, object]:
    item = await service.create_search_property(
        session,
        organization_id,
        website_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": search_property_row(item), "meta": meta(request)}


@router.get(
    "/websites/{website_id}/search-console/discover",
    dependencies=[Depends(no_store)],
    summary="Discover accessible Search Console properties and recommend a match",
)
async def discover_search_console(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.manage")],
) -> dict[str, object]:
    settings = settings_from_request(request)
    result = await search_console.discover_properties(
        session,
        settings,
        organization_id,
        website_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {
            "properties": [
                {
                    "external_property_id": p.external_property_id,
                    "property_type": p.property_type,
                    "permission_level": p.permission_level,
                }
                for p in result.properties
            ],
            "recommended": (
                {
                    "external_property_id": result.recommended.external_property_id,
                    "property_type": result.recommended.property_type,
                    "permission_level": result.recommended.permission_level,
                }
                if result.recommended is not None
                else None
            ),
        },
        "meta": meta(request),
    }


@router.post(
    "/websites/{website_id}/search-console/map",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
    summary="Map the operator-selected Search Console property",
)
async def map_search_console(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    command: SearchPropertySelect,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.manage")],
) -> dict[str, object]:
    settings = settings_from_request(request)
    item = await search_console.map_property(
        session,
        settings,
        organization_id,
        website_id,
        external_property_id=command.external_property_id,
        property_type=command.property_type,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": search_property_row(item), "meta": meta(request)}


@router.post(
    "/websites/{website_id}/search-properties/{search_property_id}/sync",
    dependencies=[Depends(no_store)],
    summary="Sync Search Console observations for a mapped property",
)
async def sync_search_console(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    search_property_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.manage")],
    command: SearchConsoleSyncRequest | None = None,
) -> dict[str, object]:
    settings = settings_from_request(request)
    days = command.days if command is not None else 28
    result = await search_console.sync_observations(
        session,
        settings,
        organization_id,
        search_property_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
        days=days,
    )
    return {"data": result, "meta": meta(request)}


@router.get(
    "/websites/{website_id}/search-console/performance",
    dependencies=[Depends(no_store)],
    summary=(
        "Search Console performance report — period comparison, daily series, top queries and pages"
    ),
)
async def search_console_performance(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
    days: int = 28,
) -> dict[str, object]:
    result = await search_console.performance_report(
        session, organization_id, website_id, days=days
    )
    return {"data": result, "meta": meta(request)}


@router.get(
    "/websites/{website_id}/search-console/summary",
    dependencies=[Depends(no_store)],
    summary="Aggregate synced Search Console performance for the SEO page",
)
async def search_console_summary(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    result = await search_console.search_performance_summary(session, organization_id, website_id)
    return {"data": result, "meta": meta(request)}


@router.get("/websites/{website_id}/landing-page-gaps", dependencies=[Depends(no_store)])
async def landing_page_gaps(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    gaps = await service.local_landing_page_gaps(session, organization_id, website_id)
    return {"data": gaps, "meta": meta(request)}


def crawl_run_row(item: SEOCrawlRun) -> dict[str, object]:
    return {
        "id": str(item.id),
        "website_id": str(item.website_id),
        "status": item.status,
        "max_pages": item.max_pages,
        "max_depth": item.max_depth,
        "crawl_delay_seconds": item.crawl_delay_seconds,
        "stop_reason": item.stop_reason,
        "safe_result": item.safe_result,
        "started_at": item.started_at,
        "completed_at": item.completed_at,
        "created_at": item.created_at,
    }


def page_row(item: SEOPage | SEOCrawlPageObservation) -> dict[str, object]:
    return {
        "id": str(item.page_id if isinstance(item, SEOCrawlPageObservation) else item.id),
        "website_id": str(item.website_id),
        "normalized_url": item.normalized_url,
        "observed_url": item.observed_url,
        "http_status": item.http_status,
        "content_type": item.content_type,
        "title": item.title,
        "meta_description": item.meta_description,
        "h1": item.h1,
        "canonical_url": item.canonical_url,
        "robots_directives": item.robots_directives,
        "internal_links_count": len(item.internal_links) if item.internal_links else 0,
        "external_links_count": len(item.external_links) if item.external_links else 0,
        "word_count": item.word_count,
        "structured_data_present": item.structured_data_present,
        "content_hash": item.content_hash,
        "indexability": item.indexability,
        "crawl_depth": item.crawl_depth,
        "redirect_destination": item.redirect_destination,
    }


@router.post(
    "/websites/{website_id}/crawl",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(no_store)],
)
async def run_crawl(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    command: CrawlRequest,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.manage")],
) -> dict[str, object]:
    crawl_run = await service.enqueue_crawl(
        session,
        organization_id,
        website_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": crawl_run_row(crawl_run),
        "meta": meta(request),
    }


@router.get("/crawl-runs", dependencies=[Depends(no_store)])
async def list_crawl_runs(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
    website_id: UUID | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, object]:
    items = await service.list_crawl_runs(
        session, organization_id, website_id=website_id, limit=limit, offset=offset
    )
    return {"data": [crawl_run_row(item) for item in items], "meta": meta(request)}


@router.get("/crawl-runs/{crawl_run_id}", dependencies=[Depends(no_store)])
async def get_crawl_run(
    request: Request,
    organization_id: UUID,
    crawl_run_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    item = await service.get_crawl_run(session, organization_id, crawl_run_id)
    if not item:
        raise SEOCrawlRunNotFoundError
    return {"data": crawl_run_row(item), "meta": meta(request)}


@router.get("/crawl-runs/{crawl_run_id}/pages", dependencies=[Depends(no_store)])
async def list_crawl_pages(
    request: Request,
    organization_id: UUID,
    crawl_run_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    crawl_run = await service.get_crawl_run(session, organization_id, crawl_run_id)
    if not crawl_run:
        raise SEOCrawlRunNotFoundError
    items = await service.list_crawl_page_observations(session, organization_id, crawl_run_id)
    evidence_status = (
        "available"
        if crawl_run.safe_result.get("page_evidence_version") == "crawl_page.v1"
        else "unavailable_legacy_run"
    )
    return {
        "data": [page_row(item) for item in items],
        "meta": {**meta(request), "evidence_status": evidence_status},
    }


@router.get(
    "/websites/{website_id}/pages/{page_id}/intelligence",
    dependencies=[Depends(no_store)],
)
async def get_page_intelligence(
    request: Request,
    organization_id: UUID,
    website_id: UUID,
    page_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    data = await read_page_intelligence(session, organization_id, website_id, page_id)
    if data is None:
        raise SEOWebsiteNotFoundError
    return {"data": data, "meta": meta(request)}


@router.get("/summary", dependencies=[Depends(no_store)])
async def summary(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    return {"data": await service.summary(session, organization_id), "meta": meta(request)}


@router.get("/opportunities", dependencies=[Depends(no_store)])
async def list_opportunities(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
    website_id: UUID | None = None,
    status_filter: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    items, has_more = await service.list_opportunities(
        session,
        organization_id,
        website_id=website_id,
        status_filter=status_filter,
        limit=limit,
        offset=offset,
    )
    return {
        "data": [opportunity_row(item) for item in items],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if has_more else None,
            "has_more": has_more,
        },
        "meta": meta(request),
    }


@router.get("/opportunities/{opportunity_id}", dependencies=[Depends(no_store)])
async def get_opportunity(
    request: Request,
    organization_id: UUID,
    opportunity_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    item = await service.get_opportunity(session, organization_id, opportunity_id)
    return {"data": opportunity_row(item), "meta": meta(request)}


@router.get("/opportunities/{opportunity_id}/audit", dependencies=[Depends(no_store)])
async def opportunity_audit(
    request: Request,
    organization_id: UUID,
    opportunity_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("audit.read")],
) -> dict[str, object]:
    await service.get_opportunity(session, organization_id, opportunity_id)
    history = await service.resource_history(
        session, organization_id, resource_type="seo_opportunity", resource_id=opportunity_id
    )
    return {"data": history, "meta": meta(request)}


@router.get("/opportunities/{opportunity_id}/recommendations", dependencies=[Depends(no_store)])
async def list_recommendations(
    request: Request,
    organization_id: UUID,
    opportunity_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    items = await service.list_recommendations(session, organization_id, opportunity_id)
    return {"data": [recommendation_row(item) for item in items], "meta": meta(request)}


@router.get("/opportunities/{opportunity_id}/hermes-run", dependencies=[Depends(no_store)])
async def get_opportunity_hermes_run(
    request: Request,
    organization_id: UUID,
    opportunity_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    await service.get_opportunity(session, organization_id, opportunity_id)
    found = await _opportunity_reasoning_run(session, organization_id, opportunity_id)
    return {"data": _reasoning_run_row(*found) if found else None, "meta": meta(request)}


@router.post("/opportunities/{opportunity_id}/hermes-run", dependencies=[Depends(no_store)])
async def start_opportunity_hermes_run(
    request: Request,
    organization_id: UUID,
    opportunity_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.recommend")],
    __: Annotated[AuthorizationDecision, policy("workflows.execute")],
) -> dict[str, object]:
    opportunity = await session.scalar(
        select(SEOOpportunity)
        .where(
            SEOOpportunity.organization_id == organization_id, SEOOpportunity.id == opportunity_id
        )
        .with_for_update()
    )
    if opportunity is None:
        raise SEOOpportunityNotFoundError
    if opportunity.location_id is None:
        raise HTTPException(
            status_code=409, detail="A scoped location is required for Hermes reasoning"
        )
    eligibility = await agent_access.decision(
        session,
        organization_id=organization_id,
        location_id=opportunity.location_id,
        product_key="seo",
    )
    if not eligibility.eligible:
        raise HTTPException(
            status_code=eligibility.status_code,
            detail=eligibility.detail or "SEO agent is unavailable for this location",
        )
    current = await resolve_decision(
        session, organization_id, opportunity, [f"seo-opportunity:{opportunity.id}"]
    )
    if current["recommendation_class"] == "growth_change" and opportunity.page_id:
        await service._check_active_growth_change(session, organization_id, opportunity)
    existing = await _opportunity_reasoning_run(session, organization_id, opportunity_id)
    if existing and existing[0].status in {
        "created",
        "queued",
        "running",
        "waiting",
        "waiting_approval",
        "retry_scheduled",
    }:
        return {"data": _reasoning_run_row(*existing), "meta": meta(request)}
    run = await execution.start_named(
        session,
        organization_id,
        "agent.seo",
        f"seo-hermes-{opportunity.id}-{uuid4().hex}",
        location_id=opportunity.location_id,
        input_document={
            "seo_opportunity_id": str(opportunity.id),
            "seo_decision_snapshot": current,
            "context_reference": f"seo-opportunity:{opportunity.id}",
            "objective": (
                "Analyze only the bound Search Intelligence opportunity. Read its current "
                "canonical decision with analyze_seo_opportunities, then propose exactly one "
                "governed SEO recommendation for human review. Do not approve or execute it."
            ),
        },
        correlation_id=request_correlation_id(request),
        actor_id=principal.platform_user_id,
        enqueue_job=True,
    )
    return {"data": _reasoning_run_row(run, None), "meta": meta(request)}


@router.post(
    "/opportunities/{opportunity_id}/recommendations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def create_recommendation(
    request: Request,
    organization_id: UUID,
    opportunity_id: UUID,
    command: RecommendationCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.recommend")],
) -> dict[str, object]:
    item = await service.create_recommendation(
        session,
        organization_id,
        opportunity_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": recommendation_row(item), "meta": meta(request)}


@router.post("/recommendations/{revision_id}/decision", dependencies=[Depends(no_store)])
async def decide_recommendation(
    request: Request,
    organization_id: UUID,
    revision_id: UUID,
    command: RecommendationDecision,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.approve", True)],
) -> dict[str, object]:
    correlation_id = request_correlation_id(request)
    item = await service.decide_recommendation(
        session,
        organization_id,
        revision_id,
        command,
        principal.platform_user_id,
        correlation_id=correlation_id,
    )
    workflow_run_id = None
    if command.approve:
        workflow_run_id = await orchestration.handoff_approved_recommendation(
            session,
            organization_id,
            item,
            actor_id=principal.platform_user_id,
            correlation_id=correlation_id,
        )
        if workflow_run_id is not None:
            opportunity = await service.get_opportunity(
                session, organization_id, item.opportunity_id
            )
            await service.create_implementation_task(
                session,
                organization_id,
                item.id,
                ImplementationTaskCreate(
                    workflow_run_id=UUID(workflow_run_id),
                    target_type="page" if opportunity.page_id else "opportunity",
                    target_reference=(
                        f"seo-page:{opportunity.page_id}"
                        if opportunity.page_id
                        else f"seo-opportunity:{opportunity.id}"
                    ),
                ),
                actor_id=principal.platform_user_id,
                correlation_id=correlation_id,
            )
    response_meta = meta(request)
    if workflow_run_id is not None:
        response_meta = {
            **response_meta,
            "workflow_run_id": workflow_run_id,
            "workflow_key": "agent.content",
        }
    return {"data": recommendation_row(item), "meta": response_meta}


@router.get("/recommendations/{revision_id}/tasks", dependencies=[Depends(no_store)])
async def list_implementation_tasks(
    request: Request,
    organization_id: UUID,
    revision_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("seo.read")],
) -> dict[str, object]:
    items = await service.list_implementation_tasks(session, organization_id, revision_id)
    return {"data": [task_row(item) for item in items], "meta": meta(request)}


@router.post(
    "/recommendations/{revision_id}/tasks",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def create_implementation_task(
    request: Request,
    organization_id: UUID,
    revision_id: UUID,
    command: ImplementationTaskCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.execute")],
) -> dict[str, object]:
    item = await service.create_implementation_task(
        session,
        organization_id,
        revision_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": task_row(item), "meta": meta(request)}


@router.post("/tasks/{task_id}/verify", dependencies=[Depends(no_store)])
async def verify_implementation_task(
    request: Request,
    organization_id: UUID,
    task_id: UUID,
    command: ImplementationTaskVerify,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.execute")],
) -> dict[str, object]:
    item = await service.verify_implementation_task(
        session,
        organization_id,
        task_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": task_row(item), "meta": meta(request)}


@router.post(
    "/tasks/{task_id}/outcome",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def record_outcome(
    request: Request,
    organization_id: UUID,
    task_id: UUID,
    command: OutcomeRecord,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("seo.execute")],
) -> dict[str, object]:
    item = await service.record_outcome(
        session,
        organization_id,
        task_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": outcome_row(item), "meta": meta(request)}
