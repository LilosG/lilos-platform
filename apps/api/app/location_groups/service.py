"""Location-group validation, isolation, concurrency, and audit orchestration."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.location_groups.contracts import LocationGroupCreate, LocationGroupReplace
from apps.api.app.location_groups.enums import LocationGroupStatus
from apps.api.app.location_groups.errors import (
    LocationGroupKeyConflictError,
    LocationGroupLocationStateConflictError,
    LocationGroupMembershipConflictError,
    LocationGroupMembershipNotFoundError,
    LocationGroupNotFoundError,
    LocationGroupParentStateConflictError,
    LocationGroupStateConflictError,
    LocationGroupVersionConflictError,
)
from apps.api.app.location_groups.models import LocationGroup, LocationGroupMembership
from apps.api.app.location_groups.repository import (
    LocationGroupMembershipRepository,
    LocationGroupRepository,
)
from apps.api.app.locations.enums import LocationStatus
from apps.api.app.locations.errors import LocationNotFoundError
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.errors import OrganizationNotFoundError
from apps.api.app.organizations.models import Organization

CREATE_UPDATE_ALLOWED = frozenset(
    {
        OrganizationStatus.PROSPECT,
        OrganizationStatus.ONBOARDING,
        OrganizationStatus.ACTIVE,
        OrganizationStatus.PAUSED,
    }
)
ARCHIVE_ALLOWED = CREATE_UPDATE_ALLOWED | {OrganizationStatus.OFFBOARDING}
ADD_MEMBERSHIP_ALLOWED = frozenset(
    {
        OrganizationStatus.PROSPECT,
        OrganizationStatus.ONBOARDING,
        OrganizationStatus.ACTIVE,
    }
)
REMOVE_MEMBERSHIP_ALLOWED = ADD_MEMBERSHIP_ALLOWED | {
    OrganizationStatus.PAUSED,
    OrganizationStatus.OFFBOARDING,
}
MEMBERSHIP_LOCATION_STATUSES = frozenset(
    {
        LocationStatus.SETUP_REQUIRED,
        LocationStatus.ACTIVE,
        LocationStatus.PAUSED,
        LocationStatus.CLOSED_TEMPORARILY,
    }
)


async def _organization(
    session: AsyncSession, organization_id: UUID, *, lock: bool = False
) -> Organization:
    statement = select(Organization).where(Organization.id == organization_id)
    if lock:
        statement = statement.with_for_update()
    organization = await session.scalar(statement)
    if organization is None:
        raise OrganizationNotFoundError
    return organization


async def _group(
    session: AsyncSession,
    organization_id: UUID,
    group_id: UUID,
    *,
    lock: bool = False,
) -> LocationGroup:
    statement = select(LocationGroup).where(
        LocationGroup.organization_id == organization_id,
        LocationGroup.id == group_id,
    )
    if lock:
        statement = statement.with_for_update()
    group = await session.scalar(statement)
    if group is None:
        raise LocationGroupNotFoundError
    return group


async def _location(
    session: AsyncSession,
    organization_id: UUID,
    location_id: UUID,
    *,
    lock: bool = False,
) -> Location:
    statement = select(Location).where(
        Location.organization_id == organization_id,
        Location.id == location_id,
    )
    if lock:
        statement = statement.with_for_update()
    location = await session.scalar(statement)
    if location is None:
        raise LocationNotFoundError
    return location


def _require_parent(status: OrganizationStatus, allowed: frozenset[OrganizationStatus]) -> None:
    if status not in allowed:
        raise LocationGroupParentStateConflictError


@dataclass(frozen=True, slots=True)
class LocationGroupService:
    repository: LocationGroupRepository = field(default_factory=LocationGroupRepository)
    membership_repository: LocationGroupMembershipRepository = field(
        default_factory=LocationGroupMembershipRepository
    )
    audit_service: AuditEventService = field(default_factory=AuditEventService)

    async def create(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: LocationGroupCreate,
        *,
        correlation_id: str,
    ) -> LocationGroup:
        organization = await _organization(session, organization_id, lock=True)
        _require_parent(organization.status, CREATE_UPDATE_ALLOWED)
        group = LocationGroup(
            organization_id=organization_id,
            name=command.name,
            key=command.key,
            description=command.description,
            status=LocationGroupStatus.ACTIVE,
            version=1,
        )
        try:
            await self.repository.add(session, organization_id, group)
        except IntegrityError:
            raise LocationGroupKeyConflictError from None
        await self._audit_group(
            session,
            group,
            operation="created",
            changed_fields=["description", "key", "name", "status"],
            correlation_id=correlation_id,
        )
        return group

    async def get(
        self, session: AsyncSession, organization_id: UUID, group_id: UUID
    ) -> LocationGroup:
        await _organization(session, organization_id)
        group = await self.repository.get(session, organization_id, group_id)
        if group is None:
            raise LocationGroupNotFoundError
        return group

    async def list_groups(
        self, session: AsyncSession, organization_id: UUID, *, limit: int, offset: int
    ) -> tuple[list[LocationGroup], bool]:
        await _organization(session, organization_id)
        return await self.repository.list(session, organization_id, limit=limit, offset=offset)

    async def replace(
        self,
        session: AsyncSession,
        organization_id: UUID,
        group_id: UUID,
        command: LocationGroupReplace,
        *,
        correlation_id: str,
    ) -> LocationGroup:
        organization = await _organization(session, organization_id, lock=True)
        _require_parent(organization.status, CREATE_UPDATE_ALLOWED)
        group = await _group(session, organization_id, group_id, lock=True)
        if group.status is not LocationGroupStatus.ACTIVE:
            raise LocationGroupStateConflictError
        if group.version != command.expected_version:
            raise LocationGroupVersionConflictError
        changed_fields = sorted(
            field_name
            for field_name in ("description", "name")
            if getattr(group, field_name) != getattr(command, field_name)
        )
        updated = await self.repository.replace(session, organization_id, group_id, command)
        if updated is None:
            raise LocationGroupVersionConflictError
        await self._audit_group(
            session,
            updated,
            operation="updated",
            changed_fields=changed_fields,
            correlation_id=correlation_id,
        )
        return updated

    async def archive(
        self,
        session: AsyncSession,
        organization_id: UUID,
        group_id: UUID,
        *,
        expected_version: int,
        correlation_id: str,
    ) -> LocationGroup:
        organization = await _organization(session, organization_id, lock=True)
        _require_parent(organization.status, ARCHIVE_ALLOWED)
        group = await _group(session, organization_id, group_id, lock=True)
        if group.status is not LocationGroupStatus.ACTIVE:
            raise LocationGroupStateConflictError
        if group.version != expected_version:
            raise LocationGroupVersionConflictError
        updated = await self.repository.archive(
            session,
            organization_id,
            group_id,
            expected_version=expected_version,
        )
        if updated is None:
            raise LocationGroupVersionConflictError
        await self._audit_group(
            session,
            updated,
            operation="archived",
            changed_fields=["archived_at", "status"],
            correlation_id=correlation_id,
        )
        return updated

    async def list_members(
        self,
        session: AsyncSession,
        organization_id: UUID,
        group_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[LocationGroupMembership], bool]:
        await _organization(session, organization_id)
        await _group(session, organization_id, group_id)
        return await self.membership_repository.list_members(
            session,
            organization_id,
            group_id,
            limit=limit,
            offset=offset,
        )

    async def add_membership(
        self,
        session: AsyncSession,
        organization_id: UUID,
        group_id: UUID,
        location_id: UUID,
        *,
        correlation_id: str,
    ) -> LocationGroupMembership:
        organization = await _organization(session, organization_id, lock=True)
        _require_parent(organization.status, ADD_MEMBERSHIP_ALLOWED)
        group = await _group(session, organization_id, group_id, lock=True)
        if group.status is not LocationGroupStatus.ACTIVE:
            raise LocationGroupStateConflictError
        location = await _location(session, organization_id, location_id, lock=True)
        if location.status not in MEMBERSHIP_LOCATION_STATUSES:
            raise LocationGroupLocationStateConflictError
        if await self.membership_repository.is_member(
            session, organization_id, group_id, location_id
        ):
            raise LocationGroupMembershipConflictError
        membership = LocationGroupMembership(
            organization_id=organization_id,
            location_group_id=group_id,
            location_id=location_id,
        )
        try:
            await self.membership_repository.add(session, organization_id, membership)
        except IntegrityError:
            raise LocationGroupMembershipConflictError from None
        await self._audit_membership(
            session,
            membership,
            operation="added",
            correlation_id=correlation_id,
        )
        return membership

    async def remove_membership(
        self,
        session: AsyncSession,
        organization_id: UUID,
        group_id: UUID,
        location_id: UUID,
        *,
        correlation_id: str,
    ) -> LocationGroupMembership:
        organization = await _organization(session, organization_id, lock=True)
        _require_parent(organization.status, REMOVE_MEMBERSHIP_ALLOWED)
        await _group(session, organization_id, group_id, lock=True)
        await _location(session, organization_id, location_id, lock=True)
        membership = await self.membership_repository.remove(
            session, organization_id, group_id, location_id
        )
        if membership is None:
            raise LocationGroupMembershipNotFoundError
        await self._audit_membership(
            session,
            membership,
            operation="removed",
            correlation_id=correlation_id,
        )
        return membership

    async def _audit_group(
        self,
        session: AsyncSession,
        group: LocationGroup,
        *,
        operation: str,
        changed_fields: list[str],
        correlation_id: str,
    ) -> None:
        audit_changed_fields: list[JsonValue] = list(changed_fields)
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type=f"platform.location_group.{operation}",
                action=f"location_group.{operation}",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=group.organization_id,
                resource_type="location_group",
                resource_id=group.id,
                correlation_id=correlation_id,
                summary=f"Location group {operation}.",
                metadata={
                    "organization_id": str(group.organization_id),
                    "group_id": str(group.id),
                    "operation": operation,
                    "version": group.version,
                    "changed_fields": audit_changed_fields,
                },
            ),
        )

    async def _audit_membership(
        self,
        session: AsyncSession,
        membership: LocationGroupMembership,
        *,
        operation: str,
        correlation_id: str,
    ) -> None:
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type=f"platform.location_group_membership.{operation}",
                action=f"location_group_membership.{operation}",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=membership.organization_id,
                location_id=membership.location_id,
                resource_type="location_group_membership",
                resource_id=membership.id,
                correlation_id=correlation_id,
                summary=f"Location-group membership {operation}.",
                metadata={
                    "organization_id": str(membership.organization_id),
                    "group_id": str(membership.location_group_id),
                    "location_id": str(membership.location_id),
                    "operation": operation,
                },
            ),
        )
