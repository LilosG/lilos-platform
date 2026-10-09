"""Automations: scheduled workflows, their latest run, and the one rule for "needs attention".

An automation is a ``workflow_schedules`` row joined to its workflow definition and the latest
``workflow_runs`` row of the same organization, workflow and location. Everything the
Automations screen and the dashboard's automations health show is derived here, so the two can
never disagree about what needs attention.

The rule, exactly:

* Only the LATEST run decides. A failure that a later run recovered from is history, not
  attention.
* A paused (or cancelled) schedule is Paused, whatever its last run did.
* A schedule that has never run is Not run yet.
* A run that is queued or running is Running; it replaces the previous outcome until it ends.
* A failure whose cause fixes itself (rate limits, provider outages, a reply Google has not
  shown yet) is "will retry", never attention.
* Only workflow run status counts. Job dead-letters (for example the review verification
  retries of ``reviews.publish_response``) are not automation failures.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Final
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.models import (
    Schedule,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES, is_tenant_workflow_key
from apps.api.app.locations.enums import LocationStatus
from apps.api.app.locations.models import Location


class AutomationStatus(StrEnum):
    HEALTHY = "healthy"
    NEEDS_ATTENTION = "needs_attention"
    RUNNING = "running"
    PAUSED = "paused"
    NOT_RUN_YET = "not_run_yet"


class RunStatus(StrEnum):
    """Every ``workflow_runs.status`` value."""

    CREATED = "created"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"
    WAITING_APPROVAL = "waiting_approval"
    RETRY_SCHEDULED = "retry_scheduled"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"
    ESCALATED = "escalated"


class RunOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    # The cause fixes itself and the work is tried again; this is not a failure.
    WILL_RETRY = "will_retry"
    NEEDS_DECISION = "needs_decision"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    IN_PROGRESS = "in_progress"


class AutomationSource(StrEnum):
    GOOGLE_BUSINESS_PROFILE = "google_business_profile"
    REVIEWS = "reviews"
    WEBSITE = "website"
    ANALYTICS = "analytics"
    SEARCH_CONSOLE = "search_console"
    LEADS = "leads"
    PLATFORM = "platform"


class FrequencyKind(StrEnum):
    INTERVAL_MINUTES = "interval_minutes"
    HOURLY = "hourly"
    INTERVAL_HOURS = "interval_hours"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class RecoveryAction(StrEnum):
    RECONNECT_GOOGLE_BUSINESS_PROFILE = "reconnect_google_business_profile"
    CHECK_ANALYTICS_CONNECTION = "check_analytics_connection"
    CHECK_SEARCH_CONSOLE_CONNECTION = "check_search_console_connection"
    CONNECT_WEBSITE = "connect_website"
    CHECK_LOCATION_MAPPING = "check_location_mapping"


class AutomationReason(StrEnum):
    """Why the latest run did not finish well: every failure code the scheduled workflows set.

    The member value is the stored ``failure_code``. ``UNMAPPED`` is the designed fallback for
    a code this list does not know; it is never a reason to hide the run.
    """

    # Google access
    GBP_PERFORMANCE_ACCESS_DENIED = "GBP_PERFORMANCE_ACCESS_DENIED"
    INTEGRATION_RECONNECT_REQUIRED = "INTEGRATION_RECONNECT_REQUIRED"
    GBP_SCOPE_REQUIRED = "GBP_SCOPE_REQUIRED"
    GBP_INTEGRATION_NOT_FOUND = "GBP_INTEGRATION_NOT_FOUND"
    NO_CONNECTED_INTEGRATION = "NO_CONNECTED_INTEGRATION"
    TOKEN_REFRESH_FAILED = "TOKEN_REFRESH_FAILED"
    SECRET_RESOLUTION_FAILED = "SECRET_RESOLUTION_FAILED"
    TOKEN_RESOLUTION_FAILED = "TOKEN_RESOLUTION_FAILED"
    # Business Profile location mapping
    GBP_LOCATION_NOT_FOUND = "GBP_LOCATION_NOT_FOUND"
    GBP_LOCATION_AMBIGUOUS = "GBP_LOCATION_AMBIGUOUS"
    GBP_LOCATION_NO_PLATFORM_LINK = "GBP_LOCATION_NO_PLATFORM_LINK"
    LOCATION_ID_INVALID = "LOCATION_ID_INVALID"
    LOCATION_ID_MISSING = "LOCATION_ID_MISSING"
    # Business Profile performance
    GBP_PERFORMANCE_REQUEST_REJECTED = "GBP_PERFORMANCE_REQUEST_REJECTED"
    GBP_PERFORMANCE_RATE_LIMITED = "GBP_PERFORMANCE_RATE_LIMITED"
    GBP_PERFORMANCE_PROVIDER_UNAVAILABLE = "GBP_PERFORMANCE_PROVIDER_UNAVAILABLE"
    GBP_PERFORMANCE_RESPONSE_INVALID = "GBP_PERFORMANCE_RESPONSE_INVALID"
    GBP_PERFORMANCE_KEYWORDS_UNAVAILABLE = "GBP_PERFORMANCE_KEYWORDS_UNAVAILABLE"
    GBP_PERFORMANCE_SYNC_FAILED = "GBP_PERFORMANCE_SYNC_FAILED"
    # Profile sync and reviews ingestion
    GBP_SYNC_FAILED = "GBP_SYNC_FAILED"
    REVIEWS_INGEST_FAILED = "REVIEWS_INGEST_FAILED"
    # Search Console
    SEARCH_CONSOLE_SCOPE_REQUIRED = "SEARCH_CONSOLE_SCOPE_REQUIRED"
    SEARCH_PROPERTY_NOT_FOUND = "SEARCH_PROPERTY_NOT_FOUND"
    SEARCH_PROPERTY_NOT_CONFIGURED = "SEARCH_PROPERTY_NOT_CONFIGURED"
    SEARCH_PROPERTY_ID_INVALID = "SEARCH_PROPERTY_ID_INVALID"
    SEARCH_CONSOLE_SYNC_INCOMPLETE = "SEARCH_CONSOLE_SYNC_INCOMPLETE"
    SEARCH_CONSOLE_SYNC_FAILED = "SEARCH_CONSOLE_SYNC_FAILED"
    # Analytics
    ANALYTICS_SCOPE_REQUIRED = "ANALYTICS_SCOPE_REQUIRED"
    ANALYTICS_PROPERTY_NOT_FOUND = "ANALYTICS_PROPERTY_NOT_FOUND"
    ANALYTICS_NOT_CONFIGURED = "ANALYTICS_NOT_CONFIGURED"
    ANALYTICS_PROPERTY_ID_INVALID = "ANALYTICS_PROPERTY_ID_INVALID"
    ANALYTICS_SYNC_INCOMPLETE = "ANALYTICS_SYNC_INCOMPLETE"
    ANALYTICS_SYNC_FAILED = "ANALYTICS_SYNC_FAILED"
    # Website crawl and analysis
    SEO_ACTIVE_WEBSITE_MISSING = "SEO_ACTIVE_WEBSITE_MISSING"
    SEO_WEBSITE_NOT_FOUND = "SEO_WEBSITE_NOT_FOUND"
    SEO_WEBSITE_NOT_ACTIVE = "SEO_WEBSITE_NOT_ACTIVE"
    SEO_WEBSITE_SCOPE_MISMATCH = "SEO_WEBSITE_SCOPE_MISMATCH"
    SEO_CRAWL_EMPTY = "SEO_CRAWL_EMPTY"
    SEO_ANALYSIS_FAILED = "SEO_ANALYSIS_FAILED"
    SEO_CRAWL_FAILED = "SEO_CRAWL_FAILED"
    SEO_CRAWL_NOT_TERMINAL = "SEO_CRAWL_NOT_TERMINAL"
    SEO_CRAWL_RUN_NOT_FOUND = "SEO_CRAWL_RUN_NOT_FOUND"
    MISSING_CRAWL_RUN_ID = "MISSING_CRAWL_RUN_ID"
    INVALID_CRAWL_RUN_ID = "INVALID_CRAWL_RUN_ID"
    # Scheduled Business Profile posts
    GBP_POST_GROUNDING_REQUIRED = "GBP_POST_GROUNDING_REQUIRED"
    GBP_POST_GENERATION_FAILED = "GBP_POST_GENERATION_FAILED"
    GBP_POST_DELIVERY_BINDING_MISSING = "GBP_POST_DELIVERY_BINDING_MISSING"
    GBP_REVIEW_SOURCE_INVALID = "GBP_REVIEW_SOURCE_INVALID"
    GBP_ORGANIZATION_UNAVAILABLE = "GBP_ORGANIZATION_UNAVAILABLE"
    GBP_POST_REVISION_UNAVAILABLE = "GBP_POST_REVISION_UNAVAILABLE"
    GBP_WEBSITE_TARGET_UNAVAILABLE = "GBP_WEBSITE_TARGET_UNAVAILABLE"
    GBP_WEBSITE_KNOWLEDGE_UNAVAILABLE = "GBP_WEBSITE_KNOWLEDGE_UNAVAILABLE"
    GBP_DRIVE_MEDIA_NOT_CONFIGURED = "GBP_DRIVE_MEDIA_NOT_CONFIGURED"
    GBP_DRIVE_NO_ELIGIBLE_IMAGE = "GBP_DRIVE_NO_ELIGIBLE_IMAGE"
    GBP_DRIVE_MEDIA_UNAVAILABLE = "GBP_DRIVE_MEDIA_UNAVAILABLE"
    GBP_DRIVE_MEDIA_PROXY_UNAVAILABLE = "GBP_DRIVE_MEDIA_PROXY_UNAVAILABLE"
    GBP_DRIVE_UNREACHABLE = "GBP_DRIVE_UNREACHABLE"
    GBP_DRIVE_TEMPORARILY_UNAVAILABLE = "GBP_DRIVE_TEMPORARILY_UNAVAILABLE"
    # Agent runs the platform retries on its own
    HERMES_SCOPED_SESSION_BUSY = "HERMES_SCOPED_SESSION_BUSY"
    # Review reply verification: a job-level retry state of reviews.publish_response. It is
    # mapped so that it can never read as a failed run, wherever it shows up.
    VERIFICATION_CONTENT_PENDING = "VERIFICATION_CONTENT_PENDING"
    VERIFICATION_REREAD_FAILED = "VERIFICATION_REREAD_FAILED"
    # The workflow runtime itself
    WORKFLOW_VERSION_NOT_EXECUTABLE = "WORKFLOW_VERSION_NOT_EXECUTABLE"
    WORKFLOW_HANDLER_NOT_REGISTERED = "WORKFLOW_HANDLER_NOT_REGISTERED"
    WORKFLOW_RUN_MISSING = "WORKFLOW_RUN_MISSING"
    WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"
    HANDLER_EXCEPTION = "HANDLER_EXCEPTION"
    DATABASE_DETERMINISTIC_ERROR = "DATABASE_DETERMINISTIC_ERROR"
    # Status-derived causes, for runs that stopped without a failure code of their own
    RUN_ESCALATED = "RUN_ESCALATED"
    RUN_WAITING_APPROVAL = "RUN_WAITING_APPROVAL"
    RUN_PARTIALLY_COMPLETED = "RUN_PARTIALLY_COMPLETED"
    RUN_EXPIRED = "RUN_EXPIRED"
    # The designed fallback for any code not listed above.
    UNMAPPED = "UNMAPPED"


class Treatment(StrEnum):
    ATTENTION = "attention"
    WILL_RETRY = "will_retry"


@dataclass(frozen=True, slots=True)
class Policy:
    treatment: Treatment
    actions: tuple[RecoveryAction, ...] = ()


_RECONNECT: Final = (RecoveryAction.RECONNECT_GOOGLE_BUSINESS_PROFILE,)
_ANALYTICS: Final = (RecoveryAction.CHECK_ANALYTICS_CONNECTION,)
_SEARCH: Final = (RecoveryAction.CHECK_SEARCH_CONSOLE_CONNECTION,)
_LOCATION: Final = (RecoveryAction.CHECK_LOCATION_MAPPING,)
_R = AutomationReason


def _attention(*actions: RecoveryAction) -> Policy:
    return Policy(Treatment.ATTENTION, actions)


_RETRY: Final = Policy(Treatment.WILL_RETRY)

# One entry for every ``AutomationReason`` except ``UNMAPPED``. A test fails when a member has
# no entry here, and another when a code the scheduled handlers set is not a member.
FAILURE_POLICY: Final[dict[AutomationReason, Policy]] = {
    _R.GBP_PERFORMANCE_ACCESS_DENIED: _attention(*_RECONNECT),
    _R.INTEGRATION_RECONNECT_REQUIRED: _attention(*_RECONNECT),
    _R.GBP_SCOPE_REQUIRED: _attention(*_RECONNECT),
    _R.GBP_INTEGRATION_NOT_FOUND: _attention(*_RECONNECT),
    _R.NO_CONNECTED_INTEGRATION: _attention(*_RECONNECT),
    _R.TOKEN_REFRESH_FAILED: _attention(*_RECONNECT),
    _R.SECRET_RESOLUTION_FAILED: _attention(*_RECONNECT),
    _R.TOKEN_RESOLUTION_FAILED: _RETRY,
    _R.GBP_LOCATION_NOT_FOUND: _attention(*_LOCATION),
    _R.GBP_LOCATION_AMBIGUOUS: _attention(*_LOCATION),
    _R.GBP_LOCATION_NO_PLATFORM_LINK: _attention(*_LOCATION),
    _R.LOCATION_ID_INVALID: _attention(*_LOCATION),
    _R.LOCATION_ID_MISSING: _attention(*_LOCATION),
    _R.GBP_PERFORMANCE_REQUEST_REJECTED: _attention(),
    _R.GBP_PERFORMANCE_RATE_LIMITED: _RETRY,
    _R.GBP_PERFORMANCE_PROVIDER_UNAVAILABLE: _RETRY,
    _R.GBP_PERFORMANCE_RESPONSE_INVALID: _RETRY,
    _R.GBP_PERFORMANCE_KEYWORDS_UNAVAILABLE: _RETRY,
    _R.GBP_PERFORMANCE_SYNC_FAILED: _attention(),
    _R.GBP_SYNC_FAILED: _attention(),
    _R.REVIEWS_INGEST_FAILED: _attention(),
    _R.SEARCH_CONSOLE_SCOPE_REQUIRED: _attention(*_SEARCH),
    _R.SEARCH_PROPERTY_NOT_FOUND: _attention(*_SEARCH),
    _R.SEARCH_PROPERTY_NOT_CONFIGURED: _attention(*_SEARCH),
    _R.SEARCH_PROPERTY_ID_INVALID: _attention(*_SEARCH),
    _R.SEARCH_CONSOLE_SYNC_INCOMPLETE: _attention(*_SEARCH),
    _R.SEARCH_CONSOLE_SYNC_FAILED: _attention(*_SEARCH),
    _R.ANALYTICS_SCOPE_REQUIRED: _attention(*_ANALYTICS),
    _R.ANALYTICS_PROPERTY_NOT_FOUND: _attention(*_ANALYTICS),
    _R.ANALYTICS_NOT_CONFIGURED: _attention(*_ANALYTICS),
    _R.ANALYTICS_PROPERTY_ID_INVALID: _attention(*_ANALYTICS),
    _R.ANALYTICS_SYNC_INCOMPLETE: _attention(*_ANALYTICS),
    _R.ANALYTICS_SYNC_FAILED: _attention(*_ANALYTICS),
    _R.SEO_ACTIVE_WEBSITE_MISSING: _attention(RecoveryAction.CONNECT_WEBSITE),
    _R.SEO_WEBSITE_NOT_FOUND: _attention(RecoveryAction.CONNECT_WEBSITE),
    _R.SEO_WEBSITE_NOT_ACTIVE: _attention(RecoveryAction.CONNECT_WEBSITE),
    _R.SEO_WEBSITE_SCOPE_MISMATCH: _attention(RecoveryAction.CONNECT_WEBSITE),
    _R.SEO_CRAWL_EMPTY: _attention(),
    _R.SEO_ANALYSIS_FAILED: _attention(),
    _R.SEO_CRAWL_FAILED: _attention(),
    _R.SEO_CRAWL_NOT_TERMINAL: _attention(),
    _R.SEO_CRAWL_RUN_NOT_FOUND: _attention(),
    _R.MISSING_CRAWL_RUN_ID: _attention(),
    _R.INVALID_CRAWL_RUN_ID: _attention(),
    _R.GBP_POST_GROUNDING_REQUIRED: _attention(),
    _R.GBP_POST_GENERATION_FAILED: _attention(),
    _R.GBP_POST_DELIVERY_BINDING_MISSING: _attention(),
    _R.GBP_REVIEW_SOURCE_INVALID: _attention(),
    _R.GBP_ORGANIZATION_UNAVAILABLE: _attention(),
    _R.GBP_POST_REVISION_UNAVAILABLE: _attention(),
    _R.GBP_WEBSITE_TARGET_UNAVAILABLE: _attention(),
    _R.GBP_WEBSITE_KNOWLEDGE_UNAVAILABLE: _RETRY,
    _R.GBP_DRIVE_MEDIA_NOT_CONFIGURED: _attention(),
    _R.GBP_DRIVE_NO_ELIGIBLE_IMAGE: _attention(),
    _R.GBP_DRIVE_MEDIA_UNAVAILABLE: _RETRY,
    _R.GBP_DRIVE_MEDIA_PROXY_UNAVAILABLE: _RETRY,
    _R.GBP_DRIVE_UNREACHABLE: _RETRY,
    _R.GBP_DRIVE_TEMPORARILY_UNAVAILABLE: _RETRY,
    _R.HERMES_SCOPED_SESSION_BUSY: _RETRY,
    _R.VERIFICATION_CONTENT_PENDING: _RETRY,
    _R.VERIFICATION_REREAD_FAILED: _RETRY,
    _R.WORKFLOW_VERSION_NOT_EXECUTABLE: _attention(),
    _R.WORKFLOW_HANDLER_NOT_REGISTERED: _attention(),
    _R.WORKFLOW_RUN_MISSING: _attention(),
    _R.WORKFLOW_CANCELLED: _attention(),
    _R.HANDLER_EXCEPTION: _attention(),
    _R.DATABASE_DETERMINISTIC_ERROR: _attention(),
    _R.RUN_ESCALATED: _attention(),
    _R.RUN_WAITING_APPROVAL: _attention(),
    _R.RUN_PARTIALLY_COMPLETED: _attention(),
    _R.RUN_EXPIRED: _attention(),
}

IN_PROGRESS_STATUSES: Final = frozenset(
    {RunStatus.CREATED, RunStatus.QUEUED, RunStatus.RUNNING, RunStatus.WAITING}
)
# Locations that no longer do any work: their schedules never run and are not automations.
RETIRED_LOCATIONS: Final = (LocationStatus.CLOSED_PERMANENTLY, LocationStatus.ARCHIVED)
# Statuses that block starting another run of the same schedule.
BLOCKING_STATUSES: Final = tuple(sorted(s.value for s in IN_PROGRESS_STATUSES))

# Read-only sync, ingest and crawl workflows. Nothing that publishes or writes to a client's
# website or Business Profile may ever be added here.
RUN_NOW_WORKFLOWS: Final = frozenset(
    {
        "gbp.sync",
        "gbp.sync_performance",
        "reviews.ingest",
        "seo.sync_search_console",
        "insights.sync_analytics",
        "seo.crawl_or_analysis",
    }
)

_SOURCE_BY_PREFIX: Final = {
    "gbp": AutomationSource.GOOGLE_BUSINESS_PROFILE,
    "reviews": AutomationSource.REVIEWS,
    "content": AutomationSource.WEBSITE,
    "leads": AutomationSource.LEADS,
    "insights": AutomationSource.ANALYTICS,
}
_SOURCE_EXACT: Final = {
    "seo.sync_search_console": AutomationSource.SEARCH_CONSOLE,
    "agent.seo": AutomationSource.WEBSITE,
    "agent.insights": AutomationSource.ANALYTICS,
}


def source_of(workflow_key: str) -> AutomationSource:
    """Where an automation's data comes from, by its workflow type."""
    if workflow_key in _SOURCE_EXACT:
        return _SOURCE_EXACT[workflow_key]
    head, _, tail = workflow_key.partition(".")
    if head == "agent":
        return _SOURCE_BY_PREFIX.get(tail, AutomationSource.PLATFORM)
    if head == "seo":
        return AutomationSource.WEBSITE
    return _SOURCE_BY_PREFIX.get(head, AutomationSource.PLATFORM)


def reason_of(failure_code: str | None) -> AutomationReason:
    try:
        return AutomationReason(failure_code) if failure_code else AutomationReason.UNMAPPED
    except ValueError:
        return AutomationReason.UNMAPPED


@dataclass(frozen=True, slots=True)
class Attention:
    reason: AutomationReason
    actions: tuple[RecoveryAction, ...]
    occurred_at: datetime | None


_STATUS_REASON: Final = {
    RunStatus.ESCALATED: AutomationReason.RUN_ESCALATED,
    RunStatus.WAITING_APPROVAL: AutomationReason.RUN_WAITING_APPROVAL,
    RunStatus.PARTIALLY_COMPLETED: AutomationReason.RUN_PARTIALLY_COMPLETED,
    RunStatus.EXPIRED: AutomationReason.RUN_EXPIRED,
}


@dataclass(frozen=True, slots=True)
class RunSnapshot:
    id: UUID
    status: RunStatus
    failure_code: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def finished_at_of(run: WorkflowRun) -> datetime | None:
    """When the run stopped: the completion time, else the last update of a stopped run."""
    status = RunStatus(run.status)
    if status in IN_PROGRESS_STATUSES or status is RunStatus.WAITING_APPROVAL:
        return None
    return run.completed_at or run.cancelled_at or run.updated_at


def snapshot(run: WorkflowRun) -> RunSnapshot:
    return RunSnapshot(
        id=run.id,
        status=RunStatus(run.status),
        failure_code=run.failure_code,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=finished_at_of(run),
    )


def treatment_of(run: RunSnapshot) -> Treatment | None:
    """How a stopped run is treated: attention, will retry, or neither (it went fine)."""
    status = run.status
    if status in (RunStatus.COMPLETED, RunStatus.CANCELLED) or status in IN_PROGRESS_STATUSES:
        return None
    if status is RunStatus.RETRY_SCHEDULED and not run.failure_code:
        # The platform has already queued another attempt and nothing says it went wrong.
        return Treatment.WILL_RETRY
    if status in (RunStatus.FAILED, RunStatus.RETRY_SCHEDULED, RunStatus.ESCALATED):
        policy = FAILURE_POLICY.get(reason_of(run.failure_code))
        if policy is not None:
            return policy.treatment
    return Treatment.ATTENTION


def outcome_of(run: RunSnapshot) -> RunOutcome:
    status = run.status
    if status in IN_PROGRESS_STATUSES:
        return RunOutcome.IN_PROGRESS
    if status is RunStatus.COMPLETED:
        return RunOutcome.SUCCEEDED
    if status is RunStatus.CANCELLED:
        return RunOutcome.CANCELLED
    if treatment_of(run) is Treatment.WILL_RETRY:
        return RunOutcome.WILL_RETRY
    return {
        RunStatus.PARTIALLY_COMPLETED: RunOutcome.PARTIAL,
        RunStatus.EXPIRED: RunOutcome.EXPIRED,
        RunStatus.ESCALATED: RunOutcome.NEEDS_DECISION,
        RunStatus.WAITING_APPROVAL: RunOutcome.NEEDS_DECISION,
    }.get(status, RunOutcome.FAILED)


def run_reason(run: RunSnapshot) -> AutomationReason | None:
    """Why a stopped run did not simply succeed, whether or not it needs a person."""
    if (
        run.status in (RunStatus.COMPLETED, RunStatus.CANCELLED)
        or run.status in IN_PROGRESS_STATUSES
    ):
        return None
    if run.status is RunStatus.RETRY_SCHEDULED and not run.failure_code:
        return None
    reason = reason_of(run.failure_code)
    if reason is AutomationReason.UNMAPPED and run.status in _STATUS_REASON:
        return _STATUS_REASON[run.status]
    return reason


def attention_of(run: RunSnapshot) -> Attention | None:
    """The reason and recovery actions when this (latest) run needs a person, else None."""
    reason = run_reason(run)
    if reason is None or treatment_of(run) is not Treatment.ATTENTION:
        return None
    policy = FAILURE_POLICY.get(reason)
    return Attention(
        reason=reason,
        actions=policy.actions if policy else (),
        occurred_at=run.finished_at,
    )


def status_of(schedule_status: str, latest: RunSnapshot | None) -> AutomationStatus:
    """The one rule. A paused schedule is Paused; otherwise the latest run decides."""
    if schedule_status != "active":
        return AutomationStatus.PAUSED
    if latest is None:
        return AutomationStatus.NOT_RUN_YET
    if latest.status in IN_PROGRESS_STATUSES:
        return AutomationStatus.RUNNING
    if attention_of(latest) is not None:
        return AutomationStatus.NEEDS_ATTENTION
    return AutomationStatus.HEALTHY


@dataclass(frozen=True, slots=True)
class FrequencyValue:
    kind: FrequencyKind
    interval: int | None = None
    hour: int | None = None
    minute: int | None = None
    # Cron numbering: 0 is Sunday.
    weekday: int | None = None
    day_of_month: int | None = None


def _whole(field_text: str) -> int | None:
    return int(field_text) if field_text.isdigit() else None


def _step(field_text: str) -> int | None:
    head, sep, tail = field_text.partition("/")
    return int(tail) if head == "*" and sep and tail.isdigit() and int(tail) > 0 else None


def parse_frequency(cron: str) -> FrequencyValue:
    """A five-field cron expression as a typed value; anything unusual is ``custom``."""
    parts = cron.split()
    if len(parts) != 5:
        return FrequencyValue(FrequencyKind.CUSTOM)
    minute, hour, day, month, weekday = parts
    if month != "*":
        return FrequencyValue(FrequencyKind.CUSTOM)
    every = _step(minute)
    if every is not None and (hour, day, weekday) == ("*", "*", "*"):
        return FrequencyValue(FrequencyKind.INTERVAL_MINUTES, interval=every)
    at_minute = _whole(minute)
    if at_minute is None or at_minute > 59:
        return FrequencyValue(FrequencyKind.CUSTOM)
    if (hour, day, weekday) == ("*", "*", "*"):
        return FrequencyValue(FrequencyKind.HOURLY, minute=at_minute)
    hours = _step(hour)
    if hours is not None and (day, weekday) == ("*", "*"):
        return FrequencyValue(FrequencyKind.INTERVAL_HOURS, interval=hours, minute=at_minute)
    at_hour = _whole(hour)
    if at_hour is None or at_hour > 23:
        return FrequencyValue(FrequencyKind.CUSTOM)
    if (day, weekday) == ("*", "*"):
        return FrequencyValue(FrequencyKind.DAILY, hour=at_hour, minute=at_minute)
    on_weekday = _whole(weekday)
    if day == "*" and on_weekday is not None and on_weekday <= 7:
        return FrequencyValue(
            FrequencyKind.WEEKLY, hour=at_hour, minute=at_minute, weekday=on_weekday % 7
        )
    on_day = _whole(day)
    if weekday == "*" and on_day is not None and 1 <= on_day <= 31:
        return FrequencyValue(
            FrequencyKind.MONTHLY, hour=at_hour, minute=at_minute, day_of_month=on_day
        )
    return FrequencyValue(FrequencyKind.CUSTOM)


@dataclass(slots=True)
class AutomationRecord:
    """One automation: its schedule, workflow type and recent runs (newest first)."""

    schedule: Schedule
    workflow_key: str
    runs: list[RunSnapshot] = field(default_factory=list)
    # The location this schedule is bound to; None for a client-wide schedule.
    location_name: str | None = None

    @property
    def latest(self) -> RunSnapshot | None:
        return self.runs[0] if self.runs else None

    @property
    def status(self) -> AutomationStatus:
        return status_of(self.schedule.status, self.latest)

    @property
    def run_now_allowed(self) -> bool:
        return self.schedule.status == "active" and self.workflow_key in RUN_NOW_WORKFLOWS


async def load_automations(
    session: AsyncSession,
    organization_ids: list[UUID],
    *,
    schedule_id: UUID | None = None,
    history: int = 1,
    include_retired_locations: bool = False,
) -> list[AutomationRecord]:
    """Every scheduled workflow of ``organization_ids`` with its newest ``history`` runs.

    A run belongs to a schedule when it has the same organization, workflow definition and
    location, whether the scheduler or someone pressing Run now started it. Callers decide
    which organizations the caller may read; this function reads exactly what it is given.
    """
    if not organization_ids:
        return []
    statement = (
        select(Schedule, WorkflowDefinition.id, WorkflowDefinition.key)
        .join(WorkflowVersion, WorkflowVersion.id == Schedule.workflow_version_id)
        .join(WorkflowDefinition, WorkflowDefinition.id == WorkflowVersion.definition_id)
        .where(Schedule.organization_id.in_(organization_ids))
        .order_by(WorkflowDefinition.key, Schedule.created_at, Schedule.id)
    )
    if not include_retired_locations:
        # An archived or permanently closed location is not an automation, so it is also not
        # counted by the dashboard's automations health, which shares this loader.
        statement = statement.outerjoin(
            Location,
            (Location.organization_id == Schedule.organization_id)
            & (Location.id == Schedule.location_id),
        ).where(or_(Schedule.location_id.is_(None), Location.status.notin_(RETIRED_LOCATIONS)))
    if schedule_id is not None:
        statement = statement.where(Schedule.id == schedule_id)
    rows = [
        (schedule, definition_id, key)
        for schedule, definition_id, key in await session.execute(statement)
        if is_tenant_workflow_key(key)
    ]
    if not rows:
        return []
    ranked = (
        select(
            WorkflowRun.id.label("id"),
            func.row_number()
            .over(
                partition_by=(
                    WorkflowRun.organization_id,
                    WorkflowVersion.definition_id,
                    WorkflowRun.location_id,
                ),
                order_by=(WorkflowRun.created_at.desc(), WorkflowRun.id.desc()),
            )
            .label("rank"),
        )
        .join(WorkflowVersion, WorkflowVersion.id == WorkflowRun.workflow_version_id)
        .where(
            WorkflowRun.organization_id.in_({schedule.organization_id for schedule, *_ in rows}),
            WorkflowVersion.definition_id.in_({definition_id for _, definition_id, _ in rows}),
        )
        .subquery()
    )
    by_scope: dict[tuple[UUID, UUID, UUID | None], list[RunSnapshot]] = defaultdict(list)
    for run, definition_id in await session.execute(
        select(WorkflowRun, WorkflowVersion.definition_id)
        .join(ranked, ranked.c.id == WorkflowRun.id)
        .join(WorkflowVersion, WorkflowVersion.id == WorkflowRun.workflow_version_id)
        .where(ranked.c.rank <= history)
        .order_by(WorkflowRun.created_at.desc(), WorkflowRun.id.desc())
    ):
        by_scope[(run.organization_id, definition_id, run.location_id)].append(snapshot(run))
    location_ids = {schedule.location_id for schedule, *_ in rows if schedule.location_id}
    names: dict[UUID, str] = {}
    if location_ids:
        names = {
            location_id: name
            for location_id, name in await session.execute(
                select(Location.id, Location.name).where(
                    Location.id.in_(location_ids),
                    Location.organization_id.in_(
                        {schedule.organization_id for schedule, *_ in rows}
                    ),
                )
            )
        }
    return [
        AutomationRecord(
            schedule=schedule,
            workflow_key=key,
            runs=by_scope.get((schedule.organization_id, definition_id, schedule.location_id), []),
            location_name=names.get(schedule.location_id) if schedule.location_id else None,
        )
        for schedule, definition_id, key in rows
    ]


async def automation_attention_counts(
    session: AsyncSession, organization_ids: list[UUID]
) -> dict[UUID, int]:
    """Automations needing attention per organization, by exactly the Automations screen's rule."""
    counts: dict[UUID, int] = defaultdict(int)
    for record in await load_automations(session, organization_ids):
        if record.status is AutomationStatus.NEEDS_ATTENTION:
            counts[record.schedule.organization_id] += 1
    return dict(counts)


def known_workflow_keys() -> list[str]:
    return sorted(key for key in WORKFLOW_TYPES if is_tenant_workflow_key(key))
