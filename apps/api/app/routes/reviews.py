"""Protected Reviews APIs."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.products.reviews.active_service import ActiveReviewService
from apps.api.app.products.reviews.contracts import AIDraftCreate, DraftCreate, PublishResponse
from apps.api.app.products.reviews.errors import (
    ReviewIngestionUnavailableError,
    ReviewNotFoundError,
)
from apps.api.app.products.reviews.ingestion_service import ReviewIngestionService
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision, ReviewRevision
from apps.api.app.routes.health import settings_from_request

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/locations/{location_id}/reviews",
    tags=["reviews"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = ActiveReviewService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def policy(key: str, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            key, ScopeType.LOCATION, AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1
        )
    )


def meta(request: Request) -> dict[str, object]:
    return {"correlation_id": request_correlation_id(request)}


def review_row(item: Review) -> dict[str, object]:
    return {
        "id": str(item.id),
        "rating": float(item.rating) if item.rating is not None else None,
        "status": item.status,
        "sentiment": item.sentiment,
        "risk_level": item.risk_level,
        "provider": item.provider,
        "review_created_at": item.review_created_at,
        "last_synced_at": item.last_synced_at,
        "current_revision_number": item.current_revision_number,
    }


@router.get("", dependencies=[Depends(no_store)])
async def list_reviews(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("reviews.read")],
    status_filter: str | None = None,
    rating_min: float | None = None,
    rating_max: float | None = None,
    search: str | None = None,
    sort: str = "recent",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    items, has_more = await service.list_reviews(
        session,
        organization_id,
        location_id,
        status_filter=status_filter,
        rating_min=rating_min,
        rating_max=rating_max,
        search=search,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    return {
        "data": [review_row(item) for item in items],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "next_offset": offset + limit if has_more else None,
            "has_more": has_more,
        },
        "meta": meta(request),
    }


@router.get("/summary", dependencies=[Depends(no_store)])
async def summary(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("reviews.read")],
) -> dict[str, object]:
    return {
        "data": await service.summary(session, organization_id, location_id),
        "meta": meta(request),
    }


@router.get("/{review_id}", dependencies=[Depends(no_store)])
async def get_review(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    review_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("reviews.read")],
) -> dict[str, object]:
    review, revisions = await service.get(session, organization_id, review_id)
    if review.location_id != location_id:
        raise ReviewNotFoundError
    return {
        "data": {
            **review_row(review),
            "revisions": [_revision_row(revision) for revision in revisions],
        },
        "meta": meta(request),
    }


def _revision_row(revision: ReviewRevision) -> dict[str, object]:
    return {
        "id": str(revision.id),
        "revision_number": revision.revision_number,
        "rating": float(revision.rating) if revision.rating is not None else None,
        "title": revision.title,
        "body": revision.body,
        "captured_at": revision.captured_at,
        "change_summary": revision.change_summary,
    }


@router.get("/{review_id}/responses", dependencies=[Depends(no_store)])
async def list_responses(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    review_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("reviews.read")],
) -> dict[str, object]:
    items = await service.list_responses(session, organization_id, review_id)
    return {
        "data": [
            {
                "id": str(item.id),
                "revision_number": item.revision_number,
                "response_text": item.response_text,
                "status": item.status,
                "generated_by_type": item.generated_by_type,
                "approved_at": item.approved_at,
                "published_at": item.published_at,
            }
            for item in items
            if item.location_id == location_id
        ],
        "meta": meta(request),
    }


@router.get("/{review_id}/audit", dependencies=[Depends(no_store)])
async def review_audit(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    review_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("audit.read")],
) -> dict[str, object]:
    review, _revisions = await service.get(session, organization_id, review_id)
    if review.location_id != location_id:
        raise ReviewNotFoundError
    history = await service.resource_history(
        session, organization_id, resource_type="review", resource_id=review_id
    )
    return {"data": history, "meta": meta(request)}


@router.get("/responses/{response_id}/audit", dependencies=[Depends(no_store)])
async def response_audit(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    response_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("audit.read")],
) -> dict[str, object]:
    response = await session.scalar(
        select(ReviewResponseRevision.id).where(
            ReviewResponseRevision.organization_id == organization_id,
            ReviewResponseRevision.location_id == location_id,
            ReviewResponseRevision.id == response_id,
        )
    )
    if response is None:
        raise ReviewNotFoundError
    history = await service.resource_history(
        session,
        organization_id,
        resource_type="review_response_revision",
        resource_id=response_id,
    )
    return {"data": history, "meta": meta(request)}


@router.post(
    "/{review_id}/responses", status_code=status.HTTP_201_CREATED, dependencies=[Depends(no_store)]
)
async def draft(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    review_id: UUID,
    command: DraftCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("reviews.generate_response")],
) -> dict[str, object]:
    item = await service.draft(
        session,
        organization_id=organization_id,
        location_id=location_id,
        review_id=review_id,
        review_revision_id=command.review_revision_id,
        text=command.response_text,
        generated_by_type=command.generated_by_type,
        fact_ids=command.approved_fact_revision_ids,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
        ai_execution_id=command.ai_execution_id,
    )
    return {
        "data": {"id": str(item.id), "revision": item.revision_number, "status": item.status},
        "meta": meta(request),
    }


@router.post(
    "/{review_id}/responses/ai-draft",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(no_store)],
)
async def ai_draft(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    review_id: UUID,
    command: AIDraftCreate,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("reviews.generate_response")],
) -> dict[str, object]:
    item, execution = await service.generate_ai_draft(
        session,
        organization_id=organization_id,
        location_id=location_id,
        review_id=review_id,
        review_revision_id=command.review_revision_id,
        fact_ids=command.approved_fact_revision_ids,
        idempotency_key=command.idempotency_key,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {
            "id": str(item.id),
            "revision": item.revision_number,
            "status": item.status,
            "response_text": item.response_text,
            "ai_execution_id": str(execution.id),
            "requires_human_review": execution.requires_human_review,
            "provider": execution.provider_key,
        },
        "meta": meta(request),
    }


@router.post("/{review_id}/responses/{response_id}/approve", dependencies=[Depends(no_store)])
async def approve(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    review_id: UUID,
    response_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("reviews.approve_response", True)],
) -> dict[str, object]:
    item = await service.approve(
        session,
        organization_id,
        location_id,
        review_id,
        response_id,
        principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {"id": str(item.id), "status": item.status},
        "meta": meta(request),
    }


@router.post(
    "/{review_id}/responses/{response_id}/publish",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(no_store)],
)
async def publish(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    review_id: UUID,
    response_id: UUID,
    command: PublishResponse,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("reviews.publish_response", True)],
) -> dict[str, object]:
    item = await service.reserve_publication(
        session,
        organization_id,
        location_id,
        review_id,
        response_id,
        command.idempotency_key,
        actor_id=principal.platform_user_id,
        correlation_id=request_correlation_id(request),
    )
    return {
        "data": {"id": str(item.id), "status": item.status},
        "meta": meta(request),
    }


@router.post(
    "/ingest",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(no_store)],
)
async def ingest_reviews(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: Session,
    principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("reviews.generate_response")],
) -> dict[str, object]:
    """Pull and reconcile reviews from the connected GBP location."""
    ingestion = ReviewIngestionService()
    try:
        summary = await ingestion.ingest_for_location(
            session,
            settings_from_request(request),
            organization_id,
            location_id,
            actor_id=principal.platform_user_id,
            correlation_id=request_correlation_id(request),
        )
    except LookupError:
        raise ReviewIngestionUnavailableError from None
    return {"data": summary, "meta": meta(request)}
