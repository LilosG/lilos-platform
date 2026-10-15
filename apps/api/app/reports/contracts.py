"""Typed contracts of the client report: one or more whole calendar months against a comparison.

Every figure is available, partial, or unavailable with a reason code; a missing number is never
0. Classes, states and data notes are enums, so no layer matches English text. The computed
snapshot and the narrative are separate documents: the narrative is stored beside the numbers
and is never part of them.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from apps.api.app.products.gbp.performance_enums import GBPPerformanceMetric
from apps.api.app.products.gbp.performance_service import months_before
from apps.api.app.reporting_periods import first_of_month, month_range
from apps.api.app.reports.errors import (
    ReportBaselineOverlapsError,
    ReportBaselineRequiredError,
    ReportBaselineUnexpectedError,
    ReportComparisonInvalidError,
    ReportMonthNotFirstError,
    ReportPeriodInvalidError,
    ReportPeriodOrderError,
    ReportPeriodTooLongError,
)
from apps.api.app.routes.command_center_search import TrackedCount

# 2: periods of 1 to 12 months, a comparison basis, headlines and monthly series.
SNAPSHOT_SCHEMA_VERSION = 2
DEFINITION_KEY = "monthly-performance"
MAX_PERIOD_MONTHS = 12


class ReportStatus(StrEnum):
    """Where a report is in its life: written, approved by a person, or recorded as sent."""

    DRAFT = "draft"
    READY = "ready"
    SENT = "sent"


class ReportReadiness(StrEnum):
    READY = "ready"
    READY_WITH_NOTE = "ready_with_note"
    MISSING_DATA = "missing_data"


class ComparisonBasis(StrEnum):
    """What a report period is compared with."""

    PREVIOUS_PERIOD = "previous_period"
    SAME_PERIOD_LAST_YEAR = "same_period_last_year"
    CUSTOM_BASELINE = "custom_baseline"


class ComparedAs(StrEnum):
    """Whether a count was compared as a total, or as a monthly average because the lengths differ.

    Rates and positions are never averaged this way.
    """

    TOTAL = "total"
    MONTHLY_AVERAGE = "monthly_average"


class HeadlineKey(StrEnum):
    PROFILE_VIEWS = "profile_views"
    PROFILE_ACTIONS = "profile_actions"
    WEBSITE_SEARCH_CLICKS = "website_search_clicks"
    ORGANIC_SESSIONS = "organic_sessions"
    NEW_REVIEWS = "new_reviews"
    AVERAGE_RATING = "average_rating"


class SeriesKey(StrEnum):
    """A figure drawn month by month."""

    PROFILE_VIEWS = "profile_views"
    PROFILE_ACTIONS = "profile_actions"
    CALLS = "calls"
    WEBSITE_CLICKS = "website_clicks"
    DIRECTION_REQUESTS = "direction_requests"
    SEARCH_CLICKS = "search_clicks"
    SEARCH_IMPRESSIONS = "search_impressions"
    ORGANIC_SESSIONS = "organic_sessions"
    NEW_REVIEWS = "new_reviews"


class SectionKey(StrEnum):
    PROFILE_VIEWS = "profile_views"
    PROFILE_ACTIONS = "profile_actions"
    DAILY_SERIES = "daily_series"
    SEARCH_TERMS = "search_terms"
    LOCATIONS = "locations"
    REVIEWS = "reviews"
    SEARCH_CONSOLE = "search_console"
    ANALYTICS = "analytics"
    LOCAL_RANK = "local_rank"
    WORK_COMPLETED = "work_completed"
    NARRATIVE = "narrative"


class Availability(StrEnum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class UnavailableReason(StrEnum):
    NOT_CONNECTED = "not_connected"
    NOT_SYNCED = "not_synced"
    NO_DATA = "no_data"
    # The profile does not report this metric (conversations, bookings, food orders, menu clicks).
    NOT_REPORTED = "not_reported"
    PARTIAL_PERIOD = "partial_period"
    NO_VIEWS = "no_views"
    NOT_TRACKED = "not_tracked"
    NOT_COMPARED = "not_compared"
    SOURCE_UNAVAILABLE = "source_unavailable"


class NoteCode(StrEnum):
    """Why part of a report is missing or approximate. The console turns each into a sentence."""

    GBP_NOT_CONNECTED = "gbp_not_connected"
    GBP_PERIOD_NOT_SYNCED = "gbp_period_not_synced"
    GBP_PERIOD_PARTIAL = "gbp_period_partial"
    GBP_SYNC_FAILED = "gbp_sync_failed"
    GBP_LOCATION_NOT_MAPPED = "gbp_location_not_mapped"
    GBP_SEARCH_TERMS_UNAVAILABLE = "gbp_search_terms_unavailable"
    GBP_COMPARED_PERIOD_INCOMPLETE = "gbp_compared_period_incomplete"
    GBP_YEAR_AGO_UNAVAILABLE = "gbp_year_ago_unavailable"
    REVIEWS_NOT_SYNCED = "reviews_not_synced"
    SEARCH_CONSOLE_NOT_CONNECTED = "search_console_not_connected"
    SEARCH_CONSOLE_NOT_SYNCED = "search_console_not_synced"
    SEARCH_CONSOLE_LAG_DAYS = "search_console_lag_days"
    SEARCH_CONSOLE_MONTHS_MISSING = "search_console_months_missing"
    SEARCH_CONSOLE_COMPARED_PERIOD_UNAVAILABLE = "search_console_compared_period_unavailable"
    ANALYTICS_NOT_CONNECTED = "analytics_not_connected"
    ANALYTICS_NOT_SYNCED = "analytics_not_synced"
    ANALYTICS_ORGANIC_UNAVAILABLE = "analytics_organic_unavailable"
    ANALYTICS_MONTHS_MISSING = "analytics_months_missing"
    ANALYTICS_COMPARED_PERIOD_UNAVAILABLE = "analytics_compared_period_unavailable"
    # Google reported no <figure> this period but did in the comparison period.
    OPTIONAL_FIGURE_NOT_REPORTED = "optional_figure_not_reported"


class NoteEffect(StrEnum):
    """What a note does to readiness: stop the report, flag it, or only inform."""

    BLOCKING = "blocking"
    DEGRADING = "degrading"
    INFORMATIONAL = "informational"


NOTE_EFFECT: dict[NoteCode, NoteEffect] = {
    NoteCode.GBP_NOT_CONNECTED: NoteEffect.BLOCKING,
    NoteCode.GBP_PERIOD_NOT_SYNCED: NoteEffect.BLOCKING,
    NoteCode.GBP_PERIOD_PARTIAL: NoteEffect.DEGRADING,
    NoteCode.GBP_SYNC_FAILED: NoteEffect.DEGRADING,
    NoteCode.GBP_LOCATION_NOT_MAPPED: NoteEffect.DEGRADING,
    NoteCode.GBP_SEARCH_TERMS_UNAVAILABLE: NoteEffect.DEGRADING,
    NoteCode.GBP_COMPARED_PERIOD_INCOMPLETE: NoteEffect.INFORMATIONAL,
    NoteCode.GBP_YEAR_AGO_UNAVAILABLE: NoteEffect.INFORMATIONAL,
    NoteCode.REVIEWS_NOT_SYNCED: NoteEffect.DEGRADING,
    NoteCode.SEARCH_CONSOLE_NOT_CONNECTED: NoteEffect.DEGRADING,
    NoteCode.SEARCH_CONSOLE_NOT_SYNCED: NoteEffect.DEGRADING,
    NoteCode.SEARCH_CONSOLE_LAG_DAYS: NoteEffect.DEGRADING,
    NoteCode.SEARCH_CONSOLE_MONTHS_MISSING: NoteEffect.DEGRADING,
    NoteCode.SEARCH_CONSOLE_COMPARED_PERIOD_UNAVAILABLE: NoteEffect.INFORMATIONAL,
    NoteCode.ANALYTICS_NOT_CONNECTED: NoteEffect.DEGRADING,
    NoteCode.ANALYTICS_NOT_SYNCED: NoteEffect.DEGRADING,
    NoteCode.ANALYTICS_ORGANIC_UNAVAILABLE: NoteEffect.DEGRADING,
    NoteCode.ANALYTICS_MONTHS_MISSING: NoteEffect.DEGRADING,
    NoteCode.ANALYTICS_COMPARED_PERIOD_UNAVAILABLE: NoteEffect.INFORMATIONAL,
    NoteCode.OPTIONAL_FIGURE_NOT_REPORTED: NoteEffect.INFORMATIONAL,
}


NOTE_SECTION: dict[NoteCode, SectionKey] = {
    NoteCode.GBP_NOT_CONNECTED: SectionKey.PROFILE_VIEWS,
    NoteCode.GBP_PERIOD_NOT_SYNCED: SectionKey.PROFILE_VIEWS,
    NoteCode.GBP_PERIOD_PARTIAL: SectionKey.PROFILE_VIEWS,
    NoteCode.GBP_SYNC_FAILED: SectionKey.PROFILE_VIEWS,
    NoteCode.GBP_LOCATION_NOT_MAPPED: SectionKey.LOCATIONS,
    NoteCode.GBP_SEARCH_TERMS_UNAVAILABLE: SectionKey.SEARCH_TERMS,
    NoteCode.GBP_COMPARED_PERIOD_INCOMPLETE: SectionKey.PROFILE_VIEWS,
    NoteCode.GBP_YEAR_AGO_UNAVAILABLE: SectionKey.PROFILE_VIEWS,
    NoteCode.REVIEWS_NOT_SYNCED: SectionKey.REVIEWS,
    NoteCode.SEARCH_CONSOLE_NOT_CONNECTED: SectionKey.SEARCH_CONSOLE,
    NoteCode.SEARCH_CONSOLE_NOT_SYNCED: SectionKey.SEARCH_CONSOLE,
    NoteCode.SEARCH_CONSOLE_LAG_DAYS: SectionKey.SEARCH_CONSOLE,
    NoteCode.SEARCH_CONSOLE_MONTHS_MISSING: SectionKey.SEARCH_CONSOLE,
    NoteCode.SEARCH_CONSOLE_COMPARED_PERIOD_UNAVAILABLE: SectionKey.SEARCH_CONSOLE,
    NoteCode.ANALYTICS_NOT_CONNECTED: SectionKey.ANALYTICS,
    NoteCode.ANALYTICS_NOT_SYNCED: SectionKey.ANALYTICS,
    NoteCode.ANALYTICS_ORGANIC_UNAVAILABLE: SectionKey.ANALYTICS,
    NoteCode.ANALYTICS_MONTHS_MISSING: SectionKey.ANALYTICS,
    NoteCode.ANALYTICS_COMPARED_PERIOD_UNAVAILABLE: SectionKey.ANALYTICS,
    NoteCode.OPTIONAL_FIGURE_NOT_REPORTED: SectionKey.PROFILE_ACTIONS,
}


class SplitKey(StrEnum):
    MAPS = "maps"
    SEARCH = "search"
    DESKTOP = "desktop"
    MOBILE = "mobile"


class WorkKind(StrEnum):
    GBP_POST = "gbp_post"
    WEBSITE_CONTENT = "website_content"
    REVIEW_RESPONSE = "review_response"
    GBP_PROFILE_CHANGE = "gbp_profile_change"
    WEBSITE_CHANGE = "website_change"


class NarrativeOrigin(StrEnum):
    NONE = "none"
    HERMES = "hermes"
    MANUAL = "manual"


class NarrativeFailureCode(StrEnum):
    """Why a narrative draft was not kept. The previous narrative is left exactly as it was."""

    DRAFT_FAILED = "draft_failed"
    DRAFT_MALFORMED = "draft_malformed"
    DRAFT_EMPTY = "draft_empty"
    NUMBER_NOT_IN_DATA = "number_not_in_data"
    AUTHORSHIP_MENTIONED = "authorship_mentioned"
    CAUSAL_CLAIM = "causal_claim"


class NarrativeOutcome(StrEnum):
    DRAFTED = "drafted"
    # The draft failed a check or the provider failed; the narrative is exactly as it was.
    NOT_USED = "not_used"


class UpcomingKind(StrEnum):
    GENERATE_MONTHLY_REPORT = "generate_monthly_report"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- Periods and comparisons -----------------------------------------------------------------


class ReportPeriod(Model):
    """1 to 12 consecutive whole calendar months, each given as its first day."""

    start_month: date
    end_month: date

    @model_validator(mode="after")
    def _whole_months_in_order(self) -> ReportPeriod:
        if self.start_month != first_of_month(self.start_month) or self.end_month != first_of_month(
            self.end_month
        ):
            raise ReportMonthNotFirstError
        if self.end_month < self.start_month:
            raise ReportPeriodOrderError
        if len(month_range(self.start_month, self.end_month)) > MAX_PERIOD_MONTHS:
            raise ReportPeriodTooLongError
        return self

    @property
    def months(self) -> list[date]:
        return month_range(self.start_month, self.end_month)

    @property
    def span(self) -> int:
        return len(self.months)

    @property
    def slug(self) -> str:
        """How the period appears in an address: ``2026-09`` or ``2026-05_2026-09``."""
        start = self.start_month.isoformat()[:7]
        end = self.end_month.isoformat()[:7]
        return start if start == end else f"{start}_{end}"

    @classmethod
    def from_slug(cls, slug: str) -> ReportPeriod:
        first, separator, last = slug.partition("_")
        if separator and not last:
            raise ReportPeriodInvalidError
        try:
            start = date.fromisoformat(f"{first}-01")
            end = date.fromisoformat(f"{last}-01") if last else start
        except ValueError:
            raise ReportPeriodInvalidError from None
        if len(first) != 7 or (last and len(last) != 7):
            raise ReportPeriodInvalidError
        return cls(start_month=start, end_month=end)


class ComparisonSpec(Model):
    """What the period is compared with; a baseline names its own months."""

    basis: ComparisonBasis = ComparisonBasis.PREVIOUS_PERIOD
    baseline_start: date | None = None
    baseline_end: date | None = None

    @model_validator(mode="after")
    def _baseline_only_for_a_baseline(self) -> ComparisonSpec:
        given = (self.baseline_start is not None, self.baseline_end is not None)
        if self.basis is ComparisonBasis.CUSTOM_BASELINE:
            if not all(given):
                raise ReportBaselineRequiredError
            _ = self.baseline  # validates whole months, order and length
        elif any(given):
            raise ReportBaselineUnexpectedError
        return self

    @property
    def baseline(self) -> ReportPeriod:
        if self.baseline_start is None or self.baseline_end is None:
            raise ReportBaselineRequiredError
        return ReportPeriod(start_month=self.baseline_start, end_month=self.baseline_end)

    @property
    def key(self) -> str:
        """The stored form: ``previous``, ``year_ago`` or ``baseline:YYYY-MM:YYYY-MM``."""
        if self.basis is ComparisonBasis.PREVIOUS_PERIOD:
            return "previous"
        if self.basis is ComparisonBasis.SAME_PERIOD_LAST_YEAR:
            return "year_ago"
        baseline = self.baseline
        return (
            f"baseline:{baseline.start_month.isoformat()[:7]}:{baseline.end_month.isoformat()[:7]}"
        )

    @property
    def slug(self) -> str:
        """The address form: ``previous``, ``year-ago`` or ``vs-YYYY-MM[_YYYY-MM]``."""
        if self.basis is ComparisonBasis.PREVIOUS_PERIOD:
            return "previous"
        if self.basis is ComparisonBasis.SAME_PERIOD_LAST_YEAR:
            return "year-ago"
        return f"vs-{self.baseline.slug}"

    @classmethod
    def from_key(cls, key: str) -> ComparisonSpec:
        if key == "previous":
            return cls()
        if key == "year_ago":
            return cls(basis=ComparisonBasis.SAME_PERIOD_LAST_YEAR)
        parts = key.split(":")
        if len(parts) != 3 or parts[0] != "baseline":
            raise ReportComparisonInvalidError
        return cls.from_slug(f"vs-{parts[1]}_{parts[2]}")

    @classmethod
    def from_slug(cls, slug: str) -> ComparisonSpec:
        if slug == "previous":
            return cls()
        if slug == "year-ago":
            return cls(basis=ComparisonBasis.SAME_PERIOD_LAST_YEAR)
        if not slug.startswith("vs-"):
            raise ReportComparisonInvalidError
        baseline = ReportPeriod.from_slug(slug[3:])
        return cls(
            basis=ComparisonBasis.CUSTOM_BASELINE,
            baseline_start=baseline.start_month,
            baseline_end=baseline.end_month,
        )

    def resolve(self, period: ReportPeriod) -> ReportComparison:
        """The months compared, the same months a year earlier, and how counts are compared."""
        span = period.span
        year_ago = ReportPeriod(
            start_month=months_before(period.start_month, 12),
            end_month=months_before(period.end_month, 12),
        )
        if self.basis is ComparisonBasis.SAME_PERIOD_LAST_YEAR:
            compared = year_ago
        elif self.basis is ComparisonBasis.PREVIOUS_PERIOD:
            compared = ReportPeriod(
                start_month=months_before(period.start_month, span),
                end_month=months_before(period.start_month, 1),
            )
        else:
            compared = self.baseline
            if compared.end_month >= period.start_month:
                raise ReportBaselineOverlapsError
        return ReportComparison(
            basis=self.basis,
            compared=compared,
            year_ago=None if self.basis is ComparisonBasis.SAME_PERIOD_LAST_YEAR else year_ago,
            compared_as=ComparedAs.TOTAL if compared.span == span else ComparedAs.MONTHLY_AVERAGE,
        )


class ReportComparison(Model):
    """A comparison once resolved against a period; stored in the snapshot."""

    basis: ComparisonBasis
    compared: ReportPeriod
    # The same months a year earlier; absent when that is already what the period is compared with.
    year_ago: ReportPeriod | None
    compared_as: ComparedAs


# ---- Figures: a number, or the typed reason there is none ----------------------------------


class ReportCountFigure(Model):
    availability: Availability
    value: int | None = None
    reason: UnavailableReason | None = None
    days_covered: int | None = None
    days_expected: int | None = None
    # For figures stored per month: how many of the period's months were synced.
    months_covered: int | None = None
    months_expected: int | None = None

    @model_validator(mode="after")
    def _missing_is_never_a_number(self) -> ReportCountFigure:
        if (self.availability is Availability.UNAVAILABLE) != (self.value is None):
            raise ValueError("a figure has a value exactly when it is available or partial")
        if self.availability is Availability.UNAVAILABLE and self.reason is None:
            raise ValueError("an unavailable figure names its reason")
        return self


class ReportRateFigure(Model):
    availability: Availability
    value: float | None = None
    reason: UnavailableReason | None = None

    @model_validator(mode="after")
    def _missing_is_never_a_number(self) -> ReportRateFigure:
        if (self.availability is Availability.UNAVAILABLE) != (self.value is None):
            raise ValueError("a figure has a value exactly when it is available or partial")
        if self.availability is Availability.UNAVAILABLE and self.reason is None:
            raise ValueError("an unavailable figure names its reason")
        return self


class ReportCountComparison(Model):
    current: ReportCountFigure
    compared: ReportCountFigure
    # TOTAL: both are totals. MONTHLY_AVERAGE: ``compared`` is the baseline's monthly average and
    # the change is against ``current_monthly_average``.
    compared_as: ComparedAs = ComparedAs.TOTAL
    current_monthly_average: int | None = None
    year_ago: ReportCountFigure | None = None
    change: int | None = None
    change_percent: float | None = None
    year_change: int | None = None
    year_change_percent: float | None = None


class ReportRateComparison(Model):
    current: ReportRateFigure
    compared: ReportRateFigure
    year_ago: ReportRateFigure | None = None
    # Percentage points (or positions) between current and compared.
    change: float | None = None
    year_change: float | None = None


class ReportRange(Model):
    start: date
    end: date
    days: int


# ---- Business Profile -----------------------------------------------------------------------


class ReportSourceRow(Model):
    metric: GBPPerformanceMetric
    comparison: ReportCountComparison


class ReportActionRow(Model):
    metric: GBPPerformanceMetric
    comparison: ReportCountComparison
    # False when the profile does not report the metric at all, so the tile is not drawn.
    reported: bool
    # False when the change would be misleading, e.g. Google reported none this period but some
    # before: that can be a change in how Google reports it, not lower demand.
    comparable: bool = True
    note: NoteCode | None = None


class ReportSplitPart(Model):
    key: SplitKey
    figure: ReportCountFigure
    share_percent: float | None = None


class ReportSplit(Model):
    parts: list[ReportSplitPart]


class ReportProfileViews(Model):
    total: ReportCountComparison
    sources: list[ReportSourceRow]
    maps_search: ReportSplit
    desktop_mobile: ReportSplit


class ReportProfileActions(Model):
    total: ReportCountComparison
    action_rate: ReportRateComparison
    actions: list[ReportActionRow]
    optional: list[ReportActionRow]


class ReportDailyPoint(Model):
    day: date
    views: int | None
    actions: int | None


class ReportDailySeries(Model):
    availability: Availability
    days_expected: int
    days_synced: int
    missing_days: list[date]
    points: list[ReportDailyPoint]


class ReportSearchTerm(Model):
    keyword: str
    # The exact count Google gave; null when Google only said "fewer than N".
    value: int | None
    below_threshold: int | None
    is_exact: bool


class ReportSearchTerms(Model):
    availability: Availability
    reason: UnavailableReason | None = None
    # The most searched terms; ``total_terms`` is how many distinct terms there were in all.
    terms: list[ReportSearchTerm]
    total_terms: int = 0
    # Terms are stored per month: how many of the period's months have any.
    months_covered: int | None = None
    months_expected: int | None = None


class ReportLocationRow(Model):
    location_id: UUID
    name: str
    mapped: bool
    profile_views: ReportCountComparison
    calls: ReportCountComparison
    website_clicks: ReportCountComparison
    direction_requests: ReportCountComparison


class ReportGbpSection(Model):
    availability: Availability
    reason: UnavailableReason | None = None
    current_range: ReportRange
    compared_range: ReportRange
    year_ago_range: ReportRange | None
    through_date: date | None
    profile_views: ReportProfileViews
    actions: ReportProfileActions
    daily: ReportDailySeries
    search_terms: ReportSearchTerms
    # One row per location, only when the client has more than one active location.
    locations: list[ReportLocationRow]


# ---- Reviews ---------------------------------------------------------------------------------


class ReportStarCount(Model):
    stars: Literal[1, 2, 3, 4, 5]
    count: int


class ReportReviewsSection(Model):
    availability: Availability
    reason: UnavailableReason | None = None
    new_reviews: ReportCountComparison
    # The average of the reviews written in the period, against the compared period's.
    average_rating_in_period: ReportRateComparison
    # All reviews up to the end of the period, against all up to the end of the compared period.
    average_rating_overall: ReportRateComparison
    total_count: ReportCountFigure
    responses_published: ReportCountFigure
    responded_to_new: ReportCountFigure
    response_rate_percent: ReportRateComparison
    distribution_overall: list[ReportStarCount]
    distribution_period: list[ReportStarCount]


# ---- Search Console and Analytics ------------------------------------------------------------


class ReportSearchQueryRow(Model):
    query: str
    # True when the search names the organization or one of its locations (see the notes).
    is_branded: bool
    clicks: int
    impressions: int
    ctr: float | None
    position: float | None
    # In the comparison's unit: the compared period's total, or its monthly average.
    compared_clicks: int | None
    clicks_change: int | None


class ReportSearchPageRow(Model):
    page: str
    clicks: int
    impressions: int
    ctr: float | None
    position: float | None
    compared_clicks: int | None
    clicks_change: int | None


class ReportSearchConsoleSection(Model):
    availability: Availability
    reason: UnavailableReason | None = None
    clicks: ReportCountComparison
    impressions: ReportCountComparison
    ctr_percent: ReportRateComparison
    average_position: ReportRateComparison
    # Top searches and pages are summed from each month's stored top rows: never totals.
    top_queries: list[ReportSearchQueryRow]
    top_pages: list[ReportSearchPageRow]
    # Share of the clicks of the top searches that are branded.
    branded_share_percent: float | None = None
    lag_days: int | None = None


class ReportAnalyticsSection(Model):
    availability: Availability
    reason: UnavailableReason | None = None
    organic_sessions: ReportCountComparison


# ---- Headlines and monthly series ------------------------------------------------------------


class ReportHeadline(Model):
    """One of the figures the report leads with. Exactly one of count or rate is set."""

    key: HeadlineKey
    count: ReportCountComparison | None = None
    rate: ReportRateComparison | None = None


class ReportMonthPoint(Model):
    month: date
    availability: Availability
    value: int | None = None

    @model_validator(mode="after")
    def _missing_is_never_a_number(self) -> ReportMonthPoint:
        if (self.availability is Availability.UNAVAILABLE) != (self.value is None):
            raise ValueError("a month has a value exactly when it is available or partial")
        return self


class ReportMonthlySeries(Model):
    key: SeriesKey
    period: list[ReportMonthPoint]
    compared: list[ReportMonthPoint]


# ---- Work completed --------------------------------------------------------------------------


class ReportWorkGroup(Model):
    kind: WorkKind
    count: int
    titles: list[str]


class ReportWorkSection(Model):
    groups: list[ReportWorkGroup]


def note(
    code: NoteCode,
    *,
    count: int | None = None,
    location_id: UUID | None = None,
    metric: GBPPerformanceMetric | None = None,
) -> ReportDataNote:
    """A data note for ``code``, placed in the section the code belongs to."""
    return ReportDataNote(
        code=code,
        section=NOTE_SECTION[code],
        count=count,
        location_id=location_id,
        metric=metric,
    )


# ---- The snapshot and its narrative ----------------------------------------------------------


class ReportDataNote(Model):
    code: NoteCode
    # The part of the report the note is about, so a screen can place it without reading the code.
    section: SectionKey
    # How many days, months or items the note is about, when it is about a count.
    count: int | None = None
    location_id: UUID | None = None
    # The figure a note is about (optional Business Profile figures).
    metric: GBPPerformanceMetric | None = None

    @model_validator(mode="before")
    @classmethod
    def _section_of_the_code(cls, data: object) -> object:
        if isinstance(data, dict) and "section" not in data and "code" in data:
            return {**data, "section": NOTE_SECTION[NoteCode(data["code"])]}
        return data


class ReportSync(Model):
    """When each source was last synced, as a day. Informational: not part of the data hash."""

    gbp: date | None = None
    search_console: date | None = None
    analytics: date | None = None


class ReportSnapshot(Model):
    """Everything computed for one organization and one period. Deterministic and typed."""

    schema_version: int = SNAPSHOT_SCHEMA_VERSION
    period: ReportPeriod
    comparison: ReportComparison
    # The reportable locations the report covers.
    location_names: list[str]
    sync: ReportSync = ReportSync()
    readiness: ReportReadiness
    notes: list[ReportDataNote]
    headlines: list[ReportHeadline]
    monthly: list[ReportMonthlySeries]
    gbp: ReportGbpSection
    reviews: ReportReviewsSection
    search_console: ReportSearchConsoleSection
    analytics: ReportAnalyticsSection
    local_rank: TrackedCount
    work: ReportWorkSection


class ReportNarrative(Model):
    """The two prose sections. Written by a person, or drafted and then reviewed by one."""

    what_changed: str = ""
    next_work: str = ""
    origin: NarrativeOrigin = NarrativeOrigin.NONE

    @property
    def is_empty(self) -> bool:
        return not (self.what_changed.strip() and self.next_work.strip())


# ---- API views -------------------------------------------------------------------------------


class ReportDeliveryView(Model):
    sent_on: date
    recorded_at: datetime


class ReportRevisionRow(Model):
    period: ReportPeriod
    comparison: ComparisonSpec
    revision: int
    status: ReportStatus
    readiness: ReportReadiness
    is_current: bool
    created_at: datetime
    approved_at: datetime | None
    delivery: ReportDeliveryView | None


class ReportUpcoming(Model):
    kind: UpcomingKind
    next_run_at: datetime
    # The month that run will report on.
    month: date


class ReportPermissions(Model):
    can_generate: bool
    can_publish: bool


class ReportListView(Model):
    organization_id: UUID
    # The month the client's current report covers: the last month that has ended.
    current_month: date
    current: ReportRevisionRow | None
    history: list[ReportRevisionRow]
    upcoming: ReportUpcoming | None
    permissions: ReportPermissions


class ReportDetailView(Model):
    organization_id: UUID
    client_name: str
    client_slug: str
    period: ReportPeriod
    comparison: ComparisonSpec
    revision: int
    revision_count: int
    status: ReportStatus
    readiness: ReportReadiness
    is_current: bool
    created_at: datetime
    approved_at: datetime | None
    delivery: ReportDeliveryView | None
    snapshot: ReportSnapshot
    narrative: ReportNarrative
    permissions: ReportPermissions


class ReportGenerateRequest(Model):
    start_month: date
    end_month: date
    comparison: ComparisonSpec = ComparisonSpec()

    @property
    def period(self) -> ReportPeriod:
        return ReportPeriod(start_month=self.start_month, end_month=self.end_month)


class ReportNarrativeUpdate(Model):
    what_changed: str = Field(max_length=4000)
    next_work: str = Field(max_length=4000)


class ReportMarkSentRequest(Model):
    sent_on: date


class ReportGenerateResult(Model):
    report: ReportDetailView
    # False when the data had not changed and the existing revision was returned.
    created: bool


class ReportNarrativeDraftResult(Model):
    report: ReportDetailView
    outcome: NarrativeOutcome
    failure: NarrativeFailureCode | None = None


class PortfolioReportRow(Model):
    organization_id: UUID
    slug: str
    name: str
    month: date
    revision: int | None
    # Null when no report has been generated for the month yet.
    status: ReportStatus | None
    readiness: ReportReadiness | None
    sent_on: date | None


class PortfolioReportCounts(Model):
    ready: int
    needs_attention: int
    missing_data: int
    sent: int
    not_generated: int


class PortfolioReportsView(Model):
    month: date
    counts: PortfolioReportCounts
    clients: list[PortfolioReportRow]
