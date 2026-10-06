"""Typed presentation projections over canonical Integrations and Local Search services.

No provider I/O on reads, no new write lifecycle, and independently authorized sources.
"""

from dataclasses import asdict
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, JsonValue
from sqlalchemy import case, func, select

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationRequest
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.integrations.directory_service import IntegrationDirectoryService
from apps.api.app.locations.models import Location
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.gbp.models import GBPLocation, GBPProfileSnapshot
from apps.api.app.products.gbp.operations_contracts import PostPublicationData
from apps.api.app.products.gbp.operations_errors import GBPCapabilitySnapshotNotFoundError
from apps.api.app.products.gbp.operations_models import GBPProviderPost
from apps.api.app.products.gbp.operations_service import GBPOperationsService
from apps.api.app.products.gbp.performance_read import (
    PerformancePeriod,
    read_actions_by_organization,
)
from apps.api.app.products.gbp.service import profile_health
from apps.api.app.products.seo.local_search_insights import (
    Insight,
    InsightCode,
    InsightLink,
    ProfileActions,
    build_insights,
)
from apps.api.app.products.seo.models import SEOPage, SEOSearchProperty
from apps.api.app.products.seo.page_intelligence import read_page_intelligence
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from apps.api.app.routes.command_center import authorization
from apps.api.app.routes.gbp import policy as location_policy
from apps.api.app.routes.gbp_operations import post_revision_row, provider_post_row
from apps.api.app.routes.seo import Session, meta, no_store, policy, service

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(no_store)],
)


class ReadDTO(BaseModel):
    model_config = ConfigDict(extra="ignore")


class WebsiteOption(ReadDTO):
    id: UUID
    name: str
    canonical_origin: str
    location_id: UUID | None
    status: str


class LocationOption(ReadDTO):
    id: UUID
    name: str
    can_map: bool


class SearchMapping(ReadDTO):
    id: UUID
    website_id: UUID | None
    external_property_id: str
    mapping_status: str
    freshness_status: str
    last_synced_at: datetime | None
    property_type: str | None = None
    display_name: str | None = None
    can_sync: bool = False


class GoogleCapability(ReadDTO):
    key: str
    label: str
    enabled: bool


class GoogleMapping(ReadDTO):
    id: UUID
    external_resource_id: str
    platform_resource_id: UUID | None
    resource_type: str
    status: str
    display_name: str | None
    last_synced_at: datetime | None
    sync_freshness: str
    gbp_location_id: UUID | None
    mapping_status: str | None
    write_enabled: bool | None


class GoogleState(ReadDTO):
    connection_status: str
    connection_id: UUID | None
    token_expires_at: datetime | None
    last_verified_at: datetime | None
    capabilities: list[GoogleCapability]
    mapped_resources: list[GoogleMapping]
    unmapped_count: int


class UnmappedProfile(ReadDTO):
    id: UUID
    business_name: str
    external_location_id: str


class SyncState(ReadDTO):
    id: UUID
    status: str
    failure_code: str | None
    started_at: datetime | None
    completed_at: datetime | None
    source_id: str | None
    source: Literal["search_console", "analytics"]


async def sync_states(
    session: Session, organization_id: UUID, *, analytics: bool
) -> list[SyncState]:
    rows = list(
        await session.scalars(
            select(WorkflowRun)
            .where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.input_document.has_key("search_property_id")
                | (
                    WorkflowRun.input_document.has_key("analytics_property_id")
                    if analytics
                    else False
                ),
            )
            .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
            .limit(20)
        )
    )
    return [
        SyncState(
            id=row.id,
            status=row.status,
            failure_code=row.failure_code,
            started_at=row.started_at,
            completed_at=row.completed_at,
            source_id=str(
                row.input_document.get("search_property_id")
                or row.input_document.get("analytics_property_id")
            )
            if (
                row.input_document.get("search_property_id")
                or row.input_document.get("analytics_property_id")
            )
            else None,
            source="search_console"
            if row.input_document.get("search_property_id")
            else "analytics",
        )
        for row in rows
    ]


class IntegrationView(ReadDTO):
    organization_id: UUID
    syncs: list[SyncState]
    google: GoogleState
    websites: list[WebsiteOption]
    locations: list[LocationOption]
    search_properties: list[SearchMapping]
    analytics_properties: list[SearchMapping]
    unmapped_profiles: list[UnmappedProfile]
    can_connect: bool
    can_manage_search: bool
    can_manage_analytics: bool
    github_status: str | None
    github_limitation: Literal["publishing_configuration_remains_in_existing_control_plane"] = (
        "publishing_configuration_remains_in_existing_control_plane"
    )


class MetricComparison(ReadDTO):
    current: float | None
    previous: float | None
    delta: float | None
    percent_delta: float | None
    quality: str
    label: str | None = None


class Freshness(ReadDTO):
    last_synced_at: datetime | None
    status: str


class SearchQuery(ReadDTO):
    query: str
    clicks: float | None
    impressions: float | None
    ctr: float | None
    position: float | None


class IndexStatus(StrEnum):
    """What the latest site crawl says about a landing page. Not Google's index."""

    INDEXABLE = "indexable"
    NOT_INDEXABLE = "not_indexable"
    NOT_CRAWLED = "not_crawled"


class SearchLanding(ReadDTO):
    page: str
    page_id: UUID | None = None
    index_status: IndexStatus = IndexStatus.NOT_CRAWLED
    clicks: float | None
    impressions: float | None
    ctr: float | None
    position: float | None


class PerformanceProperty(ReadDTO):
    id: UUID
    external_property_id: str
    freshness_status: str
    last_synced_at: datetime | None


class ReportingRange(ReadDTO):
    start: str
    end: str
    days: int


class SearchPerformance(ReadDTO):
    connected: bool
    properties: list[PerformanceProperty]
    range: ReportingRange | None
    comparison_range: ReportingRange | None
    freshness: Freshness
    metrics: dict[str, MetricComparison]
    series: list[dict[str, JsonValue]]
    top_queries: list[SearchQuery] = []
    top_pages: list[SearchLanding] = []


class CrawlView(ReadDTO):
    id: UUID
    website_id: UUID
    status: str
    stop_reason: str | None
    started_at: datetime | None
    completed_at: datetime | None
    safe_result: dict[str, JsonValue]


class PageSummary(ReadDTO):
    id: UUID
    website_id: UUID
    normalized_url: str
    title: str | None
    http_status: int | None
    indexability: str | None
    quality_status: str
    observed_at: datetime | None
    technical_issues: list[JsonValue]


class ProfileSummary(ReadDTO):
    id: UUID
    location_id: UUID
    business_name: str
    mapping_status: str
    write_enabled: bool
    last_synced_at: datetime | None


class InsightView(ReadDTO):
    """A deterministic finding as a code and numbers; the console words it."""

    code: InsightCode
    link: InsightLink
    subject: str | None
    current: float | None
    previous: float | None
    percent_change: float | None
    count: int | None


class TrackedCount(ReadDTO):
    """A count the platform collects, or the typed fact that it does not. Never a zero stand-in."""

    state: Literal["tracked", "not_tracked"]
    value: int | None = None


def tracked(value: int | None) -> TrackedCount:
    return TrackedCount(state="tracked", value=value) if value is not None else not_tracked()


def not_tracked() -> TrackedCount:
    return TrackedCount(state="not_tracked")


class TechnicalHealth(ReadDTO):
    """Indexing and technical health from the latest site crawl.

    Google's own indexed-page count is not collected, so ``google_indexed_pages`` is always
    not_tracked. The crawl's indexability is a different fact and is reported as such.
    """

    pages_crawled: TrackedCount
    indexable_pages: TrackedCount
    excluded_pages: TrackedCount
    pages_with_issues: TrackedCount
    structured_data_pages: TrackedCount
    google_indexed_pages: TrackedCount
    last_crawled_at: datetime | None


class SearchView(ReadDTO):
    organization_id: UUID
    websites: list[WebsiteOption]
    website_id: UUID | None
    syncs: list[SyncState]
    google_status: str | None
    search_console: SearchPerformance | None
    analytics: SearchPerformance | None
    analytics_scope: Literal["organization_all_channels"] = "organization_all_channels"
    analytics_availability: Literal["available", "permission_required"]
    pages: list[PageSummary]
    next_offset: int | None
    crawls: list[CrawlView]
    profiles: list[ProfileSummary]
    insights: list[InsightView] = []
    technical_health: TechnicalHealth | None = None
    can_crawl: bool
    unsupported: list[str] = [
        "geographic_rank_grid",
        "rank_scan",
        "gbp_performance_metrics",
        "google_indexation",
    ]


async def allowed(
    session: Session,
    principal: Authenticated,
    organization_id: UUID,
    request: Request,
    permission: str,
    *,
    location_id: UUID | None = None,
    aal2: bool = False,
) -> bool:
    decision = await authorization.evaluate(
        session,
        principal,
        AuthorizationRequest(
            platform_user_id=principal.platform_user_id,
            organization_id=organization_id,
            permission_key=permission,
            resource_scope=ScopeType.LOCATION if location_id else ScopeType.ORGANIZATION,
            location_id=location_id,
            minimum_assurance_level=AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1,
        ),
        correlation_id=str(meta(request)["correlation_id"]),
    )
    return decision.allowed


PERIOD_OF_DAYS = {
    7: PerformancePeriod.LAST_7_DAYS,
    28: PerformancePeriod.LAST_28_DAYS,
    90: PerformancePeriod.LAST_90_DAYS,
}


async def technical_health(
    session: Session, organization_id: UUID, website_id: UUID
) -> TechnicalHealth:
    row = (
        await session.execute(
            select(
                func.count(SEOPage.id),
                func.coalesce(func.sum(case((SEOPage.indexability == "indexable", 1), else_=0)), 0),
                func.coalesce(
                    func.sum(case((SEOPage.indexability == "not_indexable", 1), else_=0)), 0
                ),
                func.coalesce(
                    func.sum(
                        case((func.jsonb_array_length(SEOPage.technical_issues) > 0, 1), else_=0)
                    ),
                    0,
                ),
                func.coalesce(func.sum(case((SEOPage.structured_data_present, 1), else_=0)), 0),
                func.max(SEOPage.observed_at),
            ).where(SEOPage.organization_id == organization_id, SEOPage.website_id == website_id)
        )
    ).one()
    total = int(row[0])
    if total == 0:
        return TechnicalHealth(
            pages_crawled=not_tracked(),
            indexable_pages=not_tracked(),
            excluded_pages=not_tracked(),
            pages_with_issues=not_tracked(),
            structured_data_pages=not_tracked(),
            google_indexed_pages=not_tracked(),
            last_crawled_at=None,
        )
    return TechnicalHealth(
        pages_crawled=tracked(total),
        indexable_pages=tracked(int(row[1])),
        excluded_pages=tracked(int(row[2])),
        pages_with_issues=tracked(int(row[3])),
        structured_data_pages=tracked(int(row[4])),
        google_indexed_pages=not_tracked(),
        last_crawled_at=row[5],
    )


async def index_statuses(
    session: Session, organization_id: UUID, website_id: UUID, pages: list[dict[str, object]]
) -> None:
    """Add each landing page's crawl indexability, in place. A page the crawl has not seen stays
    NOT_CRAWLED; nothing is guessed from the address."""
    ids = [UUID(str(page["page_id"])) for page in pages if page.get("page_id")]
    if not ids:
        return
    rows = await session.execute(
        select(SEOPage.id, SEOPage.indexability).where(
            SEOPage.organization_id == organization_id,
            SEOPage.website_id == website_id,
            SEOPage.id.in_(ids),
        )
    )
    found: dict[UUID, str] = {row[0]: row[1] for row in rows}
    for page in pages:
        indexability = found.get(UUID(str(page["page_id"]))) if page.get("page_id") else None
        page["index_status"] = (
            IndexStatus.INDEXABLE
            if indexability == "indexable"
            else IndexStatus.NOT_INDEXABLE
            if indexability == "not_indexable"
            else IndexStatus.NOT_CRAWLED
        )


def website_option(row: object) -> WebsiteOption:
    return WebsiteOption.model_validate(row, from_attributes=True)


@router.get("/integrations", response_model=IntegrationView)
async def integrations_view(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[object, policy("gbp.connect")],
) -> IntegrationView:
    directory = IntegrationDirectoryService()
    google = GoogleState.model_validate(
        asdict(await directory.google_workspace(session, organization_id))
    )
    manage_search = await allowed(session, principal, organization_id, request, "seo.manage")
    manage_analytics = await allowed(
        session, principal, organization_id, request, "insights.manage"
    )
    read_search = manage_search or await allowed(
        session, principal, organization_id, request, "seo.read"
    )
    read_analytics = manage_analytics or await allowed(
        session, principal, organization_id, request, "insights.read"
    )
    websites = (
        await service.list_websites(session, organization_id)
        if read_search or read_analytics
        else []
    )
    search_rows = (
        list(
            await session.scalars(
                select(SEOSearchProperty).where(
                    SEOSearchProperty.organization_id == organization_id
                )
            )
        )
        if read_search
        else []
    )
    analytics_rows = (
        list(
            await session.scalars(
                select(AnalyticsProperty).where(
                    AnalyticsProperty.organization_id == organization_id
                )
            )
        )
        if read_analytics
        else []
    )
    locations = list(
        await session.scalars(select(Location).where(Location.organization_id == organization_id))
    )
    location_options = [
        LocationOption(
            id=row.id,
            name=row.name,
            can_map=await allowed(
                session,
                principal,
                organization_id,
                request,
                "gbp.connect",
                location_id=row.id,
                aal2=True,
            ),
        )
        for row in locations
    ]
    mapped_ids = {row.gbp_location_id for row in google.mapped_resources if row.gbp_location_id}
    # Provider inventory is visible only in this authorized Integrations control plane.
    discovered = (
        list(
            await session.scalars(
                select(GBPLocation).where(
                    GBPLocation.organization_id == organization_id,
                    GBPLocation.connection_id == google.connection_id,
                    GBPLocation.mapping_status != "archived",
                )
            )
        )
        if google.connection_id
        else []
    )
    github = (
        await directory.github_workspace(session, organization_id)
        if await allowed(
            session, principal, organization_id, request, "content.manage_targets", aal2=True
        )
        else None
    )
    return IntegrationView(
        organization_id=organization_id,
        google=google,
        syncs=await sync_states(session, organization_id, analytics=read_analytics)
        if read_search
        else [],
        websites=[website_option(row) for row in websites],
        locations=location_options,
        search_properties=[
            SearchMapping.model_validate(
                {
                    **SearchMapping.model_validate(row, from_attributes=True).model_dump(),
                    "can_sync": manage_search,
                }
            )
            for row in search_rows
        ],
        analytics_properties=[
            SearchMapping.model_validate(
                {
                    **SearchMapping.model_validate(row, from_attributes=True).model_dump(),
                    "can_sync": manage_analytics,
                }
            )
            for row in analytics_rows
        ],
        unmapped_profiles=[
            UnmappedProfile.model_validate(row, from_attributes=True)
            for row in discovered
            if row.id not in mapped_ids
        ],
        can_connect=True,
        can_manage_search=manage_search,
        can_manage_analytics=manage_analytics,
        github_status=github.connection_status if github else None,
    )


@router.get("/local-search", response_model=SearchView)
async def local_search_view(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[object, policy("seo.read")],
    website_id: UUID | None = None,
    days: Literal[7, 28, 90] = 28,
    offset: int = Query(0, ge=0, le=100000),
) -> SearchView:
    websites = await service.list_websites(session, organization_id)
    website = (
        await service.get_website(session, organization_id, website_id)
        if website_id
        else (websites[0] if websites else None)
    )
    can_analytics = await allowed(session, principal, organization_id, request, "insights.read")
    pages = (
        await service.list_pages(
            session, organization_id, website_id=website.id, limit=51, offset=offset
        )
        if website
        else []
    )
    crawls = (
        await service.list_crawl_runs(session, organization_id, website_id=website.id, limit=10)
        if website
        else []
    )
    connection = await IntegrationDirectoryService().connection.find_connection(
        session, organization_id
    )
    # Resolve through the canonical active mapping; never expose discovered inventory here.
    google = await IntegrationDirectoryService().google_workspace(session, organization_id)
    profiles = []
    for mapping in google.mapped_resources:
        location_id = (
            UUID(str(mapping["platform_resource_id"])) if mapping["platform_resource_id"] else None
        )
        if (
            mapping["resource_type"] != "location"
            or not mapping["gbp_location_id"]
            or not location_id
        ):
            continue
        if not await allowed(
            session, principal, organization_id, request, "gbp.read", location_id=location_id
        ):
            continue
        row = await session.scalar(
            select(GBPLocation).where(
                GBPLocation.organization_id == organization_id,
                GBPLocation.id == UUID(str(mapping["gbp_location_id"])),
                GBPLocation.location_id == location_id,
                GBPLocation.mapping_status == "confirmed",
            )
        )
        if row:
            profiles.append(ProfileSummary.model_validate(row, from_attributes=True))
    report = (
        await SearchConsoleService().performance_report(
            session, organization_id, website.id, days=days
        )
        if website
        else None
    )
    if report and website:
        await index_statuses(session, organization_id, website.id, report["top_pages"])  # type: ignore[arg-type]
    profile_actions = None
    if await allowed(session, principal, organization_id, request, "gbp.read"):
        actions = (
            await read_actions_by_organization(session, [organization_id], PERIOD_OF_DAYS[days])
        )[organization_id]
        profile_actions = ProfileActions(actions.current, actions.previous)
    insights: list[Insight] = build_insights(report, profile_actions) if report else []
    return SearchView(
        organization_id=organization_id,
        websites=[website_option(row) for row in websites],
        website_id=website.id if website else None,
        google_status=connection.status if connection else None,
        syncs=await sync_states(session, organization_id, analytics=can_analytics),
        search_console=SearchPerformance.model_validate(report) if report else None,
        insights=[
            InsightView(
                code=item.code,
                link=item.link,
                subject=item.subject,
                current=item.current,
                previous=item.previous,
                percent_change=item.percent_change,
                count=item.count,
            )
            for item in insights
        ],
        technical_health=await technical_health(session, organization_id, website.id)
        if website
        else None,
        analytics=SearchPerformance.model_validate(
            await AnalyticsService().performance_report(session, organization_id, days=days)
        )
        if can_analytics
        else None,
        analytics_availability="available" if can_analytics else "permission_required",
        pages=[PageSummary.model_validate(row, from_attributes=True) for row in pages[:50]],
        next_offset=offset + 50 if len(pages) > 50 else None,
        crawls=[CrawlView.model_validate(row, from_attributes=True) for row in crawls],
        profiles=profiles,
        can_crawl=bool(website)
        and await allowed(session, principal, organization_id, request, "seo.manage")
        and await allowed(session, principal, organization_id, request, "workflows.execute"),
    )


class PageIdentity(ReadDTO):
    organization_id: UUID
    website_id: UUID
    page_id: UUID
    normalized_url: str
    observed_url: str
    canonical_url: str | None


class PageIntelligenceView(ReadDTO):
    version: str
    identity: PageIdentity
    current_page: dict[str, JsonValue]
    crawl: dict[str, JsonValue]
    change: dict[str, JsonValue]
    gsc: dict[str, JsonValue]
    ga4_organic_landing: dict[str, JsonValue]
    internal_links: dict[str, JsonValue]
    content: dict[str, JsonValue]
    workflow: dict[str, JsonValue]


@router.get(
    "/local-search/websites/{website_id}/pages/{page_id}", response_model=PageIntelligenceView
)
async def page_intelligence_view(
    organization_id: UUID,
    website_id: UUID,
    page_id: UUID,
    session: Session,
    _: Annotated[object, policy("seo.read")],
) -> PageIntelligenceView:
    from fastapi.encoders import jsonable_encoder

    from apps.api.app.products.seo.errors import SEOWebsiteNotFoundError

    data = await read_page_intelligence(session, organization_id, website_id, page_id)
    if data is None:
        raise SEOWebsiteNotFoundError
    return PageIntelligenceView.model_validate(jsonable_encoder(data))


class PostRevisionView(ReadDTO):
    id: UUID
    post_key: UUID
    revision: int
    post_type: str
    content: str
    call_to_action: dict[str, JsonValue] | None
    event_or_offer: dict[str, JsonValue] | None
    status: str
    publication: PostPublicationData | None


class ProviderPostView(ReadDTO):
    id: UUID
    provider_post_name: str
    post_type: str
    state: str | None
    summary: str | None
    status: str
    observed_at: datetime


class GBPDetailView(ReadDTO):
    organization_id: UUID
    location_id: UUID
    profile_id: UUID
    snapshot_id: UUID | None
    profile: dict[str, JsonValue] | None
    observed_at: datetime | None
    health: dict[str, JsonValue] | None
    completeness: dict[str, JsonValue] | None
    completeness_code: str | None
    posts: list[PostRevisionView]
    provider_posts: list[ProviderPostView]
    can_propose: bool
    can_approve: bool
    can_publish: bool


@router.get(
    "/local-search/locations/{location_id}/profiles/{profile_id}", response_model=GBPDetailView
)
async def profile_view(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    profile_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[object, location_policy("gbp.read")],
) -> GBPDetailView:
    from apps.api.app.products.gbp.operations_errors import GBPLocationNotFoundError

    directory = await IntegrationDirectoryService().google_workspace(session, organization_id)
    if not any(
        row["gbp_location_id"] == str(profile_id)
        and row["platform_resource_id"] == str(location_id)
        for row in directory.mapped_resources
    ):
        raise GBPLocationNotFoundError
    item = await session.scalar(
        select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.id == profile_id,
            GBPLocation.location_id == location_id,
            GBPLocation.mapping_status == "confirmed",
        )
    )
    if item is None:
        raise GBPLocationNotFoundError
    snapshot = await session.scalar(
        select(GBPProfileSnapshot)
        .where(
            GBPProfileSnapshot.organization_id == organization_id,
            GBPProfileSnapshot.gbp_location_id == profile_id,
        )
        .order_by(GBPProfileSnapshot.observed_at.desc())
        .limit(1)
    )
    operations = GBPOperationsService()
    completeness = None
    code = None
    try:
        completeness = await operations.completeness_report(session, organization_id, profile_id)
    except GBPCapabilitySnapshotNotFoundError as error:
        code = error.code
    from fastapi.encoders import jsonable_encoder

    posts = await operations.list_post_revision_read_models(session, organization_id, profile_id)
    provider_posts = list(
        await session.scalars(
            select(GBPProviderPost)
            .where(
                GBPProviderPost.organization_id == organization_id,
                GBPProviderPost.gbp_location_id == profile_id,
            )
            .order_by(GBPProviderPost.observed_at.desc())
            .limit(50)
        )
    )
    return GBPDetailView(
        organization_id=organization_id,
        location_id=location_id,
        profile_id=profile_id,
        snapshot_id=snapshot.id if snapshot else None,
        profile=jsonable_encoder(snapshot.normalized_profile) if snapshot else None,
        observed_at=snapshot.observed_at if snapshot else None,
        health=jsonable_encoder(profile_health(snapshot.normalized_profile, snapshot.observed_at))
        if snapshot
        else None,
        completeness=jsonable_encoder(completeness),
        completeness_code=code,
        posts=jsonable_encoder(
            [
                post_revision_row(
                    row.revision, row.publication, recovery_allowed=row.recovery_allowed
                )
                for row in posts
            ]
        ),
        provider_posts=jsonable_encoder([provider_post_row(row) for row in provider_posts]),
        can_propose=await allowed(
            session, principal, organization_id, request, "gbp.propose", location_id=location_id
        ),
        can_approve=await allowed(
            session,
            principal,
            organization_id,
            request,
            "gbp.approve",
            location_id=location_id,
            aal2=True,
        ),
        can_publish=await allowed(
            session,
            principal,
            organization_id,
            request,
            "gbp.publish",
            location_id=location_id,
            aal2=True,
        )
        and await allowed(session, principal, organization_id, request, "workflows.execute"),
    )
