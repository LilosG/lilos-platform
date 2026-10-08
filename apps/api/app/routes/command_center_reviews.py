"""Reviews presentation over scoped canonical records; no provider I/O on reads."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, JsonValue, TypeAdapter
from sqlalchemy import select

from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.integrations.directory_service import IntegrationDirectoryService
from apps.api.app.locations.models import Location
from apps.api.app.products.reviews.errors import ReviewNotFoundError
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision, ReviewRevision
from apps.api.app.routes.command_center_search import allowed
from apps.api.app.routes.reviews import Session, service


def private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center/reviews",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(private)],
)


ReviewFilter = Literal["all", "needs_response", "draft", "awaiting_approval", "published"]
# One typed mapping from the console's filter tabs to canonical review statuses.
FILTER_STATUSES: dict[str, tuple[str, ...]] = {
    "needs_response": ("new", "classified", "triaged", "escalated", "publication_failed"),
    "draft": ("drafting",),
    "awaiting_approval": ("awaiting_approval", "approved", "publishing"),
    "published": ("responded",),
}


class ReviewLocation(BaseModel):
    id: UUID
    name: str


class ReviewSource(BaseModel):
    provider: Literal["google_business_profile"] = "google_business_profile"
    connection_status: str
    mapping_status: str
    last_ingested_at: datetime | None
    freshness: Literal["fresh", "stale", "unavailable"]
    quality: Literal["partial", "unavailable"]
    limitation: Literal["persisted_inventory_not_provider_total"] = (
        "persisted_inventory_not_provider_total"
    )


class ReviewInventoryItem(BaseModel):
    id: UUID
    location_id: UUID
    revision_id: UUID | None
    revision: int
    provider: str
    external_review_id: str
    reviewer_reference: str | None
    reviewer_identity: Literal["named", "anonymous", "unknown"]
    reviewer_display_name: str | None
    reviewer_photo_url: str | None
    rating: float | None
    body: str | None
    title: str | None
    status: str
    sentiment: str
    risk_level: str
    created_at: datetime
    last_synced_at: datetime
    response_status: str | None
    response_text: str | None


class ReviewsWorkspace(BaseModel):
    organization_id: UUID
    locations: list[ReviewLocation]
    location_id: UUID | None
    source: ReviewSource | None
    inventory_count: int | None
    average_rating: float | None
    open_restricted_cases: int | None
    awaiting_response_count: int | None
    items: list[ReviewInventoryItem]
    next_offset: int | None
    can_ingest: bool
    campaigns: Literal["unavailable_no_canonical_source"] = "unavailable_no_canonical_source"


class ReviewFact(BaseModel):
    id: UUID
    key: str
    value: JsonValue


class ReviewHistory(BaseModel):
    id: UUID
    event_type: str
    action: str
    result: str
    occurred_at: datetime
    summary: str
    actor_type: str


class ResponseState(BaseModel):
    id: UUID
    revision: int
    review_revision_id: UUID
    text: str
    status: Literal[
        "draft",
        "generated",
        "awaiting_approval",
        "approved",
        "publishing",
        "published",
        "failed",
        "rejected",
        "superseded",
        "reconciliation_required",
    ]
    generated_by: str
    approved_at: datetime | None
    published_at: datetime | None
    external_response_id: str | None
    safe_error_code: str | None
    workflow_id: UUID | None
    workflow_status: str | None
    workflow_failure: str | None
    approval_required: bool
    policy_code: Literal[
        "canonical_local_response_approval", "provider_observation_no_local_approval"
    ]
    can_approve: bool
    can_publish: bool
    history: list[ReviewHistory]


class ReviewDetail(BaseModel):
    organization_id: UUID
    location_id: UUID
    review: ReviewInventoryItem
    source: ReviewSource
    has_approved_facts: bool
    can_draft: bool
    can_ai_draft: bool
    responses: list[ResponseState]
    history: list[ReviewHistory]
    can_read_audit: bool
    recovery: Literal["canonical_worker_retry_and_ingestion_readback_no_manual_retry_endpoint"] = (
        "canonical_worker_retry_and_ingestion_readback_no_manual_retry_endpoint"
    )
    policy_override: Literal["unavailable_no_approval_free_local_policy"] = (
        "unavailable_no_approval_free_local_policy"
    )


async def history(
    session: Session, organization_id: UUID, *, resource_type: str, resource_id: UUID
) -> list[ReviewHistory]:
    return [
        ReviewHistory.model_validate(row)
        for row in await service.resource_history(
            session, organization_id, resource_type=resource_type, resource_id=resource_id
        )
    ]


async def source_view(
    session: Session, organization_id: UUID, selected: UUID, evidence: bool
) -> ReviewSource:
    google = await IntegrationDirectoryService().google_workspace(session, organization_id)
    mappings = [
        row
        for row in google.mapped_resources
        if str(row.get("platform_resource_id")) == str(selected)
    ]
    mapped = any(row.get("mapping_status") == "confirmed" for row in mappings)
    latest = await session.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.organization_id == organization_id,
            AuditEvent.location_id == selected,
            AuditEvent.event_type == "reviews.ingest.completed",
        )
        .order_by(AuditEvent.occurred_at.desc())
        .limit(1)
    )
    return ReviewSource(
        connection_status=google.connection_status,
        mapping_status="confirmed" if mapped else "unmapped",
        last_ingested_at=latest.occurred_at if latest else None,
        freshness="unavailable"
        if latest is None
        else "stale"
        if latest.occurred_at < datetime.now(UTC) - timedelta(days=1)
        else "fresh",
        quality="partial" if evidence or latest is not None else "unavailable",
    )


async def item_view(session: Session, review: Review) -> ReviewInventoryItem:
    revision = await session.scalar(
        select(ReviewRevision).where(
            ReviewRevision.organization_id == review.organization_id,
            ReviewRevision.review_id == review.id,
            ReviewRevision.revision_number == review.current_revision_number,
        )
    )
    response = await session.scalar(
        select(ReviewResponseRevision)
        .where(
            ReviewResponseRevision.organization_id == review.organization_id,
            ReviewResponseRevision.location_id == review.location_id,
            ReviewResponseRevision.review_id == review.id,
        )
        .order_by(ReviewResponseRevision.revision_number.desc())
        .limit(1)
    )
    return ReviewInventoryItem(
        id=review.id,
        location_id=review.location_id,
        revision_id=revision.id if revision else None,
        revision=review.current_revision_number,
        provider=review.provider,
        external_review_id=review.external_review_id,
        reviewer_reference=review.reviewer_reference,
        reviewer_identity=TypeAdapter(Literal["named", "anonymous", "unknown"]).validate_python(
            review.reviewer_identity
        ),
        reviewer_display_name=review.reviewer_display_name,
        reviewer_photo_url=review.reviewer_photo_url,
        rating=float(review.rating) if review.rating is not None else None,
        body=revision.body if revision else None,
        title=revision.title if revision else None,
        status=review.status,
        sentiment=review.sentiment,
        risk_level=review.risk_level,
        created_at=review.review_created_at,
        last_synced_at=review.last_synced_at,
        response_status=response.status if response else None,
        response_text=response.response_text if response else None,
    )


@router.get("", response_model=ReviewsWorkspace)
async def workspace(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    location_id: UUID | None = None,
    offset: int = Query(0, ge=0, le=100000),
    status: ReviewFilter = "all",
) -> ReviewsWorkspace:
    locations = []
    for location in await session.scalars(
        select(Location)
        .where(Location.organization_id == organization_id)
        .order_by(Location.name, Location.id)
    ):
        if await allowed(
            session, principal, organization_id, request, "reviews.read", location_id=location.id
        ):
            locations.append(ReviewLocation(id=location.id, name=location.name))
    if not locations or (location_id and location_id not in {row.id for row in locations}):
        raise ReviewNotFoundError
    selected = location_id or locations[0].id
    items, more = await service.list_reviews(
        session,
        organization_id,
        selected,
        status_in=FILTER_STATUSES.get(status),
        limit=50,
        offset=offset,
    )
    summary = await service.summary(session, organization_id, selected)
    by_status = TypeAdapter(dict[str, int]).validate_python(summary["by_status"])
    count = sum(by_status.values())
    source = await source_view(session, organization_id, selected, count > 0)
    evidence = count > 0 or source.last_ingested_at is not None
    return ReviewsWorkspace(
        organization_id=organization_id,
        locations=locations,
        location_id=selected,
        source=source,
        inventory_count=count if evidence else None,
        average_rating=summary["average_rating"],  # type: ignore[arg-type]
        open_restricted_cases=summary["open_restricted_cases"] if evidence else None,  # type: ignore[arg-type]
        awaiting_response_count=sum(by_status.get(k, 0) for k in FILTER_STATUSES["needs_response"])
        if evidence
        else None,
        items=[await item_view(session, item) for item in items],
        next_offset=offset + 50 if more else None,
        can_ingest=source.mapping_status == "confirmed"
        and source.connection_status == "connected"
        and await allowed(
            session,
            principal,
            organization_id,
            request,
            "reviews.generate_response",
            location_id=selected,
        ),
    )


@router.get("/locations/{location_id}/{review_id}", response_model=ReviewDetail)
async def detail(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    review_id: UUID,
    session: Session,
    principal: Authenticated,
) -> ReviewDetail:
    if not await allowed(
        session, principal, organization_id, request, "reviews.read", location_id=location_id
    ):
        raise ReviewNotFoundError
    review, _ = await service.get(session, organization_id, review_id)
    if review.location_id != location_id:
        raise ReviewNotFoundError
    has_facts = await service.has_approved_facts(session, organization_id, location_id)
    can_generate = await allowed(
        session,
        principal,
        organization_id,
        request,
        "reviews.generate_response",
        location_id=location_id,
    )
    can_approve = await allowed(
        session,
        principal,
        organization_id,
        request,
        "reviews.approve_response",
        location_id=location_id,
        aal2=True,
    )
    can_publish = await allowed(
        session,
        principal,
        organization_id,
        request,
        "reviews.publish_response",
        location_id=location_id,
        aal2=True,
    )
    can_audit = await allowed(
        session, principal, organization_id, request, "audit.read", location_id=location_id
    )
    responses = []
    for response in await service.list_responses(session, organization_id, review_id):
        if response.location_id != location_id:
            continue
        run = await session.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.location_id == location_id,
                WorkflowRun.product_key == "reviews",
                WorkflowRun.input_document["response_id"].astext == str(response.id),
            )
            .order_by(WorkflowRun.created_at.desc())
            .limit(1)
        )
        current = await session.scalar(
            select(ReviewRevision.revision_number).where(
                ReviewRevision.id == response.review_revision_id,
                ReviewRevision.organization_id == organization_id,
            )
        )
        imported = response.generated_by_type == "imported"
        responses.append(
            ResponseState(
                id=response.id,
                revision=response.revision_number,
                review_revision_id=response.review_revision_id,
                text=response.response_text,
                status=TypeAdapter(ResponseState.model_fields["status"].annotation).validate_python(
                    response.status
                ),
                generated_by=response.generated_by_type,
                approved_at=response.approved_at,
                published_at=response.published_at,
                external_response_id=response.external_response_id,
                safe_error_code=response.safe_error_code,
                workflow_id=run.id if run else None,
                workflow_status=run.status if run else None,
                workflow_failure=run.failure_code if run else None,
                approval_required=not imported,
                policy_code="provider_observation_no_local_approval"
                if imported
                else "canonical_local_response_approval",
                can_approve=can_approve
                and response.status == "awaiting_approval"
                and current == review.current_revision_number,
                can_publish=can_publish
                and response.status == "approved"
                and current == review.current_revision_number
                and review.status != "escalated",
                history=await history(
                    session,
                    organization_id,
                    resource_type="review_response_revision",
                    resource_id=response.id,
                )
                if can_audit
                else [],
            )
        )
    view = await item_view(session, review)
    return ReviewDetail(
        organization_id=organization_id,
        location_id=location_id,
        review=view,
        source=await source_view(session, organization_id, location_id, True),
        has_approved_facts=has_facts,
        can_draft=can_generate and has_facts and view.revision_id is not None,
        can_ai_draft=can_generate and has_facts and view.revision_id is not None,
        responses=responses,
        can_read_audit=can_audit,
        history=await history(
            session, organization_id, resource_type="review", resource_id=review_id
        )
        if can_audit
        else [],
    )
