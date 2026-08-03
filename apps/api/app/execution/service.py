"""Durable, transaction-owned workflow and job operations."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.contracts import JobOutcome, WorkflowSubmit
from apps.api.app.execution.models import Job, JobAttempt, Schedule, WorkflowRun


class IdempotencyConflict(ValueError):
    pass


class ExecutionService:
    @staticmethod
    def request_hash(command: WorkflowSubmit) -> str:
        payload = command.model_dump(mode="json", exclude={"idempotency_key"})
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    async def submit(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: WorkflowSubmit,
        correlation_id: str,
        *,
        trigger_type: str = "api",
    ) -> WorkflowRun:
        digest = self.request_hash(command)
        existing = await session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.idempotency_key == command.idempotency_key,
            )
        )
        if existing:
            if existing.request_hash != digest:
                raise IdempotencyConflict("idempotency key request mismatch")
            return existing
        run = WorkflowRun(
            organization_id=organization_id,
            location_id=command.location_id,
            workflow_version_id=command.workflow_version_id,
            status="queued",
            trigger_type=trigger_type,
            idempotency_key=command.idempotency_key,
            request_hash=digest,
            input_document=command.input_document,
            correlation_id=correlation_id,
        )
        session.add(run)
        await session.flush()
        session.add(
            Job(
                organization_id=organization_id,
                workflow_run_id=run.id,
                job_type="workflow.execute",
                status="queued",
                idempotency_key=f"run:{run.id}",
                payload={"run_id": str(run.id)},
            )
        )
        await session.flush()
        return run

    async def dispatch_due_schedule(
        self, session: AsyncSession, correlation_id: str
    ) -> WorkflowRun | None:
        """Atomically advance and dispatch one due durable schedule."""
        now = datetime.now(UTC)
        schedule = await session.scalar(
            select(Schedule)
            .where(Schedule.status == "active", Schedule.next_run_at <= now)
            .order_by(Schedule.next_run_at, Schedule.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if schedule is None:
            return None

        scheduled_for = schedule.next_run_at
        try:
            local_scheduled_for = scheduled_for.astimezone(ZoneInfo(schedule.timezone))
        except ZoneInfoNotFoundError as exc:
            raise ValueError("schedule timezone is invalid") from exc
        next_run = croniter(schedule.cron_expression, local_scheduled_for).get_next(datetime)
        if next_run.tzinfo is None:
            raise ValueError("schedule produced a timezone-naive next run")

        run = await self.submit(
            session,
            schedule.organization_id,
            WorkflowSubmit(
                workflow_version_id=schedule.workflow_version_id,
                location_id=schedule.location_id,
                idempotency_key=f"schedule:{schedule.id}:{scheduled_for.isoformat()}",
                input_document={
                    "schedule_id": str(schedule.id),
                    "scheduled_for": scheduled_for.isoformat(),
                },
            ),
            correlation_id,
            trigger_type="schedule",
        )
        schedule.last_run_at = scheduled_for
        schedule.next_run_at = next_run.astimezone(UTC)
        await session.flush()
        return run

    async def claim(
        self, session: AsyncSession, worker_id: str, lease_seconds: int = 60
    ) -> Job | None:
        now = datetime.now(UTC)
        job = await session.scalar(
            select(Job)
            .where(
                or_(
                    Job.status.in_(("queued", "retry_scheduled")),
                    (Job.status == "claimed") & (Job.lease_expires_at < now),
                ),
                Job.available_at <= now,
                Job.cancellation_requested_at.is_(None),
            )
            .order_by(Job.priority, Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        job.status, job.lease_owner, job.lease_expires_at = (
            "claimed",
            worker_id,
            now + timedelta(seconds=lease_seconds),
        )
        job.attempt_count += 1
        session.add(
            JobAttempt(
                organization_id=job.organization_id,
                job_id=job.id,
                attempt_number=job.attempt_count,
                status="running",
                worker_id=worker_id,
            )
        )
        await session.flush()
        return job

    async def finish(
        self, session: AsyncSession, organization_id: UUID, job_id: UUID, outcome: JobOutcome
    ) -> Job:
        job = await session.scalar(
            select(Job)
            .where(Job.organization_id == organization_id, Job.id == job_id)
            .with_for_update()
        )
        if not job:
            raise LookupError("job not found")
        attempt = await session.scalar(
            select(JobAttempt)
            .where(JobAttempt.job_id == job.id, JobAttempt.attempt_number == job.attempt_count)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if attempt:
            attempt.status, attempt.completed_at, attempt.safe_error = (
                outcome.result,
                now,
                outcome.safe_error,
            )
        if outcome.result == "succeeded":
            job.status, job.result_reference = "completed", outcome.result_reference
        elif outcome.result == "retryable_failure" and job.attempt_count < job.max_attempts:
            job.status, job.available_at = (
                "retry_scheduled",
                now + timedelta(seconds=min(3600, 2**job.attempt_count)),
            )
        elif outcome.result == "ambiguous":
            job.status = "dead_lettered"
        else:
            job.status = "failed" if job.attempt_count < job.max_attempts else "dead_lettered"
        job.lease_owner = job.lease_expires_at = None
        await session.flush()
        return job

    async def renew_lease(
        self,
        session: AsyncSession,
        organization_id: UUID,
        job_id: UUID,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        """Extend a live claim only while it remains owned and executable."""
        job = await session.scalar(
            select(Job)
            .where(
                Job.organization_id == organization_id,
                Job.id == job_id,
                Job.status == "claimed",
                Job.lease_owner == worker_id,
                Job.cancellation_requested_at.is_(None),
            )
            .with_for_update()
        )
        if job is None:
            return False
        job.lease_expires_at = datetime.now(UTC) + timedelta(seconds=lease_seconds)
        await session.flush()
        return True
