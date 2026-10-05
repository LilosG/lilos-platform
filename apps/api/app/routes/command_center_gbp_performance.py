"""Business Profile performance presentation over stored sync rows; no provider I/O on reads."""

from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select

from apps.api.app.authentication.dependencies import Authenticated, get_authenticated_principal
from apps.api.app.locations.models import Location
from apps.api.app.products.gbp.operations_errors import (
    GBPLocationNotFoundError,
    GBPPerformanceMonthRequiredError,
)
from apps.api.app.products.gbp.performance_enums import (
    GBPPerformanceAvailability,
    GBPPerformanceMetric,
    GBPPerformanceSyncStatus,
)
from apps.api.app.products.gbp.performance_read import (
    MetricComparison,
    PerformancePeriod,
    PerformanceRead,
    Total,
    read_performance,
)
from apps.api.app.products.gbp.performance_service import mapped_gbp_locations
from apps.api.app.routes.command_center_reviews import private
from apps.api.app.routes.command_center_search import allowed
from apps.api.app.routes.reviews import Session

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/command-center/gbp/performance",
    tags=["command-center"],
    dependencies=[Depends(get_authenticated_principal), Depends(private)],
)


class PerformanceLocation(BaseModel):
    id: UUID
    name: str
    mapped: bool


class PerformanceRange(BaseModel):
    start: date
    end: date
    days: int


class PerformanceTotal(BaseModel):
    """A sum over a window. ``value`` is null unless something was synced for it; never 0."""

    availability: GBPPerformanceAvailability
    value: int | None
    days_covered: int
    days_expected: int


class PerformanceComparison(BaseModel):
    current: PerformanceTotal
    previous: PerformanceTotal
    change: int | None
    change_percent: float | None


class PerformanceMetricView(PerformanceComparison):
    metric: GBPPerformanceMetric


class PerformanceSearchTerm(BaseModel):
    keyword: str
    # Sum of the exact counts Google gave; null when Google only said "fewer than N".
    value: int | None
    # Sum of the "fewer than N" figures. When set, the count is a bound, not an exact number.
    below_threshold: int | None
    is_exact: bool


class PerformanceSearchTerms(BaseModel):
    availability: GBPPerformanceAvailability
    month: date | None
    terms: list[PerformanceSearchTerm]


class PerformanceSource(BaseModel):
    last_synced_at: datetime | None
    last_status: GBPPerformanceSyncStatus | None
    last_failure_code: str | None


class GBPPerformanceView(BaseModel):
    organization_id: UUID
    period: PerformancePeriod
    month: date | None
    location_id: UUID | None
    locations: list[PerformanceLocation]
    availability: GBPPerformanceAvailability
    current_range: PerformanceRange
    previous_range: PerformanceRange
    profile_views: PerformanceComparison
    metrics: list[PerformanceMetricView]
    search_terms: PerformanceSearchTerms
    source: PerformanceSource


def _total(total: Total) -> PerformanceTotal:
    return PerformanceTotal(
        availability=total.availability,
        value=total.value,
        days_covered=total.days_covered,
        days_expected=total.days_expected,
    )


def _comparison(comparison: MetricComparison) -> PerformanceComparison:
    return PerformanceComparison(
        current=_total(comparison.current),
        previous=_total(comparison.previous),
        change=comparison.change,
        change_percent=comparison.change_percent,
    )


def _view(
    organization_id: UUID,
    period: PerformancePeriod,
    location_id: UUID | None,
    locations: list[PerformanceLocation],
    read: PerformanceRead,
) -> GBPPerformanceView:
    windows = read.windows
    return GBPPerformanceView(
        organization_id=organization_id,
        period=period,
        month=windows.month,
        location_id=location_id,
        locations=locations,
        availability=read.availability,
        current_range=PerformanceRange(
            start=windows.current.start, end=windows.current.end, days=windows.current.days
        ),
        previous_range=PerformanceRange(
            start=windows.previous.start, end=windows.previous.end, days=windows.previous.days
        ),
        profile_views=_comparison(read.profile_views),
        metrics=[
            PerformanceMetricView(metric=metric, **_comparison(comparison).model_dump())
            for metric, comparison in read.metrics.items()
        ],
        search_terms=PerformanceSearchTerms(
            availability=read.search_terms.availability,
            month=read.search_terms.month,
            terms=[
                PerformanceSearchTerm(
                    keyword=term.keyword,
                    value=term.value,
                    below_threshold=term.below_threshold,
                    is_exact=term.is_exact,
                )
                for term in read.search_terms.terms
            ],
        ),
        source=PerformanceSource(
            last_synced_at=read.source.last_synced_at,
            last_status=read.source.last_status,
            last_failure_code=read.source.last_failure_code,
        ),
    )


@router.get("", response_model=GBPPerformanceView)
async def performance(
    request: Request,
    organization_id: UUID,
    session: Session,
    principal: Authenticated,
    period: PerformancePeriod = PerformancePeriod.LAST_28_DAYS,
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    location_id: UUID | None = None,
) -> GBPPerformanceView:
    """A client's Business Profile performance for 7, 28 or 90 days or a calendar month.

    Totals are per metric, with the previous period of equal length for comparison.
    ``profile_views`` is the sum of the four impression metrics. ``location_id`` narrows to one
    platform location; without it every location the caller may read is summed.
    """
    if period is PerformancePeriod.MONTH and month is None:
        raise GBPPerformanceMonthRequiredError
    mapped_by_location = {
        row.location_id: row.id for row in await mapped_gbp_locations(session, organization_id)
    }
    visible: list[PerformanceLocation] = []
    for location in await session.scalars(
        select(Location)
        .where(Location.organization_id == organization_id)
        .order_by(Location.name, Location.id)
    ):
        if await allowed(
            session, principal, organization_id, request, "gbp.read", location_id=location.id
        ):
            visible.append(
                PerformanceLocation(
                    id=location.id, name=location.name, mapped=location.id in mapped_by_location
                )
            )
    if not visible or (location_id and location_id not in {row.id for row in visible}):
        raise GBPLocationNotFoundError
    selected = [location_id] if location_id else [row.id for row in visible]
    gbp_ids = [mapped_by_location[item] for item in selected if item in mapped_by_location]
    month_start = date.fromisoformat(f"{month}-01") if month else None
    read = await read_performance(session, organization_id, gbp_ids, period, month=month_start)
    return _view(organization_id, period, location_id, visible, read)
