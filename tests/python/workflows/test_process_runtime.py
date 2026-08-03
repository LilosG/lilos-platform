import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from pydantic import PostgresDsn, TypeAdapter
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.execution import runtime as runtime_module
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.models import Job, Schedule, WorkflowRun
from apps.api.app.execution.runtime import (
    DurableProcessBackend,
    RuntimeOptions,
    SchedulerBackend,
    WorkerBackend,
    install_signal_handlers,
    process_main,
    run_process,
)
from apps.api.app.observability.models import ServiceHeartbeat

ROOT = Path(__file__).resolve().parents[3]
POSTGRES_DSN = TypeAdapter(PostgresDsn)


class FakeBackend(DurableProcessBackend):
    def __init__(
        self,
        options: RuntimeOptions,
        cycles: list[bool | Exception],
        on_cycle: Callable[[int], None] | None = None,
    ) -> None:
        self.options = options
        self.cycles = cycles
        self.on_cycle = on_cycle
        self.started = False
        self.closed = False
        self.heartbeats: list[str] = []
        self.cycle_times: list[float] = []
        self.startup_error: Exception | None = None

    async def startup(self) -> None:
        self.started = True
        if self.startup_error is not None:
            raise self.startup_error

    async def heartbeat(self, status: str) -> None:
        self.heartbeats.append(status)

    async def cycle(self) -> bool:
        self.cycle_times.append(asyncio.get_running_loop().time())
        index = len(self.cycle_times) - 1
        if self.on_cycle is not None:
            self.on_cycle(index)
        value = self.cycles[min(index, len(self.cycles) - 1)]
        if isinstance(value, Exception):
            raise value
        return value

    async def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
async def test_process_continues_with_bounded_idle_backoff_and_heartbeat() -> None:
    stop = asyncio.Event()
    options = RuntimeOptions(
        minimum_poll_seconds=0.005,
        maximum_poll_seconds=0.01,
        heartbeat_seconds=0.01,
        shutdown_seconds=1,
    )
    backend = FakeBackend(options, [False], lambda index: stop.set() if index == 3 else None)

    await run_process(backend, stop)

    assert backend.started and backend.closed
    assert len(backend.cycle_times) == 4
    intervals = [
        second - first
        for first, second in zip(backend.cycle_times, backend.cycle_times[1:], strict=False)
    ]
    assert all(interval >= options.minimum_poll_seconds for interval in intervals)
    assert all(interval < 0.05 for interval in intervals)
    assert backend.heartbeats[0] == "running"
    assert backend.heartbeats[-1] == "stopping"


@pytest.mark.anyio
async def test_process_fails_closed_after_bounded_database_failures() -> None:
    options = RuntimeOptions(
        minimum_poll_seconds=0.001,
        maximum_poll_seconds=0.001,
        heartbeat_seconds=1,
        database_failure_limit=2,
        shutdown_seconds=1,
    )
    backend = FakeBackend(options, [SQLAlchemyError("synthetic")])

    with pytest.raises(SQLAlchemyError):
        await run_process(backend, asyncio.Event())

    assert len(backend.cycle_times) == 2
    assert backend.closed


@pytest.mark.anyio
async def test_startup_failure_closes_database_resources() -> None:
    backend = FakeBackend(RuntimeOptions(shutdown_seconds=1), [False])
    backend.startup_error = SQLAlchemyError("synthetic startup failure")

    with pytest.raises(SQLAlchemyError):
        await run_process(backend, asyncio.Event())

    assert backend.started and backend.closed
    assert backend.cycle_times == []


@pytest.mark.anyio
async def test_shutdown_finishes_inflight_cycle_without_claiming_more() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    stop = asyncio.Event()
    backend = FakeBackend(RuntimeOptions(shutdown_seconds=1), [False])

    async def blocking_cycle() -> bool:
        backend.cycle_times.append(asyncio.get_running_loop().time())
        started.set()
        await release.wait()
        return False

    backend.cycle = blocking_cycle  # type: ignore[method-assign]
    process = asyncio.create_task(run_process(backend, stop))
    await started.wait()
    stop.set()
    await asyncio.sleep(0)
    assert not process.done()
    release.set()
    await process

    assert len(backend.cycle_times) == 1
    assert backend.closed


@pytest.mark.anyio
async def test_signal_handlers_request_cooperative_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callbacks: list[Callable[[], None]] = []
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(
        loop, "add_signal_handler", lambda _signal, callback: callbacks.append(callback)
    )
    stop = asyncio.Event()

    install_signal_handlers(stop)
    assert len(callbacks) == 2
    callbacks[0]()
    assert stop.is_set()


@pytest.mark.anyio
async def test_process_main_fails_closed_on_invalid_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def invalid_settings() -> Settings:
        raise ValueError("synthetic invalid configuration")

    async def unused_runner(_settings: Settings, _stop: asyncio.Event) -> None:
        raise AssertionError("runner must not start")

    monkeypatch.setattr(runtime_module, "Settings", invalid_settings)
    assert await process_main("lilos-worker", unused_runner) == 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_postgresql_worker_scheduler_and_heartbeat_contracts(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    await asyncio.to_thread(command.upgrade, config, "head")
    settings = Settings(
        environment=EnvironmentName.TEST,
        database_url=POSTGRES_DSN.validate_python(postgresql_test_url),
        release="runtime-test",
    )
    runtime = create_database_runtime(settings)
    engine = runtime.require_engine()
    organization_id = uuid4()
    definition_id = uuid4()
    version_id = uuid4()
    run_id = uuid4()
    job_id = uuid4()
    schedule_id = uuid4()
    now = datetime.now(UTC)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO organizations
                        (id, name, slug, organization_type, status, timezone, default_currency)
                    VALUES
                        (:organization_id, 'Runtime Test', :slug, 'test', 'active', 'UTC', 'USD')
                    """
                ),
                {"organization_id": organization_id, "slug": f"runtime-{organization_id.hex[:12]}"},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO workflow_definitions (id, key, name, owner, status)
                    VALUES (:definition_id, :definition_key, 'Runtime Test', 'platform', 'active')
                    """
                ),
                {"definition_id": definition_id, "definition_key": f"runtime.{definition_id.hex}"},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO workflow_versions
                        (id, definition_id, version, status, input_schema, output_schema,
                         step_specification, retry_policy, timeout_seconds)
                    VALUES
                        (:version_id, :definition_id, 1, 'approved', '{}'::jsonb, '{}'::jsonb,
                         '[]'::jsonb, '{}'::jsonb, 30)
                    """
                ),
                {"version_id": version_id, "definition_id": definition_id},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO workflow_runs
                        (id, organization_id, workflow_version_id, status, trigger_type,
                         idempotency_key, request_hash, input_document, correlation_id)
                    VALUES
                        (:run_id, :organization_id, :version_id, 'queued', 'api', :run_key,
                         repeat('a', 64), '{}'::jsonb, 'runtime-test')
                    """
                ),
                {
                    "run_id": run_id,
                    "organization_id": organization_id,
                    "version_id": version_id,
                    "run_key": f"runtime-run-{run_id}",
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO jobs
                        (id, organization_id, workflow_run_id, job_type, status, idempotency_key,
                         payload, available_at)
                    VALUES
                        (:job_id, :organization_id, :run_id, 'workflow.execute', 'queued', :job_key,
                         jsonb_build_object('run_id', CAST(:run_id_text AS text)), :now)
                    """
                ),
                {
                    "job_id": job_id,
                    "organization_id": organization_id,
                    "run_id": run_id,
                    "run_id_text": str(run_id),
                    "job_key": f"runtime-job-{job_id}",
                    "now": now,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO workflow_schedules
                        (id, organization_id, workflow_version_id, key, cron_expression, timezone,
                         status, next_run_at)
                    VALUES
                        (:schedule_id, :organization_id, :version_id, :schedule_key, '* * * * *',
                         'UTC', 'active', :due_at)
                    """
                ),
                {
                    "organization_id": organization_id,
                    "version_id": version_id,
                    "schedule_id": schedule_id,
                    "schedule_key": f"runtime-schedule-{schedule_id}",
                    "due_at": now - timedelta(minutes=1),
                },
            )

        options = RuntimeOptions(
            minimum_poll_seconds=0.01,
            maximum_poll_seconds=0.02,
            heartbeat_seconds=0.01,
            shutdown_seconds=5,
        )
        worker = WorkerBackend(settings, options, runtime)
        await worker.startup()
        renewals = 0
        original_renew = worker.execution.renew_lease

        async def counted_renew(*args: Any, **kwargs: Any) -> bool:
            nonlocal renewals
            renewals += 1
            return await original_renew(*args, **kwargs)

        original_execute = runtime_module._execute_workflow_job

        async def delayed_execute(session: AsyncSession, job: Job) -> JobOutcome:
            await asyncio.sleep(0.03)
            return await original_execute(session, job)

        monkeypatch.setattr(worker.execution, "renew_lease", counted_renew)
        monkeypatch.setattr(runtime_module, "_execute_workflow_job", delayed_execute)
        assert await worker.cycle()
        assert renewals >= 1

        scheduler = SchedulerBackend(settings, options, runtime)
        await scheduler.startup()
        assert await scheduler.cycle()

        async with engine.connect() as connection:
            completed_job = await connection.scalar(select(Job.status).where(Job.id == job_id))
            completed_run = await connection.scalar(
                select(WorkflowRun.status).where(WorkflowRun.id == run_id)
            )
            schedule = (
                await connection.execute(select(Schedule).where(Schedule.id == schedule_id))
            ).scalar_one()
            heartbeats = (
                (
                    await connection.execute(
                        select(ServiceHeartbeat).where(
                            ServiceHeartbeat.release == "runtime-test",
                            ServiceHeartbeat.service.in_(("lilos-worker", "lilos-scheduler")),
                        )
                    )
                )
                .scalars()
                .all()
            )

        assert completed_job == "completed"
        assert completed_run == "completed"
        assert schedule.last_run_at == now - timedelta(minutes=1)
        assert schedule.next_run_at > now
        assert {heartbeat.service for heartbeat in heartbeats} == {
            "lilos-worker",
            "lilos-scheduler",
        }
    finally:
        await runtime.dispose()
