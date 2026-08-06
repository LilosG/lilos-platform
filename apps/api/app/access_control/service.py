"""Transactional organization-access services and approved state policy."""

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import timedelta
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.contracts import (
    InvitationCreate,
    MembershipCreate,
    PermissionDenyCreate,
    RoleAssignmentCreate,
)
from apps.api.app.access_control.enums import (
    InvitationStatus,
    MembershipStatus,
    MembershipType,
    ScopeType,
)
from apps.api.app.access_control.errors import (
    AccessParentStateError,
    AssignmentConflictError,
    AssignmentNotFoundError,
    CatalogConflictError,
    DenyConflictError,
    DenyNotFoundError,
    InvitationAcceptanceError,
    InvitationConflictError,
    InvitationNotFoundError,
    InvitationVersionConflictError,
    MembershipConflictError,
    MembershipLifecycleConflictError,
    MembershipNotFoundError,
    MembershipVersionConflictError,
    ScopeValidationError,
    UserAccountNotFoundError,
)
from apps.api.app.access_control.models import (
    MembershipPermissionDeny,
    MembershipRoleAssignment,
    OrganizationInvitation,
    OrganizationMembership,
)
from apps.api.app.access_control.owner_continuity import OwnerContinuityService
from apps.api.app.access_control.policy import (
    ADD_DENY_STATES,
    ADD_ROLE_STATES,
    CANCEL_INVITATION_STATES,
    CREATE_STATES,
    REMOVE_DENY_STATES,
    REMOVE_ROLE_STATES,
    RESTORE_STATES,
    SUSPEND_REVOKE_STATES,
)
from apps.api.app.access_control.repository import (
    AssignmentRepository,
    CatalogRepository,
    DenyRepository,
    InvitationRepository,
    MembershipRepository,
)
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.authentication.contracts import AuthenticatedPrincipal
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.authentication.repository import UserProfileRepository
from apps.api.app.database.base import utc_now
from apps.api.app.locations.models import Location
from apps.api.app.organizations.models import Organization

MEMBERSHIP_TRANSITIONS = {
    (MembershipStatus.INVITED, MembershipStatus.ACTIVE),
    (MembershipStatus.INVITED, MembershipStatus.REVOKED),
    (MembershipStatus.INVITED, MembershipStatus.EXPIRED),
    (MembershipStatus.ACTIVE, MembershipStatus.SUSPENDED),
    (MembershipStatus.ACTIVE, MembershipStatus.REVOKED),
    (MembershipStatus.SUSPENDED, MembershipStatus.ACTIVE),
    (MembershipStatus.SUSPENDED, MembershipStatus.REVOKED),
}


async def lock_organization(session: AsyncSession, organization_id: UUID) -> Organization:
    organization = await session.scalar(
        select(Organization).where(Organization.id == organization_id).with_for_update()
    )
    if organization is None:
        raise MembershipNotFoundError
    return organization


async def lock_user(session: AsyncSession, user_id: UUID) -> UserProfile:
    user = await session.scalar(
        select(UserProfile).where(UserProfile.id == user_id).with_for_update()
    )
    if user is None or user.status is not UserStatus.ACTIVE:
        raise MembershipNotFoundError
    return user


async def lock_location(
    session: AsyncSession, organization_id: UUID, location_id: UUID
) -> Location:
    location = await session.scalar(
        select(Location)
        .where(Location.organization_id == organization_id, Location.id == location_id)
        .with_for_update()
    )
    if location is None:
        raise ScopeValidationError
    return location


@dataclass(frozen=True, slots=True)
class InvitationAcceptanceResult:
    invitation: OrganizationInvitation | None
    membership: OrganizationMembership | None
    accepted: bool


@dataclass(frozen=True, slots=True)
class AccessControlService:
    memberships: MembershipRepository = field(default_factory=MembershipRepository)
    invitations: InvitationRepository = field(default_factory=InvitationRepository)
    catalog: CatalogRepository = field(default_factory=CatalogRepository)
    assignments: AssignmentRepository = field(default_factory=AssignmentRepository)
    denies: DenyRepository = field(default_factory=DenyRepository)
    audit: AuditEventService = field(default_factory=AuditEventService)
    owner_continuity: OwnerContinuityService = field(default_factory=OwnerContinuityService)
    user_profiles: UserProfileRepository = field(default_factory=UserProfileRepository)

    async def find_user_by_email(self, session: AsyncSession, email: str) -> UserProfile:
        """Resolve an existing platform user by email for onboarding add/invite flows.

        Only ever finds users who have already signed in at least once; there
        is no server-side path to fabricate an identity for someone who has
        not yet authenticated (no Supabase admin credential is available to
        this codebase). Callers must present ``UserAccountNotFoundError`` as
        "ask them to sign in first, then try again" rather than a raw 404.
        """
        profile = await self.user_profiles.get_by_email(session, email)
        if profile is None:
            raise UserAccountNotFoundError
        return profile

    async def list_memberships(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[OrganizationMembership], bool]:
        return await self.memberships.list_by_organization(
            session, organization_id, limit=limit, offset=offset
        )

    async def list_invitations(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[OrganizationInvitation], bool]:
        return await self.invitations.list_by_organization(
            session, organization_id, limit=limit, offset=offset
        )

    async def _audit(
        self,
        session: AsyncSession,
        *,
        event: str,
        action: str,
        organization_id: UUID,
        resource_type: str,
        resource_id: UUID,
        correlation_id: str,
        metadata: dict[str, object],
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=action,
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                organization_id=organization_id,
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=f"{resource_type.replace('_', ' ').title()} access record changed.",
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    async def create_membership(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: MembershipCreate,
        *,
        correlation_id: str,
    ) -> OrganizationMembership:
        organization = await lock_organization(session, organization_id)
        if organization.status not in CREATE_STATES:
            raise AccessParentStateError
        await lock_user(session, command.user_profile_id)
        membership = OrganizationMembership(
            organization_id=organization_id,
            user_profile_id=command.user_profile_id,
            membership_type=command.membership_type,
            status=MembershipStatus.ACTIVE,
            activated_at=utc_now(),
            version=1,
        )
        try:
            await self.memberships.add(session, membership)
        except IntegrityError:
            raise MembershipConflictError from None
        await self._audit(
            session,
            event="platform.membership.created",
            action="membership.create",
            organization_id=organization_id,
            resource_type="organization_membership",
            resource_id=membership.id,
            correlation_id=correlation_id,
            metadata={
                "membership_id": str(membership.id),
                "user_profile_id": str(membership.user_profile_id),
                "operation": "created",
                "resulting_status": membership.status.value,
                "version": membership.version,
            },
        )
        return membership

    async def create_membership_by_email(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        email: str,
        membership_type: MembershipType,
        correlation_id: str,
    ) -> OrganizationMembership:
        """Add an existing platform user (resolved by email) as an active member.

        Composes ``find_user_by_email`` with ``create_membership`` verbatim;
        adds no new membership-creation logic of its own.
        """
        profile = await self.find_user_by_email(session, email)
        return await self.create_membership(
            session,
            organization_id,
            MembershipCreate(user_profile_id=profile.id, membership_type=membership_type),
            correlation_id=correlation_id,
        )

    async def get_membership(
        self, session: AsyncSession, organization_id: UUID, membership_id: UUID
    ) -> OrganizationMembership:
        membership = await self.memberships.get(session, organization_id, membership_id)
        if membership is None:
            raise MembershipNotFoundError
        return membership

    async def list_my_organizations(
        self, session: AsyncSession, user_profile_id: UUID
    ) -> list[tuple[OrganizationMembership, Organization]]:
        """Resolve every organization the caller belongs to, self-scoped only."""
        memberships = await self.memberships.list_by_user(session, user_profile_id)
        if not memberships:
            return []
        organization_ids = {membership.organization_id for membership in memberships}
        organizations = {
            organization.id: organization
            for organization in (
                await session.scalars(
                    select(Organization).where(Organization.id.in_(organization_ids))
                )
            ).all()
        }
        return [
            (membership, organizations[membership.organization_id])
            for membership in memberships
            if membership.organization_id in organizations
        ]

    async def transition_membership(
        self,
        session: AsyncSession,
        organization_id: UUID,
        membership_id: UUID,
        *,
        target: MembershipStatus,
        expected_version: int,
        correlation_id: str,
    ) -> OrganizationMembership:
        organization = await lock_organization(session, organization_id)
        membership = await self.memberships.get(session, organization_id, membership_id, lock=True)
        if membership is None:
            raise MembershipNotFoundError
        if membership.version != expected_version:
            raise MembershipVersionConflictError
        if (membership.status, target) not in MEMBERSHIP_TRANSITIONS:
            raise MembershipLifecycleConflictError
        if target is MembershipStatus.ACTIVE and organization.status not in RESTORE_STATES:
            raise AccessParentStateError
        if (
            target in {MembershipStatus.SUSPENDED, MembershipStatus.REVOKED}
            and organization.status not in SUSPEND_REVOKE_STATES
        ):
            raise AccessParentStateError
        if target in {MembershipStatus.SUSPENDED, MembershipStatus.REVOKED}:
            await self.owner_continuity.guard_membership_change(
                session, organization, membership_id
            )
        updated = await self.memberships.transition(
            session,
            organization_id=organization_id,
            membership_id=membership_id,
            expected_status=membership.status,
            expected_version=expected_version,
            target_status=target,
            timestamp=utc_now(),
        )
        if updated is None:
            raise MembershipVersionConflictError
        operation = (
            "restored"
            if membership.status is MembershipStatus.SUSPENDED and target is MembershipStatus.ACTIVE
            else target.value
        )
        await self._audit(
            session,
            event=f"platform.membership.{operation}",
            action=f"membership.{operation}",
            organization_id=organization_id,
            resource_type="organization_membership",
            resource_id=updated.id,
            correlation_id=correlation_id,
            metadata={
                "membership_id": str(updated.id),
                "user_profile_id": str(updated.user_profile_id),
                "operation": operation,
                "prior_status": membership.status.value,
                "resulting_status": updated.status.value,
                "version": updated.version,
            },
        )
        return updated

    async def create_invitation(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: InvitationCreate,
        *,
        correlation_id: str,
    ) -> tuple[OrganizationInvitation, str]:
        organization = await lock_organization(session, organization_id)
        if organization.status not in CREATE_STATES:
            raise AccessParentStateError
        await lock_user(session, command.user_profile_id)
        await lock_user(session, command.invited_by_user_profile_id)
        if await self.memberships.get_by_user(session, organization_id, command.user_profile_id):
            raise MembershipConflictError
        if await self.invitations.get_pending_by_email(session, organization_id, command.email):
            raise InvitationConflictError
        now = utc_now()
        membership = OrganizationMembership(
            organization_id=organization_id,
            user_profile_id=command.user_profile_id,
            membership_type=command.membership_type,
            status=MembershipStatus.INVITED,
            invited_at=now,
            version=1,
        )
        try:
            await self.memberships.add(session, membership)
            token = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")
            invitation = OrganizationInvitation(
                organization_id=organization_id,
                membership_id=membership.id,
                normalized_email=command.email,
                token_hash=hashlib.sha256(token.encode("ascii")).digest(),
                status=InvitationStatus.PENDING,
                expires_at=now + timedelta(days=command.lifetime_days),
                invited_by_user_profile_id=command.invited_by_user_profile_id,
                version=1,
            )
            await self.invitations.add(session, invitation)
        except IntegrityError:
            raise InvitationConflictError from None
        await self._audit(
            session,
            event="platform.membership.created",
            action="membership.create",
            organization_id=organization_id,
            resource_type="organization_membership",
            resource_id=membership.id,
            correlation_id=correlation_id,
            metadata={
                "membership_id": str(membership.id),
                "user_profile_id": str(membership.user_profile_id),
                "operation": "created",
                "resulting_status": "invited",
                "version": membership.version,
            },
        )
        await self._audit(
            session,
            event="platform.invitation.created",
            action="invitation.create",
            organization_id=organization_id,
            resource_type="organization_invitation",
            resource_id=invitation.id,
            correlation_id=correlation_id,
            metadata={
                "invitation_id": str(invitation.id),
                "membership_id": str(membership.id),
                "user_profile_id": str(membership.user_profile_id),
                "operation": "created",
                "resulting_status": invitation.status.value,
                "version": invitation.version,
            },
        )
        return invitation, token

    async def create_invitation_by_email(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        email: str,
        membership_type: MembershipType,
        invited_by_user_profile_id: UUID,
        lifetime_days: int = 7,
        correlation_id: str,
    ) -> tuple[OrganizationInvitation, str]:
        """Invite an existing platform user (resolved by email) to this organization.

        Composes ``find_user_by_email`` with ``create_invitation`` verbatim.
        Raises ``UserAccountNotFoundError`` if nobody has authenticated yet
        with that email — this codebase has no credential to pre-provision an
        identity for someone who has never signed in.
        """
        profile = await self.find_user_by_email(session, email)
        return await self.create_invitation(
            session,
            organization_id,
            InvitationCreate(
                user_profile_id=profile.id,
                email=email,
                membership_type=membership_type,
                invited_by_user_profile_id=invited_by_user_profile_id,
                lifetime_days=lifetime_days,
            ),
            correlation_id=correlation_id,
        )

    async def get_invitation(
        self, session: AsyncSession, organization_id: UUID, invitation_id: UUID
    ) -> OrganizationInvitation:
        invitation = await self.invitations.get(session, organization_id, invitation_id)
        if invitation is None:
            raise InvitationNotFoundError
        return invitation

    async def cancel_invitation(
        self,
        session: AsyncSession,
        organization_id: UUID,
        invitation_id: UUID,
        *,
        expected_version: int,
        correlation_id: str,
    ) -> OrganizationInvitation:
        organization = await lock_organization(session, organization_id)
        if organization.status not in CANCEL_INVITATION_STATES:
            raise AccessParentStateError
        invitation = await self.invitations.get(session, organization_id, invitation_id, lock=True)
        if invitation is None:
            raise InvitationNotFoundError
        if invitation.version != expected_version:
            raise InvitationVersionConflictError
        if invitation.status is not InvitationStatus.PENDING:
            raise InvitationConflictError
        membership = await self.memberships.get(
            session, organization_id, invitation.membership_id, lock=True
        )
        if membership is None or membership.status is not MembershipStatus.INVITED:
            raise InvitationConflictError
        updated = await self.invitations.transition(
            session,
            invitation_id=invitation.id,
            expected_status=InvitationStatus.PENDING,
            expected_version=expected_version,
            target_status=InvitationStatus.CANCELLED,
        )
        changed_membership = await self.memberships.transition(
            session,
            organization_id=organization_id,
            membership_id=membership.id,
            expected_status=MembershipStatus.INVITED,
            expected_version=membership.version,
            target_status=MembershipStatus.REVOKED,
            timestamp=utc_now(),
        )
        if updated is None or changed_membership is None:
            raise InvitationVersionConflictError
        await self._audit(
            session,
            event="platform.invitation.cancelled",
            action="invitation.cancel",
            organization_id=organization_id,
            resource_type="organization_invitation",
            resource_id=updated.id,
            correlation_id=correlation_id,
            metadata={
                "invitation_id": str(updated.id),
                "membership_id": str(membership.id),
                "operation": "cancelled",
                "resulting_status": "cancelled",
                "version": updated.version,
            },
        )
        await self._audit(
            session,
            event="platform.membership.revoked",
            action="membership.revoke",
            organization_id=organization_id,
            resource_type="organization_membership",
            resource_id=changed_membership.id,
            correlation_id=correlation_id,
            metadata={
                "membership_id": str(changed_membership.id),
                "user_profile_id": str(changed_membership.user_profile_id),
                "operation": "revoked",
                "prior_status": "invited",
                "resulting_status": "revoked",
                "version": changed_membership.version,
            },
        )
        return updated

    async def accept_invitation(
        self,
        session: AsyncSession,
        token: str,
        principal: AuthenticatedPrincipal,
        *,
        correlation_id: str,
    ) -> InvitationAcceptanceResult:
        token_hash = hashlib.sha256(token.encode("utf-8")).digest()
        invitation = await self.invitations.get_by_token_hash(session, token_hash)
        if invitation is None or invitation.status is not InvitationStatus.PENDING:
            return InvitationAcceptanceResult(None, None, False)
        organization = await lock_organization(session, invitation.organization_id)
        membership = await self.memberships.get(
            session, invitation.organization_id, invitation.membership_id, lock=True
        )
        user = await lock_user(session, principal.platform_user_id)
        if membership is None or membership.status is not MembershipStatus.INVITED:
            return InvitationAcceptanceResult(None, None, False)
        if (
            user.id != membership.user_profile_id
            or user.email is None
            or user.email.strip().casefold() != invitation.normalized_email
        ):
            return InvitationAcceptanceResult(None, None, False)
        if invitation.expires_at <= utc_now():
            expired_invitation = await self.invitations.transition(
                session,
                invitation_id=invitation.id,
                expected_status=InvitationStatus.PENDING,
                expected_version=invitation.version,
                target_status=InvitationStatus.EXPIRED,
            )
            expired_membership = await self.memberships.transition(
                session,
                organization_id=organization.id,
                membership_id=membership.id,
                expected_status=MembershipStatus.INVITED,
                expected_version=membership.version,
                target_status=MembershipStatus.EXPIRED,
                timestamp=utc_now(),
            )
            if expired_invitation and expired_membership:
                await self._audit(
                    session,
                    event="platform.invitation.expired",
                    action="invitation.expire",
                    organization_id=organization.id,
                    resource_type="organization_invitation",
                    resource_id=invitation.id,
                    correlation_id=correlation_id,
                    metadata={
                        "invitation_id": str(invitation.id),
                        "membership_id": str(membership.id),
                        "operation": "expired",
                        "resulting_status": "expired",
                        "version": expired_invitation.version,
                    },
                )
                await self._audit(
                    session,
                    event="platform.membership.expired",
                    action="membership.expire",
                    organization_id=organization.id,
                    resource_type="organization_membership",
                    resource_id=expired_membership.id,
                    correlation_id=correlation_id,
                    metadata={
                        "membership_id": str(expired_membership.id),
                        "user_profile_id": str(expired_membership.user_profile_id),
                        "operation": "expired",
                        "prior_status": "invited",
                        "resulting_status": "expired",
                        "version": expired_membership.version,
                    },
                )
            return InvitationAcceptanceResult(expired_invitation, expired_membership, False)
        if organization.status not in RESTORE_STATES:
            return InvitationAcceptanceResult(None, None, False)
        accepted = await self.invitations.transition(
            session,
            invitation_id=invitation.id,
            expected_status=InvitationStatus.PENDING,
            expected_version=invitation.version,
            target_status=InvitationStatus.ACCEPTED,
            accepted_by=user.id,
        )
        active = await self.memberships.transition(
            session,
            organization_id=organization.id,
            membership_id=membership.id,
            expected_status=MembershipStatus.INVITED,
            expected_version=membership.version,
            target_status=MembershipStatus.ACTIVE,
            timestamp=utc_now(),
        )
        if accepted is None or active is None:
            raise InvitationAcceptanceError
        await self._audit(
            session,
            event="platform.invitation.accepted",
            action="invitation.accept",
            organization_id=organization.id,
            resource_type="organization_invitation",
            resource_id=accepted.id,
            correlation_id=correlation_id,
            metadata={
                "invitation_id": str(accepted.id),
                "membership_id": str(active.id),
                "user_profile_id": str(user.id),
                "operation": "accepted",
                "resulting_status": "accepted",
                "version": accepted.version,
            },
        )
        await self._audit(
            session,
            event="platform.membership.activated",
            action="membership.activate",
            organization_id=organization.id,
            resource_type="organization_membership",
            resource_id=active.id,
            correlation_id=correlation_id,
            metadata={
                "membership_id": str(active.id),
                "user_profile_id": str(user.id),
                "operation": "activated",
                "prior_status": "invited",
                "resulting_status": "active",
                "version": active.version,
            },
        )
        return InvitationAcceptanceResult(accepted, active, True)

    async def add_assignment(
        self,
        session: AsyncSession,
        organization_id: UUID,
        membership_id: UUID,
        command: RoleAssignmentCreate,
        *,
        correlation_id: str,
    ) -> MembershipRoleAssignment:
        organization = await lock_organization(session, organization_id)
        if organization.status not in ADD_ROLE_STATES:
            raise AccessParentStateError
        membership = await self.memberships.get(session, organization_id, membership_id, lock=True)
        if membership is None:
            raise MembershipNotFoundError
        role = await self.catalog.get_role(session, command.role_id)
        if role is None:
            raise CatalogConflictError
        if command.location_id is not None:
            await lock_location(session, organization_id, command.location_id)
        assignment = MembershipRoleAssignment(
            organization_id=organization_id,
            membership_id=membership_id,
            role_id=role.id,
            scope_type=command.scope_type,
            location_id=command.location_id,
        )
        try:
            await self.assignments.add(session, assignment)
        except IntegrityError:
            raise AssignmentConflictError from None
        await self._audit(
            session,
            event="platform.role.assigned",
            action="role_assignment.add",
            organization_id=organization_id,
            resource_type="membership_role_assignment",
            resource_id=assignment.id,
            correlation_id=correlation_id,
            metadata={
                "assignment_id": str(assignment.id),
                "membership_id": str(membership_id),
                "role_id": str(role.id),
                "scope_type": command.scope_type.value,
                "location_id": str(command.location_id) if command.location_id else None,
                "operation": "added",
            },
        )
        return assignment

    async def remove_assignment(
        self,
        session: AsyncSession,
        organization_id: UUID,
        membership_id: UUID,
        assignment_id: UUID,
        *,
        correlation_id: str,
    ) -> MembershipRoleAssignment:
        organization = await lock_organization(session, organization_id)
        if organization.status not in REMOVE_ROLE_STATES:
            raise AccessParentStateError
        await self.owner_continuity.guard_assignment_removal(session, organization, assignment_id)
        if await self.memberships.get(session, organization_id, membership_id, lock=True) is None:
            raise MembershipNotFoundError
        item = await self.assignments.remove(session, organization_id, membership_id, assignment_id)
        if item is None:
            raise AssignmentNotFoundError
        await self._audit(
            session,
            event="platform.role_assignment.removed",
            action="role_assignment.remove",
            organization_id=organization_id,
            resource_type="membership_role_assignment",
            resource_id=item.id,
            correlation_id=correlation_id,
            metadata={
                "assignment_id": str(item.id),
                "membership_id": str(membership_id),
                "role_id": str(item.role_id),
                "scope_type": item.scope_type.value,
                "location_id": str(item.location_id) if item.location_id else None,
                "operation": "removed",
            },
        )
        return item

    async def add_deny(
        self,
        session: AsyncSession,
        organization_id: UUID,
        membership_id: UUID,
        command: PermissionDenyCreate,
        *,
        correlation_id: str,
    ) -> MembershipPermissionDeny:
        organization = await lock_organization(session, organization_id)
        if organization.status not in ADD_DENY_STATES:
            raise AccessParentStateError
        if await self.memberships.get(session, organization_id, membership_id, lock=True) is None:
            raise MembershipNotFoundError
        permission = await self.catalog.get_permission(session, command.permission_id)
        if permission is None:
            raise CatalogConflictError
        if command.location_id is not None:
            await lock_location(session, organization_id, command.location_id)
        item = MembershipPermissionDeny(
            organization_id=organization_id,
            membership_id=membership_id,
            permission_id=permission.id,
            scope_type=command.scope_type,
            location_id=command.location_id,
        )
        try:
            await self.denies.add(session, item)
        except IntegrityError:
            raise DenyConflictError from None
        await self._audit(
            session,
            event="platform.permission_deny.added",
            action="permission_deny.add",
            organization_id=organization_id,
            resource_type="membership_permission_deny",
            resource_id=item.id,
            correlation_id=correlation_id,
            metadata={
                "deny_id": str(item.id),
                "membership_id": str(membership_id),
                "permission_id": str(item.permission_id),
                "scope_type": command.scope_type.value,
                "location_id": str(command.location_id) if command.location_id else None,
                "operation": "added",
            },
        )
        return item

    async def remove_deny(
        self,
        session: AsyncSession,
        organization_id: UUID,
        membership_id: UUID,
        deny_id: UUID,
        *,
        correlation_id: str,
    ) -> MembershipPermissionDeny:
        organization = await lock_organization(session, organization_id)
        if organization.status not in REMOVE_DENY_STATES:
            raise AccessParentStateError
        if await self.memberships.get(session, organization_id, membership_id, lock=True) is None:
            raise MembershipNotFoundError
        item = await self.denies.remove(session, organization_id, membership_id, deny_id)
        if item is None:
            raise DenyNotFoundError
        await self._audit(
            session,
            event="platform.permission_deny.removed",
            action="permission_deny.remove",
            organization_id=organization_id,
            resource_type="membership_permission_deny",
            resource_id=item.id,
            correlation_id=correlation_id,
            metadata={
                "deny_id": str(item.id),
                "membership_id": str(membership_id),
                "permission_id": str(item.permission_id),
                "scope_type": item.scope_type.value,
                "location_id": str(item.location_id) if item.location_id else None,
                "operation": "removed",
            },
        )
        return item

    async def bootstrap_owner(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: MembershipCreate,
        *,
        correlation_id: str,
    ) -> tuple[OrganizationMembership, MembershipRoleAssignment]:
        membership = await self.create_membership(
            session, organization_id, command, correlation_id=correlation_id
        )
        owner = await self.catalog.get_role_by_key(session, "organization_owner")
        if owner is None:
            raise CatalogConflictError
        assignment = await self.add_assignment(
            session,
            organization_id,
            membership.id,
            RoleAssignmentCreate(role_id=owner.id, scope_type=ScopeType.ORGANIZATION),
            correlation_id=correlation_id,
        )
        return membership, assignment
