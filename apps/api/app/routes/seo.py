"""Protected evidence-driven SEO APIs."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
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
from apps.api.app.products.seo.models import (
    SEOImplementationTask,
    SEOOpportunity,
    SEOOutcome,
    SEORecommendationRevision,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from apps.api.app.products.seo.service import SEOService
from apps.api.app.routes.health import settings_from_request

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/seo",
    tags=["seo"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = SEOService()
search_console = SearchConsoleService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


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
        "priority_score": item.priority_score,
        "score_explanation": item.score_explanation,
        "evidence": item.evidence,
        "status": item.status,
    }


def recommendation_row(item: SEORecommendationRevision) -> dict[str, object]:
    return {
        "id": str(item.id),
        "revision_number": item.revision_number,
        "proposed_action": item.proposed_action,
        "expected_result_hypothesis": item.expected_result_hypothesis,
        "risk": item.risk,
        "effort": item.effort,
        "status": item.status,
        "approved_by_user_id": str(item.approved_by_user_id) if item.approved_by_user_id else None,
    }


def task_row(item: SEOImplementationTask) -> dict[str, object]:
    return {
        "id": str(item.id),
        "target_type": item.target_type,
        "target_reference": item.target_reference,
        "status": item.status,
        "verification_evidence": item.verification_evidence,
        "verified_at": item.verified_at,
    }


def outcome_row(item: SEOOutcome) -> dict[str, object]:
    return {
        "id": str(item.id),
        "classification": item.classification,
        "metrics": item.metrics,
        "limitations": item.limitations,
        "measurement_start": item.measurement_start,
        "measurement_end": item.measurement_end,
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
    crawl_run, opportunities = await service.run_crawl(
        session,
        organization_id,
        website_id,
        command.workflow_run_id,
        command,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {
            "crawl_run_id": str(crawl_run.id),
            "status": crawl_run.status,
            "safe_result": crawl_run.safe_result,
            "opportunities_created": [opportunity_row(item) for item in opportunities],
        },
        "meta": meta(request),
    }


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
    item = await service.decide_recommendation(
        session,
        organization_id,
        revision_id,
        command,
        principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {"data": recommendation_row(item), "meta": meta(request)}


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
