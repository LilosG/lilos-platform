"""Industry registry lifecycle and transactional audit orchestration."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.industries.contracts import IndustryCreate
from apps.api.app.industries.enums import IndustryLifecycleAction, IndustryStatus
from apps.api.app.industries.errors import (
    IndustryKeyConflictError,
    IndustryNotFoundError,
    IndustryTransitionConflictError,
    IndustryVersionConflictError,
)
from apps.api.app.industries.models import Industry
from apps.api.app.industries.policy_documents import normalize_policy_document
from apps.api.app.industries.repository import IndustryRepository

TRANSITIONS: dict[
    IndustryLifecycleAction,
    tuple[frozenset[IndustryStatus], IndustryStatus],
] = {
    IndustryLifecycleAction.DEPRECATE: (
        frozenset({IndustryStatus.ACTIVE}),
        IndustryStatus.DEPRECATED,
    ),
    IndustryLifecycleAction.REACTIVATE: (
        frozenset({IndustryStatus.DEPRECATED}),
        IndustryStatus.ACTIVE,
    ),
    IndustryLifecycleAction.ARCHIVE: (
        frozenset({IndustryStatus.DEPRECATED}),
        IndustryStatus.ARCHIVED,
    ),
}


@dataclass(frozen=True, slots=True)
class IndustryService:
    repository: IndustryRepository = field(default_factory=IndustryRepository)
    audit_service: AuditEventService = field(default_factory=AuditEventService)

    async def create(
        self,
        session: AsyncSession,
        command: IndustryCreate,
        *,
        correlation_id: str,
    ) -> Industry:
        if await self.repository.get_by_key(session, command.key) is not None:
            raise IndustryKeyConflictError
        industry = Industry(
            key=command.key,
            name=command.name,
            status=IndustryStatus.ACTIVE,
            description=command.description,
            default_configuration=normalize_policy_document(command.default_configuration),
            default_risk_policy=normalize_policy_document(command.default_risk_policy),
            default_content_policy=normalize_policy_document(command.default_content_policy),
            version=1,
        )
        try:
            await self.repository.add(session, industry)
        except IntegrityError:
            raise IndustryKeyConflictError from None
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type="platform.industry.created",
                action="industry.create",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                resource_type="industry",
                resource_id=industry.id,
                correlation_id=correlation_id,
                summary="Industry classification created.",
                metadata={
                    "industry_id": str(industry.id),
                    "industry_key": industry.key,
                    "status": industry.status.value,
                    "version": industry.version,
                },
            ),
        )
        return industry

    async def get(self, session: AsyncSession, industry_id: UUID) -> Industry:
        industry = await self.repository.get_by_id(session, industry_id)
        if industry is None:
            raise IndustryNotFoundError
        return industry

    async def list(
        self, session: AsyncSession, *, limit: int, offset: int
    ) -> tuple[list[Industry], bool]:
        return await self.repository.list(session, limit=limit, offset=offset)

    async def transition(
        self,
        session: AsyncSession,
        industry_id: UUID,
        *,
        action: IndustryLifecycleAction,
        expected_version: int,
        correlation_id: str,
    ) -> Industry:
        industry = await self.get(session, industry_id)
        if industry.version != expected_version:
            raise IndustryVersionConflictError
        allowed_statuses, target_status = TRANSITIONS[action]
        if industry.status not in allowed_statuses:
            raise IndustryTransitionConflictError
        previous_status = industry.status
        updated = await self.repository.transition_status(
            session,
            industry_id,
            expected_status=previous_status,
            expected_version=expected_version,
            target_status=target_status,
        )
        if updated is None:
            raise IndustryVersionConflictError
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type="platform.industry.lifecycle_changed",
                action=f"industry.{action.value}",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                resource_type="industry",
                resource_id=updated.id,
                correlation_id=correlation_id,
                summary="Industry lifecycle state changed.",
                metadata={
                    "industry_id": str(updated.id),
                    "industry_key": updated.key,
                    "from_status": previous_status.value,
                    "to_status": updated.status.value,
                    "version": updated.version,
                },
            ),
        )
        return updated
