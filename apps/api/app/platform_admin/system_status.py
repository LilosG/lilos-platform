"""Deterministic facts about whether the platform's own machinery is working.

Everything here is a count or a timestamp read from the tables the services write. Nothing is
inferred, summarised by a model or phrased as text. A component whose rows cannot be read is
``unknown``: it is never reported healthy and its numbers are never reported as zero.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import TypeVar

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.health import check_database_health
from apps.api.app.database.runtime import DatabaseRuntime
from apps.api.app.execution.automations import RETIRED_LOCATIONS
from apps.api.app.execution.models import Job, JobAttempt, Schedule, WorkflowRun
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.platform_admin.contracts import (
    DatabaseComponent,
    DeadLetterGroup,
    DeadLetterReason,
    FailedRunsComponent,
    IntegrationsComponent,
    SchedulerComponent,
    SystemHealth,
    SystemStatus,
    WorkerQueueComponent,
)

logger = logging.getLogger("lilos.api.platform_status")

# The scheduler wakes every 45 seconds, so a schedule this far past due has been missed.
SCHEDULER_OVERDUE_AFTER = timedelta(minutes=10)
# Due work that has waited this long means the worker is not keeping up.
QUEUE_BACKLOG_AFTER = timedelta(minutes=15)
FAILED_RUN_WINDOW = timedelta(hours=24)
CONNECTION_NEEDS_ATTENTION = ("degraded", "reconnect_required")

T = TypeVar("T")


def dead_letter_reason(status: str | None, error_category: str | None) -> DeadLetterReason:
    """Classify a dead-lettered job by how its final attempt ended."""
    if status == "permanent_failure":
        return DeadLetterReason.PERMANENT_FAILURE
    if status == "retryable_failure":
        return DeadLetterReason.RETRIES_EXHAUSTED
    if status == "timed_out":
        return (
            DeadLetterReason.LEASE_EXPIRED
            if error_category == "lease_expired"
            else DeadLetterReason.TIMED_OUT
        )
    if status == "ambiguous":
        return DeadLetterReason.OUTCOME_UNCERTAIN
    return DeadLetterReason.UNRECORDED


def overall_health(components: list[SystemHealth]) -> SystemHealth:
    if SystemHealth.ATTENTION in components:
        return SystemHealth.ATTENTION
    if SystemHealth.UNKNOWN in components:
        return SystemHealth.UNKNOWN
    return SystemHealth.HEALTHY


class SystemStatusService:
    async def evaluate(
        self, session: AsyncSession, database: DatabaseRuntime, *, now: datetime | None = None
    ) -> SystemStatus:
        now = now or datetime.now(UTC)
        database_component = await self._database(database)
        scheduler = await self._guarded(session, lambda: self._scheduler(session, now))
        queue = await self._guarded(session, lambda: self._queue(session, now))
        runs = await self._guarded(session, lambda: self._failed_runs(session, now))
        integrations = await self._guarded(session, lambda: self._integrations(session))
        return SystemStatus(
            overall=overall_health(
                [
                    database_component.status,
                    scheduler.status if scheduler else SystemHealth.UNKNOWN,
                    queue.status if queue else SystemHealth.UNKNOWN,
                    runs.status if runs else SystemHealth.UNKNOWN,
                    integrations.status if integrations else SystemHealth.UNKNOWN,
                ]
            ),
            evaluated_at=now,
            database=database_component,
            scheduler=scheduler
            or SchedulerComponent(
                status=SystemHealth.UNKNOWN,
                active_schedules=None,
                last_dispatch_at=None,
                overdue=None,
            ),
            worker_queue=queue
            or WorkerQueueComponent(
                status=SystemHealth.UNKNOWN,
                dead_letter_count=None,
                dead_letter_groups=(),
                oldest_pending_at=None,
                backlogged=None,
            ),
            failed_runs=runs
            or FailedRunsComponent(status=SystemHealth.UNKNOWN, failed_last_24h=None),
            integrations=integrations
            or IntegrationsComponent(status=SystemHealth.UNKNOWN, needing_attention=None),
        )

    async def _guarded(self, session: AsyncSession, read: Callable[[], Awaitable[T]]) -> T | None:
        """Run one component's reads in a savepoint so a failure leaves the others readable."""
        try:
            async with session.begin_nested():
                return await read()
        except Exception:
            logger.warning(
                "System status component could not be read",
                extra={"event_name": "platform.system_status.unreadable", "outcome": "failure"},
                exc_info=True,
            )
            return None

    async def _database(self, database: DatabaseRuntime) -> DatabaseComponent:
        try:
            health = await check_database_health(database)
        except Exception:
            return DatabaseComponent(status=SystemHealth.UNKNOWN)
        return DatabaseComponent(
            status=SystemHealth.HEALTHY if health.available else SystemHealth.ATTENTION
        )

    async def _scheduler(self, session: AsyncSession, now: datetime) -> SchedulerComponent:
        # The same schedules the scheduler would dispatch: a retired client's or location's
        # schedule is left alone on purpose and is not "overdue".
        dispatchable = (
            Schedule.status == "active",
            Organization.status != OrganizationStatus.ARCHIVED,
            Organization.removed_at.is_(None),
            or_(Schedule.location_id.is_(None), Location.status.notin_(RETIRED_LOCATIONS)),
        )
        base = (
            select(Schedule)
            .join(Organization, Organization.id == Schedule.organization_id)
            .outerjoin(
                Location,
                (Location.organization_id == Schedule.organization_id)
                & (Location.id == Schedule.location_id),
            )
            .where(*dispatchable)
            .subquery()
        )
        total, last_dispatch, overdue = (
            await session.execute(
                select(
                    func.count(base.c.id),
                    func.max(base.c.last_run_at),
                    func.count(base.c.id).filter(
                        base.c.next_run_at < now - SCHEDULER_OVERDUE_AFTER
                    ),
                )
            )
        ).one()
        return SchedulerComponent(
            status=SystemHealth.ATTENTION if overdue else SystemHealth.HEALTHY,
            active_schedules=total,
            last_dispatch_at=last_dispatch,
            overdue=bool(overdue),
        )

    async def _queue(self, session: AsyncSession, now: datetime) -> WorkerQueueComponent:
        rows = (
            await session.execute(
                select(JobAttempt.status, JobAttempt.error_category, func.count(Job.id))
                .select_from(Job)
                .outerjoin(
                    JobAttempt,
                    (JobAttempt.job_id == Job.id)
                    & (JobAttempt.attempt_number == Job.attempt_count),
                )
                .where(Job.status == "dead_lettered")
                .group_by(JobAttempt.status, JobAttempt.error_category)
            )
        ).all()
        counts: dict[DeadLetterReason, int] = {}
        for attempt_status, category, count in rows:
            reason = dead_letter_reason(attempt_status, category)
            counts[reason] = counts.get(reason, 0) + count
        oldest = await session.scalar(
            select(func.min(Job.available_at)).where(
                Job.status.in_(("queued", "retry_scheduled")),
                Job.available_at <= now,
                Job.cancellation_requested_at.is_(None),
            )
        )
        backlogged = oldest is not None and oldest < now - QUEUE_BACKLOG_AFTER
        dead = sum(counts.values())
        return WorkerQueueComponent(
            status=SystemHealth.ATTENTION if dead or backlogged else SystemHealth.HEALTHY,
            dead_letter_count=dead,
            dead_letter_groups=tuple(
                DeadLetterGroup(reason=reason, count=counts[reason])
                for reason in DeadLetterReason
                if reason in counts
            ),
            oldest_pending_at=oldest,
            backlogged=backlogged,
        )

    async def _failed_runs(self, session: AsyncSession, now: datetime) -> FailedRunsComponent:
        failed = await session.scalar(
            select(func.count(WorkflowRun.id)).where(
                WorkflowRun.status == "failed",
                WorkflowRun.updated_at >= now - FAILED_RUN_WINDOW,
            )
        )
        return FailedRunsComponent(
            status=SystemHealth.ATTENTION if failed else SystemHealth.HEALTHY,
            failed_last_24h=failed or 0,
        )

    async def _integrations(self, session: AsyncSession) -> IntegrationsComponent:
        needing = await session.scalar(
            select(func.count(IntegrationConnection.id))
            .join(Organization, Organization.id == IntegrationConnection.organization_id)
            .where(
                IntegrationConnection.status.in_(CONNECTION_NEEDS_ATTENTION),
                Organization.status != OrganizationStatus.ARCHIVED,
                Organization.removed_at.is_(None),
            )
        )
        return IntegrationsComponent(
            status=SystemHealth.ATTENTION if needing else SystemHealth.HEALTHY,
            needing_attention=needing or 0,
        )
