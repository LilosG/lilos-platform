"""Durable, transaction-owned workflow and job operations."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.execution.contracts import (
    JobOutcome,
    ScheduleCreate,
    ScheduleUpdate,
    WorkflowSubmit,
)
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

    async def record_run_outcome(
        self,
        session: AsyncSession,
        run: WorkflowRun,
        workflow_key: str,
        outcome: JobOutcome,
    ) -> None:
        """Append the system audit event for a durable execution outcome."""
        if outcome.result == "succeeded":
            event = "workflow.run.completed"
            result = AuditResult.SUCCEEDED
            summary = f"Workflow run completed: {workflow_key}."
        elif outcome.result == "retryable_failure":
            event = "workflow.run.retry_scheduled"
            result = AuditResult.FAILED
            summary = f"Workflow run requires retry: {workflow_key}."
        elif outcome.result == "ambiguous":
            event = "workflow.run.reconciliation_required"
            result = AuditResult.PARTIALLY_SUCCEEDED
            summary = f"Workflow run requires reconciliation: {workflow_key}."
        else:
            event = "workflow.run.failed"
            result = AuditResult.FAILED
            summary = f"Workflow run failed: {workflow_key}."
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=event,
                result=result,
                actor_type=AuditActorType.WORKFLOW,
                organization_id=run.organization_id,
                location_id=run.location_id,
                product_key="workflows",
                resource_type="workflow_run",
                resource_id=run.id,
                correlation_id=run.correlation_id,
                workflow_execution_id=run.id,
                summary=summary,
                metadata={
                    "workflow_key": workflow_key,
                    "status": run.status,
                    "outcome": outcome.result,
                    "safe_error": outcome.safe_error,
                },
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
        enqueue_job: bool = True,
    ) -> tuple[WorkflowRun, bool]:
        """Create (or idempotently return) a durable workflow run.

        Returns `(run, created)`, where `created` is False when an existing run
        with the same idempotency key was returned instead of a new one being made.

        When *enqueue_job* is True (the default), an initial ``workflow.execute``
        Job is also created so a background worker will process the run.
        Set *enqueue_job* to False when a product endpoint intends to consume
        the run via ``resolve_for_consumption``, avoiding a worker race.
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
        if enqueue_job:
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
                timeout_seconds=900 if workflow_key.startswith("agent.") else 300,
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
        enqueue_job: bool = True,
    ) -> WorkflowRun:
        """Start (or idempotently resolve) a named, persisted workflow run.

        This is the only supported way to obtain a `workflow_run_id` for a
        product action. Callers never supply their own workflow_run_id: it is
        always the id of a row this method creates or resolves, scoped to the
        caller's organization and validated against the fixed workflow-type
        catalog. `workflow_key` must be one of `WORKFLOW_TYPES`; unknown keys
        are rejected before any row is created.

        Set *enqueue_job* to False when the caller intends to consume the
        reserved run through `resolve_for_consumption` and does not want a
        background worker to race for it.
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
                session,
                organization_id,
                command,
                correlation_id,
                trigger_type="api",
                enqueue_job=enqueue_job,
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

    async def enqueue_consumed_run(
        self,
        session: AsyncSession,
        run: WorkflowRun,
    ) -> Job:
        """Queue a reserved run after its authoritative resource is attached.

        Product mutation endpoints first consume/lock a reservation, persist
        the publication or implementation resource, and attach that resource
        identifier to ``input_document``. Only then may this method make the
        run visible to workers. The unique job idempotency key closes races.
        """
        existing = await session.scalar(
            select(Job).where(
                Job.organization_id == run.organization_id,
                Job.workflow_run_id == run.id,
                Job.job_type == "workflow.execute",
            )
        )
        if existing is not None:
            return existing
        if run.status != "running":
            raise WorkflowRunNotAvailableError
        job = Job(
            organization_id=run.organization_id,
            workflow_run_id=run.id,
            job_type="workflow.execute",
            status="queued",
            idempotency_key=f"run:{run.id}",
            payload={"run_id": str(run.id)},
        )
        session.add(job)
        run.status = "queued"
        await session.flush()
        return job

    async def enqueue_recovery_run(
        self,
        session: AsyncSession,
        organization_id: UUID,
        workflow_run_id: UUID,
        *,
        recovery_reference: str,
        actor_id: UUID,
        correlation_id: str,
    ) -> Job:
        """Resume a terminal run through the canonical durable job queue.

        The workflow row lock serializes recovery requests. An already-active
        job is returned idempotently; otherwise a new bounded job is attached
        to the same workflow run instead of creating another orchestration path.
        """
        run = await session.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.id == workflow_run_id,
            )
            .with_for_update()
        )
        if run is None:
            raise WorkflowRunNotFoundError

        active = await session.scalar(
            select(Job)
            .where(
                Job.organization_id == organization_id,
                Job.workflow_run_id == workflow_run_id,
                Job.status.in_(("queued", "claimed", "running", "retry_scheduled")),
            )
            .order_by(Job.created_at.desc())
            .limit(1)
        )
        if active is not None:
            return active

        prior_jobs = (
            await session.scalar(
                select(func.count())
                .select_from(Job)
                .where(
                    Job.organization_id == organization_id,
                    Job.workflow_run_id == workflow_run_id,
                )
            )
        ) or 0
        job = Job(
            organization_id=organization_id,
            workflow_run_id=workflow_run_id,
            job_type="workflow.execute",
            status="queued",
            idempotency_key=f"run:{workflow_run_id}:recovery:{prior_jobs + 1}",
            payload={"run_id": str(workflow_run_id)},
        )
        session.add(job)
        run.status = "queued"
        run.failure_code = None
        run.completed_at = None
        await session.flush()
        await self._audit(
            session,
            event="workflow.run.recovery_enqueued",
            organization_id=organization_id,
            location_id=run.location_id,
            actor_id=actor_id,
            resource_type="workflow_run",
            resource_id=run.id,
            correlation_id=correlation_id,
            summary="Workflow run recovery enqueued.",
            metadata={"recovery_reference": recovery_reference, "job_id": str(job.id)},
        )
        return job

    async def claim(
        self, session: AsyncSession, worker_id: str, lease_seconds: int = 60
    ) -> Job | None:
        now = datetime.now(UTC)
        while True:
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

            if job.status == "claimed":
                # Lease expired. A job that already exhausted its attempts must
                # never be reclaimed; close its abandoned attempt and move it to
                # a terminal state instead of cycling forever.
                if job.attempt_count >= job.max_attempts:
                    await self._close_abandoned_attempt(session, job, now)
                    job.status = "dead_lettered"
                    job.lease_owner = None
                    job.lease_expires_at = None
                    await session.flush()
                    continue
                # Reclaim after lease expiry: close the prior attempt before
                # opening a new one so it cannot linger as ``running``.
                await self._close_abandoned_attempt(session, job, now)

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

    async def _close_abandoned_attempt(
        self, session: AsyncSession, job: Job, now: datetime
    ) -> None:
        """Close any open attempts so none can linger as ``running``."""
        attempts = (
            await session.scalars(
                select(JobAttempt)
                .where(
                    JobAttempt.job_id == job.id,
                    JobAttempt.status == "running",
                )
                .with_for_update()
            )
        ).all()
        for attempt in attempts:
            attempt.status = "timed_out"
            attempt.completed_at = now
            attempt.error_category = "lease_expired"
            attempt.safe_error = "LEASE_EXPIRED"

    async def sweep_abandoned_leases(
        self,
        session: AsyncSession,
        *,
        limit: int = 100,
    ) -> int:
        """Reconcile jobs whose lease expired with no live owner.

        Closes the abandoned attempt and either requeues (within
        ``max_attempts``) or dead-letters (at or beyond it). Returns the
        number of jobs reconciled.
        """
        now = datetime.now(UTC)
        jobs = (
            await session.scalars(
                select(Job)
                .where(
                    Job.status == "claimed",
                    Job.lease_expires_at < now,
                )
                .order_by(Job.created_at)
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).all()
        for job in jobs:
            await self._close_abandoned_attempt(session, job, now)
            if job.attempt_count >= job.max_attempts:
                job.status = "dead_lettered"
            else:
                job.status = "retry_scheduled"
                job.available_at = now + timedelta(seconds=min(3600, 2**job.attempt_count))
            job.lease_owner = None
            job.lease_expires_at = None
        await session.flush()
        return len(jobs)

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
        """Extend a live claim with a conditional UPDATE that does not block.

        Uses a single no-lock ``UPDATE … WHERE …`` that atomically checks
        ownership and extends the lease only while the row is still claimed
        by this worker and not cancelled. Returns ``True`` when exactly one
        row was updated.
        """
        new_expiry = datetime.now(UTC) + timedelta(seconds=lease_seconds)
        result = cast(
            "CursorResult[Any]",
            await session.execute(
                update(Job)
                .where(
                    Job.organization_id == organization_id,
                    Job.id == job_id,
                    Job.status == "claimed",
                    Job.lease_owner == worker_id,
                    Job.cancellation_requested_at.is_(None),
                )
                .values(lease_expires_at=new_expiry)
            ),
        )
        return bool(result.rowcount == 1)

    # ------------------------------------------------------------------
    # Read-model queries for Automation & Agents product surface
    # ------------------------------------------------------------------

    async def list_workflow_types(self, session: AsyncSession) -> list[dict[str, object]]:
        """Return the known workflow catalog with definition/version state.

        This is a read-only view of the fixed ``WORKFLOW_TYPES`` registry
        enriched with any persisted ``WorkflowDefinition`` / ``WorkflowVersion``
        rows for each key, so the Automation UI can show whether a workflow
        type has been activated for execution.
        """
        definitions = (await session.scalars(select(WorkflowDefinition))).all()
        versions = (
            await session.scalars(
                select(WorkflowVersion).where(WorkflowVersion.status == "approved")
            )
        ).all()
        def_by_key: dict[str, WorkflowDefinition] = {d.key: d for d in definitions}
        ver_by_def: dict[UUID, WorkflowVersion | None] = {}
        for v in versions:
            cur = ver_by_def.get(v.definition_id)
            if cur is None or v.version > cur.version:
                ver_by_def[v.definition_id] = v

        result: list[dict[str, object]] = []
        for key, (display_name, product_key) in sorted(WORKFLOW_TYPES.items()):
            definition = def_by_key.get(key)
            version = ver_by_def.get(definition.id) if definition else None
            result.append(
                {
                    "key": key,
                    "display_name": display_name,
                    "product_key": product_key,
                    "definition_status": definition.status if definition else "not_persisted",
                    "latest_version": version.version if version else None,
                }
            )
        return result

    async def list_runs(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        workflow_key: str | None = None,
        location_id: UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, object]], int]:
        """Return paginated workflow runs for an organization.

        Includes the latest job and its attempts so the UI can show retry
        counts and error information without additional round-trips.
        """
        base = select(WorkflowRun).where(WorkflowRun.organization_id == organization_id)
        if workflow_key is not None:
            # Join through WorkflowVersion → WorkflowDefinition to filter by key
            base = (
                base.join(
                    WorkflowVersion,
                    WorkflowVersion.id == WorkflowRun.workflow_version_id,
                )
                .join(
                    WorkflowDefinition,
                    WorkflowDefinition.id == WorkflowVersion.definition_id,
                )
                .where(WorkflowDefinition.key == workflow_key)
            )
        if location_id is not None:
            base = base.where(WorkflowRun.location_id == location_id)
        if status is not None:
            base = base.where(WorkflowRun.status == status)

        count_q = select(func.count()).select_from(base.subquery())
        total = (await session.scalar(count_q)) or 0

        rows = (
            await session.scalars(
                base.order_by(WorkflowRun.created_at.desc()).limit(limit).offset(offset)
            )
        ).all()

        # Resolve workflow keys for all runs in one batch
        run_ids = [r.id for r in rows]
        version_ids = {r.workflow_version_id for r in rows}
        def_versions: dict[UUID, tuple[str | None, str | None]] = {}
        if version_ids:
            vers = (
                await session.scalars(
                    select(WorkflowVersion).where(WorkflowVersion.id.in_(version_ids))
                )
            ).all()
            def_ids = {v.definition_id for v in vers}
            defs: dict[UUID, WorkflowDefinition] = {}
            if def_ids:
                def_rows = (
                    await session.scalars(
                        select(WorkflowDefinition).where(WorkflowDefinition.id.in_(def_ids))
                    )
                ).all()
                defs = {d.id: d for d in def_rows}
            for v in vers:
                d = defs.get(v.definition_id)
                def_versions[v.id] = (d.key if d else None, d.name if d else None)

        # Resolve latest job for each run
        jobs: dict[UUID, Job] = {}
        if run_ids:
            # Get the most recent job per run
            job_rows = (
                await session.scalars(
                    select(Job)
                    .where(
                        Job.organization_id == organization_id,
                        Job.workflow_run_id.in_(run_ids),
                    )
                    .order_by(Job.created_at.desc())
                )
            ).all()
            seen: set[UUID] = set()
            for j in job_rows:
                if j.workflow_run_id not in seen:
                    seen.add(j.workflow_run_id)
                    jobs[j.workflow_run_id] = j

        results: list[dict[str, object]] = []
        for run in rows:
            wf_key, wf_name = def_versions.get(run.workflow_version_id, (None, None))
            job = jobs.get(run.id)
            results.append(
                {
                    "id": str(run.id),
                    "workflow_key": wf_key,
                    "workflow_name": wf_name,
                    "product_key": run.product_key,
                    "status": run.status,
                    "trigger_type": run.trigger_type,
                    "location_id": str(run.location_id) if run.location_id else None,
                    "input_document": run.input_document,
                    "output_reference": run.output_reference,
                    "failure_code": run.failure_code,
                    "correlation_id": run.correlation_id,
                    "started_at": run.started_at.isoformat() if run.started_at else None,
                    "completed_at": run.completed_at.isoformat() if run.completed_at else None,
                    "created_at": run.created_at.isoformat() if run.created_at else None,
                    "job_status": job.status if job else None,
                    "job_attempt_count": job.attempt_count if job else None,
                    "job_max_attempts": job.max_attempts if job else None,
                    "job_last_error_category": job.last_error_category if job else None,
                }
            )
        return results, total

    async def get_run(
        self,
        session: AsyncSession,
        organization_id: UUID,
        run_id: UUID,
    ) -> dict[str, object] | None:
        """Return a single workflow run with full job/attempt detail."""
        run = await session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.id == run_id,
            )
        )
        if not run:
            return None

        # Resolve workflow key
        version = await session.get(WorkflowVersion, run.workflow_version_id)
        wf_key: str | None = None
        wf_name: str | None = None
        if version:
            definition = await session.get(WorkflowDefinition, version.definition_id)
            if definition:
                wf_key = definition.key
                wf_name = definition.name

        # Get all jobs for this run
        job_rows = (
            await session.scalars(
                select(Job)
                .where(
                    Job.organization_id == organization_id,
                    Job.workflow_run_id == run_id,
                )
                .order_by(Job.created_at.desc())
            )
        ).all()

        # Get attempts for the latest job
        attempts: list[dict[str, object]] = []
        if job_rows:
            latest_job = job_rows[0]
            attempt_rows = (
                await session.scalars(
                    select(JobAttempt)
                    .where(
                        JobAttempt.organization_id == organization_id,
                        JobAttempt.job_id == latest_job.id,
                    )
                    .order_by(JobAttempt.attempt_number.desc())
                )
            ).all()
            attempts = [
                {
                    "attempt_number": a.attempt_number,
                    "status": a.status,
                    "worker_id": a.worker_id,
                    "started_at": a.started_at.isoformat() if a.started_at else None,
                    "completed_at": a.completed_at.isoformat() if a.completed_at else None,
                    "error_category": a.error_category,
                    "safe_error": a.safe_error,
                }
                for a in attempt_rows
            ]

        return {
            "id": str(run.id),
            "workflow_key": wf_key,
            "workflow_name": wf_name,
            "product_key": run.product_key,
            "status": run.status,
            "trigger_type": run.trigger_type,
            "location_id": str(run.location_id) if run.location_id else None,
            "input_document": run.input_document,
            "output_reference": run.output_reference,
            "failure_code": run.failure_code,
            "correlation_id": run.correlation_id,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "jobs": [
                {
                    "id": str(j.id),
                    "job_type": j.job_type,
                    "status": j.status,
                    "attempt_count": j.attempt_count,
                    "max_attempts": j.max_attempts,
                    "last_error_category": j.last_error_category,
                    "result_reference": j.result_reference,
                    "priority": j.priority,
                    "lease_owner": j.lease_owner,
                    "available_at": j.available_at.isoformat() if j.available_at else None,
                }
                for j in job_rows
            ],
            "latest_attempts": attempts,
        }

    async def list_schedules(
        self,
        session: AsyncSession,
        organization_id: UUID,
    ) -> list[dict[str, object]]:
        """Return all schedules for an organization with workflow context."""
        schedules = (
            await session.scalars(
                select(Schedule)
                .where(
                    Schedule.organization_id == organization_id,
                )
                .order_by(Schedule.created_at.desc())
            )
        ).all()

        # Resolve workflow keys in batch
        version_ids = {s.workflow_version_id for s in schedules}
        def_lookup: dict[UUID, tuple[str, str]] = {}
        if version_ids:
            vers = (
                await session.scalars(
                    select(WorkflowVersion).where(WorkflowVersion.id.in_(version_ids))
                )
            ).all()
            def_ids = {v.definition_id for v in vers}
            defs: dict[UUID, WorkflowDefinition] = {}
            if def_ids:
                def_rows = (
                    await session.scalars(
                        select(WorkflowDefinition).where(WorkflowDefinition.id.in_(def_ids))
                    )
                ).all()
                defs = {d.id: d for d in def_rows}
            for v in vers:
                d = defs.get(v.definition_id)
                if d:
                    def_lookup[v.id] = (d.key, d.name)

        results: list[dict[str, object]] = []
        for s in schedules:
            wf_key, wf_name = def_lookup.get(s.workflow_version_id, (None, None))
            results.append(
                {
                    "id": str(s.id),
                    "key": s.key,
                    "workflow_key": wf_key,
                    "workflow_name": wf_name,
                    "cron_expression": s.cron_expression,
                    "timezone": s.timezone,
                    "status": s.status,
                    "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
                    "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
                    "location_id": str(s.location_id) if s.location_id else None,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
            )
        return results

    async def create_schedule(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: ScheduleCreate,
        *,
        correlation_id: str,
        actor_id: UUID | None = None,
    ) -> Schedule:
        """Create a recurring schedule for a known workflow type.

        The ``workflow_version_id`` is resolved from the workflow type
        catalog — callers supply ``workflow_key`` instead of an opaque
        version id.
        """
        version = await self._resolve_workflow_version(session, command.workflow_key)
        command_dict = command.model_dump(exclude={"workflow_key"})
        command_dict["workflow_version_id"] = version.id

        schedule = Schedule(
            organization_id=organization_id,
            location_id=command.location_id,
            workflow_version_id=version.id,
            key=command.key,
            cron_expression=command.cron_expression,
            timezone=command.timezone,
            status="active",
            next_run_at=command.next_run_at,
            last_run_at=None,
            version=1,
        )
        session.add(schedule)
        await session.flush()

        await self._audit(
            session,
            event="workflow.schedule.created",
            organization_id=organization_id,
            location_id=command.location_id,
            actor_id=actor_id,
            resource_type="workflow_schedule",
            resource_id=schedule.id,
            correlation_id=correlation_id,
            summary=f"Schedule created: {command.key} ({command.cron_expression})",
            metadata={
                "workflow_key": command.workflow_key,
                "cron_expression": command.cron_expression,
                "timezone": command.timezone,
            },
        )
        return schedule

    async def update_schedule(
        self,
        session: AsyncSession,
        organization_id: UUID,
        schedule_id: UUID,
        command: ScheduleUpdate,
        *,
        correlation_id: str,
        actor_id: UUID | None = None,
    ) -> Schedule | None:
        """Update schedule status, cron expression, or next run time."""
        schedule = await session.scalar(
            select(Schedule)
            .where(
                Schedule.organization_id == organization_id,
                Schedule.id == schedule_id,
            )
            .with_for_update()
        )
        if not schedule:
            return None

        if command.status is not None:
            schedule.status = command.status
        if command.cron_expression is not None:
            schedule.cron_expression = command.cron_expression
        if command.next_run_at is not None:
            schedule.next_run_at = command.next_run_at
        if command.timezone is not None:
            schedule.timezone = command.timezone

        await session.flush()

        # Resolve workflow key for audit
        version = await session.get(WorkflowVersion, schedule.workflow_version_id)
        wf_key: str | None = None
        if version:
            definition = await session.get(WorkflowDefinition, version.definition_id)
            if definition:
                wf_key = definition.key

        await self._audit(
            session,
            event="workflow.schedule.updated",
            organization_id=organization_id,
            location_id=schedule.location_id,
            actor_id=actor_id,
            resource_type="workflow_schedule",
            resource_id=schedule.id,
            correlation_id=correlation_id,
            summary=f"Schedule updated: {schedule.key} (status={schedule.status})",
            metadata={
                "workflow_key": wf_key,
                "status": schedule.status,
                "cron_expression": schedule.cron_expression,
            },
        )
        return schedule
