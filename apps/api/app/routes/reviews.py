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
from apps.api.app.products.reviews.contracts import DraftCreate, PublishResponse
from apps.api.app.products.reviews.models import Review
from apps.api.app.products.reviews.service import ReviewService

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/locations/{location_id}/reviews",
    tags=["reviews"],
    dependencies=[Depends(get_authenticated_principal)],
)
service = ReviewService()
Session = Annotated[AsyncSession, Depends(get_database_session)]


def no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def policy(key: str, aal2: bool = False) -> Any:
    return Depends(
        require_authorization(
            key, ScopeType.LOCATION, AssuranceLevel.AAL2 if aal2 else AssuranceLevel.AAL1
        )
    )


@router.get("", dependencies=[Depends(no_store)])
async def list_reviews(
    request: Request,
    organization_id: UUID,
    location_id: UUID,
    session: Session,
    _: Annotated[AuthorizationDecision, policy("reviews.read")],
) -> dict[str, object]:
    items = (
        await session.scalars(
            select(Review)
            .where(Review.organization_id == organization_id, Review.location_id == location_id)
            .order_by(Review.review_created_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "data": [
            {
                "id": str(x.id),
                "rating": float(x.rating) if x.rating is not None else None,
                "status": x.status,
                "sentiment": x.sentiment,
                "risk_level": x.risk_level,
            }
            for x in items
        ],
        "meta": {"correlation_id": request_correlation_id(request)},
    }


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
    _principal: Authenticated,
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
        ai_execution_id=command.ai_execution_id,
    )
    return {
        "data": {"id": str(item.id), "revision": item.revision_number, "status": item.status},
        "meta": {"correlation_id": request_correlation_id(request)},
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
    item = await service.approve(session, organization_id, response_id, principal.platform_user_id)
    return {
        "data": {"id": str(item.id), "status": item.status},
        "meta": {"correlation_id": request_correlation_id(request)},
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
    _principal: Authenticated,
    _: Annotated[AuthorizationDecision, policy("reviews.publish_response", True)],
) -> dict[str, object]:
    item = await service.reserve_publication(
        session, organization_id, response_id, command.idempotency_key
    )
    return {
        "data": {"id": str(item.id), "status": item.status},
        "meta": {"correlation_id": request_correlation_id(request)},
    }
