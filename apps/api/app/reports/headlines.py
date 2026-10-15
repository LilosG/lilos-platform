"""The figures a report leads with, chosen by code in a fixed order. No words are written here."""

from __future__ import annotations

from apps.api.app.reports.contracts import (
    Availability,
    HeadlineKey,
    ReportAnalyticsSection,
    ReportCountComparison,
    ReportGbpSection,
    ReportHeadline,
    ReportRateComparison,
    ReportReviewsSection,
    ReportSearchConsoleSection,
)

HEADLINE_COUNT = 4


def _countable(comparison: ReportCountComparison) -> bool:
    return (
        comparison.current.availability is Availability.AVAILABLE
        and comparison.compared.availability is Availability.AVAILABLE
        and comparison.change is not None
        and comparison.change_percent is not None
    )


def _rateable(comparison: ReportRateComparison) -> bool:
    return (
        comparison.current.availability is Availability.AVAILABLE
        and comparison.compared.availability is Availability.AVAILABLE
        and comparison.change is not None
    )


def pick_headlines(
    gbp: ReportGbpSection,
    search: ReportSearchConsoleSection,
    analytics: ReportAnalyticsSection,
    reviews: ReportReviewsSection,
) -> list[ReportHeadline]:
    """The first four figures, in priority order, whose period and comparison are both settled
    and whose change can be computed."""
    counts: tuple[tuple[HeadlineKey, ReportCountComparison], ...] = (
        (HeadlineKey.PROFILE_VIEWS, gbp.profile_views.total),
        (HeadlineKey.PROFILE_ACTIONS, gbp.actions.total),
        (HeadlineKey.WEBSITE_SEARCH_CLICKS, search.clicks),
        (HeadlineKey.ORGANIC_SESSIONS, analytics.organic_sessions),
        (HeadlineKey.NEW_REVIEWS, reviews.new_reviews),
    )
    picked: list[ReportHeadline] = [
        ReportHeadline(key=key, count=comparison)
        for key, comparison in counts
        if _countable(comparison)
    ]
    if _rateable(reviews.average_rating_overall):
        picked.append(
            ReportHeadline(key=HeadlineKey.AVERAGE_RATING, rate=reviews.average_rating_overall)
        )
    return picked[:HEADLINE_COUNT]
