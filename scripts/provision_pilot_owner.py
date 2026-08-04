"""One-off, idempotent, production-safe pilot organization owner provisioning.

Reuses the exact same domain services the application uses everywhere else
(``OrganizationService``, ``UserAdministrationService``, ``AccessControlService``)
inside one transaction. Creates no product, location, or business-identity
data — only a user profile, an organization, one active membership, and the
``organization_owner`` role assignment.

This is never mounted as an HTTP route. Run it manually with direct access to
the target database (``LILOS_DATABASE_URL`` already present in the process
environment), for example as a Render one-off Job on the ``lilos-api``
service, which already carries that configuration.

Required environment variables (never logged or printed):
    PILOT_OWNER_AUTH_USER_ID   Supabase ``auth.users.id`` (UUID) for the pilot
                               user, already created in the Supabase dashboard.
    PILOT_ORGANIZATION_NAME    Organization display name.
    PILOT_ORGANIZATION_SLUG    Organization slug (lowercase, 3-63 chars).
    PILOT_INDUSTRY_KEY          One of the seeded industry keys (restaurant,
                               bar, home_services, professional_services,
                               general_local_business) — required because the
                               default organization type ("client") requires
                               an industry. Only omit this if
                               PILOT_ORGANIZATION_TYPE is set to "internal" or
                               "test".

Optional environment variables:
    PILOT_OWNER_EMAIL              Stored on the user profile if provided.
    PILOT_OWNER_DISPLAY_NAME       Stored on the user profile if provided.
    PILOT_ORGANIZATION_TYPE        Default "client".
    PILOT_ORGANIZATION_TIMEZONE    Default "UTC".
    PILOT_ORGANIZATION_CURRENCY    Default "USD".
    PILOT_MEMBERSHIP_TYPE          Default "client".

Idempotent: re-running with the same inputs reuses any existing user profile,
organization, membership, and owner role assignment rather than creating
duplicates or failing. Only the printed summary (internal IDs and
created/existing booleans) is emitted; no email, name, or token is printed.
"""

import asyncio
import os
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.contracts import MembershipCreate, RoleAssignmentCreate
from apps.api.app.access_control.enums import MembershipType, ScopeType
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.authentication.contracts import UserProfileCreate
from apps.api.app.authentication.repository import UserProfileRepository
from apps.api.app.authentication.service import UserAdministrationService
from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.repository import IndustryRepository
from apps.api.app.organizations.contracts import OrganizationCreate
from apps.api.app.organizations.enums import (
    OrganizationLifecycleAction,
    OrganizationStatus,
    OrganizationType,
)
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.repository import OrganizationRepository
from apps.api.app.organizations.service import OrganizationService

INDUSTRY_REQUIRED_TYPES = frozenset(
    {OrganizationType.CLIENT, OrganizationType.PARTNER, OrganizationType.DEMO}
)

ACTIVATION_PATH: dict[OrganizationStatus, tuple[OrganizationLifecycleAction, ...]] = {
    OrganizationStatus.PROSPECT: (
        OrganizationLifecycleAction.START_ONBOARDING,
        OrganizationLifecycleAction.ACTIVATE,
    ),
    OrganizationStatus.ONBOARDING: (OrganizationLifecycleAction.ACTIVATE,),
    OrganizationStatus.SUSPENDED: (OrganizationLifecycleAction.ACTIVATE,),
    OrganizationStatus.ACTIVE: (),
}


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"provisioning blocked: missing required environment variable {name}")
    return value


async def _ensure_active(
    service: OrganizationService,
    session: AsyncSession,
    organization: Organization,
    *,
    correlation_id: str,
) -> Organization:
    if organization.status not in ACTIVATION_PATH:
        raise SystemExit(
            f"provisioning blocked: organization {organization.id} is in status "
            f"{organization.status.value}; no safe automatic path to active"
        )
    for action in ACTIVATION_PATH[organization.status]:
        organization = await service.transition(
            session,
            organization.id,
            action=action,
            expected_version=organization.version,
            correlation_id=correlation_id,
        )
    return organization


async def provision() -> None:
    auth_user_id = UUID(_required("PILOT_OWNER_AUTH_USER_ID"))
    organization_name = _required("PILOT_ORGANIZATION_NAME")
    organization_slug = _required("PILOT_ORGANIZATION_SLUG").strip().lower()
    owner_email = os.environ.get("PILOT_OWNER_EMAIL", "").strip() or None
    owner_display_name = os.environ.get("PILOT_OWNER_DISPLAY_NAME", "").strip() or None
    organization_type = OrganizationType(os.environ.get("PILOT_ORGANIZATION_TYPE", "client"))
    timezone = os.environ.get("PILOT_ORGANIZATION_TIMEZONE", "UTC")
    currency = os.environ.get("PILOT_ORGANIZATION_CURRENCY", "USD")
    membership_type = MembershipType(os.environ.get("PILOT_MEMBERSHIP_TYPE", "client"))
    industry_key = os.environ.get("PILOT_INDUSTRY_KEY", "").strip().lower() or None
    correlation_id = "provision-pilot-owner"

    if organization_type in INDUSTRY_REQUIRED_TYPES and industry_key is None:
        raise SystemExit(
            f"provisioning blocked: organization type '{organization_type.value}' requires "
            "PILOT_INDUSTRY_KEY (one of: restaurant, bar, home_services, "
            "professional_services, general_local_business)"
        )

    runtime = create_database_runtime(Settings())
    session_factory = runtime.require_session_factory()
    user_administration = UserAdministrationService()
    user_repository = UserProfileRepository()
    organizations = OrganizationService()
    organization_repository = OrganizationRepository()
    industry_repository = IndustryRepository()
    access = AccessControlService()

    try:
        async with session_factory.begin() as session:
            profile = await user_repository.get_by_auth_user_id(session, auth_user_id)
            profile_created = False
            if profile is None:
                profile = await user_administration.provision(
                    session,
                    UserProfileCreate(
                        auth_user_id=auth_user_id,
                        email=owner_email,
                        display_name=owner_display_name,
                    ),
                    correlation_id=correlation_id,
                )
                profile_created = True

            organization = await organization_repository.get_by_slug(session, organization_slug)
            organization_created = False
            if organization is None:
                industry_id = None
                if industry_key is not None:
                    industry = await industry_repository.get_by_key(session, industry_key)
                    if industry is None:
                        raise SystemExit(
                            f"provisioning blocked: unknown PILOT_INDUSTRY_KEY '{industry_key}'"
                        )
                    if industry.status is not IndustryStatus.ACTIVE:
                        raise SystemExit(
                            f"provisioning blocked: industry '{industry_key}' is not active"
                        )
                    industry_id = industry.id
                organization = await organizations.create(
                    session,
                    OrganizationCreate(
                        name=organization_name,
                        slug=organization_slug,
                        organization_type=organization_type,
                        timezone=timezone,
                        default_currency=currency,
                        industry_id=industry_id,
                    ),
                    correlation_id=correlation_id,
                )
                organization_created = True
            organization = await _ensure_active(
                organizations, session, organization, correlation_id=correlation_id
            )

            membership = await access.memberships.get_by_user(session, organization.id, profile.id)
            membership_created = False
            if membership is None:
                membership = await access.create_membership(
                    session,
                    organization.id,
                    MembershipCreate(user_profile_id=profile.id, membership_type=membership_type),
                    correlation_id=correlation_id,
                )
                membership_created = True

            owner_role = await access.catalog.get_role_by_key(session, "organization_owner")
            if owner_role is None:
                raise SystemExit(
                    "provisioning blocked: organization_owner role is not seeded; "
                    "run the access catalog seed first"
                )
            existing_assignments = await access.assignments.list(
                session, organization.id, membership.id
            )
            assignment_created = False
            if not any(item.role_id == owner_role.id for item in existing_assignments):
                await access.add_assignment(
                    session,
                    organization.id,
                    membership.id,
                    RoleAssignmentCreate(role_id=owner_role.id, scope_type=ScopeType.ORGANIZATION),
                    correlation_id=correlation_id,
                )
                assignment_created = True

        print(
            "Pilot owner provisioning complete: "
            f"user_profile_id={profile.id} ({'created' if profile_created else 'existing'}); "
            f"organization_id={organization.id} status={organization.status.value} "
            f"({'created' if organization_created else 'existing'}); "
            f"membership_id={membership.id} ({'created' if membership_created else 'existing'}); "
            f"owner_role_assignment={'created' if assignment_created else 'existing'}"
        )
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    asyncio.run(provision())
