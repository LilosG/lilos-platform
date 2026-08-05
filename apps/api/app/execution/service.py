"""Durable, transaction-owned workflow and job operations."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.execution.contracts import JobOutcome, WorkflowSubmit
from apps.api.app.execution.errors import (
    WorkflowIdempotencyConflictError,
    WorkflowKeyUnknownError,
    WorkflowLocationScopeError,
    WorkflowRunNotAvailableError,
    WorkflowRunNotFoundError,
    WorkflowRunTypeMismatchError,
)
from apps.api.app.execution.models import (
    Job,
    JobAttempt,
    Schedule,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES, is_known_workflow_key
from apps.api.app.locations.models import Location

CONSUMABLE_WORKFLOW_RUN_STATUSES = {"created", "queued"}


class IdempotencyConflict(ValueError):
    pass


class ExecutionService:
    def __init__(self) -> None:
        self.audit = AuditEventService()

    async def _audit(
        self,
        session: AsyncSession,
        *,
        event: str,
        organization_id: UUID,
        location_id: UUID | None,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID,
        correlation_id: str,
        summary: str,
        metadata: dict[str, object],
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=event,
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                organization_id=organization_id,
                location_id=location_id,
                product_key="workflows",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

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
    ) -> tuple[WorkflowRun, bool]:
        """Create (or idempotently return) a durable workflow run and its initial job.

        Returns `(run, created)`, where `created` is False when an existing run
        with the same idempotency key was returned instead of a new one being made.
        """
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
            return existing, False
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
        return run, True

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

        run, _created = await self.submit(
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

    async def _resolve_workflow_version(
        self, session: AsyncSession, workflow_key: str
    ) -> WorkflowVersion:
        if not is_known_workflow_key(workflow_key):
            raise WorkflowKeyUnknownError
        name, owner = WORKFLOW_TYPES[workflow_key]
        definition = await session.scalar(
            select(WorkflowDefinition).where(WorkflowDefinition.key == workflow_key)
        )
        if definition is None:
            definition = WorkflowDefinition(
                key=workflow_key, name=name, owner=owner, status="active"
            )
            session.add(definition)
            await session.flush()
        version = await session.scalar(
            select(WorkflowVersion)
            .where(
                WorkflowVersion.definition_id == definition.id,
                WorkflowVersion.status == "approved",
            )
            .order_by(WorkflowVersion.version.desc())
            .limit(1)
        )
        if version is None:
            version = WorkflowVersion(
                definition_id=definition.id,
                version=1,
                status="approved",
                input_schema={},
                output_schema={},
                step_specification=[],
                retry_policy={},
                timeout_seconds=300,
            )
            session.add(version)
            await session.flush()
        return version

    async def start_named(
        self,
        session: AsyncSession,
        organization_id: UUID,
        workflow_key: str,
        idempotency_key: str,
        *,
        location_id: UUID | None = None,
        input_document: dict[str, object] | None = None,
        correlation_id: str,
        actor_id: UUID | None = None,
    ) -> WorkflowRun:
        """Start (or idempotently resolve) a named, persisted workflow run.

        This is the only supported way to obtain a `workflow_run_id` for a
        product action. Callers never supply their own workflow_run_id: it is
        always the id of a row this method creates or resolves, scoped to the
        caller's organization and validated against the fixed workflow-type
        catalog. `workflow_key` must be one of `WORKFLOW_TYPES`; unknown keys
        are rejected before any row is created.
        """
        if location_id is not None:
            location = await session.scalar(
                select(Location).where(
                    Location.organization_id == organization_id, Location.id == location_id
                )
            )
            if not location:
                raise WorkflowLocationScopeError
        version = await self._resolve_workflow_version(session, workflow_key)
        command = WorkflowSubmit(
            workflow_version_id=version.id,
            location_id=location_id,
            idempotency_key=idempotency_key,
            input_document=input_document or {},
        )
        try:
            run, created = await self.submit(
                session, organization_id, command, correlation_id, trigger_type="api"
            )
        except IdempotencyConflict as error:
            raise WorkflowIdempotencyConflictError from error
        if run.product_key != WORKFLOW_TYPES[workflow_key][1]:
            run.product_key = WORKFLOW_TYPES[workflow_key][1]
            await session.flush()
        if created:
            await self._audit(
                session,
                event="workflow.run.started",
                organization_id=organization_id,
                location_id=location_id,
                actor_id=actor_id,
                resource_type="workflow_run",
                resource_id=run.id,
                correlation_id=correlation_id,
                summary=f"Workflow run started: {workflow_key}.",
                metadata={"workflow_key": workflow_key, "status": run.status},
            )
        return run

    async def resolve_for_consumption(
        self,
        session: AsyncSession,
        organization_id: UUID,
        workflow_run_id: UUID,
        expected_workflow_key: str,
        *,
        mark_running: bool = True,
    ) -> WorkflowRun:
        """Validate a workflow run before a product action consumes it.

        Rejects a run that does not exist for this organization (tenant
        isolation), was started for a different workflow type (type
        mismatch), or is not in a freshly-created/queued state (already
        consumed, completed, cancelled, expired, or otherwise stale). On
        success, the run is atomically locked and, by default, transitioned
        to `running` so it cannot be consumed a second time by another
        product action.
        """
        run = await session.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.organization_id == organization_id, WorkflowRun.id == workflow_run_id
            )
            .with_for_update()
        )
        if not run:
            raise WorkflowRunNotFoundError
        version = await session.get(WorkflowVersion, run.workflow_version_id)
        definition = (
            await session.get(WorkflowDefinition, version.definition_id) if version else None
        )
        if not definition or definition.key != expected_workflow_key:
            raise WorkflowRunTypeMismatchError
        if run.status not in CONSUMABLE_WORKFLOW_RUN_STATUSES:
            raise WorkflowRunNotAvailableError
        if mark_running:
            run.status = "running"
            run.started_at = run.started_at or datetime.now(UTC)
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
