"""Transaction-safe continuity guard for active organization owners."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import MembershipStatus, ScopeType
from apps.api.app.access_control.errors import LastActiveOwnerConflictError
from apps.api.app.access_control.models import (
    MembershipRoleAssignment,
    OrganizationMembership,
    Role,
)
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization

OWNER_ROLE_KEY = "organization_owner"


@dataclass(frozen=True, slots=True)
class ActiveOwner:
    assignment_id: UUID
    membership_id: UUID
    user_profile_id: UUID


@dataclass(frozen=True, slots=True)
class OwnerContinuityService:
    """Serialize owner-removing operations and reject the final removal."""

    async def guard_membership_change(
        self, session: AsyncSession, organization: Organization, membership_id: UUID
    ) -> None:
        await self._guard(session, organization, membership_id=membership_id)

    async def guard_assignment_removal(
        self, session: AsyncSession, organization: Organization, assignment_id: UUID
    ) -> None:
        await self._guard(session, organization, assignment_id=assignment_id)

    async def guard_user_deactivation(self, session: AsyncSession, user_profile_id: UUID) -> None:
        organization_ids = list(
            await session.scalars(
                select(Organization.id)
                .join(
                    OrganizationMembership,
                    OrganizationMembership.organization_id == Organization.id,
                )
                .join(
                    MembershipRoleAssignment,
                    MembershipRoleAssignment.membership_id == OrganizationMembership.id,
                )
                .join(Role, Role.id == MembershipRoleAssignment.role_id)
                .where(
                    Organization.status == OrganizationStatus.ACTIVE,
                    OrganizationMembership.user_profile_id == user_profile_id,
                    OrganizationMembership.status == MembershipStatus.ACTIVE,
                    MembershipRoleAssignment.scope_type == ScopeType.ORGANIZATION,
                    MembershipRoleAssignment.location_id.is_(None),
                    Role.key == OWNER_ROLE_KEY,
                )
                .distinct()
                .order_by(Organization.id)
            )
        )
        for organization_id in organization_ids:
            organization = await session.scalar(
                select(Organization).where(Organization.id == organization_id).with_for_update()
            )
            if organization is not None:
                await self._guard(session, organization, user_profile_id=user_profile_id)

    async def _guard(
        self,
        session: AsyncSession,
        organization: Organization,
        *,
        membership_id: UUID | None = None,
        assignment_id: UUID | None = None,
        user_profile_id: UUID | None = None,
    ) -> None:
        if organization.status is not OrganizationStatus.ACTIVE:
            return
        rows = await session.execute(
            select(
                MembershipRoleAssignment.id,
                OrganizationMembership.id,
                OrganizationMembership.user_profile_id,
            )
            .join(Role, Role.id == MembershipRoleAssignment.role_id)
            .join(
                OrganizationMembership,
                OrganizationMembership.id == MembershipRoleAssignment.membership_id,
            )
            .join(UserProfile, UserProfile.id == OrganizationMembership.user_profile_id)
            .where(
                MembershipRoleAssignment.organization_id == organization.id,
                MembershipRoleAssignment.scope_type == ScopeType.ORGANIZATION,
                MembershipRoleAssignment.location_id.is_(None),
                Role.key == OWNER_ROLE_KEY,
                OrganizationMembership.status == MembershipStatus.ACTIVE,
                UserProfile.status == UserStatus.ACTIVE,
            )
            .order_by(MembershipRoleAssignment.id)
            .with_for_update(of=(MembershipRoleAssignment, OrganizationMembership, UserProfile))
        )
        owners = [ActiveOwner(*row) for row in rows.tuples()]
        affected = [
            owner
            for owner in owners
            if (membership_id is not None and owner.membership_id == membership_id)
            or (assignment_id is not None and owner.assignment_id == assignment_id)
            or (user_profile_id is not None and owner.user_profile_id == user_profile_id)
        ]
        if affected and len(affected) == len(owners):
            raise LastActiveOwnerConflictError
