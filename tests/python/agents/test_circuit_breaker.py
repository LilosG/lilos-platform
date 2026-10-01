"""One tool failing twice with the same typed code ends the run as failed."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from apps.api.app.agents.tools import (
    ACTIVE_RUN_STATUSES,
    TOOL_FAILURE_LIMIT,
    AgentToolDeniedError,
    AgentToolService,
)


class _Audit:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def record(self, _session: object, command: Any) -> None:
        self.events.append(command)


class _Session:
    """Counts recorded tool audit events the way the real query does."""

    def __init__(self, audit: _Audit) -> None:
        self.audit = audit

    def begin_nested(self) -> Any:
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def manager() -> Any:
            yield

        return manager()

    async def flush(self) -> None:
        return None

    async def get(self, *_args: object) -> None:
        return None

    async def scalar(self, _statement: object) -> int:
        tool_events = [e for e in self.audit.events if e.event_type == "agent.tool.invoked"]
        last = tool_events[-1].metadata
        return sum(
            1
            for e in tool_events
            if e.metadata["tool_name"] == last["tool_name"]
            and e.metadata["error_code"] == last["error_code"]
        )


def _run() -> Any:
    return SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        location_id=uuid4(),
        workflow_run_id=uuid4(),
        correlation_id="corr",
        skill_key="content.operator",
        status="running",
        safe_error_code=None,
        completed_at=None,
        final_output=None,
        source_references=[],
        output_references=[],
    )


def _service(handler: Any, audit: _Audit) -> AgentToolService:
    service = AgentToolService()
    service.audit = audit  # type: ignore[assignment]
    setattr(service, "_tool_generate_content_draft_proposal", handler)  # noqa: B010
    return service


async def _loop(service: AgentToolService, run: Any, session: Any, calls: int) -> int:
    """Mimic Hermes calling the tool repeatedly; the runtime refuses once the run is not active."""
    made = 0
    for _ in range(calls):
        if run.status not in ACTIVE_RUN_STATUSES:
            break
        made += 1
        with pytest.raises(AgentToolDeniedError):
            await service.invoke(session, run, "generate_content_draft_proposal", {})
    return made


@pytest.mark.anyio
async def test_nine_call_loop_stops_at_two_and_the_run_is_failed_with_the_code() -> None:
    audit = _Audit()

    async def unresolved(*_args: object) -> dict[str, object]:
        raise AgentToolDeniedError("no attributed page", code="CONTENT_SEO_TARGET_UNRESOLVED")

    run = _run()
    made = await _loop(_service(unresolved, audit), run, _Session(audit), calls=9)

    assert made == TOOL_FAILURE_LIMIT == 2
    assert run.status == "failed"
    assert run.safe_error_code == "CONTENT_SEO_TARGET_UNRESOLVED"
    assert run.completed_at is not None
    assert datetime.now(UTC) >= run.completed_at
    assert [e.event_type for e in audit.events].count("agent.run.circuit_open") == 1


@pytest.mark.anyio
async def test_different_error_codes_do_not_trip_the_breaker() -> None:
    audit = _Audit()
    codes = iter(["CODE_A", "CODE_B", "CODE_A"])

    async def varied(*_args: object) -> dict[str, object]:
        raise AgentToolDeniedError("nope", code=next(codes))

    run = _run()
    made = await _loop(_service(varied, audit), run, _Session(audit), calls=3)

    assert made == 3
    assert run.status == "failed"  # CODE_A failed twice, on the third call
    assert run.safe_error_code == "CODE_A"


@pytest.mark.anyio
async def test_a_single_failure_leaves_the_run_active() -> None:
    audit = _Audit()

    async def once(*_args: object) -> dict[str, object]:
        raise AgentToolDeniedError("nope", code="ONLY_ONCE")

    run = _run()
    assert await _loop(_service(once, audit), run, _Session(audit), calls=1) == 1
    assert run.status == "running"
    assert run.safe_error_code is None
