"""Content provider failures name themselves, are recorded, and retry only when a repeat helps."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.ai.errors import (
    RETRYABLE_FAILURE_CODES,
    AIProviderError,
    AIProviderFailureCode,
)
from apps.api.app.ai.models import AIExecution
from apps.api.app.execution.handlers import _provider_failure_outcome

from .test_content_compose import (
    ScriptedGateway,
    draft_payload,
    run_compose,
    seed_world,
    start,
    use_gateway,
)

RETRIED = {"TIMEOUT", "CONNECTION", "HTTP_RATE_LIMITED", "HTTP_SERVER"}


def failure(code: AIProviderFailureCode) -> AIProviderError:
    return AIProviderError(
        "provider",
        "safe message",
        code=code,
        http_status=502 if code == AIProviderFailureCode.HTTP_SERVER else None,
        elapsed_ms=41_234,
        finish_reason="length" if code == AIProviderFailureCode.OUTPUT_TRUNCATED else None,
        output_tokens=16_000 if code == AIProviderFailureCode.OUTPUT_TRUNCATED else None,
    )


class FailingDraftGateway(ScriptedGateway):
    """Plans normally, then fails each draft call with the scripted errors before succeeding."""

    def __init__(self, errors: list[AIProviderError]) -> None:
        super().__init__([draft_payload()])
        self.errors = list(errors)

    async def execute(self, request: Any) -> dict[str, Any]:
        if request.task_key == "content.draft_revision" and self.errors:
            self.requests.append(request)
            raise self.errors.pop(0)
        return await super().execute(request)


@pytest.mark.parametrize("code", list(AIProviderFailureCode))
def test_only_failures_a_repeat_can_fix_are_retried(code: AIProviderFailureCode) -> None:
    outcome = _provider_failure_outcome(failure(code))
    assert outcome.safe_error == f"AI_PROVIDER_{code.value}"
    assert (outcome.result == "retryable_failure") == (code.value in RETRIED)
    assert (code in RETRYABLE_FAILURE_CODES) == (code.value in RETRIED)


def test_truncated_and_malformed_output_are_never_retried() -> None:
    for code in (AIProviderFailureCode.OUTPUT_TRUNCATED, AIProviderFailureCode.MALFORMED_OUTPUT):
        assert _provider_failure_outcome(failure(code)).result == "permanent_failure"


@pytest.mark.anyio
@pytest.mark.parametrize("code", list(AIProviderFailureCode))
async def test_a_failed_compose_names_the_failure_records_a_row_and_logs_it(
    content_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    code: AIProviderFailureCode,
) -> None:
    use_gateway(monkeypatch, FailingDraftGateway([failure(code)]))
    async with content_session_factory() as session:
        world = await seed_world(session)
        _, run_input, run = await start(session, world)
        with caplog.at_level(logging.WARNING):
            outcome = await run_compose(session, world, run_input, run.id)

        assert outcome.safe_error == f"AI_PROVIDER_{code.value}"
        assert (outcome.result == "retryable_failure") == (code.value in RETRIED)

        # The workflow transaction rolling back afterwards must not take the row with it.
        await session.rollback()
        (row,) = list(
            await session.scalars(
                select(AIExecution).where(AIExecution.organization_id == world.org)
            )
        )
        assert row.status == "provider_failed"
        assert row.safe_error_code == code.value
        assert row.latency_ms == 41_234
        assert row.workflow_run_id == run.id
        assert ":failed:" in row.idempotency_key

        (record,) = [
            r
            for r in caplog.records
            if getattr(r, "event_name", "") == "content.compose.provider_failed"
        ]
        assert record.levelno == logging.WARNING
        assert record.failure_code == code.value  # type: ignore[attr-defined]
        assert record.elapsed_ms == 41_234  # type: ignore[attr-defined]
        assert record.task_key == "content.compose"  # type: ignore[attr-defined]


@pytest.mark.anyio
async def test_a_truncated_draft_logs_finish_reason_and_tokens_and_fails_the_item(
    content_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    gateway = FailingDraftGateway([failure(AIProviderFailureCode.OUTPUT_TRUNCATED)])
    use_gateway(monkeypatch, gateway)
    async with content_session_factory() as session:
        world = await seed_world(session)
        item, run_input, run = await start(session, world)
        with caplog.at_level(logging.WARNING):
            outcome = await run_compose(session, world, run_input, run.id)
        assert outcome.result == "permanent_failure"
        await session.refresh(item)
        assert item.status == "failed"
        record = next(
            r
            for r in caplog.records
            if getattr(r, "event_name", "") == "content.compose.provider_failed"
        )
        assert record.finish_reason == "length"  # type: ignore[attr-defined]
        assert record.output_tokens == 16_000  # type: ignore[attr-defined]
        # Not retried: one draft call only.
        assert len([r for r in gateway.requests if r.task_key == "content.draft_revision"]) == 1


@pytest.mark.anyio
async def test_a_retry_after_a_recorded_failure_still_writes_the_draft(
    content_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The failed row must not hold the draft's idempotency key and be replayed as its result."""
    use_gateway(monkeypatch, FailingDraftGateway([failure(AIProviderFailureCode.TIMEOUT)]))
    async with content_session_factory() as session:
        world = await seed_world(session)
        _, run_input, run = await start(session, world)
        first = await run_compose(session, world, run_input, run.id)
        assert first.result == "retryable_failure"
        second = await run_compose(session, world, run_input, run.id)
        assert second.result == "succeeded"
        statuses = sorted(
            row.status
            for row in await session.scalars(
                select(AIExecution).where(AIExecution.organization_id == world.org)
            )
        )
        assert statuses == ["completed", "provider_failed"]


@pytest.mark.anyio
async def test_a_failed_plan_call_is_recorded_too(
    content_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingPlan(ScriptedGateway):
        async def execute(self, request: Any) -> dict[str, Any]:
            if request.task_key == "content.compose_plan":
                raise failure(AIProviderFailureCode.HTTP_RATE_LIMITED)
            return await super().execute(request)

    use_gateway(monkeypatch, FailingPlan([draft_payload()]))
    async with content_session_factory() as session:
        world = await seed_world(session)
        _, run_input, run = await start(session, world)
        outcome = await run_compose(session, world, run_input, run.id)
        assert outcome.result == "retryable_failure"
        assert outcome.safe_error == "AI_PROVIDER_HTTP_RATE_LIMITED"
        (row,) = list(
            await session.scalars(
                select(AIExecution).where(AIExecution.organization_id == world.org)
            )
        )
        assert row.status == "provider_failed" and row.safe_error_code == "HTTP_RATE_LIMITED"
