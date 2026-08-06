"""Owner-bootstrap orchestration reusing existing domain services verbatim."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.errors import CatalogConflictError, UserAccountNotFoundError
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.authentication.contracts import UserProfileCreate
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authentication.repository import UserProfileRepository
from apps.api.app.authentication.service import UserAdministrationService
from apps.api.app.authorization.service import assurance_satisfies
from apps.api.app.organizations.service import OrganizationService
from apps.api.app.platform_admin.contracts import (
    PlatformAdministratorGrantResult,
    PlatformAdministratorSelfStatus,
    PlatformOwnerBootstrapResult,
)
from apps.api.app.platform_admin.models import PlatformAdministrator
from apps.api.app.platform_admin.repository import PlatformAdministratorRepository


@dataclass(frozen=True, slots=True)
class PlatformAdministrationService:
    """Bootstrap the first owner of an organization, exactly as the pilot script does."""

    user_profiles: UserProfileRepository = field(default_factory=UserProfileRepository)
    user_administration: UserAdministrationService = field(
        default_factory=UserAdministrationService
    )
    organizations: OrganizationService = field(default_factory=OrganizationService)
    access: AccessControlService = field(default_factory=AccessControlService)
    platform_administrators: PlatformAdministratorRepository = field(
        default_factory=PlatformAdministratorRepository
    )
    audit: AuditEventService = field(default_factory=AuditEventService)

    async def bootstrap_owner(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: UserProfileCreate,
        *,
        correlation_id: str,
    ) -> PlatformOwnerBootstrapResult:
        """Idempotently provision one active organization-owner membership.

        Reuses the exact sequence ``scripts/provision_pilot_owner.py`` uses:
        find-or-create the user profile, find-or-create the organization
        membership, find-or-add the ``organization_owner`` role assignment.
        Re-invoking with the same ``auth_user_id`` against the same
        organization never creates duplicate records.
        """
        await self.organizations.get(session, organization_id)

        profile = await self.user_profiles.get_by_auth_user_id(session, command.auth_user_id)
        profile_created = False
        if profile is None:
            profile = await self.user_administration.provision(
                session, command, correlation_id=correlation_id
            )
            profile_created = True

        membership = await self.access.memberships.get_by_user(session, organization_id, profile.id)
        membership_created = False
        if membership is None:
            membership = await self.access.create_membership(
                session,
                organization_id,
                MembershipCreate(user_profile_id=profile.id, membership_type=MembershipType.CLIENT),
                correlation_id=correlation_id,
            )
            membership_created = True

        owner_role = await self.access.catalog.get_role_by_key(session, "organization_owner")
        if owner_role is None:
            raise CatalogConflictError
        existing_assignments = await self.access.assignments.list(
            session, organization_id, membership.id
        )
        assignment_created = False
        if not any(item.role_id == owner_role.id for item in existing_assignments):
            await self.access.add_assignment(
                session,
                organization_id,
                membership.id,
                RoleAssignmentCreate(role_id=owner_role.id, scope_type=ScopeType.ORGANIZATION),
                correlation_id=correlation_id,
            )
            assignment_created = True

        return PlatformOwnerBootstrapResult(
            user_profile_id=profile.id,
            user_profile_created=profile_created,
            membership_id=membership.id,
            membership_created=membership_created,
            owner_role_assignment_created=assignment_created,
        )

    async def grant_administrator(
        self,
        session: AsyncSession,
        *,
        email: str,
        granted_by_user_profile_id: UUID | None,
        reason: str,
        source: str,
        correlation_id: str,
    ) -> PlatformAdministratorGrantResult:
        """Idempotently grant the narrow, cross-organization platform-administrator role.

        Resolves the target by email against an *existing* ``UserProfile``
        (created only on that person's own first real sign-in) — never
        creates or fabricates an identity, and never accepts a raw UUID from
        a caller. Additive to the per-organization RBAC engine used
        everywhere else: this grants no membership, role, or organization
        access on its own. Re-invoking for an already-active grant returns
        the existing grant untouched and writes no duplicate audit event.
        """
        profile = await self.user_profiles.get_by_email(session, email)
        if profile is None:
            raise UserAccountNotFoundError

        existing = await self.platform_administrators.get_active_by_user_profile_id(
            session, profile.id
        )
        if existing is not None:
            return PlatformAdministratorGrantResult(
                user_profile_id=profile.id, grant_id=existing.id, grant_created=False
            )

        grant = PlatformAdministrator(
            user_profile_id=profile.id,
            granted_by_user_profile_id=granted_by_user_profile_id,
        )
        await self.platform_administrators.add(session, grant)
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type="platform.administrator.granted",
                action="platform_administrator.grant",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER
                if granted_by_user_profile_id
                else AuditActorType.SYSTEM,
                actor_id=granted_by_user_profile_id,
                resource_type="platform_administrator",
                resource_id=grant.id,
                correlation_id=correlation_id,
                summary="Platform administrator grant created.",
                metadata={
                    "grant_id": str(grant.id),
                    "user_profile_id": str(profile.id),
                    "source": source,
                    "reason": reason,
                    "operation": "granted",
                },
            ),
        )
        return PlatformAdministratorGrantResult(
            user_profile_id=profile.id, grant_id=grant.id, grant_created=True
        )

    async def self_status(
        self,
        session: AsyncSession,
        *,
        user_profile_id: UUID,
        assurance_level: AssuranceLevel,
    ) -> PlatformAdministratorSelfStatus:
        """Self-scoped read: does the caller hold a grant, and does their
        current session already meet the assurance level
        ``require_platform_administrator`` will enforce?

        Reuses the identical repository lookup that dependency uses — this
        never re-derives or duplicates that check, it only also reports it
        back to the caller about themselves, at whatever assurance level
        their current session happens to carry (grant existence is checked
        independently of assurance, exactly as the dependency's own lookup
        is).
        """
        grant = await self.platform_administrators.get_active_by_user_profile_id(
            session, user_profile_id
        )
        return PlatformAdministratorSelfStatus(
            is_platform_administrator=grant is not None,
            meets_required_assurance=assurance_satisfies(assurance_level, AssuranceLevel.AAL2),
            required_assurance_level=AssuranceLevel.AAL2.value,
        )
