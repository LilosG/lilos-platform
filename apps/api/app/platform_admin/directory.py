"""A read-only directory of people for platform administrators."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import InvitationStatus, MembershipStatus
from apps.api.app.access_control.models import (
    MembershipRoleAssignment,
    OrganizationInvitation,
    OrganizationMembership,
    Role,
)
from apps.api.app.authentication.models import UserProfile
from apps.api.app.organizations.models import Organization
from apps.api.app.platform_admin.contracts import (
    PendingInvitation,
    PlatformUser,
    PlatformUserPage,
    SystemRole,
    UserClientAccess,
)
from apps.api.app.platform_admin.models import PlatformAdministrator

# A person with more clients than this still shows the true total; the list is capped so one
# page stays a bounded size.
ACCESS_PER_USER = 25
# Access that has ended is history, not access.
ENDED = (MembershipStatus.REVOKED, MembershipStatus.EXPIRED)


class PlatformDirectoryService:
    """People, their standing and the clients they reach: name, email, role, status only."""

    async def list_users(
        self, session: AsyncSession, *, limit: int, offset: int
    ) -> PlatformUserPage:
        profiles = list(
            (
                await session.scalars(
                    select(UserProfile)
                    .order_by(
                        func.lower(func.coalesce(UserProfile.display_name, UserProfile.email))
                        .asc()
                        .nulls_last(),
                        UserProfile.id,
                    )
                    .offset(offset)
                    .limit(limit + 1)
                )
            ).all()
        )
        has_more = len(profiles) > limit
        profiles = profiles[:limit]
        ids = [profile.id for profile in profiles]

        administrators: set[UUID] = set()
        access: dict[UUID, list[UserClientAccess]] = defaultdict(list)
        if ids:
            administrators = set(
                (
                    await session.scalars(
                        select(PlatformAdministrator.user_profile_id).where(
                            PlatformAdministrator.user_profile_id.in_(ids),
                            PlatformAdministrator.revoked_at.is_(None),
                        )
                    )
                ).all()
            )
            rows = (
                await session.execute(
                    select(OrganizationMembership, Organization.name)
                    .join(Organization, Organization.id == OrganizationMembership.organization_id)
                    .where(
                        OrganizationMembership.user_profile_id.in_(ids),
                        OrganizationMembership.status.notin_(ENDED),
                        Organization.removed_at.is_(None),
                    )
                    .order_by(func.lower(Organization.name), Organization.id)
                )
            ).all()
            membership_ids = [membership.id for membership, _ in rows]
            roles: dict[UUID, set[SystemRole]] = defaultdict(set)
            pending: dict[UUID, PendingInvitation] = {}
            if membership_ids:
                for membership_id, key in (
                    await session.execute(
                        select(MembershipRoleAssignment.membership_id, Role.key)
                        .join(Role, Role.id == MembershipRoleAssignment.role_id)
                        .where(MembershipRoleAssignment.membership_id.in_(membership_ids))
                    )
                ).all():
                    if key in SystemRole:
                        roles[membership_id].add(SystemRole(key))
                for invitation in (
                    await session.scalars(
                        select(OrganizationInvitation).where(
                            OrganizationInvitation.membership_id.in_(membership_ids),
                            OrganizationInvitation.status == InvitationStatus.PENDING,
                        )
                    )
                ).all():
                    pending[invitation.membership_id] = PendingInvitation(
                        id=invitation.id,
                        version=invitation.version,
                        status=invitation.status,
                        expires_at=invitation.expires_at,
                    )
            for membership, organization_name in rows:
                access[membership.user_profile_id].append(
                    UserClientAccess(
                        organization_id=membership.organization_id,
                        organization_name=organization_name,
                        membership_type=membership.membership_type,
                        membership_status=membership.status,
                        roles=tuple(sorted(roles[membership.id], key=lambda role: role.value)),
                        invitation=pending.get(membership.id),
                    )
                )
        return PlatformUserPage(
            items=tuple(
                PlatformUser(
                    id=profile.id,
                    display_name=profile.display_name,
                    email=profile.email,
                    status=profile.status,
                    platform_administrator=profile.id in administrators,
                    access=tuple(access[profile.id][:ACCESS_PER_USER]),
                    access_total=len(access[profile.id]),
                )
                for profile in profiles
            ),
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        )
