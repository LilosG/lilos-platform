"""Location rules, scoped isolation, concurrency, and transactional auditing."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.locations.contracts import LocationCreate, LocationUpdate
from apps.api.app.locations.enums import LocationLifecycleAction, LocationStatus
from apps.api.app.locations.errors import (
    LocationNotFoundError,
    LocationParentStateConflictError,
    LocationPrimaryConflictError,
    LocationSlugConflictError,
    LocationTransitionConflictError,
    LocationVersionConflictError,
)
from apps.api.app.locations.models import Location
from apps.api.app.locations.repository import LocationRepository
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.errors import OrganizationNotFoundError
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.repository import OrganizationRepository

TRANSITIONS: dict[LocationStatus, frozenset[LocationStatus]] = {
    LocationStatus.SETUP_REQUIRED: frozenset({LocationStatus.ACTIVE, LocationStatus.ARCHIVED}),
    LocationStatus.ACTIVE: frozenset(
        {
            LocationStatus.PAUSED,
            LocationStatus.CLOSED_TEMPORARILY,
            LocationStatus.CLOSED_PERMANENTLY,
        }
    ),
    LocationStatus.PAUSED: frozenset(
        {
            LocationStatus.ACTIVE,
            LocationStatus.CLOSED_TEMPORARILY,
            LocationStatus.CLOSED_PERMANENTLY,
            LocationStatus.ARCHIVED,
        }
    ),
    LocationStatus.CLOSED_TEMPORARILY: frozenset(
        {LocationStatus.ACTIVE, LocationStatus.PAUSED, LocationStatus.CLOSED_PERMANENTLY}
    ),
    LocationStatus.CLOSED_PERMANENTLY: frozenset({LocationStatus.ARCHIVED}),
    LocationStatus.ARCHIVED: frozenset(),
}
ACTION_TARGET = {
    LocationLifecycleAction.ACTIVATE: LocationStatus.ACTIVE,
    LocationLifecycleAction.PAUSE: LocationStatus.PAUSED,
    LocationLifecycleAction.CLOSE_TEMPORARILY: LocationStatus.CLOSED_TEMPORARILY,
    LocationLifecycleAction.CLOSE_PERMANENTLY: LocationStatus.CLOSED_PERMANENTLY,
    LocationLifecycleAction.ARCHIVE: LocationStatus.ARCHIVED,
}
CREATE_ALLOWED = frozenset(
    {
        OrganizationStatus.PROSPECT,
        OrganizationStatus.ONBOARDING,
        OrganizationStatus.ACTIVE,
        OrganizationStatus.PAUSED,
    }
)


@dataclass(frozen=True, slots=True)
class LocationService:
    repository: LocationRepository = field(default_factory=LocationRepository)
    organization_repository: OrganizationRepository = field(default_factory=OrganizationRepository)
    audit_service: AuditEventService = field(default_factory=AuditEventService)

    async def _organization(self, session: AsyncSession, organization_id: UUID) -> Organization:
        organization = await self.organization_repository.get_by_id(session, organization_id)
        if organization is None:
            raise OrganizationNotFoundError
        return organization

    async def create(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: LocationCreate,
        *,
        correlation_id: str,
    ) -> Location:
        organization = await self._organization(session, organization_id)
        if organization.status not in CREATE_ALLOWED:
            raise LocationParentStateConflictError
        if await self.repository.get_by_slug(session, organization_id, command.slug) is not None:
            raise LocationSlugConflictError
        if (
            command.is_primary
            and await self.repository.get_primary(session, organization_id) is not None
        ):
            raise LocationPrimaryConflictError
        location = Location(
            organization_id=organization_id,
            name=command.name,
            slug=command.slug,
            location_type=command.location_type,
            status=LocationStatus.SETUP_REQUIRED,
            timezone=command.timezone,
            address_line_1=command.address_line_1,
            address_line_2=command.address_line_2,
            city=command.city,
            region=command.region,
            postal_code=command.postal_code,
            country_code=command.country_code,
            latitude=command.latitude,
            longitude=command.longitude,
            service_area_description=command.service_area_description,
            phone=command.phone,
            email=command.email,
            website_url=str(command.website_url) if command.website_url else None,
            external_reference=command.external_reference,
            is_primary=command.is_primary,
            version=1,
        )
        try:
            await self.repository.add(session, organization_id, location)
        except IntegrityError:
            raise (
                LocationPrimaryConflictError if command.is_primary else LocationSlugConflictError
            ) from None
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type="platform.location.created",
                action="location.create",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=organization_id,
                location_id=location.id,
                resource_type="location",
                resource_id=location.id,
                correlation_id=correlation_id,
                summary="Location created in setup-required state.",
                metadata={
                    "location_slug": location.slug,
                    "location_type": location.location_type.value,
                    "status": location.status.value,
                    "version": location.version,
                    "is_primary": location.is_primary,
                },
            ),
        )
        return location

    async def update(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        command: LocationUpdate,
        *,
        correlation_id: str,
    ) -> Location:
        """Correct the details of an existing location.

        Only fields the caller supplied are written. Everything else keeps its
        current value, so correcting an address cannot blank a phone number by
        omission — which matters because this is reached from a form that may
        only render a subset of the fields.
        """
        await self._organization(session, organization_id)
        location = await self.repository.get_by_id(session, organization_id, location_id)
        if location is None:
            raise LocationNotFoundError
        if location.version != command.expected_version:
            raise LocationVersionConflictError

        supplied = command.model_dump(exclude={"expected_version"}, exclude_unset=True)
        changed: dict[str, Any] = {}
        for attribute, value in supplied.items():
            if attribute == "website_url" and value is not None:
                value = str(value)
            if getattr(location, attribute) != value:
                changed[attribute] = value

        if not changed:
            # Nothing to write. Returning early keeps the version stable, so a
            # no-op save does not invalidate a form the operator still has open.
            return location

        for attribute, value in changed.items():
            setattr(location, attribute, value)
        location.version += 1
        await session.flush()

        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type="platform.location.updated",
                action="location.update",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=organization_id,
                location_id=location.id,
                resource_type="location",
                resource_id=location.id,
                correlation_id=correlation_id,
                summary="Location details corrected.",
                # Field names only. The values can carry a client's address and
                # contact details, which do not belong in the audit payload.
                metadata={
                    "fields": ", ".join(sorted(changed)),
                    "version": location.version,
                },
            ),
        )
        return location

    async def set_primary(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        *,
        expected_version: int,
        correlation_id: str,
    ) -> Location:
        """Move the primary designation to this location.

        A partial unique index enforces one primary per organization, so the
        incumbent must be demoted before the new one is promoted, in that order
        and in one transaction. Doing it the other way round trips the
        constraint; doing it in two transactions can leave a client with no
        primary at all, which blocks activation.
        """
        await self._organization(session, organization_id)
        location = await self.repository.get_by_id(session, organization_id, location_id)
        if location is None:
            raise LocationNotFoundError
        if location.version != expected_version:
            raise LocationVersionConflictError
        if location.status in {LocationStatus.CLOSED_PERMANENTLY, LocationStatus.ARCHIVED}:
            # The primary location is what product readiness and GBP mapping
            # resolve against. Pointing it at a retired location would create a
            # client that looks configured and cannot work.
            raise LocationTransitionConflictError
        if location.is_primary:
            return location

        incumbent = await self.repository.get_primary(session, organization_id)
        if incumbent is not None:
            incumbent.is_primary = False
            incumbent.version += 1
            await session.flush()

        location.is_primary = True
        location.version += 1
        await session.flush()

        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type="platform.location.primary_changed",
                action="location.set_primary",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=organization_id,
                location_id=location.id,
                resource_type="location",
                resource_id=location.id,
                correlation_id=correlation_id,
                summary="Primary location changed.",
                metadata={
                    "previous_primary_id": str(incumbent.id) if incumbent else None,
                    "version": location.version,
                },
            ),
        )
        return location

    async def get(
        self, session: AsyncSession, organization_id: UUID, location_id: UUID
    ) -> Location:
        await self._organization(session, organization_id)
        location = await self.repository.get_by_id(session, organization_id, location_id)
        if location is None:
            raise LocationNotFoundError
        return location

    async def list(
        self, session: AsyncSession, organization_id: UUID, *, limit: int, offset: int
    ) -> tuple[list[Location], bool]:
        await self._organization(session, organization_id)
        return await self.repository.list(session, organization_id, limit=limit, offset=offset)

    @staticmethod
    def _parent_allows(
        status: OrganizationStatus, current: LocationStatus, target: LocationStatus
    ) -> bool:
        if status is OrganizationStatus.ACTIVE:
            return True
        if status in {OrganizationStatus.SUSPENDED, OrganizationStatus.ARCHIVED}:
            return False
        if status in {
            OrganizationStatus.PROSPECT,
            OrganizationStatus.ONBOARDING,
            OrganizationStatus.PAUSED,
        }:
            return target is not LocationStatus.ACTIVE
        if status is OrganizationStatus.OFFBOARDING:
            return target is LocationStatus.CLOSED_PERMANENTLY or (
                target is LocationStatus.ARCHIVED
                and current
                in {
                    LocationStatus.SETUP_REQUIRED,
                    LocationStatus.PAUSED,
                    LocationStatus.CLOSED_PERMANENTLY,
                }
            )
        return False

    async def transition(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        *,
        action: LocationLifecycleAction,
        expected_version: int,
        correlation_id: str,
    ) -> Location:
        organization = await self._organization(session, organization_id)
        location = await self.repository.get_by_id(session, organization_id, location_id)
        if location is None:
            raise LocationNotFoundError
        if location.version != expected_version:
            raise LocationVersionConflictError
        target = ACTION_TARGET[action]
        if target not in TRANSITIONS[location.status]:
            raise LocationTransitionConflictError
        if not self._parent_allows(organization.status, location.status, target):
            raise LocationParentStateConflictError
        previous = location.status
        updated = await self.repository.transition_status(
            session,
            organization_id,
            location_id,
            expected_status=previous,
            expected_version=expected_version,
            target_status=target,
        )
        if updated is None:
            raise LocationVersionConflictError
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type="platform.location.lifecycle_changed",
                action=f"location.{action.value}",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=organization_id,
                location_id=updated.id,
                resource_type="location",
                resource_id=updated.id,
                correlation_id=correlation_id,
                summary="Location lifecycle state changed.",
                metadata={
                    "from_status": previous.value,
                    "to_status": updated.status.value,
                    "version": updated.version,
                },
            ),
        )
        return updated
