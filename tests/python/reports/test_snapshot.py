"""The monthly snapshot: windows, comparisons, partial and missing data, optional metrics, scope."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from apps.api.app.locations.enums import LocationStatus
from apps.api.app.products.gbp.performance_enums import GBPPerformanceMetric
from apps.api.app.reports.cards import figure_table
from apps.api.app.reports.contracts import (
    NOTE_EFFECT,
    Availability,
    ComparisonSpec,
    NoteCode,
    NoteEffect,
    ReportPeriod,
    ReportReadiness,
    SplitKey,
    UnavailableReason,
    WorkKind,
)
from apps.api.app.reports.errors import ReportMonthNotEndedError, ReportMonthNotFirstError
from apps.api.app.reports.snapshot import build_snapshot, data_hash, last_ended_month
from reports.support import (
    AUGUST,
    CORE,
    OCTOBER_FIRST,
    SEPTEMBER,
    Factory,
    add_location,
    add_review,
    connect_analytics,
    connect_search_console,
    days_of,
    seed_complete_month,
    seed_org,
    set_location_status,
    store_metrics,
    store_organic_month,
    store_search_month,
    store_terms,
)

pytestmark = pytest.mark.integration


async def snapshot(  # type: ignore[no-untyped-def]
    factory: Factory,
    organization_id,
    month: date = SEPTEMBER,
    now=OCTOBER_FIRST,
    *,
    end: date | None = None,
    comparison: ComparisonSpec | None = None,
):
    period = ReportPeriod(start_month=month, end_month=end or month)
    async with factory() as session:
        return await build_snapshot(
            session, organization_id, period, comparison or ComparisonSpec(), now=now
        )


def codes(result) -> set[NoteCode]:  # type: ignore[no-untyped-def]
    return {note.code for note in result.notes}


@pytest.mark.anyio
async def test_a_fully_stored_month_is_ready_and_every_figure_compares(factory: Factory) -> None:
    org, gbp, location = await seed_org(factory)
    await seed_complete_month(factory, org, gbp, location)

    result = await snapshot(factory, org)

    assert result.readiness is ReportReadiness.READY and result.notes == []
    views = result.gbp.profile_views.total
    # 30 days x 4 impression metrics x 6, against the same 30 days of August and September 2025.
    assert (
        views.current.value == 30 * 4 * 6 and views.current.availability is Availability.AVAILABLE
    )
    assert views.compared.value == 30 * 4 * 5
    assert views.year_ago and views.year_ago.value == 30 * 4 * 4
    assert views.change == 720 - 600 and views.year_change == 720 - 480
    assert views.change_percent == round(120 / 600 * 100, 1)
    assert [r.metric for r in result.gbp.profile_views.sources] == [
        m for m in CORE if "IMPRESSIONS" in m.value
    ]
    maps_search = {p.key: p for p in result.gbp.profile_views.maps_search.parts}
    assert (
        maps_search[SplitKey.MAPS].figure.value == 360
        and maps_search[SplitKey.MAPS].share_percent == 50.0
    )
    desktop_mobile = {p.key: p for p in result.gbp.profile_views.desktop_mobile.parts}
    assert desktop_mobile[SplitKey.DESKTOP].share_percent == 50.0
    assert result.local_rank.state == "not_tracked" and result.local_rank.value is None


@pytest.mark.anyio
async def test_actions_and_the_action_rate_are_computed_in_code(factory: Factory) -> None:
    org, gbp, location = await seed_org(factory)

    def value(metric: GBPPerformanceMetric, day: date) -> int:
        return 10 if "IMPRESSIONS" in metric.value else 2

    await store_metrics(factory, org, gbp, SEPTEMBER, value)

    result = await snapshot(factory, org)

    actions = result.gbp.actions
    assert actions.total.current.value == 30 * 3 * 2
    assert actions.action_rate.current.value == round(180 / 1200 * 100, 1) == 15.0
    assert [row.metric for row in actions.actions] == [
        GBPPerformanceMetric.CALL_CLICKS,
        GBPPerformanceMetric.WEBSITE_CLICKS,
        GBPPerformanceMetric.BUSINESS_DIRECTION_REQUESTS,
    ]
    # August and last year were not synced: unavailable, never 0, and no change is claimed.
    assert actions.total.compared.availability is Availability.UNAVAILABLE
    assert actions.total.compared.value is None and actions.total.change is None
    assert actions.action_rate.compared.reason is UnavailableReason.NO_DATA


@pytest.mark.anyio
async def test_the_action_rate_is_null_when_there_are_no_views(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(
        factory, org, gbp, SEPTEMBER, lambda m, d: 0 if "IMPRESSIONS" in m.value else 3
    )

    result = await snapshot(factory, org)

    assert result.gbp.profile_views.total.current.value == 0  # a real, stored zero
    assert result.gbp.actions.action_rate.current.value is None
    assert result.gbp.actions.action_rate.current.reason is UnavailableReason.NO_VIEWS


@pytest.mark.anyio
async def test_a_missing_day_makes_the_month_partial_not_short(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    missing = date(2026, 9, 14)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5, skip_days=[missing])

    result = await snapshot(factory, org)

    views = result.gbp.profile_views.total.current
    assert views.availability is Availability.PARTIAL and views.value == 29 * 4 * 5
    assert (views.days_covered, views.days_expected) == (29, 30)
    daily = result.gbp.daily
    assert daily.availability is Availability.PARTIAL and daily.missing_days == [missing]
    assert daily.days_synced == 29 and missing not in {p.day for p in daily.points}
    assert NoteCode.GBP_PERIOD_PARTIAL in codes(result)
    partial = next(n for n in result.notes if n.code is NoteCode.GBP_PERIOD_PARTIAL)
    assert partial.count == 1
    assert result.readiness is ReportReadiness.READY_WITH_NOTE
    # A half-synced side proves nothing about change.
    assert result.gbp.profile_views.total.change is None


@pytest.mark.anyio
async def test_an_optional_figure_with_no_total_in_either_period_has_no_row(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    bookings = GBPPerformanceMetric.BUSINESS_BOOKINGS
    # Google stored zeros for bookings in both months: that is nothing to report, not "0".
    for month in (SEPTEMBER, AUGUST):
        await store_metrics(
            factory,
            org,
            gbp,
            month,
            lambda m, d: 4 if m is not bookings else 0,
            metrics=(*CORE, bookings),
        )

    result = await snapshot(factory, org)

    assert result.gbp.actions.optional == []
    assert NoteCode.OPTIONAL_FIGURE_NOT_REPORTED not in codes(result)


@pytest.mark.anyio
async def test_an_optional_figure_that_drops_to_zero_is_not_comparable_and_says_so(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    bookings = GBPPerformanceMetric.BUSINESS_BOOKINGS
    await store_metrics(
        factory,
        org,
        gbp,
        SEPTEMBER,
        lambda m, d: 4 if m is not bookings else 0,
        metrics=(*CORE, bookings),
    )
    await store_metrics(factory, org, gbp, AUGUST, lambda m, d: 3, metrics=(*CORE, bookings))

    result = await snapshot(factory, org)

    (row,) = result.gbp.actions.optional
    assert row.metric is bookings and row.comparable is False
    assert row.note is NoteCode.OPTIONAL_FIGURE_NOT_REPORTED
    assert row.comparison.change is None and row.comparison.change_percent is None
    reported = next(n for n in result.notes if n.code is NoteCode.OPTIONAL_FIGURE_NOT_REPORTED)
    assert reported.metric is bookings and reported.count == 3 * 30  # the first 30 days of August
    assert NOTE_EFFECT[NoteCode.OPTIONAL_FIGURE_NOT_REPORTED] is NoteEffect.INFORMATIONAL
    # It is never a headline.
    assert all(h.key.value != "bookings" for h in result.headlines)


@pytest.mark.anyio
async def test_an_optional_figure_that_stops_part_way_through_the_period_is_marked_incomplete(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    bookings = GBPPerformanceMetric.BUSINESS_BOOKINGS
    per_day = {4: 2, 5: 2, 6: 2, 7: 3, 8: 1, 9: 0}
    # Bookings are reported through August and then Google stores zeros: July 93, August 31, then 0.
    for month_number, booked in per_day.items():
        await store_metrics(
            factory,
            org,
            gbp,
            date(2026, month_number, 1),
            lambda m, d, booked=booked: booked if m is bookings else 4,
            metrics=(*CORE, bookings),
        )

    result = await snapshot(
        factory, org, date(2026, 7, 1), end=SEPTEMBER, comparison=ComparisonSpec()
    )

    (row,) = result.gbp.actions.optional
    assert row.metric is bookings and row.comparable is False
    assert row.note is NoteCode.OPTIONAL_FIGURE_STOPPED
    # The total so far is kept, but no change is drawn against an incomplete period.
    assert row.comparison.current.value == 3 * 31 + 1 * 31 and row.comparison.compared.value
    assert row.comparison.change is None and row.comparison.change_percent is None
    stopped = next(n for n in result.notes if n.code is NoteCode.OPTIONAL_FIGURE_STOPPED)
    assert stopped.metric is bookings and stopped.month == AUGUST
    assert NoteCode.OPTIONAL_FIGURE_NOT_REPORTED not in codes(result)
    assert NOTE_EFFECT[NoteCode.OPTIONAL_FIGURE_STOPPED] is NoteEffect.INFORMATIONAL
    # Never a headline and never a result card.
    assert all(h.key.value != "bookings" for h in result.headlines)
    assert all("booking" not in key.value for key in figure_table(result, None))


@pytest.mark.anyio
async def test_an_optional_figure_still_reported_in_the_last_month_is_not_stopped(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    bookings = GBPPerformanceMetric.BUSINESS_BOOKINGS
    for month_number, booked in {4: 2, 5: 2, 6: 2, 7: 0, 8: 1, 9: 3}.items():
        await store_metrics(
            factory,
            org,
            gbp,
            date(2026, month_number, 1),
            lambda m, d, booked=booked: booked if m is bookings else 4,
            metrics=(*CORE, bookings),
        )

    result = await snapshot(factory, org, date(2026, 7, 1), end=SEPTEMBER)

    # A quiet July followed by bookings again is an ordinary figure, not a stopped one.
    (row,) = result.gbp.actions.optional
    assert row.comparable and row.note is None
    assert NoteCode.OPTIONAL_FIGURE_STOPPED not in codes(result)


@pytest.mark.anyio
async def test_an_optional_figure_that_grows_from_nothing_is_a_row_without_a_percent(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    bookings = GBPPerformanceMetric.BUSINESS_BOOKINGS
    await store_metrics(factory, org, gbp, SEPTEMBER, 4, metrics=(*CORE, bookings))
    await store_metrics(factory, org, gbp, AUGUST, 4, metrics=CORE)

    result = await snapshot(factory, org)

    (row,) = result.gbp.actions.optional
    assert row.comparable and row.comparison.current.value == 4 * 30
    assert row.comparison.change_percent is None
    # Conversations, food orders and menu clicks were never reported: no row, no zero.
    assert {r.metric for r in result.gbp.actions.optional} == {bookings}


@pytest.mark.anyio
async def test_search_terms_keep_exact_counts_and_bounds_apart(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)
    await store_terms(
        factory,
        org,
        gbp,
        SEPTEMBER,
        {
            "pizza": 40,
            "delivery": 12,
            "rare": ("below", 15),
            **{f"term {i}": i + 1 for i in range(30)},
        },
    )

    result = await snapshot(factory, org)

    terms = result.gbp.search_terms.terms
    assert len(terms) == 33  # the full table, not the top 25
    bounded = next(t for t in terms if t.keyword == "rare")
    assert (bounded.value, bounded.below_threshold, bounded.is_exact) == (None, 15, False)
    assert terms[0].keyword == "pizza" and terms[0].is_exact
    assert terms.index(bounded) == len(terms) - 1  # bounds follow every exact count


@pytest.mark.anyio
async def test_the_year_ago_month_counts_only_when_it_was_fully_synced(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)
    await store_metrics(factory, org, gbp, date(2025, 9, 1), 4, skip_days=[date(2025, 9, 3)])

    result = await snapshot(factory, org)

    year = result.gbp.profile_views.total.year_ago
    assert year is not None and year.availability is Availability.UNAVAILABLE
    assert year.reason is UnavailableReason.PARTIAL_PERIOD
    assert result.gbp.profile_views.total.year_change is None
    assert NoteCode.GBP_YEAR_AGO_UNAVAILABLE in codes(result)


@pytest.mark.anyio
async def test_leap_year_february_has_29_days_and_compares_with_the_same_days_of_january(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    february = date(2028, 2, 1)
    await store_metrics(factory, org, gbp, february, 3)
    await store_metrics(factory, org, gbp, date(2028, 1, 1), 2)
    now = datetime(2028, 3, 1, 16, 0, tzinfo=UTC)

    result = await snapshot(factory, org, february, now)

    assert result.gbp.current_range.days == 29 and result.gbp.daily.days_expected == 29
    assert result.gbp.compared_range.days == 29  # the same length, from January 1st
    assert result.gbp.profile_views.total.current.value == 29 * 4 * 3
    assert result.gbp.profile_views.total.compared.value == 29 * 4 * 2


@pytest.mark.anyio
async def test_a_31_day_month_never_reaches_into_the_next_month_for_its_comparison(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    march = date(2026, 3, 1)
    await store_metrics(factory, org, gbp, march, 3)
    await store_metrics(factory, org, gbp, date(2026, 2, 1), 2)

    result = await snapshot(factory, org, march, datetime(2026, 4, 1, 16, 0, tzinfo=UTC))

    previous = result.gbp.compared_range
    assert (previous.start, previous.end, previous.days) == (
        date(2026, 2, 1),
        date(2026, 2, 28),
        28,
    )
    assert result.gbp.profile_views.total.compared.value == 28 * 4 * 2


@pytest.mark.anyio
async def test_only_a_month_that_has_ended_can_be_reported(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)
    just_before = datetime(2026, 10, 1, 6, 59, tzinfo=UTC)  # 11:59 PM on Sept 30, Pacific

    for month, now in ((date(2026, 10, 1), OCTOBER_FIRST), (SEPTEMBER, just_before)):
        with pytest.raises(ReportMonthNotEndedError):
            await snapshot(factory, org, month, now)
    with pytest.raises(ReportMonthNotFirstError):
        await snapshot(factory, org, date(2026, 9, 15), OCTOBER_FIRST)
    assert last_ended_month(OCTOBER_FIRST) == SEPTEMBER
    assert last_ended_month(just_before) == AUGUST


@pytest.mark.anyio
async def test_a_client_without_a_business_profile_is_missing_data(factory: Factory) -> None:
    org, gbp, location = await seed_org(factory)
    # Nothing stored for the month at all: the profile is mapped but never synced it.
    result = await snapshot(factory, org)

    assert result.readiness is ReportReadiness.MISSING_DATA
    assert NoteCode.GBP_PERIOD_NOT_SYNCED in codes(result)
    assert result.gbp.profile_views.total.current.value is None
    assert result.gbp.profile_views.total.current.reason is UnavailableReason.NOT_SYNCED
    assert result.gbp.daily.points == [] and result.gbp.daily.days_synced == 0

    unmapped_org, _, _ = await seed_org(factory, "Unmapped")
    async with factory.begin() as session:
        from sqlalchemy import delete

        from apps.api.app.products.gbp.models import GBPLocation

        await session.execute(
            delete(GBPLocation).where(GBPLocation.organization_id == unmapped_org)
        )
    result = await snapshot(factory, unmapped_org)
    assert result.readiness is ReportReadiness.MISSING_DATA
    assert codes(result) >= {NoteCode.GBP_NOT_CONNECTED}
    assert result.gbp.profile_views.total.current.reason is UnavailableReason.NOT_CONNECTED


@pytest.mark.anyio
async def test_two_locations_sum_and_each_gets_a_row_and_a_paused_one_is_left_out(
    factory: Factory,
) -> None:
    org, gbp, first = await seed_org(factory, "Multi")
    second, second_gbp = await add_location(factory, org, "Second")
    paused, paused_gbp = await add_location(factory, org, "Paused", status=LocationStatus.PAUSED)
    archived, archived_gbp = await add_location(factory, org, "Old", status=LocationStatus.ARCHIVED)
    assert second_gbp and paused_gbp and archived_gbp
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)
    await store_metrics(factory, org, second_gbp, SEPTEMBER, 3)
    await store_metrics(factory, org, paused_gbp, SEPTEMBER, 100)
    await store_metrics(factory, org, archived_gbp, SEPTEMBER, 100)

    result = await snapshot(factory, org)

    assert result.gbp.profile_views.total.current.value == 30 * 4 * (5 + 3)
    rows = {row.name: row for row in result.gbp.locations}
    assert set(rows) == {"Main", "Second"}
    assert rows["Main"].profile_views.current.value == 30 * 4 * 5
    assert rows["Second"].calls.current.value == 30 * 3
    assert rows["Second"].location_id == second


@pytest.mark.anyio
async def test_a_single_location_has_no_per_location_rows(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)

    assert (await snapshot(factory, org)).gbp.locations == []


@pytest.mark.anyio
async def test_a_location_that_is_not_mapped_is_a_note_not_a_failure(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    unmapped, _ = await add_location(factory, org, "Unmapped", mapped=False)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)

    result = await snapshot(factory, org)

    note = next(n for n in result.notes if n.code is NoteCode.GBP_LOCATION_NOT_MAPPED)
    assert note.location_id == unmapped
    assert result.readiness is ReportReadiness.READY_WITH_NOTE
    assert next(r for r in result.gbp.locations if r.location_id == unmapped).mapped is False


@pytest.mark.anyio
async def test_reviews_exclude_removed_count_once_and_measure_the_response_rate(
    factory: Factory,
) -> None:
    org, gbp, location = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)
    sept = datetime(2026, 9, 12, 12, tzinfo=UTC)
    await add_review(
        factory,
        org,
        location,
        rating=5,
        created=sept,
        status="responded",
        responded_at=sept + timedelta(days=1),
    )
    await add_review(factory, org, location, rating=3, created=sept)
    await add_review(factory, org, location, rating=1, created=sept, status="removed")
    await add_review(factory, org, location, rating=4, created=datetime(2026, 8, 20, tzinfo=UTC))
    await add_review(factory, org, location, rating=2, created=datetime(2026, 10, 2, tzinfo=UTC))
    # A response published in September to an August review still counts as a response published.
    august = await add_review(
        factory,
        org,
        location,
        rating=5,
        created=datetime(2026, 8, 1, tzinfo=UTC),
        status="responded",
        responded_at=datetime(2026, 9, 3, tzinfo=UTC),
    )
    assert august

    reviews = (await snapshot(factory, org)).reviews

    assert reviews.new_reviews.current.value == 2  # the removed review is history
    assert reviews.average_rating_in_period.current.value == 4.0
    assert (
        reviews.responded_to_new.value == 1 and reviews.response_rate_percent.current.value == 50.0
    )
    assert reviews.responses_published.value == 2
    # As of the end of September: October's review is not part of it.
    assert reviews.total_count.value == 4
    assert reviews.average_rating_overall.current.value == round((5 + 3 + 4 + 5) / 4, 2)
    assert {s.stars: s.count for s in reviews.distribution_period} == {1: 0, 2: 0, 3: 1, 4: 0, 5: 1}
    assert {s.stars: s.count for s in reviews.distribution_overall} == {
        1: 0,
        2: 0,
        3: 1,
        4: 1,
        5: 2,
    }


@pytest.mark.anyio
async def test_a_client_with_no_stored_reviews_is_not_synced_never_zero(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)

    result = await snapshot(factory, org)

    assert result.reviews.new_reviews.current.value is None
    assert result.reviews.new_reviews.current.reason is UnavailableReason.NOT_SYNCED
    assert NoteCode.REVIEWS_NOT_SYNCED in codes(result)


@pytest.mark.anyio
async def test_reviews_of_an_archived_location_are_not_counted(factory: Factory) -> None:
    org, gbp, location = await seed_org(factory)
    old, _ = await add_location(factory, org, "Old")
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)
    sept = datetime(2026, 9, 12, tzinfo=UTC)
    await add_review(factory, org, location, rating=5, created=sept)
    await add_review(factory, org, old, rating=1, created=sept)
    await set_location_status(factory, org, old, LocationStatus.ARCHIVED)

    reviews = (await snapshot(factory, org)).reviews

    assert (
        reviews.new_reviews.current.value == 1
        and reviews.average_rating_in_period.current.value == 5.0
    )


@pytest.mark.anyio
async def test_search_console_months_report_exact_months_with_month_over_month_change(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)
    prop, website = await connect_search_console(factory, org)
    await store_search_month(
        factory,
        org,
        prop,
        website,
        SEPTEMBER,
        clicks=120,
        impressions=3000,
        position=8.44,
        queries={"pizza": (60, 1000), "new term": (5, 100)},
        pages={"https://x.test/": (70, 900)},
    )
    await store_search_month(
        factory,
        org,
        prop,
        website,
        AUGUST,
        clicks=100,
        impressions=2500,
        position=9.0,
        queries={"pizza": (50, 900)},
        pages={"https://x.test/": (60, 800)},
    )

    search = (await snapshot(factory, org)).search_console

    assert search.availability is Availability.AVAILABLE
    assert (search.clicks.current.value, search.clicks.compared.value) == (120, 100)
    assert search.clicks.change == 20 and search.clicks.change_percent == 20.0
    assert search.ctr_percent.current.value == 4.0
    assert search.average_position.current.value == 8.4 and search.average_position.change == -0.6
    pizza = next(q for q in search.top_queries if q.query == "pizza")
    assert (pizza.compared_clicks, pizza.clicks_change) == (50, 10)
    new = next(q for q in search.top_queries if q.query == "new term")
    assert (new.compared_clicks, new.clicks_change) == (None, None)
    assert search.top_pages[0].clicks_change == 10


@pytest.mark.anyio
async def test_a_rolling_28_day_window_is_never_used_for_a_month(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)
    prop, website = await connect_search_console(factory, org)
    # A 28-day window that happens to be stored: the month still reads as not synced.
    from apps.api.app.products.seo.models import SEOSearchObservation

    async with factory.begin() as session:
        session.add(
            SEOSearchObservation(
                organization_id=org,
                search_property_id=prop,
                website_id=website,
                date_start=datetime(2026, 9, 3, tzinfo=UTC),
                date_end=datetime(2026, 10, 1, tzinfo=UTC),
                dimensions={"observation_type": "site_summary", "website_id": str(website)},
                dimension_hash="rolling",
                clicks=999,
                impressions=9999,
                ctr=0.1,
                position=3,
                quality_status="valid",
                partial=False,
            )
        )

    result = await snapshot(factory, org)

    assert result.search_console.availability is Availability.UNAVAILABLE
    assert result.search_console.reason is UnavailableReason.NOT_SYNCED
    assert result.search_console.clicks.current.value is None
    assert NoteCode.SEARCH_CONSOLE_NOT_SYNCED in codes(result)


@pytest.mark.anyio
async def test_a_search_console_month_the_provider_has_not_settled_is_partial_with_its_lag(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)
    prop, website = await connect_search_console(factory, org)
    await store_search_month(
        factory,
        org,
        prop,
        website,
        SEPTEMBER,
        clicks=120,
        impressions=3000,
        position=8.0,
        partial=True,
    )

    result = await snapshot(factory, org)

    assert result.search_console.availability is Availability.PARTIAL
    assert result.search_console.clicks.current.availability is Availability.PARTIAL
    lag = next(n for n in result.notes if n.code is NoteCode.SEARCH_CONSOLE_LAG_DAYS)
    assert lag.count and lag.count >= 1
    assert result.readiness is ReportReadiness.READY_WITH_NOTE


@pytest.mark.anyio
async def test_google_analytics_organic_sessions_report_a_month_or_say_why_not(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    await store_metrics(factory, org, gbp, SEPTEMBER, 5)

    unconnected = await snapshot(factory, org)
    assert unconnected.analytics.reason is UnavailableReason.NOT_CONNECTED
    assert NoteCode.ANALYTICS_NOT_CONNECTED in codes(unconnected)
    assert unconnected.analytics.organic_sessions.current.value is None

    _, website = await connect_search_console(factory, org)
    await connect_analytics(factory, org, website)
    not_synced = await snapshot(factory, org)
    assert not_synced.analytics.reason is UnavailableReason.NOT_SYNCED

    await store_organic_month(factory, org, website, SEPTEMBER, 900)
    await store_organic_month(factory, org, website, AUGUST, 800)
    synced = await snapshot(factory, org)
    sessions = synced.analytics.organic_sessions
    assert (sessions.current.value, sessions.compared.value) == (900, 800)
    assert sessions.change == 100 and sessions.change_percent == 12.5

    zero_org, zero_gbp, _ = await seed_org(factory, "Zero")
    await store_metrics(factory, zero_org, zero_gbp, SEPTEMBER, 5)
    _, zero_site = await connect_search_console(factory, zero_org)
    await connect_analytics(factory, zero_org, zero_site)
    await store_organic_month(factory, zero_org, zero_site, SEPTEMBER, 0)
    zero = (await snapshot(factory, zero_org)).analytics.organic_sessions.current
    assert zero.value == 0 and zero.availability is Availability.AVAILABLE  # a read zero


@pytest.mark.anyio
async def test_work_completed_comes_only_from_existing_records(factory: Factory) -> None:
    org, gbp, location = await seed_org(factory)
    await seed_complete_month(factory, org, gbp, location)

    work = {g.kind: g for g in (await snapshot(factory, org)).work.groups}

    assert set(work) == set(WorkKind)
    # Nothing was published or changed, so every group is an honest zero with no titles.
    assert work[WorkKind.REVIEW_RESPONSE].count == 1
    assert work[WorkKind.GBP_POST].count == 0 and work[WorkKind.GBP_POST].titles == []
    assert work[WorkKind.WEBSITE_CONTENT].titles == []


@pytest.mark.anyio
async def test_the_same_stored_data_always_gives_the_same_snapshot_and_hash(
    factory: Factory,
) -> None:
    org, gbp, location = await seed_org(factory)
    await seed_complete_month(factory, org, gbp, location)

    first = await snapshot(factory, org)
    second = await snapshot(factory, org, now=OCTOBER_FIRST + timedelta(hours=5))

    assert first == second and data_hash(first) == data_hash(second)
    assert days_of(SEPTEMBER)[0] == date(2026, 9, 1)
