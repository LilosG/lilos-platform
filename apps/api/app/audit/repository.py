"""Controlled persistence and retrieval for append-only audit events."""

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.models import AuditEvent

MAX_AUDIT_QUERY_LIMIT = 100


class AuditEventRepository:
    """Append and retrieve audit events without mutation methods."""

    async def add(self, session: AsyncSession, event: AuditEvent) -> AuditEvent:
        """Append an event within the caller-owned transaction."""
        session.add(event)
        await session.flush()
        return event

    async def get_by_id(self, session: AsyncSession, event_id: UUID) -> AuditEvent | None:
        """Retrieve one event by its internal identifier."""
        return await session.get(AuditEvent, event_id)

    async def list_for_correlation(
        self,
        session: AsyncSession,
        correlation_id: str,
        *,
        limit: int = 50,
    ) -> list[AuditEvent]:
        """Retrieve a bounded causal history in deterministic descending order."""
        statement = self._ordered_query().where(AuditEvent.correlation_id == correlation_id)
        return await self._list(session, statement, limit)

    async def list_for_resource(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        resource_type: str,
        resource_id: UUID,
        limit: int = 50,
    ) -> list[AuditEvent]:
        """Retrieve tenant-scoped resource history in deterministic descending order."""
        statement = self._ordered_query().where(
            AuditEvent.organization_id == organization_id,
            AuditEvent.resource_type == resource_type,
            AuditEvent.resource_id == resource_id,
        )
        return await self._list(session, statement, limit)

    @staticmethod
    def _ordered_query() -> Select[tuple[AuditEvent]]:
        return select(AuditEvent).order_by(
            AuditEvent.occurred_at.desc(),
            AuditEvent.id.desc(),
        )

    @staticmethod
    async def _list(
        session: AsyncSession,
        statement: Select[tuple[AuditEvent]],
        limit: int,
    ) -> list[AuditEvent]:
        if not 1 <= limit <= MAX_AUDIT_QUERY_LIMIT:
            raise ValueError(f"Audit query limit must be between 1 and {MAX_AUDIT_QUERY_LIMIT}")
        result = await session.scalars(statement.limit(limit))
        return list(result)
