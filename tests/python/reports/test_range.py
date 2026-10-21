"""A report over several months: windows for every comparison, sums across months, partial data."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
import sqlalchemy as sa

from apps.api.app.reports.contracts import (
    Availability,
    ComparedAs,
    ComparisonBasis,
    ComparisonSpec,
    HeadlineKey,
    NoteCode,
    ReportPeriod,
    SeriesKey,
)
from apps.api.app.reports.service import ReportService
from apps.api.app.reports.snapshot import build_snapshot
from reports.support import (
    OCTOBER_FIRST,
    Factory,
    add_review,
    connect_analytics,
    connect_search_console,
    seed_org,
    store_metrics,
    store_organic_month,
    store_search_month,
    store_terms,
)

pytestmark = pytest.mark.integration
MAY, JUN, JUL, AUG, SEP = (date(2026, m, 1) for m in (5, 6, 7, 8, 9))
JAN, FEB, MAR = (date(2026, m, 1) for m in (1, 2, 3))
AUG_25, SEP_25 = date(2025, 8, 1), date(2025, 9, 1)
AUG_SEP = ReportPeriod(start_month=AUG, end_month=SEP)
PREVIOUS = ComparisonSpec()
YEAR_AGO = ComparisonSpec(basis=ComparisonBasis.SAME_PERIOD_LAST_YEAR)


def baseline(start: date, end: date) -> ComparisonSpec:
    return ComparisonSpec(
        basis=ComparisonBasis.CUSTOM_BASELINE, baseline_start=start, baseline_end=end
    )


async def snapshot(factory: Factory, org, spec: ComparisonSpec = PREVIOUS, period=AUG_SEP):  # type: ignore[no-untyped-def]
    async with factory() as session:
        return await build_snapshot(session, org, period, spec, now=OCTOBER_FIRST)


async def seed_views(factory: Factory, org, gbp, values: dict[date, int]) -> None:  # type: ignore[no-untyped-def]
    for month, per_day in values.items():
        await store_metrics(factory, org, gbp, month, per_day)


def monthly(result, key: SeriesKey):  # type: ignore[no-untyped-def]
    return next(series for series in result.monthly if series.key is key)


@pytest.mark.anyio
async def test_two_months_are_summed_against_the_two_months_before(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    await seed_views(factory, org, gbp, {JUN: 5, JUL: 5, AUG: 6, SEP: 6, AUG_25: 4, SEP_25: 4})

    result = await snapshot(factory, org)

    views = result.gbp.profile_views.total
    assert views.current.value == (31 + 30) * 4 * 6  # all 61 days of August and September
    assert views.compared.value == (30 + 31) * 4 * 5  # June and July
    assert views.change == 1464 - 1220 and views.change_percent == round(244 / 1220 * 100, 1)
    assert views.year_ago and views.year_ago.value == 61 * 4 * 4
    assert views.compared_as is ComparedAs.TOTAL and views.current_monthly_average is None
    assert result.gbp.current_range.days == 61 and result.gbp.compared_range.days == 61
    assert result.gbp.year_ago_range is not None
    assert result.comparison.compared == ReportPeriod(start_month=JUN, end_month=JUL)
    # A point per month for the period and for the comparison.
    series = monthly(result, SeriesKey.PROFILE_VIEWS)
    assert [(p.month, p.value) for p in series.period] == [(AUG, 31 * 4 * 6), (SEP, 30 * 4 * 6)]
    assert [(p.month, p.value) for p in series.compared] == [(JUN, 30 * 4 * 5), (JUL, 31 * 4 * 5)]
    assert all(p.availability is Availability.AVAILABLE for p in series.period + series.compared)


@pytest.mark.anyio
async def test_same_period_last_year_is_the_comparison_and_has_no_second_year(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    await seed_views(factory, org, gbp, {AUG: 6, SEP: 6, AUG_25: 4, SEP_25: 4})

    result = await snapshot(factory, org, YEAR_AGO)

    views = result.gbp.profile_views.total
    assert views.compared.value == 61 * 4 * 4 and views.year_ago is None
    assert result.gbp.year_ago_range is None
    assert result.comparison.compared == ReportPeriod(start_month=AUG_25, end_month=SEP_25)


@pytest.mark.anyio
async def test_a_baseline_of_another_length_is_compared_as_monthly_averages(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    await seed_views(factory, org, gbp, {JAN: 5, FEB: 5, MAR: 5, AUG: 6, SEP: 6})

    result = await snapshot(factory, org, baseline(JAN, MAR))

    views = result.gbp.profile_views.total
    assert views.compared_as is ComparedAs.MONTHLY_AVERAGE
    assert views.current.value == 1464  # the real total of the two months
    assert views.current_monthly_average == 732
    assert views.compared.value == round((31 + 28 + 31) * 4 * 5 / 3)  # 600 a month
    assert (views.change, views.change_percent) == (132, 22.0)
    # Rates are never averaged: the action rate compares the two periods' own rates.
    rate = result.gbp.actions.action_rate
    assert (rate.current.value, rate.compared.value, rate.change) == (75.0, 75.0, 0.0)


@pytest.mark.anyio
async def test_search_terms_are_summed_across_the_months_with_their_bounds(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    await seed_views(factory, org, gbp, {AUG: 5, SEP: 5})
    await store_terms(factory, org, gbp, AUG, {"pizza": 30, "tacos": 10, "rare": ("below", 15)})
    await store_terms(factory, org, gbp, SEP, {"pizza": 20, "rare": ("below", 15)})

    terms = (await snapshot(factory, org)).gbp.search_terms

    by_keyword = {t.keyword: t for t in terms.terms}
    assert by_keyword["pizza"].value == 50 and by_keyword["pizza"].is_exact
    assert by_keyword["tacos"].value == 10
    assert by_keyword["rare"].value is None and by_keyword["rare"].below_threshold == 30
    assert not by_keyword["rare"].is_exact
    assert terms.total_terms == 3 and (terms.months_covered, terms.months_expected) == (2, 2)
    assert [t.keyword for t in terms.terms][:2] == ["pizza", "tacos"]


@pytest.mark.anyio
async def test_search_console_months_are_summed_and_one_unsynced_month_is_partial(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    await seed_views(factory, org, gbp, {AUG: 5, SEP: 5})
    prop, site = await connect_search_console(factory, org)
    for month, clicks, impressions, position in (
        (
            MAY,
            10,
            300,
            12.0,
        ),  # first data month: no baseline
        (JUN, 40, 1000, 10.0),
        (JUL, 60, 1000, 10.0),
        (AUG, 100, 2000, 6.0),
        (SEP, 80, 6000, 12.0),
    ):
        await store_search_month(
            factory,
            org,
            prop,
            site,
            month,
            clicks=clicks,
            impressions=impressions,
            position=position,
        )

    complete = (await snapshot(factory, org)).search_console

    assert complete.availability is Availability.AVAILABLE
    assert (complete.clicks.current.value, complete.clicks.compared.value) == (180, 100)
    assert complete.impressions.current.value == 8000
    # CTR comes from the sums and the position is weighted by impressions.
    assert complete.ctr_percent.current.value == round(180 / 8000 * 100, 2)
    assert complete.average_position.current.value == round((6 * 2000 + 12 * 6000) / 8000, 1)
    assert complete.clicks.change == 80

    # Remove July: the compared period is now missing a month.
    async with factory.begin() as session:
        await session.execute(
            sa.text(
                "delete from seo_search_observations where date_start = '2026-07-01T00:00:00+00'"
            )
        )
    missing_compared = await snapshot(factory, org)
    assert missing_compared.search_console.clicks.compared.availability is Availability.PARTIAL
    assert missing_compared.search_console.clicks.change is None
    assert NoteCode.SEARCH_CONSOLE_COMPARED_PERIOD_UNAVAILABLE in {
        n.code for n in missing_compared.notes
    }

    # Remove August: the period itself is missing a month, with how many it covers.
    async with factory.begin() as session:
        await session.execute(
            sa.text(
                "delete from seo_search_observations where date_start = '2026-08-01T00:00:00+00'"
            )
        )
    partial = await snapshot(factory, org)
    clicks = partial.search_console.clicks.current
    assert clicks.availability is Availability.PARTIAL and clicks.value == 80
    assert (clicks.months_covered, clicks.months_expected) == (1, 2)
    assert partial.search_console.availability is Availability.PARTIAL
    missing = next(n for n in partial.notes if n.code is NoteCode.SEARCH_CONSOLE_MONTHS_MISSING)
    assert missing.count == 1
    points = monthly(partial, SeriesKey.SEARCH_CLICKS).period
    assert [(p.month, p.availability, p.value) for p in points] == [
        (AUG, Availability.UNAVAILABLE, None),
        (SEP, Availability.AVAILABLE, 80),
    ]
    # A partial figure is never a headline.
    assert HeadlineKey.WEBSITE_SEARCH_CLICKS not in {h.key for h in partial.headlines}


@pytest.mark.anyio
async def test_top_searches_are_aggregated_and_split_into_branded_and_not(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory, "Coco")
    async with factory.begin() as session:  # the slug rules forbid a space; the name has one
        await session.execute(
            sa.text("update organizations set name = 'Coco Maya' where id = :id"), {"id": org}
        )
    await seed_views(factory, org, gbp, {AUG: 5, SEP: 5})
    prop, site = await connect_search_console(factory, org)
    for month, queries in (
        (AUG, {"coco maya": (50, 500), "best tacos": (20, 900), "mexican near me": (5, 400)}),
        (SEP, {"Coco Maya's menu": (30, 300), "best tacos": (30, 1000)}),
        (JUL, {"best tacos": (25, 800)}),
        (JUN, {"best tacos": (15, 800)}),
        (MAY, {"best tacos": (5, 800)}),  # the first data month, never a baseline
    ):
        await store_search_month(
            factory,
            org,
            prop,
            site,
            month,
            clicks=200,
            impressions=4000,
            position=7.0,
            queries=queries,
        )

    search = (await snapshot(factory, org)).search_console

    rows = {row.query: row for row in search.top_queries}
    assert rows["best tacos"].clicks == 50 and rows["best tacos"].impressions == 1900
    assert rows["best tacos"].compared_clicks == 40 and rows["best tacos"].clicks_change == 10
    assert rows["best tacos"].is_branded is False
    assert rows["coco maya"].is_branded and rows["Coco Maya's menu"].is_branded
    assert rows["mexican near me"].compared_clicks is None  # not in the comparison's top rows
    assert rows["mexican near me"].clicks_change is None
    # Branded clicks over all clicks of the top searches: 80 of 135.
    assert search.branded_share_percent == round(80 / 135 * 100, 1)
    # Ranked by clicks, then impressions: the tie at 50 clicks goes to the more seen search.
    assert [r.query for r in search.top_queries][:2] == ["best tacos", "coco maya"]


@pytest.mark.anyio
async def test_analytics_sums_months_and_reports_the_months_it_has(factory: Factory) -> None:
    org, gbp, _ = await seed_org(factory)
    await seed_views(factory, org, gbp, {AUG: 5, SEP: 5})
    _, site = await connect_search_console(factory, org)
    await connect_analytics(factory, org, site)
    for month, sessions in ((JUN, 300), (JUL, 300), (AUG, 400), (SEP, 500)):
        await store_organic_month(factory, org, site, month, sessions)

    sessions = (await snapshot(factory, org)).analytics.organic_sessions
    assert (sessions.current.value, sessions.compared.value, sessions.change) == (900, 600, 300)

    async with factory.begin() as session:
        await session.execute(
            sa.text("delete from metric_observations where period_start = '2026-08-01T00:00:00+00'")
        )
    result = await snapshot(factory, org)
    partial = result.analytics.organic_sessions
    assert partial.current.availability is Availability.PARTIAL and partial.current.value == 500
    assert (partial.current.months_covered, partial.current.months_expected) == (1, 2)
    assert NoteCode.ANALYTICS_MONTHS_MISSING in {n.code for n in result.notes}


@pytest.mark.anyio
async def test_reviews_are_counted_for_the_period_and_the_comparison(factory: Factory) -> None:
    org, gbp, location = await seed_org(factory)
    await seed_views(factory, org, gbp, {AUG: 5, SEP: 5})
    for created, rating in (
        (datetime(2026, 6, 10, tzinfo=UTC), 3),
        (datetime(2026, 7, 10, tzinfo=UTC), 4),
        (datetime(2026, 8, 10, tzinfo=UTC), 5),
        (datetime(2026, 9, 10, tzinfo=UTC), 5),
        (datetime(2026, 9, 12, tzinfo=UTC), 4),
    ):
        await add_review(factory, org, location, rating=rating, created=created)

    reviews = (await snapshot(factory, org)).reviews

    assert (reviews.new_reviews.current.value, reviews.new_reviews.compared.value) == (3, 2)
    assert reviews.new_reviews.change == 1 and reviews.new_reviews.change_percent == 50.0
    assert reviews.average_rating_in_period.current.value == round(14 / 3, 2)
    assert reviews.average_rating_in_period.compared.value == 3.5
    assert reviews.average_rating_overall.current.value == round(21 / 5, 2)
    assert reviews.average_rating_overall.compared.value == 3.5  # as of the end of July
    series = monthly(await snapshot(factory, org), SeriesKey.NEW_REVIEWS)
    assert [p.value for p in series.period] == [1, 2] and [p.value for p in series.compared] == [
        1,
        1,
    ]


@pytest.mark.anyio
async def test_regenerating_with_identical_inputs_returns_the_same_revision(
    factory: Factory,
) -> None:
    org, gbp, _ = await seed_org(factory)
    await seed_views(factory, org, gbp, {JUN: 5, JUL: 5, AUG: 6, SEP: 6})
    service = ReportService()

    async def generate(spec: ComparisonSpec):  # type: ignore[no-untyped-def]
        async with factory.begin() as session:
            return await service.generate(
                session, org, AUG_SEP, spec, actor_id=None, correlation_id="t", now=OCTOBER_FIRST
            )

    first, created = await generate(PREVIOUS)
    again, created_again = await generate(PREVIOUS)
    other, other_created = await generate(YEAR_AGO)

    assert created and not created_again and again.revision.id == first.revision.id
    assert first.revision.period_month == AUG and first.revision.period_end_month == SEP
    assert first.revision.comparison_key == "previous"
    # Another comparison of the same months is its own report, numbered from 1.
    assert other_created and other.revision.revision == 1
    assert other.revision.comparison_key == "year_ago"
    assert other.revision.snapshot_hash != first.revision.snapshot_hash
    # A sync that only touches the sync dates changes no number and makes no new revision.
    assert first.data_hash == again.data_hash


@pytest.mark.anyio
async def test_the_sent_date_is_after_the_last_month_of_the_period(factory: Factory) -> None:
    from uuid import uuid4

    from apps.api.app.authentication.enums import UserStatus
    from apps.api.app.authentication.models import UserProfile
    from apps.api.app.reports.contracts import NarrativeOrigin, ReportNarrative
    from apps.api.app.reports.errors import ReportSentDateInvalidError

    org, gbp, _ = await seed_org(factory)
    await seed_views(factory, org, gbp, {JUN: 5, JUL: 5, AUG: 6, SEP: 6})
    service = ReportService()
    async with factory.begin() as session:
        person = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
        session.add(person)
        await session.flush()
        await service.generate(
            session, org, AUG_SEP, PREVIOUS, actor_id=None, correlation_id="t", now=OCTOBER_FIRST
        )
        await service.set_narrative(
            session,
            org,
            AUG_SEP,
            PREVIOUS,
            1,
            ReportNarrative(what_changed="a", next_work="b", origin=NarrativeOrigin.MANUAL),
            actor_id=None,
            correlation_id="t",
        )
        await service.approve(
            session, org, AUG_SEP, PREVIOUS, 1, actor_id=person.id, correlation_id="t"
        )
        person_id = person.id
    now = datetime(2026, 10, 6, tzinfo=UTC)
    async with factory.begin() as session:
        with pytest.raises(ReportSentDateInvalidError):  # still inside the last month, September
            await service.mark_sent(
                session, org, AUG_SEP, PREVIOUS, 1, date(2026, 9, 30),
                actor_id=person_id, correlation_id="t", now=now,
            )  # fmt: skip
    async with factory.begin() as session:
        delivery, created = await service.mark_sent(
            session, org, AUG_SEP, PREVIOUS, 1, date(2026, 10, 1),
            actor_id=person_id, correlation_id="t", now=now,
        )  # fmt: skip
    assert created and delivery.idempotency_key.endswith(":2026-08_2026-09:previous:1")
