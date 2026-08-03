"""Deterministic review ingestion, risk, drafting, approval, and publication intent."""

import hashlib
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.reviews.models import (
    Review,
    ReviewEscalation,
    ReviewResponseRevision,
    ReviewRevision,
)

RISK_TERMS = {
    "legal": ("lawyer", "lawsuit", "attorney"),
    "injury": ("injured", "hospital", "hurt"),
    "discrimination": ("discrimination", "racist"),
    "employee_misconduct": ("employee assaulted", "staff stole"),
    "refund": ("refund", "chargeback"),
    "privacy": ("private information", "phone number"),
}
PROHIBITED_DRAFT_TERMS = (
    "we admit liability",
    "we guarantee compensation",
    "the reviewer is lying",
)


def review_hash(rating: float | None, title: str | None, body: str | None) -> str:
    return hashlib.sha256(f"{rating}|{title or ''}|{body or ''}".encode()).hexdigest()


def classify(body: str | None, rating: float | None) -> dict[str, object]:
    text = (body or "").casefold()
    risks = sorted(key for key, terms in RISK_TERMS.items() if any(term in text for term in terms))
    sentiment = (
        "unknown"
        if not text
        else ("negative" if any(x in text for x in ("bad", "terrible", "awful")) else "unknown")
    )
    return {
        "risks": risks,
        "restricted": bool(risks),
        "sentiment": sentiment,
        "rating_band": None
        if rating is None
        else ("positive" if rating >= 4 else "negative" if rating <= 2 else "neutral"),
    }


def validate_draft(text: str) -> None:
    normalized = text.casefold()
    if not text.strip() or any(term in normalized for term in PROHIBITED_DRAFT_TERMS):
        raise ValueError("unsafe review response draft")


class ReviewService:
    async def ingest(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID,
        integration_resource_id: UUID,
        external_review_id: str,
        provider: str,
        rating: float | None,
        title: str | None,
        body: str | None,
        created_at: datetime,
        updated_at: datetime | None,
    ) -> tuple[Review, ReviewRevision, bool]:
        digest = review_hash(rating, title, body)
        review = await session.scalar(
            select(Review)
            .where(
                Review.organization_id == organization_id,
                Review.integration_resource_id == integration_resource_id,
                Review.external_review_id == external_review_id,
            )
            .with_for_update()
        )
        if review:
            current = await session.scalar(
                select(ReviewRevision).where(
                    ReviewRevision.review_id == review.id, ReviewRevision.content_hash == digest
                )
            )
            if current:
                return review, current, False
            number = review.current_revision_number + 1
            review.current_revision_number = number
            review.status = "new"
            review.review_updated_at = updated_at
            for response in (
                await session.scalars(
                    select(ReviewResponseRevision).where(
                        ReviewResponseRevision.review_id == review.id,
                        ReviewResponseRevision.status.in_(("approved", "awaiting_approval")),
                    )
                )
            ).all():
                response.status = "superseded"
        else:
            number = 1
            review = Review(
                organization_id=organization_id,
                location_id=location_id,
                integration_resource_id=integration_resource_id,
                external_review_id=external_review_id,
                provider=provider,
                rating=rating,
                status="new",
                sentiment="unknown",
                topics=[],
                risk_level="unknown",
                current_revision_number=1,
                review_created_at=created_at,
                review_updated_at=updated_at,
            )
            session.add(review)
            await session.flush()
        revision = ReviewRevision(
            organization_id=organization_id,
            review_id=review.id,
            revision_number=number,
            rating=rating,
            title=title,
            body=body,
            content_hash=digest,
            change_summary="provider content changed"
            if number > 1
            else "initial provider observation",
        )
        session.add(revision)
        await session.flush()
        result = classify(body, rating)
        review.sentiment = str(result["sentiment"])
        review.status = "escalated" if result["restricted"] else "classified"
        review.risk_level = "high" if result["restricted"] else "low"
        if result["restricted"]:
            session.add(
                ReviewEscalation(
                    organization_id=organization_id,
                    review_id=review.id,
                    case_type=str(result["risks"][0]),
                    severity="high",
                    status="open",
                    restricted=True,
                    safe_reason="Deterministic restricted-risk candidate.",
                )
            )
        await session.flush()
        return review, revision, True

    async def draft(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID,
        review_id: UUID,
        review_revision_id: UUID,
        text: str,
        generated_by_type: str,
        fact_ids: list[UUID],
        ai_execution_id: UUID | None = None,
    ) -> ReviewResponseRevision:
        validate_draft(text)
        if not fact_ids:
            raise ValueError("approved business facts required")
        review = await session.scalar(
            select(Review).where(Review.organization_id == organization_id, Review.id == review_id)
        )
        if not review:
            raise LookupError("review not found")
        status = "awaiting_approval"
        last = await session.scalar(
            select(ReviewResponseRevision.revision_number)
            .where(ReviewResponseRevision.review_id == review_id)
            .order_by(ReviewResponseRevision.revision_number.desc())
            .limit(1)
        )
        item = ReviewResponseRevision(
            organization_id=organization_id,
            location_id=location_id,
            review_id=review_id,
            review_revision_id=review_revision_id,
            revision_number=(last or 0) + 1,
            response_text=text,
            content_hash=hashlib.sha256(text.encode()).hexdigest(),
            status=status,
            generated_by_type=generated_by_type,
            ai_execution_id=ai_execution_id,
            approved_fact_revision_ids=[str(x) for x in fact_ids],
        )
        session.add(item)
        await session.flush()
        return item

    async def approve(
        self, session: AsyncSession, organization_id: UUID, response_id: UUID, user_id: UUID
    ) -> ReviewResponseRevision:
        item = await session.scalar(
            select(ReviewResponseRevision)
            .where(
                ReviewResponseRevision.organization_id == organization_id,
                ReviewResponseRevision.id == response_id,
            )
            .with_for_update()
        )
        if not item or item.status != "awaiting_approval":
            raise ValueError("current response is not approval eligible")
        review = await session.scalar(select(Review).where(Review.id == item.review_id))
        if not review or review.current_revision_number != (
            await session.scalar(
                select(ReviewRevision.revision_number).where(
                    ReviewRevision.id == item.review_revision_id
                )
            )
        ):
            raise ValueError("review changed after draft")
        item.status = "approved"
        item.approved_by_user_id = user_id
        item.approved_at = datetime.now().astimezone()
        await session.flush()
        return item

    async def reserve_publication(
        self, session: AsyncSession, organization_id: UUID, response_id: UUID, idempotency_key: str
    ) -> ReviewResponseRevision:
        item = await session.scalar(
            select(ReviewResponseRevision)
            .where(
                ReviewResponseRevision.organization_id == organization_id,
                ReviewResponseRevision.id == response_id,
            )
            .with_for_update()
        )
        if not item or item.status != "approved":
            raise ValueError("approved response required")
        review = await session.scalar(select(Review).where(Review.id == item.review_id))
        if review and review.status == "escalated":
            raise ValueError("restricted review cannot auto-publish")
        item.status = "publishing"
        item.idempotency_key = idempotency_key
        await session.flush()
        return item
