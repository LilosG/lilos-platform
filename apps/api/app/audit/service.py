"""Transactional application service for recording audit evidence."""

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.metadata import normalize_audit_metadata
from apps.api.app.audit.models import AuditEvent
from apps.api.app.audit.repository import AuditEventRepository


@dataclass(frozen=True, slots=True)
class AuditEventService:
    """Create audit events inside a caller-owned database transaction."""

    repository: AuditEventRepository = field(default_factory=AuditEventRepository)

    async def record(self, session: AsyncSession, command: AuditEventCreate) -> AuditEvent:
        """Validate, detach, and append one audit event without committing."""
        event = AuditEvent(
            event_type=command.event_type,
            action=command.action,
            result=command.result,
            occurred_at=command.occurred_at,
            actor_type=command.actor_type,
            actor_id=command.actor_id,
            actor_display_reference=command.actor_display_reference,
            organization_id=command.organization_id,
            location_id=command.location_id,
            product_key=command.product_key,
            resource_type=command.resource_type,
            resource_id=command.resource_id,
            correlation_id=command.correlation_id,
            workflow_execution_id=command.workflow_execution_id,
            source_ip=str(command.source_ip) if command.source_ip is not None else None,
            user_agent_summary=command.user_agent_summary,
            reason_code=command.reason_code,
            summary=command.summary,
            event_metadata=normalize_audit_metadata(command.metadata),
            error_code=command.error_code,
            approval_reference_id=command.approval_reference_id,
            previous_audit_event_id=command.previous_audit_event_id,
        )
        return await self.repository.add(session, event)
