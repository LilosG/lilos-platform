from collections.abc import Awaitable, Callable

import pytest

from apps.scheduler import __main__ as scheduler_entrypoint
from apps.worker import __main__ as worker_entrypoint


def _exit_runner(exit_code: int) -> Callable[[str, Callable[..., Awaitable[None]]], Awaitable[int]]:
    async def run(_service: str, _runner: Callable[..., Awaitable[None]]) -> int:
        return exit_code

    return run


def test_worker_entrypoint_returns_runtime_exit_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker_entrypoint, "process_main", _exit_runner(0))
    assert worker_entrypoint.main() == 0


def test_scheduler_entrypoint_returns_fail_closed_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(scheduler_entrypoint, "process_main", _exit_runner(1))
    assert scheduler_entrypoint.main() == 1
