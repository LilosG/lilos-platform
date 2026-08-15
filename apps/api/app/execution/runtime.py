"""Production process adapters for the durable PostgreSQL execution foundation."""

import asyncio
import logging
import os
import signal
import socket
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from types import FrameType

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DataError, IntegrityError, ProgrammingError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config import Settings
from apps.api.app.database.runtime import DatabaseRuntime, create_database_runtime
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.models import Job, WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.execution.service import ExecutionService
from apps.api.app.observability.models import ServiceHeartbeat
from apps.api.app.observability.telemetry import MetricPoint

logger = logging.getLogger("lilos")

# Database errors that are deterministic: retrying them yields the identical
# failure, so they must fail the individual job rather than the process loop.
DETERMINISTIC_DB_ERRORS = (IntegrityError, DataError, ProgrammingError)


def is_deterministic_db_error(exc: BaseException) -> bool:
    """Return whether an exception is a deterministic (non-transient) DB error."""
    return isinstance(exc, DETERMINISTIC_DB_ERRORS)


def postgres_error_context(exc: BaseException) -> dict[str, object]:
    """Extract a safe, redacted Postgres error context for diagnostics.

    ``IntegrityError`` and friends carry the underlying driver exception on
    ``.orig``, exposing the constraint name, table, and detail. A detail
    message contains row values, so only the column context (the portion
    before any ``=``) is retained — never the values.
    """
    orig = getattr(exc, "orig", None)
    detail = getattr(orig, "detail", None)
    safe_detail: str | None = None
    if isinstance(detail, str) and "=" in detail:
        safe_detail = detail.split("=", 1)[0].strip() or None
    return {
        "constraint_name": getattr(orig, "constraint_name", None),
        "table_name": getattr(orig, "table_name", None),
        "schema_name": getattr(orig, "schema_name", None),
        "sqlstate": getattr(orig, "sqlstate", None),
        "safe_detail": safe_detail,
    }


@dataclass(frozen=True, slots=True)
class RuntimeOptions:
    """Bounded process timing policy; tests may inject shorter intervals."""

    minimum_poll_seconds: float = 1.0
    maximum_poll_seconds: float = 10.0
    heartbeat_seconds: float = 15.0
    lease_seconds: int = 60
    sweep_seconds: float = 60.0
    sweep_batch_size: int = 100
    database_failure_limit: int = 3
    shutdown_seconds: float = 270.0

    def __post_init__(self) -> None:
        if not 0 < self.minimum_poll_seconds <= self.maximum_poll_seconds:
            raise ValueError("poll bounds are invalid")
        if not 0 < self.heartbeat_seconds <= 60:
            raise ValueError("heartbeat interval is invalid")
        if not 5 <= self.lease_seconds <= 3600:
            raise ValueError("lease duration is invalid")
        if not 0 < self.sweep_seconds <= 3600:
            raise ValueError("sweep interval is invalid")
        if self.sweep_batch_size < 1:
            raise ValueError("sweep batch size is invalid")
        if self.database_failure_limit < 1:
            raise ValueError("database failure limit is invalid")
        if self.shutdown_seconds <= 0:
            raise ValueError("shutdown allowance is invalid")


def process_instance_key() -> str:
    """Return a bounded non-secret identity for heartbeat and lease ownership."""
    return (os.getenv("RENDER_INSTANCE_ID") or socket.gethostname())[:128]


class DurableProcessBackend:
    """Shared database, heartbeat, and lifecycle behavior for background processes."""

    def __init__(
        self,
        settings: Settings,
        service_name: str,
        options: RuntimeOptions,
        database: DatabaseRuntime | None = None,
    ) -> None:
        self.settings = settings
        self.service_name = service_name
        self.options = options
        self.instance_key = process_instance_key()
        self.database = database or create_database_runtime(settings)
        self.sessions = self.database.require_session_factory()

    async def startup(self) -> None:
        async with self.database.require_engine().connect() as connection:
            await connection.execute(text("SELECT 1"))
        await self.heartbeat("running")

    async def heartbeat(self, status: str) -> None:
        now = datetime.now(UTC)
        statement = insert(ServiceHeartbeat).values(
            environment=self.settings.environment.value,
            service=self.service_name,
            instance_key=self.instance_key,
            release=self.settings.release,
            status=status,
            last_seen_at=now,
            safe_details={"process": "durable-postgresql"},
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_service_heartbeat",
            set_={
                "release": statement.excluded.release,
                "status": statement.excluded.status,
                "last_seen_at": statement.excluded.last_seen_at,
                "safe_details": statement.excluded.safe_details,
                "updated_at": now,
            },
        )
        async with self.sessions() as session, session.begin():
            await session.execute(statement)

    async def cycle(self) -> bool:
        raise NotImplementedError

    async def sweep(self) -> None:
        """Periodic reconciliation hook; the base process performs no work."""

    async def close(self) -> None:
        await self.database.dispose()


class WorkerBackend(DurableProcessBackend):
    """Claim and complete jobs through the established lease/retry service."""

    def __init__(
        self,
        settings: Settings,
        options: RuntimeOptions,
        database: DatabaseRuntime | None = None,
    ) -> None:
        super().__init__(settings, "lilos-worker", options, database)
        self.execution = ExecutionService()

    async def cycle(self) -> bool:
        async with self.sessions() as session, session.begin():
            job = await self.execution.claim(session, self.instance_key, self.options.lease_seconds)
        if job is None:
            return False

        started = monotonic()
        outcome = await self._execute_with_lease(job)
        MetricPoint.create(
            "jobs.completed",
            1,
            {
                "service": self.service_name,
                "operation": job.job_type,
                "outcome": outcome.result,
            },
        )
        logger.info(
            "Durable job attempt completed",
            extra={
                "event_name": "worker.job.completed",
                "job_id": str(job.id),
                "workflow_run_id": str(job.workflow_run_id),
                "operation": job.job_type,
                "outcome": outcome.result,
                "duration_ms": round((monotonic() - started) * 1000, 3),
                "retry_count": job.attempt_count,
            },
        )
        return True

    async def sweep(self) -> None:
        """Reconcile abandoned leases that have no live worker owner."""
        async with self.sessions() as session, session.begin():
            await self.execution.sweep_abandoned_leases(
                session, limit=self.options.sweep_batch_size
            )

    async def _execute_with_lease(self, job: Job) -> JobOutcome:
        task = asyncio.create_task(self._execute(job))
        process_safe_timeout = max(0.1, self.options.shutdown_seconds - 1)
        deadline = monotonic() + min(job.timeout_seconds, process_safe_timeout)
        renewal_interval = min(self.options.heartbeat_seconds, self.options.lease_seconds / 2)
        try:
            while True:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                    outcome = JobOutcome(result="retryable_failure", safe_error="JOB_TIMEOUT")
                    async with self.sessions() as session, session.begin():
                        await self.execution.finish(session, job.organization_id, job.id, outcome)
                    return outcome
                done, _ = await asyncio.wait(
                    {task},
                    timeout=min(renewal_interval, remaining),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if task in done:
                    return task.result()

                # The task may complete after asyncio.wait() times out but before
                # lease renewal starts. Avoid treating successful completion as
                # lease loss.
                if task.done():
                    return task.result()

                async with self.sessions() as session, session.begin():
                    renewed = await self.execution.renew_lease(
                        session,
                        job.organization_id,
                        job.id,
                        self.instance_key,
                        self.options.lease_seconds,
                    )

                if not renewed:
                    # The task may have completed and released its lease while
                    # the renewal transaction was executing.
                    if task.done():
                        return task.result()

                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                    raise RuntimeError("durable job lease was lost")
        except asyncio.CancelledError:
            if not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            raise

    async def _execute(self, job: Job) -> JobOutcome:
        async with self.sessions() as session, session.begin():
            if job.job_type == "workflow.execute":
                outcome = await _execute_workflow_job(session, job)
            else:
                outcome = JobOutcome(result="permanent_failure", safe_error="JOB_TYPE_UNSUPPORTED")
            await self.execution.finish(session, job.organization_id, job.id, outcome)
            return outcome


async def _execute_workflow_job(session: AsyncSession, job: Job) -> JobOutcome:
    """Execute a workflow job using registered step handlers or the deterministic envelope."""
    run = await session.scalar(
        select(WorkflowRun)
        .where(
            WorkflowRun.organization_id == job.organization_id,
            WorkflowRun.id == job.workflow_run_id,
        )
        .with_for_update()
    )
    if run is None:
        return JobOutcome(result="permanent_failure", safe_error="WORKFLOW_RUN_MISSING")
    if run.status == "cancelled" or run.cancelled_at is not None:
        return JobOutcome(result="permanent_failure", safe_error="WORKFLOW_CANCELLED")
    version = await session.get(WorkflowVersion, run.workflow_version_id)
    if version is None or version.status != "approved":
        run.status = "failed"
        run.failure_code = "WORKFLOW_VERSION_NOT_EXECUTABLE"
        return JobOutcome(result="permanent_failure", safe_error="WORKFLOW_VERSION_NOT_EXECUTABLE")

    definition = await session.get(WorkflowDefinition, version.definition_id)
    workflow_key = definition.key if definition else None

    if workflow_key:
        from apps.api.app.execution.handlers import get_workflow_handler
        from apps.api.app.execution.workflow_catalog import is_known_workflow_key

        handler = get_workflow_handler(workflow_key)
        if handler is not None:
            now = datetime.now(UTC)
            run.status = "running"
            run.started_at = run.started_at or now
            await session.flush()

            try:
                async with session.begin_nested():
                    outcome = await handler(
                        session,
                        organization_id=run.organization_id,
                        location_id=run.location_id,
                        input_document=run.input_document,
                        correlation_id=f"workflow-{run.id}",
                    )
            except DETERMINISTIC_DB_ERRORS as exc:
                run.status = "failed"
                run.failure_code = "DATABASE_DETERMINISTIC_ERROR"
                logger.error(
                    "Workflow handler raised a deterministic database error",
                    extra={
                        "event_name": "workflow.handler.database_error",
                        "workflow_key": workflow_key,
                        "workflow_run_id": str(run.id),
                        "exception_type": type(exc).__name__,
                        **postgres_error_context(exc),
                    },
                )
                return JobOutcome(
                    result="permanent_failure", safe_error="DATABASE_DETERMINISTIC_ERROR"
                )
            except Exception as exc:
                run.status = "failed"
                run.failure_code = "HANDLER_EXCEPTION"
                logger.exception(
                    "Workflow handler raised an exception",
                    extra={
                        "event_name": "workflow.handler.exception",
                        "workflow_key": workflow_key,
                        "workflow_run_id": str(run.id),
                        "error": str(exc)[:200],
                    },
                )
                return JobOutcome(result="permanent_failure", safe_error="HANDLER_EXCEPTION")

            if outcome.result == "succeeded":
                run.status = "completed"
                run.completed_at = datetime.now(UTC)
                run.output_reference = outcome.result_reference
            elif outcome.result in ("permanent_failure", "retryable_failure"):
                run.status = "failed"
                run.failure_code = outcome.safe_error
            await session.flush()
            return outcome

        if is_known_workflow_key(workflow_key):
            run.status = "failed"
            run.failure_code = "WORKFLOW_HANDLER_NOT_REGISTERED"
            return JobOutcome(
                result="permanent_failure", safe_error="WORKFLOW_HANDLER_NOT_REGISTERED"
            )

    now = datetime.now(UTC)
    run.status = "completed"
    run.started_at = run.started_at or now
    run.completed_at = now
    run.output_reference = f"workflow-run:{run.id}"
    await session.flush()
    return JobOutcome(result="succeeded", result_reference=run.output_reference)


class SchedulerBackend(DurableProcessBackend):
    """Atomically advance due schedules and enqueue their durable workflow jobs."""

    def __init__(
        self,
        settings: Settings,
        options: RuntimeOptions,
        database: DatabaseRuntime | None = None,
    ) -> None:
        super().__init__(settings, "lilos-scheduler", options, database)
        self.execution = ExecutionService()

    async def cycle(self) -> bool:
        correlation_id = f"schedule-{self.instance_key}"[:64]
        async with self.sessions() as session, session.begin():
            run = await self.execution.dispatch_due_schedule(session, correlation_id)
        if run is None:
            return False
        MetricPoint.create(
            "schedules.dispatched",
            1,
            {"service": self.service_name, "operation": "dispatch", "outcome": "success"},
        )
        logger.info(
            "Durable schedule dispatched",
            extra={
                "event_name": "scheduler.schedule.dispatched",
                "workflow_run_id": str(run.id),
                "operation": "dispatch",
                "outcome": "success",
            },
        )
        return True


BackendFactory = Callable[[Settings, RuntimeOptions], DurableProcessBackend]


async def run_process(
    backend: DurableProcessBackend,
    stop: asyncio.Event,
) -> None:
    """Run bounded polling until signalled, failing after consecutive database errors."""
    delay = backend.options.minimum_poll_seconds
    failures = 0
    next_heartbeat = monotonic()
    next_sweep = monotonic()
    started = False
    try:
        await backend.startup()
        started = True
        logger.info(
            "Durable process started",
            extra={
                "event_name": "process.started",
                "operation": "startup",
                "outcome": "success",
            },
        )
        while not stop.is_set():
            try:
                if monotonic() >= next_heartbeat:
                    await backend.heartbeat("running")
                    next_heartbeat = monotonic() + backend.options.heartbeat_seconds
                if monotonic() >= next_sweep:
                    await backend.sweep()
                    next_sweep = monotonic() + backend.options.sweep_seconds
                worked = await asyncio.wait_for(
                    backend.cycle(), timeout=backend.options.shutdown_seconds
                )
                failures = 0
            except SQLAlchemyError as exc:
                context = postgres_error_context(exc)
                if is_deterministic_db_error(exc):
                    logger.error(
                        "Durable process encountered a deterministic database error",
                        extra={
                            "event_name": "process.database.deterministic_error",
                            "operation": "poll",
                            "outcome": "failure",
                            "normalized_error_code": "DATABASE_DETERMINISTIC_ERROR",
                            "exception_type": type(exc).__name__,
                            **context,
                        },
                    )
                    worked = False
                else:
                    failures += 1
                    logger.error(
                        "Durable process database operation failed",
                        extra={
                            "event_name": "process.database.failed",
                            "operation": "poll",
                            "outcome": "failure",
                            "normalized_error_code": "DATABASE_UNAVAILABLE",
                            "exception_type": type(exc).__name__,
                            "retry_count": failures,
                            **context,
                        },
                    )
                    if failures >= backend.options.database_failure_limit:
                        raise
                    worked = False
            except TimeoutError:
                logger.error(
                    "Durable process cycle timed out",
                    extra={
                        "event_name": "process.cycle.timed_out",
                        "operation": "poll",
                        "outcome": "failure",
                        "normalized_error_code": "PROCESS_CYCLE_TIMEOUT",
                    },
                )
                raise

            if worked:
                delay = backend.options.minimum_poll_seconds
                await asyncio.sleep(0)
                continue
            delay = min(backend.options.maximum_poll_seconds, max(delay * 2, delay))
            with suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=delay)
    finally:
        if started:
            try:
                await backend.heartbeat("stopping")
            except SQLAlchemyError:
                logger.error(
                    "Final process heartbeat failed",
                    extra={
                        "event_name": "process.heartbeat.failed",
                        "operation": "shutdown",
                        "outcome": "failure",
                        "normalized_error_code": "DATABASE_UNAVAILABLE",
                    },
                )
        await backend.close()
        logger.info(
            "Durable process stopped",
            extra={"event_name": "process.stopped", "operation": "shutdown", "outcome": "success"},
        )


async def run_worker(
    settings: Settings,
    stop: asyncio.Event,
    options: RuntimeOptions | None = None,
    database: DatabaseRuntime | None = None,
) -> None:
    await run_process(WorkerBackend(settings, options or RuntimeOptions(), database), stop)


async def run_scheduler(
    settings: Settings,
    stop: asyncio.Event,
    options: RuntimeOptions | None = None,
    database: DatabaseRuntime | None = None,
) -> None:
    scheduler_options = options or RuntimeOptions(shutdown_seconds=45.0)
    await run_process(SchedulerBackend(settings, scheduler_options, database), stop)


def install_signal_handlers(stop: asyncio.Event) -> None:
    """Translate termination signals into cooperative process shutdown."""
    loop = asyncio.get_running_loop()

    def request_stop(_signal: int | None = None, _frame: FrameType | None = None) -> None:
        stop.set()

    for process_signal in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(process_signal, request_stop)
        except NotImplementedError:
            signal.signal(process_signal, request_stop)


async def process_main(
    service_name: str,
    runner: Callable[[Settings, asyncio.Event], Awaitable[None]],
) -> int:
    """Validate configuration, own signals, and return a process exit status."""
    from apps.api.app.logging_config import configure_logging

    try:
        settings = Settings()
        configure_logging(settings, service_name)
        if settings.application_database_url() is None:
            raise ValueError("database configuration is required")
        stop = asyncio.Event()
        install_signal_handlers(stop)
        await runner(settings, stop)
    except Exception as exc:
        logger.error(
            "Durable process terminated",
            extra={
                "event_name": "process.terminated",
                "operation": "runtime",
                "outcome": "failure",
                "normalized_error_code": "PROCESS_CONFIGURATION_OR_DATABASE_FAILURE",
                "exception_type": type(exc).__name__,
            },
        )
        return 1
    return 0
