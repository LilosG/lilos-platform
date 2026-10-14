"""Typed contracts of the monthly client report.

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

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from apps.api.app.products.gbp.performance_enums import GBPPerformanceMetric
from apps.api.app.routes.command_center_search import TrackedCount

SNAPSHOT_SCHEMA_VERSION = 1
DEFINITION_KEY = "monthly-performance"


class ReportStatus(StrEnum):
    """Where a report is in its life: written, approved by a person, or recorded as sent."""

    DRAFT = "draft"
    READY = "ready"
    SENT = "sent"


class ReportReadiness(StrEnum):
    READY = "ready"
    READY_WITH_NOTE = "ready_with_note"
    MISSING_DATA = "missing_data"


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
    GBP_MONTH_NOT_SYNCED = "gbp_month_not_synced"
    GBP_MONTH_PARTIAL = "gbp_month_partial"
    GBP_SYNC_FAILED = "gbp_sync_failed"
    GBP_LOCATION_NOT_MAPPED = "gbp_location_not_mapped"
    GBP_SEARCH_TERMS_UNAVAILABLE = "gbp_search_terms_unavailable"
    GBP_PREVIOUS_MONTH_INCOMPLETE = "gbp_previous_month_incomplete"
    GBP_YEAR_AGO_UNAVAILABLE = "gbp_year_ago_unavailable"
    REVIEWS_NOT_SYNCED = "reviews_not_synced"
    SEARCH_CONSOLE_NOT_CONNECTED = "search_console_not_connected"
    SEARCH_CONSOLE_NOT_SYNCED = "search_console_not_synced"
    SEARCH_CONSOLE_LAG_DAYS = "search_console_lag_days"
    SEARCH_CONSOLE_PREVIOUS_MONTH_UNAVAILABLE = "search_console_previous_month_unavailable"
    ANALYTICS_NOT_CONNECTED = "analytics_not_connected"
    ANALYTICS_NOT_SYNCED = "analytics_not_synced"
    ANALYTICS_ORGANIC_UNAVAILABLE = "analytics_organic_unavailable"
    ANALYTICS_PREVIOUS_MONTH_UNAVAILABLE = "analytics_previous_month_unavailable"


class NoteEffect(StrEnum):
    """What a note does to readiness: stop the report, flag it, or only inform."""

    BLOCKING = "blocking"
    DEGRADING = "degrading"
    INFORMATIONAL = "informational"


NOTE_EFFECT: dict[NoteCode, NoteEffect] = {
    NoteCode.GBP_NOT_CONNECTED: NoteEffect.BLOCKING,
    NoteCode.GBP_MONTH_NOT_SYNCED: NoteEffect.BLOCKING,
    NoteCode.GBP_MONTH_PARTIAL: NoteEffect.DEGRADING,
    NoteCode.GBP_SYNC_FAILED: NoteEffect.DEGRADING,
    NoteCode.GBP_LOCATION_NOT_MAPPED: NoteEffect.DEGRADING,
    NoteCode.GBP_SEARCH_TERMS_UNAVAILABLE: NoteEffect.DEGRADING,
    NoteCode.GBP_PREVIOUS_MONTH_INCOMPLETE: NoteEffect.INFORMATIONAL,
    NoteCode.GBP_YEAR_AGO_UNAVAILABLE: NoteEffect.INFORMATIONAL,
    NoteCode.REVIEWS_NOT_SYNCED: NoteEffect.DEGRADING,
    NoteCode.SEARCH_CONSOLE_NOT_CONNECTED: NoteEffect.DEGRADING,
    NoteCode.SEARCH_CONSOLE_NOT_SYNCED: NoteEffect.DEGRADING,
    NoteCode.SEARCH_CONSOLE_LAG_DAYS: NoteEffect.DEGRADING,
    NoteCode.SEARCH_CONSOLE_PREVIOUS_MONTH_UNAVAILABLE: NoteEffect.INFORMATIONAL,
    NoteCode.ANALYTICS_NOT_CONNECTED: NoteEffect.DEGRADING,
    NoteCode.ANALYTICS_NOT_SYNCED: NoteEffect.DEGRADING,
    NoteCode.ANALYTICS_ORGANIC_UNAVAILABLE: NoteEffect.DEGRADING,
    NoteCode.ANALYTICS_PREVIOUS_MONTH_UNAVAILABLE: NoteEffect.INFORMATIONAL,
}


NOTE_SECTION: dict[NoteCode, SectionKey] = {
    NoteCode.GBP_NOT_CONNECTED: SectionKey.PROFILE_VIEWS,
    NoteCode.GBP_MONTH_NOT_SYNCED: SectionKey.PROFILE_VIEWS,
    NoteCode.GBP_MONTH_PARTIAL: SectionKey.PROFILE_VIEWS,
    NoteCode.GBP_SYNC_FAILED: SectionKey.PROFILE_VIEWS,
    NoteCode.GBP_LOCATION_NOT_MAPPED: SectionKey.LOCATIONS,
    NoteCode.GBP_SEARCH_TERMS_UNAVAILABLE: SectionKey.SEARCH_TERMS,
    NoteCode.GBP_PREVIOUS_MONTH_INCOMPLETE: SectionKey.PROFILE_VIEWS,
    NoteCode.GBP_YEAR_AGO_UNAVAILABLE: SectionKey.PROFILE_VIEWS,
    NoteCode.REVIEWS_NOT_SYNCED: SectionKey.REVIEWS,
    NoteCode.SEARCH_CONSOLE_NOT_CONNECTED: SectionKey.SEARCH_CONSOLE,
    NoteCode.SEARCH_CONSOLE_NOT_SYNCED: SectionKey.SEARCH_CONSOLE,
    NoteCode.SEARCH_CONSOLE_LAG_DAYS: SectionKey.SEARCH_CONSOLE,
    NoteCode.SEARCH_CONSOLE_PREVIOUS_MONTH_UNAVAILABLE: SectionKey.SEARCH_CONSOLE,
    NoteCode.ANALYTICS_NOT_CONNECTED: SectionKey.ANALYTICS,
    NoteCode.ANALYTICS_NOT_SYNCED: SectionKey.ANALYTICS,
    NoteCode.ANALYTICS_ORGANIC_UNAVAILABLE: SectionKey.ANALYTICS,
    NoteCode.ANALYTICS_PREVIOUS_MONTH_UNAVAILABLE: SectionKey.ANALYTICS,
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


# ---- Figures: a number, or the typed reason there is none ----------------------------------


class ReportCountFigure(Model):
    availability: Availability
    value: int | None = None
    reason: UnavailableReason | None = None
    days_covered: int | None = None
    days_expected: int | None = None

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
    previous: ReportCountFigure
    year_ago: ReportCountFigure | None = None
    change: int | None = None
    change_percent: float | None = None
    year_change: int | None = None
    year_change_percent: float | None = None


class ReportRateComparison(Model):
    current: ReportRateFigure
    previous: ReportRateFigure
    year_ago: ReportRateFigure | None = None
    # Percentage points (or positions) between current and previous.
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
    terms: list[ReportSearchTerm]


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
    previous_range: ReportRange
    year_ago_range: ReportRange
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
    new_in_month: ReportCountFigure
    average_rating_in_month: ReportRateFigure
    average_rating_overall: ReportRateFigure
    total_count: ReportCountFigure
    responses_published: ReportCountFigure
    responded_to_new: ReportCountFigure
    response_rate_percent: ReportRateFigure
    distribution_overall: list[ReportStarCount]
    distribution_month: list[ReportStarCount]


# ---- Search Console and Analytics ------------------------------------------------------------


class ReportSearchQueryRow(Model):
    query: str
    clicks: int
    impressions: int
    ctr: float | None
    position: float | None
    previous_clicks: int | None
    clicks_change: int | None


class ReportSearchPageRow(Model):
    page: str
    clicks: int
    impressions: int
    ctr: float | None
    position: float | None
    previous_clicks: int | None
    clicks_change: int | None


class ReportSearchConsoleSection(Model):
    availability: Availability
    reason: UnavailableReason | None = None
    clicks: ReportCountComparison
    impressions: ReportCountComparison
    ctr_percent: ReportRateComparison
    average_position: ReportRateComparison
    top_queries: list[ReportSearchQueryRow]
    top_pages: list[ReportSearchPageRow]
    lag_days: int | None = None


class ReportAnalyticsSection(Model):
    availability: Availability
    reason: UnavailableReason | None = None
    organic_sessions: ReportCountComparison


# ---- Work completed --------------------------------------------------------------------------


class ReportWorkGroup(Model):
    kind: WorkKind
    count: int
    titles: list[str]


class ReportWorkSection(Model):
    groups: list[ReportWorkGroup]


def note(
    code: NoteCode, *, count: int | None = None, location_id: UUID | None = None
) -> ReportDataNote:
    """A data note for ``code``, placed in the section the code belongs to."""
    return ReportDataNote(
        code=code, section=NOTE_SECTION[code], count=count, location_id=location_id
    )


# ---- The snapshot and its narrative ----------------------------------------------------------


class ReportDataNote(Model):
    code: NoteCode
    # The part of the report the note is about, so a screen can place it without reading the code.
    section: SectionKey
    # How many days or items the note is about, when it is about a count.
    count: int | None = None
    location_id: UUID | None = None

    @model_validator(mode="before")
    @classmethod
    def _section_of_the_code(cls, data: object) -> object:
        if isinstance(data, dict) and "section" not in data and "code" in data:
            return {**data, "section": NOTE_SECTION[NoteCode(data["code"])]}
        return data


class ReportSnapshot(Model):
    """Everything computed for one organization and one month. Deterministic and typed."""

    schema_version: int = SNAPSHOT_SCHEMA_VERSION
    month: date
    readiness: ReportReadiness
    notes: list[ReportDataNote]
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
    month: date
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
    month: date
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
    month: date

    @field_validator("month")
    @classmethod
    def _first_of_month(cls, value: date) -> date:
        if value.day != 1:
            raise ValueError("a report month is given as its first day")
        return value


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
