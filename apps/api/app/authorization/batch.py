"""Set-based organization-scope permission resolution for read projections.

``AuthorizationService.evaluate`` decides one permission for one organization with roughly
nine queries. A portfolio read needs five permissions for every visible client, which made the
decision alone cost hundreds of round trips. This resolves the same decisions for any number
of organizations in a constant number of queries.

It applies exactly the rules of ``AuthorizationService._evaluate`` for organization scope and
AAL1: active principal, permitting organization state, active membership, consistent role and
deny records, active system roles, fixed-catalog role grants, explicit denies, and an effective
product entitlement. ``tests/python/authorization/test_batch_resolution.py`` pins the
equivalence. Any disagreement fails closed (the permission is simply absent).
"""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import MembershipStatus, RoleStatus, ScopeType
from apps.api.app.access_control.models import (
    MembershipPermissionDeny,
    MembershipRoleAssignment,
    OrganizationMembership,
    Permission,
    Role,
    RolePermission,
)
from apps.api.app.administration.models import (
    Product,
    ProductEntitlement,
    ProductEntitlementLocation,
)
from apps.api.app.authentication.contracts import AuthenticatedPrincipal
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authorization.entitlements import (
    ProductEntitlementAuthorizationContext,
    product_key_for_permission,
)
from apps.api.app.authorization.onboarding_scope import organization_permits
from apps.api.app.authorization.service import _scope_is_consistent, scope_applies
from apps.api.app.database.base import utc_now
from apps.api.app.organizations.models import Organization


@dataclass(frozen=True, slots=True)
class OrganizationPermissions:
    """The permissions a principal holds, per organization, for organization-scope reads."""

    granted: dict[UUID, frozenset[str]]

    def allows(self, organization_id: UUID, permission_key: str) -> bool:
        return permission_key in self.granted.get(organization_id, frozenset())


async def resolve_organization_permissions(
    session: AsyncSession,
    principal: AuthenticatedPrincipal,
    pairs: Sequence[tuple[OrganizationMembership, Organization]],
    permission_keys: Iterable[str],
) -> OrganizationPermissions:
    keys = tuple(dict.fromkeys(permission_keys))
    granted: dict[UUID, frozenset[str]] = {}
    if principal.user_status is not UserStatus.ACTIVE or not pairs:
        return OrganizationPermissions(granted)
    candidates = [
        (membership, organization)
        for membership, organization in pairs
        if membership.user_profile_id == principal.platform_user_id
        and membership.organization_id == organization.id
        and membership.status is MembershipStatus.ACTIVE
    ]
    if not candidates:
        return OrganizationPermissions(granted)
    organization_ids = [organization.id for _, organization in candidates]
    membership_ids = [membership.id for membership, _ in candidates]

    permissions = {
        row.key: row.id
        for row in await session.scalars(select(Permission).where(Permission.key.in_(keys)))
    }
    assignments: dict[UUID, list[MembershipRoleAssignment]] = defaultdict(list)
    for assignment in await session.scalars(
        select(MembershipRoleAssignment).where(
            MembershipRoleAssignment.membership_id.in_(membership_ids),
            MembershipRoleAssignment.organization_id.in_(organization_ids),
        )
    ):
        assignments[assignment.membership_id].append(assignment)
    denies: dict[UUID, list[MembershipPermissionDeny]] = defaultdict(list)
    for deny in await session.scalars(
        select(MembershipPermissionDeny).where(
            MembershipPermissionDeny.membership_id.in_(membership_ids),
            MembershipPermissionDeny.organization_id.in_(organization_ids),
        )
    ):
        denies[deny.membership_id].append(deny)
    role_ids = {item.role_id for items in assignments.values() for item in items}
    roles = (
        {row.id: row for row in await session.scalars(select(Role).where(Role.id.in_(role_ids)))}
        if role_ids
        else {}
    )
    allowing: dict[UUID, set[UUID]] = defaultdict(set)  # permission id -> role ids
    if role_ids and permissions:
        for role_id, permission_id in await session.execute(
            select(RolePermission.role_id, RolePermission.permission_id).where(
                RolePermission.role_id.in_(role_ids),
                RolePermission.permission_id.in_(permissions.values()),
            )
        ):
            allowing[permission_id].add(role_id)
    products = {key for key in map(product_key_for_permission, keys) if key is not None}
    entitlements = await _entitlements(session, organization_ids, products)

    now = utc_now()
    for membership, organization in candidates:
        own_assignments = assignments.get(membership.id, [])
        own_denies = denies.get(membership.id, [])
        records_consistent = all(
            item.organization_id == organization.id
            and item.membership_id == membership.id
            and _scope_is_consistent(item.scope_type, item.location_id)
            for item in own_assignments
        ) and all(
            item.organization_id == organization.id
            and item.membership_id == membership.id
            and _scope_is_consistent(item.scope_type, item.location_id)
            for item in own_denies
        )
        applicable = [
            item
            for item in own_assignments
            if scope_applies(item.scope_type, item.location_id, ScopeType.ORGANIZATION, None)
        ]
        applicable_roles = {item.role_id for item in applicable}
        roles_valid = records_consistent and all(
            role_id in roles
            and roles[role_id].status is RoleStatus.ACTIVE
            and roles[role_id].is_system
            for role_id in applicable_roles
        )
        if not roles_valid:
            continue
        held: set[str] = set()
        for key in keys:
            permission_id = permissions.get(key)
            if permission_id is None or not organization_permits(organization.status, key):
                continue
            if any(
                deny.permission_id == permission_id
                and scope_applies(deny.scope_type, deny.location_id, ScopeType.ORGANIZATION, None)
                for deny in own_denies
            ):
                continue
            if not (allowing[permission_id] & applicable_roles):
                continue
            product_key = product_key_for_permission(key)
            if product_key is not None:
                context = entitlements.get((organization.id, product_key))
                if (
                    context is None
                    or not context.catalog_consistent
                    or not context.authorizes(ScopeType.ORGANIZATION, None, now=now)
                ):
                    continue
            held.add(key)
        granted[organization.id] = frozenset(held)
    return OrganizationPermissions(granted)


async def _entitlements(
    session: AsyncSession, organization_ids: list[UUID], product_keys: set[str]
) -> dict[tuple[UUID, str], ProductEntitlementAuthorizationContext]:
    if not product_keys:
        return {}
    product_status = {
        key: status
        for key, status in await session.execute(
            select(Product.key, Product.status).where(Product.key.in_(product_keys))
        )
    }
    rows = (
        await session.execute(
            select(
                ProductEntitlement.organization_id,
                Product.key,
                ProductEntitlement.id,
                ProductEntitlement.status,
                ProductEntitlement.effective_from,
                ProductEntitlement.effective_until,
                ProductEntitlementLocation.location_id,
                ProductEntitlementLocation.status,
            )
            .join(Product, Product.id == ProductEntitlement.product_id)
            .outerjoin(
                ProductEntitlementLocation,
                (ProductEntitlementLocation.organization_id == ProductEntitlement.organization_id)
                & (ProductEntitlementLocation.entitlement_id == ProductEntitlement.id),
            )
            .where(
                ProductEntitlement.organization_id.in_(organization_ids),
                Product.key.in_(product_keys),
            )
        )
    ).all()
    grouped: dict[tuple[UUID, str], list[tuple[Any, ...]]] = defaultdict(list)
    for row in rows:
        grouped[(row[0], row[1])].append(tuple(row))
    result: dict[tuple[UUID, str], ProductEntitlementAuthorizationContext] = {}
    for (organization_id, product_key), items in grouped.items():
        signatures = {(item[2], item[3], item[4], item[5]) for item in items}
        if product_status.get(product_key) != "registered" or len(signatures) != 1:
            result[(organization_id, product_key)] = ProductEntitlementAuthorizationContext(
                catalog_consistent=False
            )
            continue
        entitlement_id, status, effective_from, effective_until = next(iter(signatures))
        location_rows = [(item[6], item[7]) for item in items if item[6] is not None]
        result[(organization_id, product_key)] = ProductEntitlementAuthorizationContext(
            catalog_consistent=True,
            entitlement_id=entitlement_id,
            status=status,
            effective_from=effective_from,
            effective_until=effective_until,
            has_location_scope=bool(location_rows),
            active_location_ids=frozenset(
                location_id for location_id, state in location_rows if state == "active"
            ),
        )
    return result
