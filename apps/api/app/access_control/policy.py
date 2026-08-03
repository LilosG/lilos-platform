"""Approved organization-state administration and future evaluation policy."""

from collections.abc import Iterable
from uuid import UUID

from apps.api.app.access_control.enums import MembershipStatus, ScopeType
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.organizations.enums import OrganizationStatus

CREATE_STATES = frozenset(
    {OrganizationStatus.PROSPECT, OrganizationStatus.ONBOARDING, OrganizationStatus.ACTIVE}
)
RESTORE_STATES = CREATE_STATES
SUSPEND_REVOKE_STATES = frozenset(set(OrganizationStatus) - {OrganizationStatus.ARCHIVED})
ADD_ROLE_STATES = CREATE_STATES
REMOVE_ROLE_STATES = frozenset(
    {
        OrganizationStatus.PROSPECT,
        OrganizationStatus.ONBOARDING,
        OrganizationStatus.ACTIVE,
        OrganizationStatus.PAUSED,
        OrganizationStatus.SUSPENDED,
        OrganizationStatus.OFFBOARDING,
    }
)
ADD_DENY_STATES = REMOVE_ROLE_STATES
REMOVE_DENY_STATES = frozenset(
    {
        OrganizationStatus.PROSPECT,
        OrganizationStatus.ONBOARDING,
        OrganizationStatus.ACTIVE,
        OrganizationStatus.PAUSED,
    }
)
CANCEL_INVITATION_STATES = frozenset(
    {
        OrganizationStatus.PROSPECT,
        OrganizationStatus.ONBOARDING,
        OrganizationStatus.ACTIVE,
        OrganizationStatus.OFFBOARDING,
    }
)


def organization_permits_effective_access(status: OrganizationStatus) -> bool:
    """Only active organizations can produce effective runtime access."""
    return status is OrganizationStatus.ACTIVE


def scope_applies(
    scope_type: ScopeType, scope_location_id: UUID | None, location_id: UUID | None
) -> bool:
    """Narrow deterministic fixture for the approved organization/location precedence."""
    return scope_type is ScopeType.ORGANIZATION or (
        scope_type is ScopeType.LOCATION
        and location_id is not None
        and scope_location_id == location_id
    )


def permission_fixture_allows(
    *,
    organization_status: OrganizationStatus,
    user_status: UserStatus,
    membership_status: MembershipStatus,
    location_id: UUID | None,
    allow_scopes: Iterable[tuple[ScopeType, UUID | None]],
    deny_scopes: Iterable[tuple[ScopeType, UUID | None]],
) -> bool:
    """Prove deny precedence without becoming request authorization enforcement."""
    if (
        not organization_permits_effective_access(organization_status)
        or user_status is not UserStatus.ACTIVE
        or membership_status is not MembershipStatus.ACTIVE
    ):
        return False
    if any(
        scope_applies(kind, scoped_location, location_id) for kind, scoped_location in deny_scopes
    ):
        return False
    return any(
        scope_applies(kind, scoped_location, location_id) for kind, scoped_location in allow_scopes
    )
