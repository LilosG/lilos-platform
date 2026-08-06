"""Narrow organization-scoped persistence for the access domain."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import InvitationStatus, MembershipStatus
from apps.api.app.access_control.models import (
    MembershipPermissionDeny,
    MembershipRoleAssignment,
    OrganizationInvitation,
    OrganizationMembership,
    Permission,
    Role,
    RolePermission,
)
from apps.api.app.database.base import utc_now

MAX_ACCESS_LIST_LIMIT = 100


class MembershipRepository:
    async def add(
        self, session: AsyncSession, item: OrganizationMembership
    ) -> OrganizationMembership:
        session.add(item)
        await session.flush()
        return item

    async def get(
        self,
        session: AsyncSession,
        organization_id: UUID,
        membership_id: UUID,
        *,
        lock: bool = False,
    ) -> OrganizationMembership | None:
        statement = select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.id == membership_id,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(OrganizationMembership | None, await session.scalar(statement))

    async def get_by_user(
        self, session: AsyncSession, organization_id: UUID, user_profile_id: UUID
    ) -> OrganizationMembership | None:
        return cast(
            OrganizationMembership | None,
            await session.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == organization_id,
                    OrganizationMembership.user_profile_id == user_profile_id,
                )
            ),
        )

    async def list_by_user(
        self, session: AsyncSession, user_profile_id: UUID
    ) -> list[OrganizationMembership]:
        """Return every membership owned by the given user, across organizations.

        Self-scoped by ``user_profile_id`` only; callers must derive that value
        from the authenticated principal, never from client input.
        """
        return list(
            (
                await session.scalars(
                    select(OrganizationMembership)
                    .where(OrganizationMembership.user_profile_id == user_profile_id)
                    .order_by(OrganizationMembership.created_at.asc(), OrganizationMembership.id)
                )
            ).all()
        )

    async def transition(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        membership_id: UUID,
        expected_status: MembershipStatus,
        expected_version: int,
        target_status: MembershipStatus,
        timestamp: datetime,
    ) -> OrganizationMembership | None:
        values: dict[str, object] = {
            "status": target_status,
            "version": OrganizationMembership.version + 1,
            "updated_at": utc_now(),
        }
        if target_status is MembershipStatus.ACTIVE:
            values["activated_at"] = timestamp
            values["suspended_at"] = None
        elif target_status is MembershipStatus.SUSPENDED:
            values["suspended_at"] = timestamp
        elif target_status is MembershipStatus.REVOKED:
            values["revoked_at"] = timestamp
            values["suspended_at"] = None
        elif target_status is MembershipStatus.EXPIRED:
            values["expired_at"] = timestamp
        statement = (
            update(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.id == membership_id,
                OrganizationMembership.status == expected_status,
                OrganizationMembership.version == expected_version,
            )
            .values(**values)
            .returning(OrganizationMembership)
        )
        return cast(OrganizationMembership | None, await session.scalar(statement))

    async def list_by_organization(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[OrganizationMembership], bool]:
        if not 1 <= limit <= MAX_ACCESS_LIST_LIMIT:
            raise ValueError(f"Membership list limit must be 1-{MAX_ACCESS_LIST_LIMIT}")
        if offset < 0:
            raise ValueError("Membership list offset must not be negative")
        result = await session.scalars(
            select(OrganizationMembership)
            .where(OrganizationMembership.organization_id == organization_id)
            .order_by(OrganizationMembership.created_at.asc(), OrganizationMembership.id.asc())
            .offset(offset)
            .limit(limit + 1)
        )
        items = list(result)
        return items[:limit], len(items) > limit


class InvitationRepository:
    async def add(
        self, session: AsyncSession, item: OrganizationInvitation
    ) -> OrganizationInvitation:
        session.add(item)
        await session.flush()
        return item

    async def get(
        self,
        session: AsyncSession,
        organization_id: UUID,
        invitation_id: UUID,
        *,
        lock: bool = False,
    ) -> OrganizationInvitation | None:
        statement = select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.id == invitation_id,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(OrganizationInvitation | None, await session.scalar(statement))

    async def get_by_token_hash(
        self, session: AsyncSession, token_hash: bytes
    ) -> OrganizationInvitation | None:
        return cast(
            OrganizationInvitation | None,
            await session.scalar(
                select(OrganizationInvitation)
                .where(OrganizationInvitation.token_hash == token_hash)
                .with_for_update()
            ),
        )

    async def get_pending_by_email(
        self, session: AsyncSession, organization_id: UUID, normalized_email: str
    ) -> OrganizationInvitation | None:
        return cast(
            OrganizationInvitation | None,
            await session.scalar(
                select(OrganizationInvitation).where(
                    OrganizationInvitation.organization_id == organization_id,
                    OrganizationInvitation.normalized_email == normalized_email,
                    OrganizationInvitation.status == InvitationStatus.PENDING,
                )
            ),
        )

    async def list_by_organization(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[OrganizationInvitation], bool]:
        if not 1 <= limit <= MAX_ACCESS_LIST_LIMIT:
            raise ValueError(f"Invitation list limit must be 1-{MAX_ACCESS_LIST_LIMIT}")
        if offset < 0:
            raise ValueError("Invitation list offset must not be negative")
        result = await session.scalars(
            select(OrganizationInvitation)
            .where(OrganizationInvitation.organization_id == organization_id)
            .order_by(OrganizationInvitation.created_at.asc(), OrganizationInvitation.id.asc())
            .offset(offset)
            .limit(limit + 1)
        )
        items = list(result)
        return items[:limit], len(items) > limit

    async def transition(
        self,
        session: AsyncSession,
        *,
        invitation_id: UUID,
        expected_status: InvitationStatus,
        expected_version: int,
        target_status: InvitationStatus,
        accepted_by: UUID | None = None,
    ) -> OrganizationInvitation | None:
        now = utc_now()
        values: dict[str, object] = {
            "status": target_status,
            "version": OrganizationInvitation.version + 1,
            "updated_at": now,
        }
        if target_status is InvitationStatus.ACCEPTED:
            values.update(accepted_at=now, accepted_by_user_profile_id=accepted_by)
        elif target_status is InvitationStatus.CANCELLED:
            values["cancelled_at"] = now
        statement = (
            update(OrganizationInvitation)
            .where(
                OrganizationInvitation.id == invitation_id,
                OrganizationInvitation.status == expected_status,
                OrganizationInvitation.version == expected_version,
            )
            .values(**values)
            .returning(OrganizationInvitation)
        )
        return cast(OrganizationInvitation | None, await session.scalar(statement))


class CatalogRepository:
    async def get_role(self, session: AsyncSession, role_id: UUID) -> Role | None:
        return await session.get(Role, role_id)

    async def get_role_by_key(self, session: AsyncSession, key: str) -> Role | None:
        return cast(Role | None, await session.scalar(select(Role).where(Role.key == key)))

    async def list_roles(self, session: AsyncSession) -> list[Role]:
        return list(await session.scalars(select(Role).order_by(Role.key.asc())))

    async def get_permission(self, session: AsyncSession, permission_id: UUID) -> Permission | None:
        return await session.get(Permission, permission_id)

    async def get_permission_by_key(self, session: AsyncSession, key: str) -> Permission | None:
        return cast(
            Permission | None, await session.scalar(select(Permission).where(Permission.key == key))
        )

    async def list_permissions(self, session: AsyncSession) -> list[Permission]:
        return list(await session.scalars(select(Permission).order_by(Permission.key.asc())))

    async def list_mapping_pairs(self, session: AsyncSession) -> set[tuple[UUID, UUID]]:
        rows = await session.execute(select(RolePermission.role_id, RolePermission.permission_id))
        return set(rows.tuples())

    async def get_roles_by_ids(self, session: AsyncSession, role_ids: set[UUID]) -> list[Role]:
        """Resolve only roles referenced by one membership's applicable assignments."""
        if not role_ids:
            return []
        return list(await session.scalars(select(Role).where(Role.id.in_(role_ids))))

    async def role_ids_for_permission(
        self, session: AsyncSession, permission_id: UUID, role_ids: set[UUID]
    ) -> set[UUID]:
        """Resolve fixed-catalog allows for one permission and bounded role set."""
        if not role_ids:
            return set()
        rows = await session.scalars(
            select(RolePermission.role_id).where(
                RolePermission.permission_id == permission_id,
                RolePermission.role_id.in_(role_ids),
            )
        )
        return set(rows)

    async def seed_add(self, session: AsyncSession, *items: object) -> None:
        session.add_all(items)
        await session.flush()


class AssignmentRepository:
    async def add(
        self, session: AsyncSession, item: MembershipRoleAssignment
    ) -> MembershipRoleAssignment:
        session.add(item)
        await session.flush()
        return item

    async def remove(
        self, session: AsyncSession, organization_id: UUID, membership_id: UUID, assignment_id: UUID
    ) -> MembershipRoleAssignment | None:
        return cast(
            MembershipRoleAssignment | None,
            await session.scalar(
                delete(MembershipRoleAssignment)
                .where(
                    MembershipRoleAssignment.organization_id == organization_id,
                    MembershipRoleAssignment.membership_id == membership_id,
                    MembershipRoleAssignment.id == assignment_id,
                )
                .returning(MembershipRoleAssignment)
            ),
        )

    async def list(
        self, session: AsyncSession, organization_id: UUID, membership_id: UUID
    ) -> list[MembershipRoleAssignment]:
        return list(
            await session.scalars(
                select(MembershipRoleAssignment)
                .where(
                    MembershipRoleAssignment.organization_id == organization_id,
                    MembershipRoleAssignment.membership_id == membership_id,
                )
                .order_by(MembershipRoleAssignment.created_at, MembershipRoleAssignment.id)
            )
        )


class DenyRepository:
    async def add(
        self, session: AsyncSession, item: MembershipPermissionDeny
    ) -> MembershipPermissionDeny:
        session.add(item)
        await session.flush()
        return item

    async def remove(
        self, session: AsyncSession, organization_id: UUID, membership_id: UUID, deny_id: UUID
    ) -> MembershipPermissionDeny | None:
        return cast(
            MembershipPermissionDeny | None,
            await session.scalar(
                delete(MembershipPermissionDeny)
                .where(
                    MembershipPermissionDeny.organization_id == organization_id,
                    MembershipPermissionDeny.membership_id == membership_id,
                    MembershipPermissionDeny.id == deny_id,
                )
                .returning(MembershipPermissionDeny)
            ),
        )

    async def list(
        self, session: AsyncSession, organization_id: UUID, membership_id: UUID
    ) -> list[MembershipPermissionDeny]:
        return list(
            await session.scalars(
                select(MembershipPermissionDeny)
                .where(
                    MembershipPermissionDeny.organization_id == organization_id,
                    MembershipPermissionDeny.membership_id == membership_id,
                )
                .order_by(MembershipPermissionDeny.created_at, MembershipPermissionDeny.id)
            )
        )
