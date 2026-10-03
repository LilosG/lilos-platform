"""Deterministic read-only authorization decision service."""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import MembershipStatus, RoleStatus, ScopeType
from apps.api.app.access_control.models import (
    MembershipPermissionDeny,
    MembershipRoleAssignment,
    OrganizationMembership,
    Permission,
    Role,
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
from apps.api.app.authorization.entitlements import (
    ProductEntitlementAuthorizationContext,
    ProductEntitlementAuthorizationRepository,
    product_key_for_permission,
)
from apps.api.app.authorization.enums import AuthorizationReason
from apps.api.app.authorization.onboarding_scope import organization_permits
from apps.api.app.database.base import utc_now
from apps.api.app.locations.repository import LocationRepository
from apps.api.app.organizations.models import Organization
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


def principal_may_evaluate(
    principal: AuthenticatedPrincipal, request: AuthorizationRequest
) -> bool:
    """The principal is the requested user and is active; nothing else is read before this."""
    return (
        principal.platform_user_id == request.platform_user_id
        and principal.user_status is UserStatus.ACTIVE
    )


@dataclass(slots=True)
class DecisionRows:
    """The already-loaded records one decision is made from. Absent rows read as missing."""

    organization: Organization | None = None
    membership: OrganizationMembership | None = None
    location_found: bool = False
    permission: Permission | None = None
    assignments: Sequence[MembershipRoleAssignment] = ()
    denies: Sequence[MembershipPermissionDeny] = ()
    roles: Mapping[UUID, Role] = field(default_factory=dict)
    allowing_role_ids: frozenset[UUID] = frozenset()
    entitlement: ProductEntitlementAuthorizationContext | None = None


@dataclass(frozen=True, slots=True)
class AccessVerdict:
    reason: AuthorizationReason
    membership_id: UUID | None = None
    assignment_ids: tuple[UUID, ...] = ()
    deny_ids: tuple[UUID, ...] = ()
    organization_validated: bool = True


def decide_organization_access(
    principal: AuthenticatedPrincipal,
    request: AuthorizationRequest,
    rows: DecisionRows,
    *,
    now: datetime,
) -> AccessVerdict:
    """The one authorization rule. Pure: it decides from rows that are already loaded.

    Both ``AuthorizationService.evaluate`` and ``evaluate_many`` call this and nothing else
    decides. The checks run in a fixed order and every refusal carries its own reason.
    """
    if not principal_may_evaluate(principal, request):
        return AccessVerdict(AuthorizationReason.USER_INACTIVE, organization_validated=False)

    organization = rows.organization
    membership = rows.membership
    if organization is None or not organization_permits(
        organization.status, request.permission_key
    ):
        return AccessVerdict(
            AuthorizationReason.ORGANIZATION_NOT_EFFECTIVE,
            membership_id=(
                membership.id
                if organization is not None
                and membership is not None
                and membership.status is MembershipStatus.ACTIVE
                else None
            ),
            organization_validated=organization is not None,
        )
    if membership is None:
        return AccessVerdict(AuthorizationReason.MEMBERSHIP_MISSING)
    if membership.status is not MembershipStatus.ACTIVE:
        return AccessVerdict(AuthorizationReason.MEMBERSHIP_INACTIVE, membership_id=membership.id)
    if request.resource_scope is ScopeType.LOCATION and not rows.location_found:
        return AccessVerdict(AuthorizationReason.LOCATION_NOT_FOUND, membership_id=membership.id)
    if not assurance_satisfies(principal.assurance_level, request.minimum_assurance_level):
        return AccessVerdict(
            AuthorizationReason.INSUFFICIENT_ASSURANCE, membership_id=membership.id
        )

    assignments = list(rows.assignments)
    denies = list(rows.denies)
    permission = rows.permission
    if permission is None or not AuthorizationService._records_are_consistent(
        assignments, denies, request.organization_id, membership.id
    ):
        return AccessVerdict(AuthorizationReason.CATALOG_INCONSISTENCY, membership_id=membership.id)

    applicable_assignments = [
        item
        for item in assignments
        if scope_applies(
            item.scope_type, item.location_id, request.resource_scope, request.location_id
        )
    ]
    role_ids = {item.role_id for item in applicable_assignments}
    roles = [rows.roles[role_id] for role_id in role_ids if role_id in rows.roles]
    if len(roles) != len(role_ids) or any(
        role.status is not RoleStatus.ACTIVE or not role.is_system for role in roles
    ):
        return AccessVerdict(AuthorizationReason.CATALOG_INCONSISTENCY, membership_id=membership.id)
    allowing_role_ids = rows.allowing_role_ids & role_ids
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
        product_key = product_key_for_permission(request.permission_key)
        if product_key is None:
            reason = AuthorizationReason.ALLOWED
        else:
            entitlement = rows.entitlement
            if entitlement is None or not entitlement.catalog_consistent:
                reason = AuthorizationReason.CATALOG_INCONSISTENCY
            elif not entitlement.authorizes(request.resource_scope, request.location_id, now=now):
                reason = AuthorizationReason.PRODUCT_ENTITLEMENT_NOT_EFFECTIVE
            else:
                reason = AuthorizationReason.ALLOWED
    return AccessVerdict(
        reason,
        membership_id=membership.id,
        assignment_ids=allowing_assignment_ids,
        deny_ids=applicable_deny_ids,
    )


@dataclass(frozen=True, slots=True)
class AuthorizationService:
    organization_repository: OrganizationRepository = field(default_factory=OrganizationRepository)
    location_repository: LocationRepository = field(default_factory=LocationRepository)
    membership_repository: MembershipRepository = field(default_factory=MembershipRepository)
    assignment_repository: AssignmentRepository = field(default_factory=AssignmentRepository)
    deny_repository: DenyRepository = field(default_factory=DenyRepository)
    catalog_repository: CatalogRepository = field(default_factory=CatalogRepository)
    entitlement_repository: ProductEntitlementAuthorizationRepository = field(
        default_factory=ProductEntitlementAuthorizationRepository
    )

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
        rows = await self._load_rows(session, principal, request)
        verdict = decide_organization_access(principal, request, rows, now=utc_now())
        return self._decide(principal, request, verdict, correlation_id=correlation_id)

    async def _load_rows(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        request: AuthorizationRequest,
    ) -> DecisionRows:
        """Load only the rows ``decide_organization_access`` can reach for this request.

        Each stage is skipped with the very predicate the rule uses, so a request that is
        refused early costs what it always did and the rule itself is stated once.
        """
        rows = DecisionRows()
        if not principal_may_evaluate(principal, request):
            return rows
        organization = await self.organization_repository.get_by_id(
            session, request.organization_id
        )
        rows.organization = organization
        if organization is None:
            return rows
        # The membership is read for refusals too, so a denial can say a member's client is
        # not activated yet without telling a stranger whether an organization exists.
        membership = await self.membership_repository.get_by_user(
            session, request.organization_id, principal.platform_user_id
        )
        rows.membership = membership
        if (
            not organization_permits(organization.status, request.permission_key)
            or membership is None
            or membership.status is not MembershipStatus.ACTIVE
        ):
            return rows
        if request.resource_scope is ScopeType.LOCATION:
            assert request.location_id is not None
            rows.location_found = (
                await self.location_repository.get_by_id(
                    session, request.organization_id, request.location_id
                )
                is not None
            )
            if not rows.location_found:
                return rows
        if not assurance_satisfies(principal.assurance_level, request.minimum_assurance_level):
            return rows
        rows.permission = await self.catalog_repository.get_permission_by_key(
            session, request.permission_key
        )
        rows.assignments = await self.assignment_repository.list(
            session, request.organization_id, membership.id
        )
        rows.denies = await self.deny_repository.list(
            session, request.organization_id, membership.id
        )
        role_ids = {item.role_id for item in rows.assignments}
        rows.roles = {
            role.id: role
            for role in await self.catalog_repository.get_roles_by_ids(session, role_ids)
        }
        if rows.permission is not None:
            rows.allowing_role_ids = frozenset(
                await self.catalog_repository.role_ids_for_permission(
                    session, rows.permission.id, set(rows.roles)
                )
            )
        product_key = product_key_for_permission(request.permission_key)
        if product_key is not None:
            rows.entitlement = await self.entitlement_repository.resolve(
                session, request.organization_id, product_key
            )
        return rows

    async def evaluate_many(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        organization_ids: Sequence[UUID],
        permission_keys: Sequence[str],
        *,
        correlation_id: str,
        minimum_assurance_level: AssuranceLevel = AssuranceLevel.AAL1,
    ) -> dict[tuple[UUID, str], AuthorizationDecision]:
        """Decide organization-scope permissions for many organizations in constant queries.

        Every decision comes from the same ``decide_organization_access`` as ``evaluate`` and is
        logged the same way; only the loading is set-based. Read projections that need several
        permissions for every client use this instead of one evaluation per pair.
        """
        pairs = [
            (o, k) for o in dict.fromkeys(organization_ids) for k in dict.fromkeys(permission_keys)
        ]
        requests = {
            (organization_id, key): AuthorizationRequest(
                platform_user_id=principal.platform_user_id,
                organization_id=organization_id,
                permission_key=key,
                resource_scope=ScopeType.ORGANIZATION,
                minimum_assurance_level=minimum_assurance_level,
            )
            for organization_id, key in pairs
        }
        try:
            rows = await self._load_many(session, principal, requests)
        except SQLAlchemyError as exc:
            logger.error(
                "Authorization persistence read failed",
                extra={
                    "event_name": "security.authorization.persistence_failure",
                    "correlation_id": correlation_id,
                    "outcome": "denied",
                    "normalized_error_code": AuthorizationReason.CATALOG_INCONSISTENCY.value,
                    "platform_user_id": str(principal.platform_user_id),
                    "assurance_level": principal.assurance_level.value,
                    "minimum_assurance_level": minimum_assurance_level.value,
                    "exception_type": type(exc).__name__,
                },
            )
            return {
                pair: self._decision(
                    principal,
                    request,
                    correlation_id=correlation_id,
                    reason=AuthorizationReason.CATALOG_INCONSISTENCY,
                    organization_validated=False,
                )
                for pair, request in requests.items()
            }
        now = utc_now()
        return {
            pair: self._decide(
                principal,
                request,
                decide_organization_access(principal, request, rows[pair], now=now),
                correlation_id=correlation_id,
            )
            for pair, request in requests.items()
        }

    async def _load_many(
        self,
        session: AsyncSession,
        principal: AuthenticatedPrincipal,
        requests: dict[tuple[UUID, str], AuthorizationRequest],
    ) -> dict[tuple[UUID, str], DecisionRows]:
        """Set-based counterpart of ``_load_rows``: the rows every request can reach."""
        loaded = {pair: DecisionRows() for pair in requests}
        if not requests or not any(
            principal_may_evaluate(principal, request) for request in requests.values()
        ):
            return loaded
        organization_ids = list(dict.fromkeys(o for o, _ in requests))
        keys = list(dict.fromkeys(k for _, k in requests))
        organizations = await self.organization_repository.get_many(session, organization_ids)
        memberships = await self.membership_repository.get_by_user_in(
            session, list(organizations), principal.platform_user_id
        )
        active_membership_ids = [
            m.id for m in memberships.values() if m.status is MembershipStatus.ACTIVE
        ]
        assignments = await self.assignment_repository.list_for_memberships(
            session, organization_ids, active_membership_ids
        )
        denies = await self.deny_repository.list_for_memberships(
            session, organization_ids, active_membership_ids
        )
        permissions = await self.catalog_repository.list_permissions_by_keys(session, keys)
        role_ids = {item.role_id for items in assignments.values() for item in items}
        roles = {
            role.id: role
            for role in await self.catalog_repository.get_roles_by_ids(session, role_ids)
        }
        grants = await self.catalog_repository.role_ids_by_permission(
            session, {p.id for p in permissions.values()}, set(roles)
        )
        products = [p for p in {product_key_for_permission(k) for k in keys} if p is not None]
        entitlements = await self.entitlement_repository.resolve_many(
            session, organization_ids, products
        )
        for (organization_id, key), request in requests.items():
            rows = loaded[(organization_id, key)]
            if not principal_may_evaluate(principal, request):
                continue
            rows.organization = organizations.get(organization_id)
            rows.membership = memberships.get(organization_id)
            membership = rows.membership
            if membership is None or membership.status is not MembershipStatus.ACTIVE:
                continue
            rows.assignments = assignments.get(membership.id, [])
            rows.denies = denies.get(membership.id, [])
            rows.roles = {
                rid: roles[rid] for rid in {a.role_id for a in rows.assignments} if rid in roles
            }
            rows.permission = permissions.get(key)
            if rows.permission is not None:
                rows.allowing_role_ids = frozenset(grants.get(rows.permission.id, set()))
            product_key = product_key_for_permission(key)
            if product_key is not None:
                rows.entitlement = entitlements.get((organization_id, product_key))
        return loaded

    def _decide(
        self,
        principal: AuthenticatedPrincipal,
        request: AuthorizationRequest,
        verdict: "AccessVerdict",
        *,
        correlation_id: str,
    ) -> AuthorizationDecision:
        return self._decision(
            principal,
            request,
            correlation_id=correlation_id,
            reason=verdict.reason,
            membership_id=verdict.membership_id,
            assignment_ids=verdict.assignment_ids,
            deny_ids=verdict.deny_ids,
            organization_validated=verdict.organization_validated,
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
