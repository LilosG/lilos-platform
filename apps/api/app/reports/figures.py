"""Turn stored totals into report figures: a number, a partial number, or the reason there is none.

Nothing here invents a value. A total that was never synced stays unavailable; zero only appears
when the stored rows say zero.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from apps.api.app.products.gbp.performance_enums import GBPPerformanceAvailability
from apps.api.app.products.gbp.performance_read import Total
from apps.api.app.reports.contracts import (
    Availability,
    ComparedAs,
    ReportCountComparison,
    ReportCountFigure,
    ReportMonthPoint,
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


def year_figure(figure: ReportCountFigure | None) -> ReportCountFigure:
    """The same months a year earlier count only when every one of them was synced."""
    if figure is None:
        return unavailable_count(UnavailableReason.NOT_COMPARED)
    if figure.availability is Availability.PARTIAL:
        return unavailable_count(UnavailableReason.PARTIAL_PERIOD)
    return figure


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


def _settled(figure: ReportCountFigure) -> bool:
    """A figure a change can be drawn from: a half-settled one proves nothing."""
    return figure.availability is Availability.AVAILABLE and figure.value is not None


def _delta(current: float, other: float) -> tuple[float, float | None]:
    return current - other, (round((current - other) / other * 100, 1) if other else None)


@dataclass(frozen=True, slots=True)
class Basis:
    """How a period is set against its comparison: months on each side and the unit compared."""

    compared_as: ComparedAs = ComparedAs.TOTAL
    period_months: int = 1
    compared_months: int = 1

    def compared_value(self, total: int) -> int:
        """The compared figure in the comparison's unit: the total, or its monthly average."""
        if self.compared_as is ComparedAs.TOTAL:
            return total
        return round(total / self.compared_months)

    def current_average(self, total: int) -> int | None:
        return (
            round(total / self.period_months)
            if self.compared_as is ComparedAs.MONTHLY_AVERAGE
            else None
        )


def compare_counts(
    current: ReportCountFigure,
    compared: ReportCountFigure,
    year_ago: ReportCountFigure | None,
    basis: Basis,
    *,
    with_year: bool = True,
) -> ReportCountComparison:
    """A period's count against its comparison and (when asked) the same months a year earlier.

    ``compared`` is the comparison's total; it is turned into a monthly average here when the
    two periods differ in length, and the change is between like quantities.
    """
    averaged = basis.compared_as is ComparedAs.MONTHLY_AVERAGE
    shown = compared
    if averaged and compared.value is not None:
        shown = compared.model_copy(update={"value": basis.compared_value(compared.value)})
    change: int | None = None
    percent: float | None = None
    if _settled(current) and _settled(compared):
        assert current.value is not None and compared.value is not None
        if averaged:
            now_average = current.value / basis.period_months
            before_average = compared.value / basis.compared_months
            _, percent = _delta(now_average, before_average)
            change = round(now_average) - round(before_average)
        else:
            difference, percent = _delta(current.value, compared.value)
            change = int(difference)
    year_change: int | None = None
    year_percent: float | None = None
    year_shown: ReportCountFigure | None = None
    if with_year and year_ago is not None:
        year_shown = year_figure(year_ago)
        if _settled(current) and _settled(year_shown):
            assert current.value is not None and year_shown.value is not None
            difference, year_percent = _delta(current.value, year_shown.value)
            year_change = int(difference)
    return ReportCountComparison(
        current=current,
        compared=shown,
        compared_as=basis.compared_as,
        current_monthly_average=(
            basis.current_average(current.value) if current.value is not None else None
        ),
        year_ago=year_shown,
        change=change,
        change_percent=percent,
        year_change=year_change,
        year_change_percent=year_percent,
    )


def total_comparison(
    current: Total,
    compared: Total,
    year_ago: Total | None,
    basis: Basis,
    *,
    optional: bool = False,
    with_year: bool = True,
) -> ReportCountComparison:
    """``compare_counts`` over stored Business Profile totals."""
    return compare_counts(
        count_figure(current, optional=optional),
        count_figure(compared, optional=optional),
        count_figure(year_ago, optional=optional) if year_ago is not None else None,
        basis,
        with_year=with_year,
    )


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
    compared: ReportRateFigure,
    year_ago: ReportRateFigure | None = None,
) -> ReportRateComparison:
    """Rates and positions are set against each other directly, never averaged over months."""

    def difference(other: ReportRateFigure | None) -> float | None:
        if other is None or current.value is None or other.value is None:
            return None
        if Availability.PARTIAL in (current.availability, other.availability):
            return None
        return round(current.value - other.value, 1)

    return ReportRateComparison(
        current=current,
        compared=compared,
        year_ago=year_ago,
        change=difference(compared),
        year_change=difference(year_ago),
    )


# ---- Figures stored one total per calendar month (Search Console, Analytics) ------------------


@dataclass(frozen=True, slots=True)
class MonthValue:
    """One stored month: its total, and whether the provider had not yet settled it."""

    month: date
    value: int
    partial: bool = False


def months_figure(expected: Sequence[date], present: Sequence[MonthValue]) -> ReportCountFigure:
    """The sum of the months that were synced.

    All months settled: available. Some missing, or stored before the provider settled them:
    partial, with how many months were covered. None synced: unavailable, never 0.
    """
    if not present:
        return unavailable_count(UnavailableReason.NOT_SYNCED)
    complete = len(present) == len(expected) and not any(item.partial for item in present)
    return ReportCountFigure(
        availability=Availability.AVAILABLE if complete else Availability.PARTIAL,
        value=sum(item.value for item in present),
        months_covered=len(present),
        months_expected=len(expected),
    )


def month_points(expected: Sequence[date], present: Sequence[MonthValue]) -> list[ReportMonthPoint]:
    """One point per month; a month that was not synced is a point with no value."""
    by_month = {item.month: item for item in present}
    points: list[ReportMonthPoint] = []
    for month in expected:
        item = by_month.get(month)
        if item is None:
            points.append(ReportMonthPoint(month=month, availability=Availability.UNAVAILABLE))
        else:
            points.append(
                ReportMonthPoint(
                    month=month,
                    availability=Availability.PARTIAL if item.partial else Availability.AVAILABLE,
                    value=item.value,
                )
            )
    return points
