"""Active Google review read model.

Provider inventory reconciliation preserves removed reviews for audit/history, but
client-facing counts, queues, and agents must operate on the currently observed
review set only.  This service centralizes that rule instead of teaching every
caller to remember a status exclusion.
"""

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.reviews.errors import InvalidReviewQueryError
from apps.api.app.products.reviews.models import Review, ReviewEscalation, ReviewRevision
from apps.api.app.products.reviews.service import ReviewService


class ActiveReviewService(ReviewService):
    """ReviewService read operations scoped to the current provider inventory."""

    async def list_reviews(
        self,
        session: AsyncSession,
        organization_id,
        location_id,
        *,
        status_filter: str | None = None,
        rating_min: float | None = None,
        rating_max: float | None = None,
        search: str | None = None,
        sort: str = "recent",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Review], bool]:
        if not 1 <= limit <= 100 or offset < 0:
            raise InvalidReviewQueryError
        statement: Select[tuple[Review]] = select(Review).where(
            Review.organization_id == organization_id,
            Review.location_id == location_id,
        )
        if status_filter is None:
            statement = statement.where(Review.status != "removed")
        else:
            statement = statement.where(Review.status == status_filter)
        if rating_min is not None:
            statement = statement.where(Review.rating >= rating_min)
        if rating_max is not None:
            statement = statement.where(Review.rating <= rating_max)
        if search:
            pattern = f"%{search.casefold()}%"
            statement = statement.where(
                Review.id.in_(
                    select(ReviewRevision.review_id).where(
                        ReviewRevision.review_id == Review.id,
                        or_(
                            func.lower(ReviewRevision.body).like(pattern),
                            func.lower(ReviewRevision.title).like(pattern),
                        ),
                    )
                )
            )
        statement = statement.order_by(
            Review.rating.asc()
            if sort == "rating_asc"
            else Review.rating.desc()
            if sort == "rating_desc"
            else Review.review_created_at.desc()
        )
        rows = list(await session.scalars(statement.limit(limit + 1).offset(offset)))
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def summary(
        self, session: AsyncSession, organization_id, location_id
    ) -> dict[str, object]:
        active = (
            Review.organization_id == organization_id,
            Review.location_id == location_id,
            Review.status != "removed",
        )
        rows = (
            await session.execute(
                select(Review.status, func.count()).where(*active).group_by(Review.status)
            )
        ).all()
        average_rating = await session.scalar(
            select(func.avg(Review.rating)).where(*active, Review.rating.is_not(None))
        )
        restricted = await session.scalar(
            select(func.count())
            .select_from(ReviewEscalation)
            .join(Review, Review.id == ReviewEscalation.review_id)
            .where(*active, ReviewEscalation.status == "open")
        )
        return {
            "by_status": {status: count for status, count in rows},
            "average_rating": float(average_rating) if average_rating is not None else None,
            "open_restricted_cases": int(restricted or 0),
        }
