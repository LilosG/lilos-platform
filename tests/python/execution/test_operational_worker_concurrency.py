import asyncio
from typing import Any, cast

import pytest

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.database.runtime import DatabaseRuntime
from apps.api.app.execution.runtime import RuntimeOptions
from apps.worker import runtime as worker_runtime


class FakeOperationalBackend:
    def __init__(
        self,
        _settings: Settings,
        _options: RuntimeOptions,
        database: DatabaseRuntime | None = None,
    ) -> None:
        self.instance_key = "render-instance"
        self.database = database


@pytest.mark.anyio
async def test_operational_worker_runs_bounded_concurrent_slots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, object | None]] = []

    async def fake_run_process(
        backend: FakeOperationalBackend,
        _stop: asyncio.Event,
    ) -> None:
        observed.append((backend.instance_key, backend.database))

    monkeypatch.setattr(worker_runtime, "OperationalWorkerBackend", FakeOperationalBackend)
    monkeypatch.setattr(worker_runtime, "run_process", fake_run_process)

    settings = Settings(environment=EnvironmentName.TEST, worker_concurrency=3)
    await worker_runtime.run_operational_worker(
        settings,
        asyncio.Event(),
        RuntimeOptions(shutdown_seconds=1, cycle_seconds=1),
    )

    assert {instance_key for instance_key, _ in observed} == {
        "render-instance:1",
        "render-instance:2",
        "render-instance:3",
    }
    assert all(database is None for _, database in observed)


@pytest.mark.anyio
async def test_injected_database_keeps_worker_single_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[str, object | None]] = []

    async def fake_run_process(
        backend: FakeOperationalBackend,
        _stop: asyncio.Event,
    ) -> None:
        observed.append((backend.instance_key, backend.database))

    monkeypatch.setattr(worker_runtime, "OperationalWorkerBackend", FakeOperationalBackend)
    monkeypatch.setattr(worker_runtime, "run_process", fake_run_process)

    injected = cast(DatabaseRuntime, cast(Any, object()))
    settings = Settings(environment=EnvironmentName.TEST, worker_concurrency=4)
    await worker_runtime.run_operational_worker(
        settings,
        asyncio.Event(),
        RuntimeOptions(shutdown_seconds=1, cycle_seconds=1),
        database=injected,
    )

    assert observed == [("render-instance:1", injected)]


@pytest.mark.anyio
async def test_operational_worker_slot_restarts_after_unexpected_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = {"count": 0}
    stop = asyncio.Event()

    async def flaky_run_process(
        _backend: FakeOperationalBackend,
        _stop: asyncio.Event,
    ) -> None:
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("synthetic worker-slot crash")
        stop.set()

    monkeypatch.setattr(worker_runtime, "OperationalWorkerBackend", FakeOperationalBackend)
    monkeypatch.setattr(worker_runtime, "run_process", flaky_run_process)

    settings = Settings(environment=EnvironmentName.TEST, worker_concurrency=1)
    await worker_runtime._run_operational_worker_slot(
        settings,
        stop,
        RuntimeOptions(
            minimum_poll_seconds=0.001,
            maximum_poll_seconds=0.001,
            shutdown_seconds=1,
            cycle_seconds=1,
        ),
        slot=1,
        database=None,
    )

    assert calls["count"] == 2

