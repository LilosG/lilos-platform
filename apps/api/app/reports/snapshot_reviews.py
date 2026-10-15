"""The reviews section of a report, counted from stored reviews.

Reviews Google no longer lists (status ``removed``) are history: they are never counted. A review
is one row, so it can never be counted twice. A client with no stored review at all has not been
synced, which is reported as such and never as zero. Every window is counted the same way, so the
period, its comparison and the same months a year earlier are directly comparable.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import and_, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.reviews.models import Review, ReviewResponseRevision
from apps.api.app.products.reviews.service import REVIEW_REMOVED
from apps.api.app.reporting_periods import calendar_month_window
from apps.api.app.reports.contracts import (
    Availability,
    NoteCode,
    ReportComparison,
    ReportCountComparison,
    ReportDataNote,
    ReportMonthlySeries,
    ReportPeriod,
    ReportRateComparison,
    ReportRateFigure,
    ReportReviewsSection,
    ReportStarCount,
    SeriesKey,
    UnavailableReason,
    note,
)
from apps.api.app.reports.figures import (
    Basis,
    MonthValue,
    available_count,
    available_rate,
    compare_counts,
    month_points,
    rate_comparison,
    unavailable_count,
    unavailable_rate,
)

STARS: tuple[int, ...] = (1, 2, 3, 4, 5)
RESPONSE_PUBLISHED = "published"


def period_bounds(period: ReportPeriod) -> tuple[datetime, datetime]:
    """The half-open UTC interval of a period of whole months."""
    return calendar_month_window(period.start_month)[0], calendar_month_window(period.end_month)[1]


@dataclass(frozen=True, slots=True)
class ReviewWindow:
    new_total: int
    new_average: float | None
    new_distribution: list[ReportStarCount]
    overall_total: int
    overall_average: float | None
    overall_distribution: list[ReportStarCount]
    responded: int
    published: int

    @property
    def response_rate(self) -> float | None:
        return round(self.responded / self.new_total * 100, 1) if self.new_total else None


@dataclass(frozen=True, slots=True)
class ReviewsResult:
    section: ReportReviewsSection
    notes: list[ReportDataNote]
    series: list[ReportMonthlySeries]


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


async def _window(
    session: AsyncSession, scope: tuple[object, ...], start: datetime, following: datetime
) -> ReviewWindow:
    # Overall figures are as of the end of the window, so a later review never changes them.
    overall_total, overall_average, overall_distribution = await _stars(
        session, *scope, Review.review_created_at < following
    )
    in_window = (*scope, Review.review_created_at >= start, Review.review_created_at < following)
    new_total, new_average, new_distribution = await _stars(session, *in_window)
    responded = int(
        await session.scalar(
            select(func.count(Review.id)).where(
                *in_window,  # type: ignore[arg-type]
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
                *scope,  # type: ignore[arg-type]
                ReviewResponseRevision.status == RESPONSE_PUBLISHED,
                ReviewResponseRevision.published_at >= start,
                ReviewResponseRevision.published_at < following,
            )
        )
        or 0
    )
    return ReviewWindow(
        new_total,
        new_average,
        new_distribution,
        overall_total,
        overall_average,
        overall_distribution,
        responded,
        published,
    )


def _rate(value: float | None) -> ReportRateFigure:
    return (
        available_rate(value) if value is not None else unavailable_rate(UnavailableReason.NO_DATA)
    )


def _rates(
    pick: str, current: ReviewWindow, compared: ReviewWindow, year: ReviewWindow | None
) -> ReportRateComparison:
    return rate_comparison(
        _rate(getattr(current, pick)),
        _rate(getattr(compared, pick)),
        _rate(getattr(year, pick)) if year else None,
    )


async def _monthly_new(
    session: AsyncSession, scope: tuple[object, ...], months: Sequence[date]
) -> list[MonthValue]:
    started = func.date_trunc("month", Review.review_created_at)
    rows = await session.execute(
        select(started, func.count(Review.id))
        .where(
            *scope,  # type: ignore[arg-type]
            Review.review_created_at >= calendar_month_window(months[0])[0],
            Review.review_created_at < calendar_month_window(months[-1])[1],
        )
        .group_by(started)
    )
    counted = {row[0].date(): int(row[1]) for row in rows}
    return [MonthValue(month, counted.get(month, 0)) for month in months]


async def build_reviews(
    session: AsyncSession,
    organization_id: UUID,
    period: ReportPeriod,
    comparison: ReportComparison,
    location_ids: Sequence[UUID],
    basis: Basis,
) -> ReviewsResult:
    scope: tuple[object, ...] = (
        Review.organization_id == organization_id,
        Review.location_id.in_(location_ids),
        Review.status != REVIEW_REMOVED,
    )
    stored = int(await session.scalar(select(func.count(Review.id)).where(*scope)) or 0)  # type: ignore[arg-type]
    if not location_ids or stored == 0:
        reason = UnavailableReason.NOT_SYNCED
        empty = [ReportStarCount(stars=s, count=0) for s in STARS]  # type: ignore[arg-type]
        missing_counts = ReportCountComparison(
            current=unavailable_count(reason), compared=unavailable_count(reason)
        )
        missing_rates = ReportRateComparison(
            current=unavailable_rate(reason), compared=unavailable_rate(reason)
        )
        return ReviewsResult(
            ReportReviewsSection(
                availability=Availability.UNAVAILABLE,
                reason=reason,
                new_reviews=missing_counts,
                average_rating_in_period=missing_rates,
                average_rating_overall=missing_rates,
                total_count=unavailable_count(reason),
                responses_published=unavailable_count(reason),
                responded_to_new=unavailable_count(reason),
                response_rate_percent=missing_rates,
                distribution_overall=empty,
                distribution_period=empty,
            ),
            [note(NoteCode.REVIEWS_NOT_SYNCED)],
            [
                ReportMonthlySeries(
                    key=SeriesKey.NEW_REVIEWS,
                    period=month_points(period.months, []),
                    compared=month_points(comparison.compared.months, []),
                )
            ],
        )
    current = await _window(session, scope, *period_bounds(period))
    compared = await _window(session, scope, *period_bounds(comparison.compared))
    year = (
        await _window(session, scope, *period_bounds(comparison.year_ago))
        if comparison.year_ago
        else None
    )
    return ReviewsResult(
        ReportReviewsSection(
            availability=Availability.AVAILABLE,
            new_reviews=compare_counts(
                available_count(current.new_total),
                available_count(compared.new_total),
                available_count(year.new_total) if year else None,
                basis,
            ),
            average_rating_in_period=_rates("new_average", current, compared, year),
            average_rating_overall=_rates("overall_average", current, compared, year),
            total_count=available_count(current.overall_total),
            responses_published=available_count(current.published),
            responded_to_new=available_count(current.responded),
            response_rate_percent=_rates("response_rate", current, compared, year),
            distribution_overall=current.overall_distribution,
            distribution_period=current.new_distribution,
        ),
        [],
        [
            ReportMonthlySeries(
                key=SeriesKey.NEW_REVIEWS,
                period=month_points(
                    period.months, await _monthly_new(session, scope, period.months)
                ),
                compared=month_points(
                    comparison.compared.months,
                    await _monthly_new(session, scope, comparison.compared.months),
                ),
            )
        ],
    )
