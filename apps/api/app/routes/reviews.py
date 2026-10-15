"""Protected Reviews APIs."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authorization.contracts import AuthorizationDecision
from apps.api.app.authorization.dependencies import require_authorization
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.execution.automations import RunStatus
from apps.api.app.execution.service import ExecutionService
from apps.api.app.products.reviews.contracts import (
    AIDraftCreate,
    DraftCreate,
    PublishResponse,
    ReviewIngestResult,
    ReviewIngestRun,
    ReviewIngestStatus,
)
from apps.api.app.products.reviews.errors import ReviewNotFoundError
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision, ReviewRevision
from apps.api.app.products.reviews.service import ReviewService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/locations/{location_id}/reviews",
    tags=["reviews"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = ReviewService()
execution = ExecutionService()
INGEST_WORKFLOW = "reviews.ingest"
# The handler's code for a Google authorization that has to be redone by a person.
RECONNECT_FAILURE_CODE = "TOKEN_REFRESH_FAILED"
FINISHED_STATUSES = frozenset(
    {
        RunStatus.PARTIALLY_COMPLETED,
        RunStatus.CANCELLED,
        RunStatus.EXPIRED,
        RunStatus.FAILED,
        RunStatus.ESCALATED,
    }
)
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
    response_model=ReviewIngestRun,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(no_store)],
)
async def ingest_reviews(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: Session,
    principal: Authenticated,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
    _: Annotated[AuthorizationDecision, policy("reviews.generate_response")],
) -> ReviewIngestRun:
    """Queue a review import for the location; the worker pulls the reviews from Google.

    Returns the run to poll. A queued or running import for the location is returned as is.
    Does not publish any response; preserves the approval workflow.
    """
    run, _created = await execution.run_now_for_location(
        session,
        organization_id,
        location_id,
        INGEST_WORKFLOW,
        idempotency_key,
        correlation_id=str(request_correlation_id(request)),
        actor_id=principal.platform_user_id,
    )
    return ReviewIngestRun(run_id=run.id, run_status=RunStatus(run.status))


@router.get(
    "/ingest/{run_id}",
    response_model=ReviewIngestStatus,
    dependencies=[Depends(no_store)],
)
async def ingest_reviews_status(
    organization_id: UUID,
    location_id: UUID,
    run_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("reviews.generate_response")],
) -> ReviewIngestStatus:
    """Where a manual review import stands, with a typed result once it has finished."""
    run = await execution.find_location_run(
        session, organization_id, location_id, INGEST_WORKFLOW, run_id
    )
    run_status = RunStatus(run.status)
    return ReviewIngestStatus(
        run_id=run.id, run_status=run_status, result=ingest_result(run_status, run.failure_code)
    )


def ingest_result(run_status: RunStatus, failure_code: str | None) -> ReviewIngestResult | None:
    """The typed outcome of an import, or None while it is still going to finish."""
    if run_status is RunStatus.COMPLETED:
        return ReviewIngestResult.SUCCEEDED
    if failure_code == RECONNECT_FAILURE_CODE and (
        run_status is RunStatus.RETRY_SCHEDULED or run_status in FINISHED_STATUSES
    ):
        # Retrying cannot fix a lost Google authorization, so say so straight away.
        return ReviewIngestResult.RECONNECT_REQUIRED
    if run_status in FINISHED_STATUSES:
        return ReviewIngestResult.FAILED
    return None
