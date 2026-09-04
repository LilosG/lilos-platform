"""Organization approved-domain registry service."""

from dataclasses import dataclass, field
from typing import cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.domains.contracts import OrganizationDomainCreate
from apps.api.app.domains.enums import OrganizationDomainStatus
from apps.api.app.domains.errors import (
    OrganizationDomainConflictError,
    OrganizationDomainNotFoundError,
    OrganizationDomainPrimaryConflictError,
    OrganizationDomainVersionConflictError,
)
from apps.api.app.domains.models import OrganizationDomain
from apps.api.app.domains.repository import OrganizationDomainRepository
from apps.api.app.organizations.errors import OrganizationNotFoundError
from apps.api.app.organizations.repository import OrganizationRepository


@dataclass(frozen=True, slots=True)
class OrganizationDomainService:
    repository: OrganizationDomainRepository = field(default_factory=OrganizationDomainRepository)
    organization_repository: OrganizationRepository = field(default_factory=OrganizationRepository)
    audit_service: AuditEventService = field(default_factory=AuditEventService)

    async def _require_organization(self, session: AsyncSession, organization_id: UUID) -> None:
        if await self.organization_repository.get_by_id(session, organization_id) is None:
            raise OrganizationNotFoundError

    async def _audit(
        self,
        session: AsyncSession,
        *,
        event: str,
        action: str,
        organization_id: UUID,
        resource_id: UUID,
        correlation_id: str,
        metadata: dict[str, object],
    ) -> None:
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=action,
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER,
                organization_id=organization_id,
                product_key="platform",
                resource_type="organization_domain",
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary="Organization domain changed.",
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    async def list(self, session: AsyncSession, organization_id: UUID) -> list[OrganizationDomain]:
        await self._require_organization(session, organization_id)
        return await self.repository.list(session, organization_id)

    async def create(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: OrganizationDomainCreate,
        *,
        correlation_id: str,
    ) -> OrganizationDomain:
        await self._require_organization(session, organization_id)

        existing = await self.repository.get_by_domain(
            session, organization_id, command.domain, lock=True
        )
        if existing is not None:
            if existing.status is OrganizationDomainStatus.ACTIVE:
                raise OrganizationDomainConflictError

            if command.is_primary:
                active_domains = await self.repository.list(session, organization_id)
                if any(item.is_primary for item in active_domains):
                    raise OrganizationDomainPrimaryConflictError

            reactivated = await self.repository.reactivate(
                session,
                organization_id,
                existing.id,
                expected_version=existing.version,
                is_primary=command.is_primary,
            )
            if reactivated is None:
                raise OrganizationDomainConflictError
            await self._audit(
                session,
                event="platform.organization_domain.reactivated",
                action="organization_domain.reactivate",
                organization_id=organization_id,
                resource_id=reactivated.id,
                correlation_id=correlation_id,
                metadata={
                    "domain_id": str(reactivated.id),
                    "domain": reactivated.domain,
                    "is_primary": reactivated.is_primary,
                    "operation": "reactivated",
                },
            )
            return reactivated

        if command.is_primary:
            active_domains = await self.repository.list(session, organization_id)
            if any(item.is_primary for item in active_domains):
                raise OrganizationDomainPrimaryConflictError

        domain = OrganizationDomain(
            organization_id=organization_id,
            domain=command.domain,
            is_primary=command.is_primary,
            status=OrganizationDomainStatus.ACTIVE,
            version=1,
        )
        try:
            await self.repository.add(session, domain)
        except IntegrityError:
            raise OrganizationDomainConflictError from None
        await self._audit(
            session,
            event="platform.organization_domain.created",
            action="organization_domain.create",
            organization_id=organization_id,
            resource_id=domain.id,
            correlation_id=correlation_id,
            metadata={
                "domain_id": str(domain.id),
                "domain": domain.domain,
                "is_primary": domain.is_primary,
                "operation": "created",
            },
        )
        return domain

    async def set_primary(
        self,
        session: AsyncSession,
        organization_id: UUID,
        domain_id: UUID,
        *,
        expected_version: int,
        correlation_id: str,
    ) -> OrganizationDomain:
        await self._require_organization(session, organization_id)
        current = await self.repository.get(session, organization_id, domain_id)
        if current is None:
            raise OrganizationDomainNotFoundError
        if current.is_primary:
            return current
        await self.repository.clear_primary(session, organization_id)
        updated = await self.repository.set_primary(
            session, organization_id, domain_id, expected_version=expected_version
        )
        if updated is None:
            raise OrganizationDomainVersionConflictError
        await self._audit(
            session,
            event="platform.organization_domain.primary_changed",
            action="organization_domain.set_primary",
            organization_id=organization_id,
            resource_id=updated.id,
            correlation_id=correlation_id,
            metadata={
                "domain_id": str(updated.id),
                "domain": updated.domain,
                "operation": "primary_changed",
            },
        )
        return updated

    async def archive(
        self,
        session: AsyncSession,
        organization_id: UUID,
        domain_id: UUID,
        *,
        expected_version: int,
        correlation_id: str,
    ) -> OrganizationDomain:
        await self._require_organization(session, organization_id)
        updated = await self.repository.archive(
            session, organization_id, domain_id, expected_version=expected_version
        )
        if updated is None:
            current = await self.repository.get(session, organization_id, domain_id)
            if current is None:
                raise OrganizationDomainNotFoundError
            raise OrganizationDomainVersionConflictError
        await self._audit(
            session,
            event="platform.organization_domain.archived",
            action="organization_domain.archive",
            organization_id=organization_id,
            resource_id=updated.id,
            correlation_id=correlation_id,
            metadata={
                "domain_id": str(updated.id),
                "domain": updated.domain,
                "operation": "archived",
            },
        )
        return updated
