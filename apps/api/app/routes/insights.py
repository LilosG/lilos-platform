"""Protected Insights APIs backed by real cross-product activity data."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import (
    Authenticated,
    get_authenticated_principal,
)
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.insights.aggregation_service import InsightsService
from apps.api.app.insights.website_readiness import WebsiteReadinessService
from apps.api.app.products.analytics.contracts import (
    AnalyticsDiscoverRequest,
    AnalyticsPropertySelect,
    AnalyticsSyncRequest,
)
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.routes.health import settings_from_request

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/insights",
    tags=["insights"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = InsightsService()
analytics = AnalyticsService()
website_readiness = WebsiteReadinessService()
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


@router.get("/summary", dependencies=[Depends(no_store)])
async def summary(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("insights.read")],
) -> dict[str, object]:
    return {"data": await service.summary(session, organization_id), "meta": meta(request)}


@router.get(
    "/website-readiness",
    dependencies=[Depends(no_store)],
    summary="Derived website readiness facts — domain, SEO, Search Console, Analytics, crawl",
)
async def website_readiness_route(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("insights.read")],
) -> dict[str, object]:
    result = await website_readiness.readiness(session, organization_id)
    return {"data": result, "meta": meta(request)}


@router.post(
    "/analytics/discover",
    dependencies=[Depends(no_store)],
    summary="Discover accessible GA4 properties and recommend a match",
)
async def discover_analytics(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("insights.manage")],
    command: AnalyticsDiscoverRequest | None = None,
) -> dict[str, object]:
    settings = settings_from_request(request)
    website_id = command.website_id if command is not None else None
    result = await analytics.discover_properties(
        session,
        settings,
        organization_id,
        website_id=website_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {
            "properties": [
                {
                    "external_property_id": p.external_property_id,
                    "property_number": p.property_number,
                    "display_name": p.display_name,
                    "account_display_name": p.account_display_name,
                }
                for p in result.properties
            ],
            "recommended": (
                {
                    "external_property_id": result.recommended.external_property_id,
                    "property_number": result.recommended.property_number,
                    "display_name": result.recommended.display_name,
                    "account_display_name": result.recommended.account_display_name,
                }
                if result.recommended is not None
                else None
            ),
        },
        "meta": meta(request),
    }


@router.post(
    "/analytics/map",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
    summary="Map the operator-selected GA4 property",
)
async def map_analytics(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("insights.manage")],
    command: AnalyticsPropertySelect,
) -> dict[str, object]:
    settings = settings_from_request(request)
    item = await analytics.map_property(
        session,
        settings,
        organization_id,
        external_property_id=command.external_property_id,
        property_number=command.property_number,
        display_name=command.display_name,
        website_id=None,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {
            "id": str(item.id),
            "display_name": item.display_name,
            "external_property_id": item.external_property_id,
            "mapping_status": item.mapping_status,
            "freshness_status": item.freshness_status,
        },
        "meta": meta(request),
    }


@router.post(
    "/analytics/properties/{analytics_property_id}/sync",
    dependencies=[Depends(no_store)],
    summary="Sync GA4 metrics for a mapped property",
)
async def sync_analytics(
    request: Request,
    organization_id: UUID,
    analytics_property_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("insights.manage")],
    command: AnalyticsSyncRequest | None = None,
) -> dict[str, object]:
    settings = settings_from_request(request)
    days = command.days if command is not None else 28
    result = await analytics.sync_metrics(
        session,
        settings,
        organization_id,
        analytics_property_id,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
        days=days,
    )
    return {"data": result, "meta": meta(request)}


@router.get(
    "/analytics/performance",
    dependencies=[Depends(no_store)],
    summary="GA4 performance report with period comparison and daily series",
)
async def analytics_performance(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("insights.read")],
    days: int = 28,
) -> dict[str, object]:
    result = await analytics.performance_report(session, organization_id, days=days)
    return {"data": result, "meta": meta(request)}


@router.get(
    "/analytics/summary",
    dependencies=[Depends(no_store)],
    summary="Aggregate synced GA4 metrics for the Insights page",
)
async def analytics_summary(
    request: Request,
    organization_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("insights.read")],
) -> dict[str, object]:
    result = await analytics.summary(session, organization_id)
    return {"data": result, "meta": meta(request)}
