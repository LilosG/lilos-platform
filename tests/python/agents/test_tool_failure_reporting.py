"""Sanctioned tool failures are typed, logged server-side, and never opaque."""

import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from apps.api.app.agents.tools import AgentToolDeniedError, AgentToolService
from apps.api.app.ai.errors import AIProviderError


class _Audit:
    def __init__(self) -> None:
        self.events: list[Any] = []

    async def record(self, _session: object, command: Any) -> None:
        self.events.append(command)


class _Session:
    def __init__(self) -> None:
        self.savepoints = 0
        self.rolled_back = 0

    @asynccontextmanager
    async def begin_nested(self) -> Any:
        self.savepoints += 1
        try:
            yield
        except BaseException:
            self.rolled_back += 1
            raise

    async def flush(self) -> None:
        return None

    async def get(self, *_args: object) -> None:
        return None


def _run(skill_key: str = "content.operator") -> Any:
    return SimpleNamespace(
        id=uuid4(),
        organization_id=uuid4(),
        location_id=uuid4(),
        workflow_run_id=uuid4(),
        correlation_id="corr-test",
        skill_key=skill_key,
        source_references=[],
        output_references=[],
    )


def _service(handler: Callable[..., Any]) -> tuple[AgentToolService, _Audit]:
    service = AgentToolService()
    audit = _Audit()
    service.audit = audit  # type: ignore[assignment]
    setattr(service, "_tool_read_client_business_facts", handler)  # noqa: B010
    return service, audit


@pytest.mark.anyio
async def test_unexpected_tool_exception_is_logged_with_run_and_tool(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def boom(*_args: object) -> dict[str, object]:
        raise RuntimeError("root cause detail")

    service, audit = _service(boom)
    run = _run()
    session = _Session()
    with (
        caplog.at_level(logging.ERROR, logger="lilos.agents.tools"),
        pytest.raises(RuntimeError),
    ):
        await service.invoke(session, run, "read_client_business_facts", {})  # type: ignore[arg-type]
    record = next(r for r in caplog.records if r.name == "lilos.agents.tools")
    assert record.agent_run_id == str(run.id)  # type: ignore[attr-defined]
    assert record.tool_name == "read_client_business_facts"  # type: ignore[attr-defined]
    assert record.correlation_id == "corr-test"  # type: ignore[attr-defined]
    assert record.exception_type == "RuntimeError"  # type: ignore[attr-defined]
    assert "root cause detail" in record.exception_message  # type: ignore[attr-defined]
    assert record.exc_info is not None
    assert audit.events[0].metadata["error_code"] == "HERMES_TOOL_FAILED"
    assert session.savepoints == 1
    assert session.rolled_back == 1


@pytest.mark.anyio
async def test_provider_error_in_a_tool_keeps_its_typed_code() -> None:
    async def provider_down(*_args: object) -> dict[str, object]:
        raise AgentToolDeniedError("timed out", code="AI_PROVIDER_TRANSIENT")

    service, audit = _service(provider_down)
    with pytest.raises(AgentToolDeniedError) as caught:
        await service.invoke(_Session(), _run(), "read_client_business_facts", {})  # type: ignore[arg-type]
    assert caught.value.code == "AI_PROVIDER_TRANSIENT"
    assert audit.events[0].metadata["error_code"] == "AI_PROVIDER_TRANSIENT"


def test_denied_error_defaults_to_denied_code() -> None:
    assert AgentToolDeniedError("nope").code == "HERMES_TOOL_DENIED"


def test_ai_provider_error_category_becomes_typed_code() -> None:
    exc = AIProviderError("transient", "Hermes timed out")
    assert f"AI_PROVIDER_{exc.category.upper()}" == "AI_PROVIDER_TRANSIENT"
