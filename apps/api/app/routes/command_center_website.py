"""Website & Content projections over canonical persisted evidence and operator services."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, JsonValue
from sqlalchemy import or_, select

from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.products.content.operator_service import ContentOperatorService
from apps.api.app.products.seo.errors import SEOSiteMappingRequiredError
from apps.api.app.products.seo.models import SEOOpportunity
from apps.api.app.products.seo.site_change_service import SiteChangeService
from apps.api.app.products.seo.site_map_resolver import page_map_from_contract, resolve_entry
from apps.api.app.routes.command_center import OpportunityView, project
from apps.api.app.routes.command_center_reviews import ReviewFact, private
from apps.api.app.routes.command_center_search import (
    CrawlView,
    PageIntelligenceView,
    PageSummary,
    WebsiteOption,
    allowed,
    page_intelligence_view,
    website_option,
)
from apps.api.app.routes.content import policy as content_policy
from apps.api.app.routes.seo import Session, policy, service

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center/website-content",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(private)],
)
operator = ContentOperatorService()


class WebsiteContentItem(BaseModel):
    id: UUID
    title: str
    slug: str
    content_type: str
    stage: str
    next_action: dict[str, str]
    published_at: datetime | None
    latest_revision_status: str | None
    latest_revision_number: int | None
    publication_status: str | None
    publication_job_status: str | None
    technical_site_change: bool


class WebsiteWorkspace(BaseModel):
    organization_id: UUID
    websites: list[WebsiteOption]
    website_id: UUID | None
    pages: list[PageSummary]
    next_page_offset: int | None
    crawls: list[CrawlView]
    opportunities: list[OpportunityView]
    next_opportunity_offset: int | None
    content: list[WebsiteContentItem]
    next_content_offset: int | None
    page_availability: Literal["available", "permission_required", "unavailable"]
    content_availability: Literal["available", "permission_required"]
    content_scope: Literal["organization"] = "organization"
    can_create: bool
    can_crawl: bool
    conversions: Literal["unavailable_no_canonical_path_source"] = (
        "unavailable_no_canonical_path_source"
    )
    unsupported: list[str] = [
        "named_cta_events",
        "conversion_funnels",
        "page_health_score",
        "google_indexation",
    ]


@router.get("", response_model=WebsiteWorkspace)
async def workspace(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    website_id: UUID | None = None,
    offset: int = Query(0, ge=0, le=100000),
) -> WebsiteWorkspace:
    seo = await allowed(session, principal, organization_id, request, "seo.read")
    content = await allowed(session, principal, organization_id, request, "content.read")
    if not seo and not content:
        raise HTTPException(403, "Website & Content access required")
    websites = await service.list_websites(session, organization_id) if seo else []
    website = (
        (
            await service.get_website(session, organization_id, website_id)
            if website_id
            else (websites[0] if websites else None)
        )
        if seo
        else None
    )
    if website_id and not seo:
        raise HTTPException(403, "Website evidence access required")
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
    opportunities = (
        list(
            await session.scalars(
                select(SEOOpportunity)
                .where(
                    SEOOpportunity.organization_id == organization_id,
                    SEOOpportunity.website_id == website.id,
                )
                .order_by(SEOOpportunity.created_at.desc(), SEOOpportunity.id)
                .offset(offset)
                .limit(51)
            )
        )
        if website
        else []
    )
    items, more = (
        await operator.list_workspace(session, organization_id, limit=50, offset=offset)
        if content
        else ([], False)
    )
    return WebsiteWorkspace(
        organization_id=organization_id,
        websites=[website_option(row) for row in websites],
        website_id=website.id if website else None,
        pages=[PageSummary.model_validate(row, from_attributes=True) for row in pages[:50]],
        next_page_offset=offset + 50 if len(pages) > 50 else None,
        crawls=[CrawlView.model_validate(row, from_attributes=True) for row in crawls],
        opportunities=[project(row) for row in opportunities[:50]],
        next_opportunity_offset=offset + 50 if len(opportunities) > 50 else None,
        content=[WebsiteContentItem.model_validate(row) for row in items],
        next_content_offset=offset + 50 if more else None,
        page_availability="permission_required"
        if not seo
        else "available"
        if website
        else "unavailable",
        content_availability="available" if content else "permission_required",
        can_create=content
        and await allowed(session, principal, organization_id, request, "content.create"),
        can_crawl=bool(website)
        and await allowed(session, principal, organization_id, request, "seo.manage")
        and await allowed(session, principal, organization_id, request, "workflows.execute"),
    )


class PageRepositoryMapping(BaseModel):
    state: Literal["mapped", "unavailable"]
    code: str | None = None
    repository: str | None = None
    base_branch: str | None = None
    fields: dict[str, str] = {}
    verification: Literal["executor_rechecks_before_write"] = "executor_rechecks_before_write"


class WebsitePageDetail(BaseModel):
    evidence: PageIntelligenceView
    mapping: PageRepositoryMapping
    opportunities: list[OpportunityView]


@router.get("/websites/{website_id}/pages/{page_id}", response_model=WebsitePageDetail)
async def page_detail(
    organization_id: UUID,
    website_id: UUID,
    page_id: UUID,
    session: Session,
    _: Annotated[object, policy("seo.read")],
) -> WebsitePageDetail:
    evidence = await page_intelligence_view(organization_id, website_id, page_id, session, _)
    mapping = PageRepositoryMapping(state="unavailable", code="SITE_MAPPING_REQUIRED")
    target = await SiteChangeService().active_target(session, organization_id)
    if target and target.allowed_site_change_prefixes:
        try:
            entry = resolve_entry(
                page_map_from_contract(target.frontmatter_contract),
                evidence.identity.normalized_url,
                target.allowed_site_change_prefixes,
            )
            mapping = PageRepositoryMapping(
                state="mapped",
                repository=target.repository_id,
                base_branch=target.base_branch,
                fields={field.value: locator.file_path for field, locator in entry.fields.items()},
            )
        except SEOSiteMappingRequiredError:
            pass
    opportunities = await session.scalars(
        select(SEOOpportunity)
        .where(
            SEOOpportunity.organization_id == organization_id,
            SEOOpportunity.website_id == website_id,
            SEOOpportunity.page_id == page_id,
        )
        .order_by(SEOOpportunity.created_at.desc())
        .limit(50)
    )
    return WebsitePageDetail(
        evidence=evidence, mapping=mapping, opportunities=[project(row) for row in opportunities]
    )


class ContentBriefView(BaseModel):
    id: UUID
    revision_number: int
    audience: str
    intent: str
    target_reference: str
    approved_fact_revision_ids: list[UUID]
    status: str


class ContentRevisionView(BaseModel):
    id: UUID
    revision_number: int
    body: str
    frontmatter: dict[str, JsonValue]
    created_by_type: str
    status: str
    validation_document: dict[str, JsonValue]
    approved_at: datetime | None


class ContentTargetView(BaseModel):
    id: UUID
    key: str
    repository_id: str
    base_branch: str
    allowed_path_prefix: str
    file_extensions: list[str]
    status: str


class ContentRequirementsView(BaseModel):
    target_selected: bool
    target_id: UUID | None = None
    missing: list[str]
    requires_image: bool
    requires_image_alt: bool
    file_extensions: list[str]


class ContentPublicationView(BaseModel):
    id: UUID
    status: str
    target_path: str
    external_pull_request_id: str | None
    published_url: str | None
    build_status: str | None
    deployment_status: str | None
    verified_at: datetime | None
    safe_error_code: str | None
    revision_id: UUID | None
    workflow_id: UUID
    workflow_status: str | None
    workflow_failure: str | None
    correlation_id: str | None
    approved_head_sha: str | None
    external_revision_id: str | None
    verification_status: str | None
    verification_evidence: dict[str, JsonValue] | None
    can_recover: bool


class ContentDraftRun(BaseModel):
    id: UUID
    status: str
    failure_code: str | None
    correlation_id: str | None
    started_at: datetime | None
    completed_at: datetime | None


class WebsiteContentDetail(WebsiteContentItem):
    organization_id: UUID
    briefs: list[ContentBriefView]
    revisions: list[ContentRevisionView]
    publications: list[ContentPublicationView]
    publishing_targets: list[ContentTargetView]
    publishing_requirements: ContentRequirementsView
    publishing_requirements_by_target: dict[str, ContentRequirementsView]
    facts: list[ReviewFact]
    draft_runs: list[ContentDraftRun]
    can_edit: bool
    can_approve: bool
    can_publish: bool


@router.get("/content/{item_id}", response_model=WebsiteContentDetail)
async def content_detail(
    request: Request,
    organization_id: UUID,
    item_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[object, content_policy("content.read")],
) -> WebsiteContentDetail:
    # Persisted read only: provider target reconciliation remains in the canonical publish action.
    data = await operator.detail(session, organization_id, item_id)
    item = await operator.content.get_item(session, organization_id, item_id)
    facts = await session.scalars(
        select(BusinessFactRevision)
        .where(
            BusinessFactRevision.organization_id == organization_id,
            BusinessFactRevision.status.in_(("approved", "active")),
            or_(
                BusinessFactRevision.location_id.is_(None),
                BusinessFactRevision.location_id == item.location_id,
            ),
        )
        .order_by(BusinessFactRevision.fact_key, BusinessFactRevision.id)
        .limit(100)
    )
    publish = await allowed(
        session, principal, organization_id, request, "content.publish", aal2=True
    )
    publications = []
    for row in await operator.content.list_publications(session, organization_id, item_id):
        run = await session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.id == row.workflow_run_id,
            )
        )
        publications.append(
            ContentPublicationView.model_validate(
                {
                    **operator._publication_row(row),
                    "revision_id": row.content_revision_id,
                    "workflow_id": row.workflow_run_id,
                    "workflow_status": run.status if run else None,
                    "workflow_failure": run.failure_code if run else None,
                    "correlation_id": run.correlation_id if run else None,
                    "approved_head_sha": row.approved_head_sha,
                    "external_revision_id": row.external_revision_id,
                    "verification_status": row.verification_status,
                    "verification_evidence": row.verification_evidence,
                    "can_recover": publish
                    and row.status not in {"verified", "failed", "checks_failed", "rolled_back"},
                }
            )
        )
    draft_runs = await session.scalars(
        select(WorkflowRun)
        .join(WorkflowVersion, WorkflowVersion.id == WorkflowRun.workflow_version_id)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
        .where(
            WorkflowRun.organization_id == organization_id,
            WorkflowDefinition.key == "content.draft_revision",
            WorkflowRun.input_document["item_id"].astext == str(item_id),
        )
        .order_by(WorkflowRun.created_at.desc())
        .limit(10)
    )
    return WebsiteContentDetail.model_validate(
        {
            **data,
            "organization_id": organization_id,
            "draft_runs": [
                ContentDraftRun.model_validate(row, from_attributes=True) for row in draft_runs
            ],
            "publications": publications,
            "facts": [{"id": f.id, "key": f.fact_key, "value": f.value} for f in facts],
            "can_edit": await allowed(session, principal, organization_id, request, "content.edit"),
            "can_approve": await allowed(
                session, principal, organization_id, request, "content.approve", aal2=True
            ),
            "can_publish": publish,
        }
    )
