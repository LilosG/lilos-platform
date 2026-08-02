"""Controlled retrieval and append-only enforcement tests."""

import asyncio
import inspect as python_inspect
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.models import AuditEvent
from apps.api.app.audit.repository import AuditEventRepository


def audit_event(*, event_id: UUID, correlation_id: str, resource_id: UUID) -> AuditEvent:
    return AuditEvent(
        id=event_id,
        event_type="platform.repository_test",
        action="record",
        result=AuditResult.SUCCEEDED,
        occurred_at=datetime(2026, 8, 1, 14, 0, tzinfo=UTC),
        actor_type=AuditActorType.SYSTEM,
        correlation_id=correlation_id,
        resource_type="audit_probe",
        resource_id=resource_id,
        summary="Fabricated repository test event.",
        event_metadata={},
    )


@pytest.mark.integration
def test_repository_orders_by_occurred_at_then_id_and_supports_chains(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        repository = AuditEventRepository()
        correlation_id = "audit.repository:ordering"
        resource_id = uuid4()
        first = audit_event(
            event_id=UUID(int=1),
            correlation_id=correlation_id,
            resource_id=resource_id,
        )
        second = audit_event(
            event_id=UUID(int=2),
            correlation_id=correlation_id,
            resource_id=resource_id,
        )
        second.previous_audit_event_id = first.id

        async with audit_session_factory.begin() as session:
            await repository.add(session, first)
            await repository.add(session, second)

        async with audit_session_factory() as session:
            correlated = await repository.list_for_correlation(session, correlation_id)
            resource_history = await repository.list_for_resource(
                session,
                resource_type="audit_probe",
                resource_id=resource_id,
            )

        assert [event.id for event in correlated] == [UUID(int=2), UUID(int=1)]
        assert [event.id for event in resource_history] == [UUID(int=2), UUID(int=1)]
        assert correlated[0].previous_audit_event_id == correlated[1].id

    asyncio.run(exercise())


@pytest.mark.integration
def test_database_rejects_update_delete_and_truncate(
    audit_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        repository = AuditEventRepository()
        event = audit_event(
            event_id=uuid4(),
            correlation_id="audit.repository:immutable",
            resource_id=uuid4(),
        )
        async with audit_session_factory.begin() as session:
            await repository.add(session, event)

        statements = (
            text("UPDATE audit_events SET summary = 'changed'"),
            text("DELETE FROM audit_events"),
            text("TRUNCATE TABLE audit_events"),
        )
        for statement in statements:
            async with audit_session_factory() as session:
                with pytest.raises(DBAPIError, match="append-only"):
                    async with session.begin():
                        await session.execute(statement)

        async with audit_session_factory() as session:
            count = await session.scalar(select(func.count()).select_from(AuditEvent))
            stored = await repository.get_by_id(session, event.id)
        assert count == 1
        assert stored is not None
        assert stored.summary == "Fabricated repository test event."

    asyncio.run(exercise())


def test_repository_exposes_no_update_or_delete_method() -> None:
    public_methods = {
        name
        for name, member in python_inspect.getmembers(
            AuditEventRepository,
            predicate=python_inspect.isfunction,
        )
        if not name.startswith("_")
    }

    assert public_methods == {"add", "get_by_id", "list_for_correlation", "list_for_resource"}
