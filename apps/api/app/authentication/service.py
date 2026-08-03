"""Authentication mapping and audited platform-user administration."""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.owner_continuity import OwnerContinuityService
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.authentication.contracts import (
    AuthenticatedPrincipal,
    UserProfileCreate,
    VerifiedProviderClaims,
)
from apps.api.app.authentication.enums import UserLifecycleAction, UserStatus
from apps.api.app.authentication.errors import (
    AuthenticationRequiredError,
    UserLifecycleConflictError,
    UserProfileConflictError,
    UserProfileNotFoundError,
    UserVersionConflictError,
)
from apps.api.app.authentication.models import UserProfile
from apps.api.app.authentication.repository import UserProfileRepository


@dataclass(frozen=True, slots=True)
class AuthenticationService:
    repository: UserProfileRepository = field(default_factory=UserProfileRepository)

    async def authenticate(
        self, session: AsyncSession, claims: VerifiedProviderClaims
    ) -> AuthenticatedPrincipal:
        profile = await self.repository.get_by_auth_user_id(session, claims.auth_user_id)
        if profile is None or profile.status is not UserStatus.ACTIVE:
            raise AuthenticationRequiredError
        return AuthenticatedPrincipal(
            platform_user_id=profile.id,
            auth_user_id=profile.auth_user_id,
            user_status=profile.status,
            session_id=claims.session_id,
            assurance_level=claims.assurance_level,
            token_issued_at=claims.issued_at,
            token_expires_at=claims.expires_at,
        )


@dataclass(frozen=True, slots=True)
class UserAdministrationService:
    repository: UserProfileRepository = field(default_factory=UserProfileRepository)
    audit_service: AuditEventService = field(default_factory=AuditEventService)
    owner_continuity: OwnerContinuityService = field(default_factory=OwnerContinuityService)

    async def provision(
        self, session: AsyncSession, command: UserProfileCreate, *, correlation_id: str
    ) -> UserProfile:
        profile = UserProfile(
            auth_user_id=command.auth_user_id,
            email=command.email,
            display_name=command.display_name,
            status=UserStatus.ACTIVE,
            version=1,
        )
        try:
            await self.repository.add(session, profile)
        except IntegrityError:
            raise UserProfileConflictError from None
        await self._audit(
            session,
            profile,
            operation="provisioned",
            correlation_id=correlation_id,
            prior_status=None,
            changed_fields=["auth_user_id", "email", "display_name", "status"],
        )
        return profile

    async def get(self, session: AsyncSession, user_id: UUID) -> UserProfile:
        profile = await self.repository.get_by_id(session, user_id)
        if profile is None:
            raise UserProfileNotFoundError
        return profile

    async def transition(
        self,
        session: AsyncSession,
        user_id: UUID,
        *,
        action: UserLifecycleAction,
        expected_version: int,
        correlation_id: str,
    ) -> UserProfile:
        profile = await self.get(session, user_id)
        if profile.version != expected_version:
            raise UserVersionConflictError
        expected_status, target_status = {
            UserLifecycleAction.DEACTIVATE: (UserStatus.ACTIVE, UserStatus.DEACTIVATED),
            UserLifecycleAction.REACTIVATE: (UserStatus.DEACTIVATED, UserStatus.ACTIVE),
        }[action]
        if profile.status is not expected_status:
            raise UserLifecycleConflictError
        if action is UserLifecycleAction.DEACTIVATE:
            await self.owner_continuity.guard_user_deactivation(session, user_id)
        updated = await self.repository.transition_status(
            session,
            user_id=user_id,
            expected_status=expected_status,
            expected_version=expected_version,
            target_status=target_status,
        )
        if updated is None:
            raise UserVersionConflictError
        await self._audit(
            session,
            updated,
            operation=action.value,
            correlation_id=correlation_id,
            prior_status=expected_status,
            changed_fields=["status", "deactivated_at", "version"],
        )
        return updated

    async def _audit(
        self,
        session: AsyncSession,
        profile: UserProfile,
        *,
        operation: str,
        correlation_id: str,
        prior_status: UserStatus | None,
        changed_fields: list[str],
    ) -> None:
        await self.audit_service.record(
            session,
            AuditEventCreate(
                event_type=f"platform.user_profile.{operation}",
                action=f"user_profile.{operation}",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.SYSTEM,
                resource_type="user_profile",
                resource_id=profile.id,
                correlation_id=correlation_id,
                summary=f"Platform user profile {operation}.",
                metadata={
                    "platform_user_id": str(profile.id),
                    "auth_user_id": str(profile.auth_user_id),
                    "operation": operation,
                    "prior_status": prior_status.value if prior_status is not None else None,
                    "resulting_status": profile.status.value,
                    "resulting_version": profile.version,
                    "changed_fields": list[JsonValue](changed_fields),
                },
            ),
        )
