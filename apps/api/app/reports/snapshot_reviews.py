"""The reviews section of a monthly report, counted from stored reviews.

Reviews Google no longer lists (status ``removed``) are history: they are never counted. A review
is one row, so it can never be counted twice. A client with no stored review at all has not been
synced, which is reported as such and never as zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.reviews.models import Review, ReviewResponseRevision
from apps.api.app.products.reviews.service import REVIEW_REMOVED
from apps.api.app.reports.contracts import (
    Availability,
    NoteCode,
    ReportDataNote,
    ReportReviewsSection,
    ReportStarCount,
    UnavailableReason,
    note,
)
from apps.api.app.reports.figures import (
    available_count,
    available_rate,
    unavailable_count,
    unavailable_rate,
)

STARS: tuple[int, ...] = (1, 2, 3, 4, 5)
RESPONSE_PUBLISHED = "published"


def month_bounds(month: date) -> tuple[datetime, datetime]:
    """The half-open UTC interval of a calendar month."""
    start = datetime(month.year, month.month, 1, tzinfo=UTC)
    following = datetime(month.year + (month.month == 12), month.month % 12 + 1, 1, tzinfo=UTC)
    return start, following


async def _stars(
    session: AsyncSession, *conditions: object
) -> tuple[int, float | None, list[ReportStarCount]]:
    """Review count, average rating and 1-5 star distribution of the reviews that match."""
    total = int(await session.scalar(select(func.count(Review.id)).where(*conditions)) or 0)  # type: ignore[arg-type]
    average = await session.scalar(select(func.avg(Review.rating)).where(*conditions))  # type: ignore[arg-type]
    rows = await session.execute(
        select(func.round(Review.rating), func.count(Review.id))
        .where(*conditions, Review.rating.is_not(None))  # type: ignore[arg-type]
        .group_by(func.round(Review.rating))
    )
    counts = {int(stars): int(count) for stars, count in rows if stars is not None}
    distribution = [ReportStarCount(stars=s, count=counts.get(s, 0)) for s in STARS]  # type: ignore[arg-type]
    return total, (round(float(average), 2) if average is not None else None), distribution


async def build_reviews(
    session: AsyncSession, organization_id: UUID, month: date, location_ids: Sequence[UUID]
) -> tuple[ReportReviewsSection, list[ReportDataNote]]:
    start, following = month_bounds(month)
    scope = (
        Review.organization_id == organization_id,
        Review.location_id.in_(location_ids),
        Review.status != REVIEW_REMOVED,
    )
    stored = int(await session.scalar(select(func.count(Review.id)).where(*scope)) or 0)
    if not location_ids or stored == 0:
        reason = UnavailableReason.NOT_SYNCED
        empty = [ReportStarCount(stars=s, count=0) for s in STARS]  # type: ignore[arg-type]
        return (
            ReportReviewsSection(
                availability=Availability.UNAVAILABLE,
                reason=reason,
                new_in_month=unavailable_count(reason),
                average_rating_in_month=unavailable_rate(reason),
                average_rating_overall=unavailable_rate(reason),
                total_count=unavailable_count(reason),
                responses_published=unavailable_count(reason),
                responded_to_new=unavailable_count(reason),
                response_rate_percent=unavailable_rate(reason),
                distribution_overall=empty,
                distribution_month=empty,
            ),
            [note(NoteCode.REVIEWS_NOT_SYNCED)],
        )
    # Overall figures are as of the end of the month, so a later review never changes them.
    overall_total, overall_average, overall_distribution = await _stars(
        session, *scope, Review.review_created_at < following
    )
    in_month = (*scope, Review.review_created_at >= start, Review.review_created_at < following)
    new_total, new_average, month_distribution = await _stars(session, *in_month)
    responded = int(
        await session.scalar(
            select(func.count(Review.id)).where(
                *in_month,
                exists().where(
                    and_(
                        ReviewResponseRevision.organization_id == Review.organization_id,
                        ReviewResponseRevision.review_id == Review.id,
                        ReviewResponseRevision.status == RESPONSE_PUBLISHED,
                    )
                ),
            )
        )
        or 0
    )
    published = int(
        await session.scalar(
            select(func.count(ReviewResponseRevision.id))
            .join(
                Review,
                and_(
                    Review.organization_id == ReviewResponseRevision.organization_id,
                    Review.id == ReviewResponseRevision.review_id,
                ),
            )
            .where(
                *scope,
                ReviewResponseRevision.status == RESPONSE_PUBLISHED,
                ReviewResponseRevision.published_at >= start,
                ReviewResponseRevision.published_at < following,
            )
        )
        or 0
    )
    return (
        ReportReviewsSection(
            availability=Availability.AVAILABLE,
            new_in_month=available_count(new_total),
            average_rating_in_month=(
                available_rate(new_average)
                if new_average is not None
                else unavailable_rate(UnavailableReason.NO_DATA)
            ),
            average_rating_overall=(
                available_rate(overall_average)
                if overall_average is not None
                else unavailable_rate(UnavailableReason.NO_DATA)
            ),
            total_count=available_count(overall_total),
            responses_published=available_count(published),
            responded_to_new=available_count(responded),
            response_rate_percent=(
                available_rate(round(responded / new_total * 100, 1))
                if new_total
                else unavailable_rate(UnavailableReason.NO_DATA)
            ),
            distribution_overall=overall_distribution,
            distribution_month=month_distribution,
        ),
        [],
    )
