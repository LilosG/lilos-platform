"""Transactional audit-event service tests."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.models import AuditEvent
from apps.api.app.audit.service import AuditEventService


def command_for(result: AuditResult, **overrides: object) -> AuditEventCreate:
    values: dict[str, object] = {
        "event_type": "platform.test_action",
        "action": "execute",
        "result": result,
        "occurred_at": datetime(2026, 8, 1, 13, 0, tzinfo=UTC),
        "actor_type": AuditActorType.SERVICE,
        "actor_id": uuid4(),
        "summary": f"Fabricated action {result.value}.",
    }
    values.update(overrides)
    return AuditEventCreate.model_validate(values)


async def stored_events(factory: async_sessionmaker[AsyncSession]) -> list[AuditEvent]:
    async with factory() as session:
        result = await session.scalars(select(AuditEvent))
        return list(result)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("result", "reason_code", "error_code"),
    [
        (AuditResult.SUCCEEDED, None, None),
        (AuditResult.FAILED, "PROVIDER_FAILURE", "PROVIDER_UNAVAILABLE"),
        (AuditResult.DENIED, "PERMISSION_REQUIRED", None),
    ],
)
def test_service_records_success_failure_and_denial(
    audit_session_factory: async_sessionmaker[AsyncSession],
    result: AuditResult,
    reason_code: str | None,
    error_code: str | None,
) -> None:
    async def exercise() -> None:
        service = AuditEventService()
        async with audit_session_factory.begin() as session:
            event = await service.record(
                session,
                command_for(result, reason_code=reason_code, error_code=error_code),
            )
            assert event.id is not None
            assert event.recorded_at.tzinfo is not None

        events = await stored_events(audit_session_factory)
        assert len(events) == 1
        assert events[0].result is result
        assert events[0].reason_code == reason_code
        assert events[0].error_code == error_code

    asyncio.run(exercise())


@pytest.mark.integration
def test_service_preserves_nullable_scope_correlation_and_detached_metadata(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        supplied_metadata: dict[str, JsonValue] = {"context": {"attempt": 1}}
        command = command_for(
            AuditResult.SUCCEEDED,
            actor_type=AuditActorType.SYSTEM,
            actor_id=None,
            organization_id=None,
            location_id=None,
            workflow_execution_id=None,
            approval_reference_id=None,
            correlation_id="phase-01.task-03:test",
            metadata=supplied_metadata,
            source_ip="192.0.2.10",
        )
        service = AuditEventService()
        async with audit_session_factory.begin() as session:
            event = await service.record(session, command)
            command_context = command.metadata["context"]
            supplied_context = supplied_metadata["context"]
            assert isinstance(command_context, dict)
            assert isinstance(supplied_context, dict)
            command_context["attempt"] = 2
            supplied_context["attempt"] = 3
            event_id = event.id

        async with audit_session_factory() as session:
            stored = await session.get(AuditEvent, event_id)
            assert stored is not None
            assert stored.organization_id is None
            assert stored.location_id is None
            assert stored.workflow_execution_id is None
            assert stored.approval_reference_id is None
            assert stored.correlation_id == "phase-01.task-03:test"
            assert stored.event_metadata == {"context": {"attempt": 1}}
            assert str(stored.source_ip) == "192.0.2.10"

    asyncio.run(exercise())


@pytest.mark.integration
def test_failed_owning_transaction_rolls_back_audit_event(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = AuditEventService()
        with pytest.raises(RuntimeError, match="forced owning transaction failure"):
            async with audit_session_factory.begin() as session:
                await service.record(session, command_for(AuditResult.FAILED))
                raise RuntimeError("forced owning transaction failure")

        assert await stored_events(audit_session_factory) == []

    asyncio.run(exercise())
