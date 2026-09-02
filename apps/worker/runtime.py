"""Production worker policy with self-healing execution reconciliation."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from time import monotonic

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config import Settings
from apps.api.app.database.runtime import DatabaseRuntime
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.models import (
    Job,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from apps.api.app.execution.runtime import RuntimeOptions, WorkerBackend, run_process
from apps.api.app.execution.service import ExecutionService
from apps.worker.recovery import reconcile_exhausted_workflows, reconcile_worker_state

logger = logging.getLogger("lilos")


class OperationalExecutionService(ExecutionService):
    """Apply workflow-version execution policy when a durable job is claimed."""

    async def claim(
        self,
        session: AsyncSession,
        worker_id: str,
        lease_seconds: int = 60,
    ) -> Job | None:
        # Old builds could leave retry_scheduled jobs at max_attempts. Repair
        # those before the base claimer increments attempt_count again.
        await reconcile_exhausted_workflows(session, limit=100)
        job = await super().claim(session, worker_id, lease_seconds)
        if job is None:
            return None

        run = await session.get(WorkflowRun, job.workflow_run_id)
        version = await session.get(WorkflowVersion, run.workflow_version_id) if run else None
        definition = (
            await session.get(WorkflowDefinition, version.definition_id) if version else None
        )
        if version is not None:
            job.timeout_seconds = max(job.timeout_seconds, version.timeout_seconds)
        if definition is not None and definition.key.startswith("agent."):
            # Hermes agents are long-running provider jobs. Three generic queue
            # attempts were too brittle for transient stream/session recovery.
            job.max_attempts = max(job.max_attempts, 5)
            job.timeout_seconds = max(job.timeout_seconds, 900)
        await session.flush()
        return job


class OperationalWorkerBackend(WorkerBackend):
    """Worker backend that heals stale queue/agent boundaries automatically."""

    def __init__(
        self,
        settings: Settings,
        options: RuntimeOptions,
        database: DatabaseRuntime | None = None,
    ) -> None:
        super().__init__(settings, options, database)
        self.execution = OperationalExecutionService()

    async def sweep(self) -> None:
        await super().sweep()
        try:
            result = await reconcile_worker_state(self.sessions, self.settings)
        except Exception:
            # Reconciliation must never take the worker down. The durable queue
            # keeps polling and the next bounded sweep will retry recovery.
            logger.exception(
                "Worker operational reconciliation failed",
                extra={
                    "event_name": "worker.reconciliation.failed",
                    "operation": "reconcile",
                    "outcome": "failure",
                },
            )
            return
        if any(result.values()):
            logger.info(
                "Worker operational state reconciled",
                extra={
                    "event_name": "worker.reconciliation.completed",
                    "operation": "reconcile",
                    "outcome": "success",
                    **result,
                },
            )

    async def _execute_with_lease(self, job: Job) -> JobOutcome:
        """Honor the job timeout while renewing its durable lease.

        The core worker historically capped every attempt by the 270-second
        shutdown grace period. That made the 900-second agent workflow contract
        unreachable. The process cycle now owns the hard attempt budget; Render
        may still terminate a deployment after its shutdown grace, in which case
        the lease sweeper safely reclaims the job on the replacement worker.
        """
        task = asyncio.create_task(self._execute(job))
        cycle_safe_timeout = max(0.1, self.options.cycle_seconds - 1)
        deadline = monotonic() + min(job.timeout_seconds, cycle_safe_timeout)
        renewal_interval = min(
            self.options.heartbeat_seconds,
            self.options.lease_seconds / 2,
        )
        try:
            while True:
                remaining = deadline - monotonic()
                if remaining <= 0:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                    outcome = JobOutcome(
                        result="retryable_failure",
                        safe_error="JOB_TIMEOUT",
                    )
                    async with self.sessions() as session, session.begin():
                        await self.execution.finish(
                            session,
                            job.organization_id,
                            job.id,
                            outcome,
                        )
                    return outcome

                done, _ = await asyncio.wait(
                    {task},
                    timeout=min(renewal_interval, remaining),
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if task in done:
                    return task.result()
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
                if renewed:
                    continue
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


async def run_operational_worker(
    settings: Settings,
    stop: asyncio.Event,
    options: RuntimeOptions | None = None,
    database: DatabaseRuntime | None = None,
) -> None:
    worker_options = options or RuntimeOptions(
        shutdown_seconds=270.0,
        cycle_seconds=960.0,
    )
    backend = OperationalWorkerBackend(settings, worker_options, database)
    await run_process(backend, stop)
