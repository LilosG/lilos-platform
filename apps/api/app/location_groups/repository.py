"""Strictly organization-scoped location-group persistence."""

from typing import cast
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.base import utc_now
from apps.api.app.location_groups.contracts import LocationGroupReplace
from apps.api.app.location_groups.enums import LocationGroupStatus
from apps.api.app.location_groups.models import LocationGroup, LocationGroupMembership

MAX_LOCATION_GROUP_LIST_LIMIT = 100
MAX_LOCATION_GROUP_MEMBER_LIST_LIMIT = 100


class LocationGroupRepository:
    async def add(
        self, session: AsyncSession, organization_id: UUID, group: LocationGroup
    ) -> LocationGroup:
        if group.organization_id != organization_id:
            raise ValueError("Location-group ownership does not match repository scope")
        session.add(group)
        await session.flush()
        return group

    async def get(
        self, session: AsyncSession, organization_id: UUID, group_id: UUID
    ) -> LocationGroup | None:
        return cast(
            LocationGroup | None,
            await session.scalar(
                select(LocationGroup).where(
                    LocationGroup.organization_id == organization_id,
                    LocationGroup.id == group_id,
                )
            ),
        )

    async def list(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[LocationGroup], bool]:
        if not 1 <= limit <= MAX_LOCATION_GROUP_LIST_LIMIT:
            raise ValueError(f"Location-group list limit must be 1-{MAX_LOCATION_GROUP_LIST_LIMIT}")
        if offset < 0:
            raise ValueError("Location-group list offset must not be negative")
        result = await session.scalars(
            select(LocationGroup)
            .where(LocationGroup.organization_id == organization_id)
            .order_by(LocationGroup.created_at.asc(), LocationGroup.id.asc())
            .offset(offset)
            .limit(limit + 1)
        )
        groups = list(result)
        return groups[:limit], len(groups) > limit

    async def replace(
        self,
        session: AsyncSession,
        organization_id: UUID,
        group_id: UUID,
        command: LocationGroupReplace,
    ) -> LocationGroup | None:
        statement = (
            update(LocationGroup)
            .where(
                LocationGroup.organization_id == organization_id,
                LocationGroup.id == group_id,
                LocationGroup.status == LocationGroupStatus.ACTIVE,
                LocationGroup.version == command.expected_version,
            )
            .values(
                name=command.name,
                description=command.description,
                version=LocationGroup.version + 1,
                updated_at=utc_now(),
            )
            .returning(LocationGroup)
        )
        return cast(LocationGroup | None, await session.scalar(statement))

    async def archive(
        self,
        session: AsyncSession,
        organization_id: UUID,
        group_id: UUID,
        *,
        expected_version: int,
    ) -> LocationGroup | None:
        statement = (
            update(LocationGroup)
            .where(
                LocationGroup.organization_id == organization_id,
                LocationGroup.id == group_id,
                LocationGroup.status == LocationGroupStatus.ACTIVE,
                LocationGroup.version == expected_version,
            )
            .values(
                status=LocationGroupStatus.ARCHIVED,
                archived_at=utc_now(),
                version=LocationGroup.version + 1,
                updated_at=utc_now(),
            )
            .returning(LocationGroup)
        )
        return cast(LocationGroup | None, await session.scalar(statement))


class LocationGroupMembershipRepository:
    async def add(
        self,
        session: AsyncSession,
        organization_id: UUID,
        membership: LocationGroupMembership,
    ) -> LocationGroupMembership:
        if membership.organization_id != organization_id:
            raise ValueError("Location-group membership ownership does not match repository scope")
        session.add(membership)
        await session.flush()
        return membership

    async def remove(
        self,
        session: AsyncSession,
        organization_id: UUID,
        group_id: UUID,
        location_id: UUID,
    ) -> LocationGroupMembership | None:
        statement = (
            delete(LocationGroupMembership)
            .where(
                LocationGroupMembership.organization_id == organization_id,
                LocationGroupMembership.location_group_id == group_id,
                LocationGroupMembership.location_id == location_id,
            )
            .returning(LocationGroupMembership)
        )
        return cast(LocationGroupMembership | None, await session.scalar(statement))

    async def list_members(
        self,
        session: AsyncSession,
        organization_id: UUID,
        group_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[LocationGroupMembership], bool]:
        if not 1 <= limit <= MAX_LOCATION_GROUP_MEMBER_LIST_LIMIT:
            raise ValueError(
                f"Location-group member list limit must be 1-{MAX_LOCATION_GROUP_MEMBER_LIST_LIMIT}"
            )
        if offset < 0:
            raise ValueError("Location-group member list offset must not be negative")
        result = await session.scalars(
            select(LocationGroupMembership)
            .where(
                LocationGroupMembership.organization_id == organization_id,
                LocationGroupMembership.location_group_id == group_id,
            )
            .order_by(
                LocationGroupMembership.created_at.asc(),
                LocationGroupMembership.id.asc(),
            )
            .offset(offset)
            .limit(limit + 1)
        )
        memberships = list(result)
        return memberships[:limit], len(memberships) > limit

    async def is_member(
        self,
        session: AsyncSession,
        organization_id: UUID,
        group_id: UUID,
        location_id: UUID,
    ) -> bool:
        membership_id = await session.scalar(
            select(LocationGroupMembership.id).where(
                LocationGroupMembership.organization_id == organization_id,
                LocationGroupMembership.location_group_id == group_id,
                LocationGroupMembership.location_id == location_id,
            )
        )
        return membership_id is not None
