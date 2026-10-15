"""Report periods, comparisons, figures over several months, and the pure rules built on them."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from apps.api.app.reports.contracts import (
    Availability,
    ComparedAs,
    ComparisonBasis,
    ComparisonSpec,
    HeadlineKey,
    ReportAnalyticsSection,
    ReportCountComparison,
    ReportPeriod,
    UnavailableReason,
)
from apps.api.app.reports.errors import (
    ReportBaselineOverlapsError,
    ReportBaselineRequiredError,
    ReportBaselineUnexpectedError,
    ReportComparisonInvalidError,
    ReportMonthNotEndedError,
    ReportMonthNotFirstError,
    ReportPeriodInvalidError,
    ReportPeriodOrderError,
    ReportPeriodTooLongError,
)
from apps.api.app.reports.figures import (
    Basis,
    MonthValue,
    available_count,
    available_rate,
    compare_counts,
    month_points,
    months_figure,
    rate_comparison,
    unavailable_count,
)
from apps.api.app.reports.headlines import pick_headlines
from apps.api.app.reports.snapshot import require_ended
from apps.api.app.reports.snapshot_search import is_branded, normalize_text


def period(start: str, end: str | None = None) -> ReportPeriod:
    return ReportPeriod(
        start_month=date.fromisoformat(f"{start}-01"),
        end_month=date.fromisoformat(f"{end or start}-01"),
    )


def baseline(start: str, end: str) -> ComparisonSpec:
    return ComparisonSpec(
        basis=ComparisonBasis.CUSTOM_BASELINE,
        baseline_start=date.fromisoformat(f"{start}-01"),
        baseline_end=date.fromisoformat(f"{end}-01"),
    )


class TestPeriodValidation:
    def test_one_to_twelve_months_are_allowed(self) -> None:
        assert period("2026-09").span == 1
        assert period("2025-10", "2026-09").span == 12
        assert [m.isoformat() for m in period("2025-11", "2026-02").months] == [
            "2025-11-01",
            "2025-12-01",
            "2026-01-01",
            "2026-02-01",
        ]

    def test_thirteen_months_are_too_long(self) -> None:
        with pytest.raises(ReportPeriodTooLongError):
            period("2025-09", "2026-09")

    def test_the_last_month_cannot_come_first(self) -> None:
        with pytest.raises(ReportPeriodOrderError):
            period("2026-09", "2026-08")

    def test_a_month_is_its_first_day(self) -> None:
        with pytest.raises(ReportMonthNotFirstError):
            ReportPeriod(start_month=date(2026, 9, 2), end_month=date(2026, 9, 2))

    def test_a_month_that_has_not_ended_is_refused_in_pacific_time(self) -> None:
        october_first_utc = datetime(2026, 10, 1, 6, 59, tzinfo=UTC)  # still Sept 30 in Pacific
        with pytest.raises(ReportMonthNotEndedError):
            require_ended(date(2026, 9, 1), october_first_utc)
        require_ended(date(2026, 9, 1), datetime(2026, 10, 1, 7, 0, tzinfo=UTC))
        with pytest.raises(ReportMonthNotEndedError):
            require_ended(date(2026, 10, 1), datetime(2026, 10, 20, tzinfo=UTC))

    @pytest.mark.parametrize("slug", ["2026-9", "2026-09_", "2026-09_2026-10_2026-11", "x", ""])
    def test_a_malformed_period_slug_is_a_typed_error(self, slug: str) -> None:
        with pytest.raises(ReportPeriodInvalidError):
            ReportPeriod.from_slug(slug)

    def test_slugs_round_trip(self) -> None:
        for text in ("2026-09", "2026-05_2026-09"):
            assert ReportPeriod.from_slug(text).slug == text
        assert period("2026-05", "2026-05").slug == "2026-05"


class TestComparisonSpec:
    def test_keys_and_slugs_round_trip(self) -> None:
        for spec in (
            ComparisonSpec(),
            ComparisonSpec(basis=ComparisonBasis.SAME_PERIOD_LAST_YEAR),
            baseline("2026-01", "2026-03"),
            baseline("2026-01", "2026-01"),
        ):
            assert ComparisonSpec.from_key(spec.key) == spec
            assert ComparisonSpec.from_slug(spec.slug) == spec
        assert ComparisonSpec().key == "previous"
        assert ComparisonSpec(basis=ComparisonBasis.SAME_PERIOD_LAST_YEAR).key == "year_ago"
        assert baseline("2026-01", "2026-03").key == "baseline:2026-01:2026-03"
        assert baseline("2026-01", "2026-01").slug == "vs-2026-01"

    @pytest.mark.parametrize("slug", ["", "sometimes", "vs", "vs-x"])
    def test_an_unknown_comparison_slug_is_a_typed_error(self, slug: str) -> None:
        with pytest.raises((ReportComparisonInvalidError, ReportPeriodInvalidError)):
            ComparisonSpec.from_slug(slug)

    def test_a_baseline_needs_both_months_and_others_take_none(self) -> None:
        with pytest.raises(ReportBaselineRequiredError):
            ComparisonSpec(basis=ComparisonBasis.CUSTOM_BASELINE, baseline_start=date(2026, 1, 1))
        with pytest.raises(ReportBaselineUnexpectedError):
            ComparisonSpec(baseline_start=date(2026, 1, 1), baseline_end=date(2026, 2, 1))

    def test_a_baseline_is_one_to_twelve_whole_months_in_order(self) -> None:
        with pytest.raises(ReportPeriodTooLongError):
            baseline("2024-01", "2025-06")
        with pytest.raises(ReportPeriodOrderError):
            baseline("2026-03", "2026-01")

    def test_previous_period_is_the_same_number_of_months_just_before(self) -> None:
        resolved = ComparisonSpec().resolve(period("2026-05", "2026-07"))
        assert (resolved.compared.start_month, resolved.compared.end_month) == (
            date(2026, 2, 1),
            date(2026, 4, 1),
        )
        assert resolved.compared_as is ComparedAs.TOTAL
        assert resolved.year_ago == period("2025-05", "2025-07")

    def test_a_single_month_is_compared_with_the_month_before_across_a_year_end(self) -> None:
        resolved = ComparisonSpec().resolve(period("2026-01"))
        assert resolved.compared == period("2025-12")

    def test_same_period_last_year_is_the_comparison_and_adds_no_second_year_ago(self) -> None:
        resolved = ComparisonSpec(basis=ComparisonBasis.SAME_PERIOD_LAST_YEAR).resolve(
            period("2026-05", "2026-09")
        )
        assert resolved.compared == period("2025-05", "2025-09")
        assert resolved.year_ago is None and resolved.compared_as is ComparedAs.TOTAL

    def test_a_baseline_of_the_same_length_compares_totals(self) -> None:
        resolved = baseline("2026-01", "2026-03").resolve(period("2026-05", "2026-07"))
        assert resolved.compared == period("2026-01", "2026-03")
        assert resolved.compared_as is ComparedAs.TOTAL
        assert resolved.year_ago == period("2025-05", "2025-07")

    def test_a_baseline_of_another_length_compares_monthly_averages(self) -> None:
        resolved = baseline("2026-01", "2026-02").resolve(period("2026-05", "2026-07"))
        assert resolved.compared_as is ComparedAs.MONTHLY_AVERAGE

    def test_a_baseline_must_end_before_the_period_starts(self) -> None:
        for spec in (baseline("2026-03", "2026-05"), baseline("2026-06", "2026-08")):
            with pytest.raises(ReportBaselineOverlapsError):
                spec.resolve(period("2026-05", "2026-07"))
        # Adjacent months do not overlap.
        assert baseline("2026-03", "2026-04").resolve(period("2026-05", "2026-07"))


class TestComparedFigures:
    def test_totals_of_equal_length_are_compared_directly(self) -> None:
        result = compare_counts(
            available_count(150), available_count(100), available_count(75), Basis(), with_year=True
        )
        assert (result.change, result.change_percent) == (50, 50.0)
        assert (result.year_change, result.year_change_percent) == (75, 100.0)
        assert result.compared_as is ComparedAs.TOTAL and result.current_monthly_average is None

    def test_a_different_length_baseline_is_compared_as_a_monthly_average(self) -> None:
        # Three months now (900), two months before (400): 300 a month against 200 a month.
        basis = Basis(ComparedAs.MONTHLY_AVERAGE, period_months=3, compared_months=2)
        result = compare_counts(available_count(900), available_count(400), None, basis)
        assert result.compared.value == 200 and result.current_monthly_average == 300
        assert (result.change, result.change_percent) == (100, 50.0)
        assert result.current.value == 900  # the real total is still the figure shown

    def test_nothing_is_compared_when_a_side_is_partial_or_missing(self) -> None:
        partial = months_figure(
            [date(2026, 8, 1), date(2026, 9, 1)], [MonthValue(date(2026, 9, 1), 80)]
        )
        for current, compared in (
            (partial, available_count(100)),
            (available_count(100), unavailable_count(UnavailableReason.NOT_SYNCED)),
        ):
            result = compare_counts(current, compared, None, Basis())
            assert (result.change, result.change_percent) == (None, None)

    def test_a_partial_year_ago_is_not_used(self) -> None:
        partial = months_figure(
            [date(2025, 8, 1), date(2025, 9, 1)], [MonthValue(date(2025, 9, 1), 80)]
        )
        result = compare_counts(available_count(100), available_count(90), partial, Basis())
        assert result.year_ago is not None and result.year_ago.value is None
        assert result.year_ago.reason is UnavailableReason.PARTIAL_PERIOD
        assert result.year_change is None

    def test_rates_and_positions_are_never_averaged_over_months(self) -> None:
        result = rate_comparison(available_rate(4.0), available_rate(3.5))
        assert result.change == 0.5


class TestMonthlyFigures:
    MONTHS = [date(2026, 7, 1), date(2026, 8, 1), date(2026, 9, 1)]

    def test_every_month_synced_and_settled_is_available(self) -> None:
        figure = months_figure(self.MONTHS, [MonthValue(m, 10) for m in self.MONTHS])
        assert (figure.availability, figure.value) == (Availability.AVAILABLE, 30)

    def test_one_missing_month_makes_the_figure_partial_with_the_months_covered(self) -> None:
        figure = months_figure(self.MONTHS, [MonthValue(m, 10) for m in self.MONTHS[:2]])
        assert figure.availability is Availability.PARTIAL and figure.value == 20
        assert (figure.months_covered, figure.months_expected) == (2, 3)

    def test_a_month_stored_before_the_provider_settled_it_is_partial(self) -> None:
        stored = [MonthValue(m, 10, partial=m == self.MONTHS[-1]) for m in self.MONTHS]
        assert months_figure(self.MONTHS, stored).availability is Availability.PARTIAL

    def test_no_month_synced_is_unavailable_never_zero(self) -> None:
        figure = months_figure(self.MONTHS, [])
        assert figure.availability is Availability.UNAVAILABLE and figure.value is None
        assert figure.reason is UnavailableReason.NOT_SYNCED

    def test_monthly_points_keep_a_missing_month_as_a_point_without_a_value(self) -> None:
        points = month_points(self.MONTHS, [MonthValue(self.MONTHS[0], 7)])
        assert [(p.availability, p.value) for p in points] == [
            (Availability.AVAILABLE, 7),
            (Availability.UNAVAILABLE, None),
            (Availability.UNAVAILABLE, None),
        ]


class TestBrandedSearches:
    def test_normalisation_lowercases_and_drops_apostrophes_and_punctuation(self) -> None:
        assert normalize_text("Coco Maya's  Café!") == "coco mayas café"
        assert normalize_text("coco-maya") == "coco maya"
        assert normalize_text("Coco’s") == "cocos"

    def test_a_search_naming_the_organization_or_a_location_is_branded(self) -> None:
        terms = ["Coco Maya", "Maya Beach Cafe"]
        assert is_branded("coco maya menu", terms)
        assert is_branded("Coco Maya's happy hour", terms)
        assert is_branded("maya beach cafe hours", terms)
        assert not is_branded("best tacos near me", terms)
        assert not is_branded("coco chanel", terms)

    def test_an_empty_brand_name_brands_nothing(self) -> None:
        assert not is_branded("anything at all", ["", "  "])


def count(
    current: int | None, compared: int | None, *, change: bool = True
) -> ReportCountComparison:
    cur = (
        available_count(current)
        if current is not None
        else unavailable_count(UnavailableReason.NOT_SYNCED)
    )
    cmp_ = (
        available_count(compared)
        if compared is not None
        else unavailable_count(UnavailableReason.NOT_SYNCED)
    )
    return (
        compare_counts(cur, cmp_, None, Basis())
        if change
        else ReportCountComparison(current=cur, compared=cmp_)
    )


class TestHeadlines:
    def sections(self, **counts: ReportCountComparison):  # type: ignore[no-untyped-def]
        from types import SimpleNamespace

        missing = count(None, None)
        rating = rate_comparison(available_rate(4.6), available_rate(4.5))
        return pick_headlines(
            SimpleNamespace(
                profile_views=SimpleNamespace(total=counts.get("views", missing)),
                actions=SimpleNamespace(total=counts.get("actions", missing)),
            ),  # type: ignore[arg-type]
            SimpleNamespace(clicks=counts.get("clicks", missing)),  # type: ignore[arg-type]
            ReportAnalyticsSection(
                availability=Availability.AVAILABLE,
                organic_sessions=counts.get("sessions", missing),
            ),
            SimpleNamespace(  # type: ignore[arg-type]
                new_reviews=counts.get("reviews", missing), average_rating_overall=rating
            ),
        )

    def test_the_first_four_computable_figures_in_a_fixed_order(self) -> None:
        picked = self.sections(
            views=count(120, 100),
            actions=count(60, 50),
            clicks=count(30, 20),
            sessions=count(80, 40),
            reviews=count(5, 4),
        )
        assert [h.key for h in picked] == [
            HeadlineKey.PROFILE_VIEWS,
            HeadlineKey.PROFILE_ACTIONS,
            HeadlineKey.WEBSITE_SEARCH_CLICKS,
            HeadlineKey.ORGANIC_SESSIONS,
        ]

    def test_unavailable_or_incomparable_figures_are_skipped(self) -> None:
        picked = self.sections(
            views=count(None, 100),  # not synced this period
            actions=count(60, 0),  # nothing before: no percent, no headline
            clicks=count(30, 20),
            reviews=count(5, 4),
        )
        assert [h.key for h in picked] == [
            HeadlineKey.WEBSITE_SEARCH_CLICKS,
            HeadlineKey.NEW_REVIEWS,
            HeadlineKey.AVERAGE_RATING,
        ]
        assert picked[-1].rate is not None and picked[-1].count is None
