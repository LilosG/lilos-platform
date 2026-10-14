"""Turn stored totals into report figures: a number, a partial number, or the reason there is none.

Nothing here invents a value. A total that was never synced stays unavailable; zero only appears
when the stored rows say zero.
"""

from __future__ import annotations

from collections.abc import Sequence

from apps.api.app.products.gbp.performance_enums import GBPPerformanceAvailability
from apps.api.app.products.gbp.performance_read import MetricComparison, Total, compare
from apps.api.app.reports.contracts import (
    Availability,
    ReportCountComparison,
    ReportCountFigure,
    ReportRateComparison,
    ReportRateFigure,
    UnavailableReason,
)

_REASON: dict[GBPPerformanceAvailability, UnavailableReason] = {
    GBPPerformanceAvailability.NO_DATA: UnavailableReason.NO_DATA,
    GBPPerformanceAvailability.NOT_SYNCED: UnavailableReason.NOT_SYNCED,
    GBPPerformanceAvailability.NOT_CONNECTED: UnavailableReason.NOT_CONNECTED,
}


def unavailable_count(reason: UnavailableReason) -> ReportCountFigure:
    return ReportCountFigure(availability=Availability.UNAVAILABLE, reason=reason)


def unavailable_rate(reason: UnavailableReason) -> ReportRateFigure:
    return ReportRateFigure(availability=Availability.UNAVAILABLE, reason=reason)


def available_count(value: int) -> ReportCountFigure:
    return ReportCountFigure(availability=Availability.AVAILABLE, value=value)


def available_rate(value: float) -> ReportRateFigure:
    return ReportRateFigure(availability=Availability.AVAILABLE, value=value)


def count_figure(total: Total, *, optional: bool = False) -> ReportCountFigure:
    """A stored total as a figure. An optional metric with no rows is "not reported"."""
    if total.value is None:
        reason = _REASON[total.availability]
        if optional and total.availability is GBPPerformanceAvailability.NO_DATA:
            reason = UnavailableReason.NOT_REPORTED
        return unavailable_count(reason)
    return ReportCountFigure(
        availability=(
            Availability.AVAILABLE
            if total.availability is GBPPerformanceAvailability.AVAILABLE
            else Availability.PARTIAL
        ),
        value=total.value,
        days_covered=total.days_covered,
        days_expected=total.days_expected,
    )


def year_figure(total: Total | None) -> ReportCountFigure:
    """The same month a year earlier counts only when that whole month was synced."""
    if total is None:
        return unavailable_count(UnavailableReason.NOT_COMPARED)
    if total.availability is GBPPerformanceAvailability.AVAILABLE:
        return count_figure(total)
    if total.availability is GBPPerformanceAvailability.PARTIAL:
        return unavailable_count(UnavailableReason.PARTIAL_PERIOD)
    return unavailable_count(_REASON[total.availability])


def combine(totals: Sequence[Total]) -> Total:
    """The sum of several totals; unavailable as soon as one of them has no value at all."""
    expected = max((total.days_expected for total in totals), default=0)
    missing = [total for total in totals if total.value is None]
    if missing:
        return Total(missing[0].availability, None, 0, expected)
    complete = all(total.availability is GBPPerformanceAvailability.AVAILABLE for total in totals)
    return Total(
        GBPPerformanceAvailability.AVAILABLE if complete else GBPPerformanceAvailability.PARTIAL,
        sum(total.value or 0 for total in totals),
        min(total.days_covered for total in totals),
        expected,
    )


def count_comparison(
    current: Total,
    previous: Total,
    year_ago: Total | None,
    *,
    optional: bool = False,
    with_year: bool = True,
) -> ReportCountComparison:
    """Current against the month before and (when asked) the same month a year earlier."""
    month = compare(current, previous)
    year = compare(current, year_ago) if year_ago is not None else None
    return ReportCountComparison(
        current=count_figure(current, optional=optional),
        previous=count_figure(previous, optional=optional),
        year_ago=year_figure(year_ago) if with_year else None,
        change=month.change,
        change_percent=month.change_percent,
        year_change=year.change if year else None,
        year_change_percent=year.change_percent if year else None,
    )


def comparison_of(
    read: MetricComparison, year_ago: Total | None, *, optional: bool = False
) -> ReportCountComparison:
    return count_comparison(read.current, read.previous, year_ago, optional=optional)


def rate_figure(numerator: Total, denominator: Total) -> ReportRateFigure:
    """numerator / denominator as a percent; null when either side is missing, partial or zero."""
    for side in (numerator, denominator):
        if side.value is None:
            return unavailable_rate(_REASON[side.availability])
    if GBPPerformanceAvailability.PARTIAL in (numerator.availability, denominator.availability):
        return unavailable_rate(UnavailableReason.PARTIAL_PERIOD)
    if not denominator.value:
        return unavailable_rate(UnavailableReason.NO_VIEWS)
    return available_rate(round((numerator.value or 0) / denominator.value * 100, 1))


def rate_comparison(
    current: ReportRateFigure,
    previous: ReportRateFigure,
    year_ago: ReportRateFigure | None = None,
) -> ReportRateComparison:
    def difference(other: ReportRateFigure | None) -> float | None:
        if other is None or current.value is None or other.value is None:
            return None
        if Availability.PARTIAL in (current.availability, other.availability):
            return None
        return round(current.value - other.value, 1)

    return ReportRateComparison(
        current=current,
        previous=previous,
        year_ago=year_ago,
        change=difference(previous),
        year_change=difference(year_ago),
    )
