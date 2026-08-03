"""Deterministic read-only authorization decision service."""

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import MembershipStatus, RoleStatus, ScopeType
from apps.api.app.access_control.models import (
    MembershipPermissionDeny,
    MembershipRoleAssignment,
)
from apps.api.app.access_control.repository import (
    AssignmentRepository,
    CatalogRepository,
    DenyRepository,
    MembershipRepository,
)
from apps.api.app.authentication.contracts import AuthenticatedPrincipal
from apps.api.app.authentication.enums import AssuranceLevel, UserStatus
from apps.api.app.authorization.contracts import AuthorizationDecision, AuthorizationRequest
from apps.api.app.authorization.enums import AuthorizationReason
from apps.api.app.locations.repository import LocationRepository
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.repository import OrganizationRepository

logger = logging.getLogger("lilos.security.authorization")


def assurance_satisfies(actual: AssuranceLevel, minimum: AssuranceLevel) -> bool:
    return actual is AssuranceLevel.AAL2 or minimum is AssuranceLevel.AAL1


def scope_applies(
    scope_type: ScopeType,
    scoped_location_id: UUID | None,
    request_scope: ScopeType,
    request_location_id: UUID | None,
) -> bool:
    if scope_type is ScopeType.ORGANIZATION:
        return scoped_location_id is None
    return (
        request_scope is ScopeType.LOCATION
        and scoped_location_id is not None
        and scoped_location_id == request_location_id
    )


def _scope_is_consistent(scope_type: ScopeType, location_id: UUID | None) -> bool:
    return (scope_type is ScopeType.ORGANIZATION) == (location_id is None)


@dataclass(frozen=True, slots=True)
class AuthorizationService:
    organization_repository: OrganizationRepository = field(default_factory=OrganizationRepository)
    location_repository: LocationRepository = field(default_factory=LocationRepository)
    membership_repository: MembershipRepository = field(default_factory=MembershipRepository)
    assignment_repository: AssignmentRepository = field(default_factory=AssignmentRepository)
    deny_repository: DenyRepository = field(default_factory=DenyRepository)
    catalog_repository: CatalogRepository = field(default_factory=CatalogRepository)

    async def evaluate(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        request: AuthorizationRequest,
        *,
        correlation_id: str,
    ) -> AuthorizationDecision:
        """Evaluate current authoritative records without mutating or committing."""
        try:
            return await self._evaluate(session, principal, request, correlation_id=correlation_id)
        except SQLAlchemyError as exc:
            logger.error(
                "Authorization persistence read failed",
                extra={
                    "event_name": "security.authorization.persistence_failure",
                    "correlation_id": correlation_id,
                    "outcome": "denied",
                    "normalized_error_code": AuthorizationReason.CATALOG_INCONSISTENCY.value,
                    "platform_user_id": str(request.platform_user_id),
                    "permission_key": request.permission_key,
                    "resource_scope": request.resource_scope.value,
                    "assurance_level": principal.assurance_level.value,
                    "minimum_assurance_level": request.minimum_assurance_level.value,
                    "exception_type": type(exc).__name__,
                },
            )
            return self._decision(
                principal,
                request,
                correlation_id=correlation_id,
                reason=AuthorizationReason.CATALOG_INCONSISTENCY,
                organization_validated=False,
            )

    async def _evaluate(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        request: AuthorizationRequest,
        *,
        correlation_id: str,
    ) -> AuthorizationDecision:
        if (
            principal.platform_user_id != request.platform_user_id
            or principal.user_status is not UserStatus.ACTIVE
        ):
            return self._decision(
                principal,
                request,
                correlation_id=correlation_id,
                reason=AuthorizationReason.USER_INACTIVE,
                organization_validated=False,
            )

        organization = await self.organization_repository.get_by_id(
            session, request.organization_id
        )
        if organization is None or organization.status is not OrganizationStatus.ACTIVE:
            return self._decision(
                principal,
                request,
                correlation_id=correlation_id,
                reason=AuthorizationReason.ORGANIZATION_NOT_EFFECTIVE,
                organization_validated=organization is not None,
            )

        membership = await self.membership_repository.get_by_user(
            session, request.organization_id, principal.platform_user_id
        )
        if membership is None:
            return self._decision(
                principal,
                request,
                correlation_id=correlation_id,
                reason=AuthorizationReason.MEMBERSHIP_MISSING,
                organization_validated=True,
            )
        if membership.status is not MembershipStatus.ACTIVE:
            return self._decision(
                principal,
                request,
                correlation_id=correlation_id,
                reason=AuthorizationReason.MEMBERSHIP_INACTIVE,
                membership_id=membership.id,
                organization_validated=True,
            )

        if request.resource_scope is ScopeType.LOCATION:
            assert request.location_id is not None
            location = await self.location_repository.get_by_id(
                session, request.organization_id, request.location_id
            )
            if location is None:
                return self._decision(
                    principal,
                    request,
                    correlation_id=correlation_id,
                    reason=AuthorizationReason.LOCATION_NOT_FOUND,
                    membership_id=membership.id,
                    organization_validated=True,
                )

        if not assurance_satisfies(principal.assurance_level, request.minimum_assurance_level):
            return self._decision(
                principal,
                request,
                correlation_id=correlation_id,
                reason=AuthorizationReason.INSUFFICIENT_ASSURANCE,
                membership_id=membership.id,
                organization_validated=True,
            )

        permission = await self.catalog_repository.get_permission_by_key(
            session, request.permission_key
        )
        assignments = await self.assignment_repository.list(
            session, request.organization_id, membership.id
        )
        denies = await self.deny_repository.list(session, request.organization_id, membership.id)
        if permission is None or not self._records_are_consistent(
            assignments, denies, request.organization_id, membership.id
        ):
            return self._decision(
                principal,
                request,
                correlation_id=correlation_id,
                reason=AuthorizationReason.CATALOG_INCONSISTENCY,
                membership_id=membership.id,
                organization_validated=True,
            )

        applicable_assignments = [
            item
            for item in assignments
            if scope_applies(
                item.scope_type, item.location_id, request.resource_scope, request.location_id
            )
        ]
        role_ids = {item.role_id for item in applicable_assignments}
        roles = await self.catalog_repository.get_roles_by_ids(session, role_ids)
        if len(roles) != len(role_ids) or any(
            role.status is not RoleStatus.ACTIVE or not role.is_system for role in roles
        ):
            return self._decision(
                principal,
                request,
                correlation_id=correlation_id,
                reason=AuthorizationReason.CATALOG_INCONSISTENCY,
                membership_id=membership.id,
                organization_validated=True,
            )
        allowing_role_ids = await self.catalog_repository.role_ids_for_permission(
            session, permission.id, role_ids
        )
        allowing_assignment_ids = tuple(
            sorted(
                {item.id for item in applicable_assignments if item.role_id in allowing_role_ids},
                key=str,
            )
        )
        applicable_deny_ids = tuple(
            sorted(
                {
                    item.id
                    for item in denies
                    if item.permission_id == permission.id
                    and scope_applies(
                        item.scope_type,
                        item.location_id,
                        request.resource_scope,
                        request.location_id,
                    )
                },
                key=str,
            )
        )
        if applicable_deny_ids:
            reason = AuthorizationReason.EXPLICIT_DENY
        elif not allowing_assignment_ids:
            reason = AuthorizationReason.PERMISSION_NOT_GRANTED
        else:
            reason = AuthorizationReason.ALLOWED
        return self._decision(
            principal,
            request,
            correlation_id=correlation_id,
            reason=reason,
            membership_id=membership.id,
            assignment_ids=allowing_assignment_ids,
            deny_ids=applicable_deny_ids,
            organization_validated=True,
        )

    @staticmethod
    def _records_are_consistent(
        assignments: list[MembershipRoleAssignment],
        denies: list[MembershipPermissionDeny],
        organization_id: UUID,
        membership_id: UUID,
    ) -> bool:
        assignments_valid = all(
            item.organization_id == organization_id
            and item.membership_id == membership_id
            and _scope_is_consistent(item.scope_type, item.location_id)
            for item in assignments
        )
        denies_valid = all(
            item.organization_id == organization_id
            and item.membership_id == membership_id
            and _scope_is_consistent(item.scope_type, item.location_id)
            for item in denies
        )
        return assignments_valid and denies_valid

    @staticmethod
    def _decision(
        principal: AuthenticatedPrincipal,
        request: AuthorizationRequest,
        *,
        correlation_id: str,
        reason: AuthorizationReason,
        membership_id: UUID | None = None,
        assignment_ids: tuple[UUID, ...] = (),
        deny_ids: tuple[UUID, ...] = (),
        organization_validated: bool,
    ) -> AuthorizationDecision:
        allowed = reason is AuthorizationReason.ALLOWED
        decision = AuthorizationDecision(
            allowed=allowed,
            organization_id=request.organization_id,
            platform_user_id=request.platform_user_id,
            membership_id=membership_id,
            permission_key=request.permission_key,
            resource_scope=request.resource_scope,
            location_id=request.location_id,
            assurance_level=principal.assurance_level,
            minimum_assurance_level=request.minimum_assurance_level,
            applicable_role_assignment_ids=assignment_ids,
            applicable_deny_ids=deny_ids,
            reason_code=reason,
        )
        logger.info(
            "Authorization evaluated",
            extra={
                "event_name": "security.authorization.evaluated",
                "correlation_id": correlation_id,
                "outcome": "allowed" if allowed else "denied",
                "normalized_error_code": reason.value,
                "platform_user_id": str(request.platform_user_id),
                "organization_id": str(request.organization_id) if organization_validated else None,
                "permission_key": request.permission_key,
                "resource_scope": request.resource_scope.value,
                "assurance_level": principal.assurance_level.value,
                "minimum_assurance_level": request.minimum_assurance_level.value,
            },
        )
        return decision
