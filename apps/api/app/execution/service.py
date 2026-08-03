"""Durable, transaction-owned workflow and job operations."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.contracts import JobOutcome, WorkflowSubmit
from apps.api.app.execution.models import Job, JobAttempt, WorkflowRun


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
            trigger_type="api",
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
