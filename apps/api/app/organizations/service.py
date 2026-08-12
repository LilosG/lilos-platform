"""Organization lifecycle service with transactional audit integration."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.errors import (
    IndustryAssignmentConflictError,
    IndustryNotFoundError,
)
from apps.api.app.industries.repository import IndustryRepository
from apps.api.app.organizations.contracts import OrganizationCreate
from apps.api.app.organizations.enums import (
    OrganizationLifecycleAction,
    OrganizationStatus,
)
from apps.api.app.organizations.errors import (
    OrganizationNotFoundError,
    OrganizationSlugConflictError,
    OrganizationTransitionConflictError,
    OrganizationVersionConflictError,
)
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.repository import OrganizationRepository

TRANSITIONS: dict[
    OrganizationLifecycleAction,
    tuple[frozenset[OrganizationStatus], OrganizationStatus],
] = {
    OrganizationLifecycleAction.START_ONBOARDING: (
        frozenset({OrganizationStatus.PROSPECT}),
        OrganizationStatus.ONBOARDING,
    ),
    OrganizationLifecycleAction.ACTIVATE: (
        frozenset({OrganizationStatus.ONBOARDING, OrganizationStatus.SUSPENDED}),
        OrganizationStatus.ACTIVE,
    ),
    OrganizationLifecycleAction.PAUSE: (
        frozenset({OrganizationStatus.ACTIVE}),
        OrganizationStatus.PAUSED,
    ),
    OrganizationLifecycleAction.RESUME: (
        frozenset({OrganizationStatus.PAUSED}),
        OrganizationStatus.ACTIVE,
    ),
    OrganizationLifecycleAction.SUSPEND: (
        frozenset({OrganizationStatus.ACTIVE, OrganizationStatus.PAUSED}),
        OrganizationStatus.SUSPENDED,
    ),
    OrganizationLifecycleAction.START_OFFBOARDING: (
        frozenset(
            {
                OrganizationStatus.PROSPECT,
                OrganizationStatus.ONBOARDING,
                OrganizationStatus.ACTIVE,
                OrganizationStatus.PAUSED,
                OrganizationStatus.SUSPENDED,
            }
        ),
        OrganizationStatus.OFFBOARDING,
    ),
    OrganizationLifecycleAction.ARCHIVE: (
        frozenset({OrganizationStatus.OFFBOARDING}),
        OrganizationStatus.ARCHIVED,
    ),
}


@dataclass(frozen=True, slots=True)
class OrganizationService:
    """Own organization validation, lifecycle, concurrency, and audit orchestration."""

    repository: OrganizationRepository = field(default_factory=OrganizationRepository)
    industry_repository: IndustryRepository = field(default_factory=IndustryRepository)
    audit_service: AuditEventService = field(default_factory=AuditEventService)

    async def create(
        self,
        session: AsyncSession,
        command: OrganizationCreate,
        *,
        correlation_id: str,
    ) -> Organization:
        """Create one prospect organization and its audit record without committing."""
        if await self.repository.get_by_slug(session, command.slug) is not None:
            raise OrganizationSlugConflictError
        industry = None
        if command.industry_id is not None:
            industry = await self.industry_repository.get_by_id(session, command.industry_id)
            if industry is None:
                raise IndustryNotFoundError
            if industry.status is not IndustryStatus.ACTIVE:
                raise IndustryAssignmentConflictError
        organization = Organization(
            name=command.name,
            slug=command.slug,
            organization_type=command.organization_type,
            status=OrganizationStatus.PROSPECT,
            timezone=command.timezone,
            default_currency=command.default_currency,
            legal_name=command.legal_name,
            website_url=str(command.website_url) if command.website_url is not None else None,
            primary_contact_name=command.primary_contact_name,
            primary_contact_email=command.primary_contact_email,
            primary_contact_phone=command.primary_contact_phone,
            billing_email=command.billing_email,
            external_reference=command.external_reference,
            onboarding_status=command.onboarding_status,
            onboarding_mode=command.onboarding_mode,
            industry_id=industry.id if industry is not None else None,
            version=1,
        )
        try:
            await self.repository.add(session, organization)
        except IntegrityError:
            raise OrganizationSlugConflictError from None
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type="platform.organization.created",
                action="organization.create",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=organization.id,
                resource_type="organization",
                resource_id=organization.id,
                correlation_id=correlation_id,
                summary="Organization created in prospect state.",
                metadata={
                    "organization_slug": organization.slug,
                    "organization_type": organization.organization_type.value,
                    "status": organization.status.value,
                    "version": organization.version,
                    "onboarding_mode": organization.onboarding_mode,
                    "industry_id": (
                        str(organization.industry_id)
                        if organization.industry_id is not None
                        else None
                    ),
                },
            ),
        )
        return organization

    async def get(self, session: AsyncSession, organization_id: UUID) -> Organization:
        """Retrieve one organization or return a stable not-found error."""
        organization = await self.repository.get_by_id(session, organization_id)
        if organization is None:
            raise OrganizationNotFoundError
        return organization

    async def list(
        self,
        session: AsyncSession,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Organization], bool]:
        """Return a deterministic bounded organization page."""
        return await self.repository.list(session, limit=limit, offset=offset)

    async def transition(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        action: OrganizationLifecycleAction,
        expected_version: int,
        correlation_id: str,
    ) -> Organization:
        """Apply a valid compare-and-swap lifecycle transition and append its audit event."""
        organization = await self.get(session, organization_id)
        if organization.version != expected_version:
            raise OrganizationVersionConflictError
        allowed_statuses, target_status = TRANSITIONS[action]
        if organization.status not in allowed_statuses:
            raise OrganizationTransitionConflictError
        previous_status = organization.status
        updated = await self.repository.transition_status(
            session,
            organization_id=organization_id,
            expected_status=previous_status,
            expected_version=expected_version,
            target_status=target_status,
        )
        if updated is None:
            raise OrganizationVersionConflictError
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type="platform.organization.lifecycle_changed",
                action=f"organization.{action.value}",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=updated.id,
                resource_type="organization",
                resource_id=updated.id,
                correlation_id=correlation_id,
                summary="Organization lifecycle state changed.",
                metadata={
                    "from_status": previous_status.value,
                    "to_status": updated.status.value,
                    "version": updated.version,
                },
            ),
        )
        return updated

    async def set_industry(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        industry_id: UUID,
        expected_version: int,
        correlation_id: str,
    ) -> Organization:
        """Assign one active primary industry without exposing a generic update."""
        organization = await self.get(session, organization_id)
        if organization.version != expected_version:
            raise OrganizationVersionConflictError
        industry = await self.industry_repository.get_by_id(session, industry_id)
        if industry is None:
            raise IndustryNotFoundError
        if industry.status is not IndustryStatus.ACTIVE:
            raise IndustryAssignmentConflictError
        previous_industry_id = organization.industry_id
        updated = await self.repository.set_industry(
            session,
            organization_id,
            industry_id=industry.id,
            expected_version=expected_version,
        )
        if updated is None:
            raise OrganizationVersionConflictError
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type="platform.organization.industry_assigned",
                action="organization.set_industry",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=updated.id,
                resource_type="organization",
                resource_id=updated.id,
                correlation_id=correlation_id,
                summary="Organization primary industry assigned.",
                metadata={
                    "industry_id": str(industry.id),
                    "industry_key": industry.key,
                    "previous_industry_id": (
                        str(previous_industry_id) if previous_industry_id is not None else None
                    ),
                    "organization_version": updated.version,
                },
            ),
        )
        return updated
