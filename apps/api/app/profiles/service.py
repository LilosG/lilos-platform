"""Profile validation, parent-state locking, concurrency, and audit orchestration."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.locations.enums import LocationStatus
from apps.api.app.locations.errors import LocationNotFoundError
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.errors import OrganizationNotFoundError
from apps.api.app.organizations.models import Organization
from apps.api.app.profiles.contracts import (
    LocationProfileCreate,
    LocationProfileReplace,
    OrganizationProfileCreate,
    OrganizationProfileReplace,
)
from apps.api.app.profiles.errors import (
    LocationProfileConflictError,
    LocationProfileNotFoundError,
    LocationProfileVersionConflictError,
    OrganizationProfileConflictError,
    OrganizationProfileNotFoundError,
    OrganizationProfileVersionConflictError,
    ProfileParentStateConflictError,
)
from apps.api.app.profiles.models import LocationProfile, OrganizationProfile
from apps.api.app.profiles.repository import (
    LOCATION_CONTENT_FIELDS,
    ORGANIZATION_CONTENT_FIELDS,
    LocationProfileRepository,
    OrganizationProfileRepository,
)

MUTABLE_ORGANIZATION_STATUSES = frozenset(
    {
        OrganizationStatus.PROSPECT,
        OrganizationStatus.ONBOARDING,
        OrganizationStatus.ACTIVE,
        OrganizationStatus.PAUSED,
    }
)
MUTABLE_LOCATION_STATUSES = frozenset(
    {
        LocationStatus.SETUP_REQUIRED,
        LocationStatus.ACTIVE,
        LocationStatus.PAUSED,
        LocationStatus.CLOSED_TEMPORARILY,
    }
)


def _detached_values(command: object, fields: tuple[str, ...]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field_name in fields:
        value = getattr(command, field_name)
        values[field_name] = list(value) if isinstance(value, list) else value
    return values


def _changed_fields(
    stored: object,
    command: object,
    fields: tuple[str, ...],
) -> list[str]:
    return sorted(
        field_name
        for field_name in fields
        if getattr(stored, field_name) != getattr(command, field_name)
    )


async def _lock_organization(session: AsyncSession, organization_id: UUID) -> Organization:
    organization = await session.scalar(
        select(Organization).where(Organization.id == organization_id).with_for_update()
    )
    if organization is None:
        raise OrganizationNotFoundError
    return organization


async def _lock_location(
    session: AsyncSession,
    organization_id: UUID,
    location_id: UUID,
) -> Location:
    location = await session.scalar(
        select(Location)
        .where(
            Location.organization_id == organization_id,
            Location.id == location_id,
        )
        .with_for_update()
    )
    if location is None:
        raise LocationNotFoundError
    return location


def _require_mutable_organization(organization: Organization) -> None:
    if organization.status not in MUTABLE_ORGANIZATION_STATUSES:
        raise ProfileParentStateConflictError


def _require_mutable_location(location: Location) -> None:
    if location.status not in MUTABLE_LOCATION_STATUSES:
        raise ProfileParentStateConflictError


@dataclass(frozen=True, slots=True)
class OrganizationProfileService:
    repository: OrganizationProfileRepository = field(default_factory=OrganizationProfileRepository)
    audit_service: AuditEventService = field(default_factory=AuditEventService)

    async def create(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: OrganizationProfileCreate,
        *,
        correlation_id: str,
    ) -> OrganizationProfile:
        organization = await _lock_organization(session, organization_id)
        _require_mutable_organization(organization)
        if await self.repository.get_for_organization(session, organization_id) is not None:
            raise OrganizationProfileConflictError
        profile = OrganizationProfile(
            organization_id=organization_id,
            **_detached_values(command, ORGANIZATION_CONTENT_FIELDS),
            version=1,
        )
        try:
            await self.repository.add(session, profile)
        except IntegrityError:
            raise OrganizationProfileConflictError from None
        await self._audit(
            session,
            profile,
            operation="created",
            changed_fields=sorted(
                field_name
                for field_name in ORGANIZATION_CONTENT_FIELDS
                if getattr(profile, field_name) is not None
            ),
            correlation_id=correlation_id,
        )
        return profile

    async def get(self, session: AsyncSession, organization_id: UUID) -> OrganizationProfile:
        profile = await self.repository.get_for_organization(session, organization_id)
        if profile is None:
            raise OrganizationProfileNotFoundError
        return profile

    async def replace(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: OrganizationProfileReplace,
        *,
        correlation_id: str,
    ) -> OrganizationProfile:
        organization = await _lock_organization(session, organization_id)
        _require_mutable_organization(organization)
        stored = await self.get(session, organization_id)
        if stored.version != command.expected_version:
            raise OrganizationProfileVersionConflictError
        changed_fields = _changed_fields(stored, command, ORGANIZATION_CONTENT_FIELDS)
        updated = await self.repository.replace(session, organization_id, command)
        if updated is None:
            raise OrganizationProfileVersionConflictError
        await self._audit(
            session,
            updated,
            operation="updated",
            changed_fields=changed_fields,
            correlation_id=correlation_id,
        )
        return updated

    async def _audit(
        self,
        session: AsyncSession,
        profile: OrganizationProfile,
        *,
        operation: str,
        changed_fields: list[str],
        correlation_id: str,
    ) -> None:
        audit_changed_fields: list[JsonValue] = [field_name for field_name in changed_fields]
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type=f"platform.organization_profile.{operation}",
                action=f"organization_profile.{operation}",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=profile.organization_id,
                resource_type="organization_profile",
                resource_id=profile.id,
                correlation_id=correlation_id,
                summary=f"Organization profile {operation}.",
                metadata={
                    "profile_id": str(profile.id),
                    "operation": operation,
                    "version": profile.version,
                    "changed_fields": audit_changed_fields,
                },
            ),
        )


@dataclass(frozen=True, slots=True)
class LocationProfileService:
    repository: LocationProfileRepository = field(default_factory=LocationProfileRepository)
    audit_service: AuditEventService = field(default_factory=AuditEventService)

    async def create(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        command: LocationProfileCreate,
        *,
        correlation_id: str,
    ) -> LocationProfile:
        organization = await _lock_organization(session, organization_id)
        _require_mutable_organization(organization)
        location = await _lock_location(session, organization_id, location_id)
        _require_mutable_location(location)
        if (
            await self.repository.get_for_location(session, organization_id, location_id)
            is not None
        ):
            raise LocationProfileConflictError
        profile = LocationProfile(
            organization_id=organization_id,
            location_id=location_id,
            **_detached_values(command, LOCATION_CONTENT_FIELDS),
            version=1,
        )
        try:
            await self.repository.add(session, profile)
        except IntegrityError:
            raise LocationProfileConflictError from None
        await self._audit(
            session,
            profile,
            operation="created",
            changed_fields=sorted(
                field_name
                for field_name in LOCATION_CONTENT_FIELDS
                if getattr(profile, field_name) is not None
            ),
            correlation_id=correlation_id,
        )
        return profile

    async def get(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
    ) -> LocationProfile:
        profile = await self.repository.get_for_location(session, organization_id, location_id)
        if profile is None:
            raise LocationProfileNotFoundError
        return profile

    async def replace(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        command: LocationProfileReplace,
        *,
        correlation_id: str,
    ) -> LocationProfile:
        organization = await _lock_organization(session, organization_id)
        _require_mutable_organization(organization)
        location = await _lock_location(session, organization_id, location_id)
        _require_mutable_location(location)
        stored = await self.get(session, organization_id, location_id)
        if stored.version != command.expected_version:
            raise LocationProfileVersionConflictError
        changed_fields = _changed_fields(stored, command, LOCATION_CONTENT_FIELDS)
        updated = await self.repository.replace(session, organization_id, location_id, command)
        if updated is None:
            raise LocationProfileVersionConflictError
        await self._audit(
            session,
            updated,
            operation="updated",
            changed_fields=changed_fields,
            correlation_id=correlation_id,
        )
        return updated

    async def _audit(
        self,
        session: AsyncSession,
        profile: LocationProfile,
        *,
        operation: str,
        changed_fields: list[str],
        correlation_id: str,
    ) -> None:
        audit_changed_fields: list[JsonValue] = [field_name for field_name in changed_fields]
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type=f"platform.location_profile.{operation}",
                action=f"location_profile.{operation}",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=profile.organization_id,
                location_id=profile.location_id,
                resource_type="location_profile",
                resource_id=profile.id,
                correlation_id=correlation_id,
                summary=f"Location profile {operation}.",
                metadata={
                    "profile_id": str(profile.id),
                    "operation": operation,
                    "version": profile.version,
                    "changed_fields": audit_changed_fields,
                },
            ),
        )
