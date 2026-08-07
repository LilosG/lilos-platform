"""Composes existing domain services into one client-onboarding read model.

No authoritative business rule is duplicated here: every step's completion
state is derived by calling the owning service (or reading the same rows it
would read) at request time.
"""

from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import MembershipStatus
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.administration.contracts import ReadinessFinding
from apps.api.app.administration.errors import AdministrationNotFoundError
from apps.api.app.administration.service import AdministrationService
from apps.api.app.database.base import utc_now
from apps.api.app.domains.service import OrganizationDomainService
from apps.api.app.locations.service import LocationService
from apps.api.app.onboarding.contracts import (
    OnboardingProductStatus,
    OnboardingState,
    OnboardingStep,
    OnboardingStepState,
)
from apps.api.app.organizations.service import OrganizationService
from apps.api.app.profiles.errors import OrganizationProfileNotFoundError
from apps.api.app.profiles.service import OrganizationProfileService

CANONICAL_PRODUCT_KEYS: tuple[str, ...] = (
    "gbp",
    "reviews",
    "leads",
    "content",
    "seo",
    "insights",
)

# Findings that reflect external integration/connection or platform-level
# state the operator resolves per-product, not something that should block
# *organization* activation — they remain truthfully visible as per-product
# blockers only.
_NON_ACTIVATION_BLOCKING_CODES = frozenset(
    {"CONNECTION_REQUIRED", "ORGANIZATION_NOT_ACTIVE", "ENTITLEMENT_NOT_EFFECTIVE"}
)
_NOT_SELECTED_ENTITLEMENT_STATUSES = frozenset({"not_enabled", "archived"})


@dataclass(frozen=True, slots=True)
class OnboardingOrchestrationService:
    organizations: OrganizationService = field(default_factory=OrganizationService)
    locations: LocationService = field(default_factory=LocationService)
    domains: OrganizationDomainService = field(default_factory=OrganizationDomainService)
    profiles: OrganizationProfileService = field(default_factory=OrganizationProfileService)
    access: AccessControlService = field(default_factory=AccessControlService)
    administration: AdministrationService = field(default_factory=AdministrationService)

    async def get_state(self, session: AsyncSession, organization_id: UUID) -> OnboardingState:
        organization = await self.organizations.get(session, organization_id)

        steps: list[OnboardingStep] = []
        blockers: list[str] = []
        warnings: list[str] = []

        has_profile = True
        try:
            await self.profiles.get(session, organization_id)
        except OrganizationProfileNotFoundError:
            has_profile = False
        steps.append(
            OnboardingStep(
                key="organization_profile",
                label="Organization profile",
                state=OnboardingStepState.COMPLETE
                if has_profile
                else OnboardingStepState.INCOMPLETE,
                blocking=True,
                detail="Profile complete." if has_profile else "Organization profile is missing.",
                next_action=None
                if has_profile
                else "Complete the organization profile (legal name, contact, locale details).",
            )
        )
        if not has_profile:
            blockers.append("Complete the organization profile.")

        all_locations, _ = await self.locations.list(session, organization_id, limit=100, offset=0)
        has_location = len(all_locations) > 0
        has_primary_location = any(location.is_primary for location in all_locations)
        steps.append(
            OnboardingStep(
                key="locations",
                label="Business locations",
                state=OnboardingStepState.COMPLETE
                if has_location
                else OnboardingStepState.INCOMPLETE,
                blocking=True,
                detail=f"{len(all_locations)} location(s) on file."
                if has_location
                else "No locations added yet.",
                next_action=None if has_location else "Add at least one business location.",
            )
        )
        if not has_location:
            blockers.append("Add at least one business location.")
        steps.append(
            OnboardingStep(
                key="primary_location",
                label="Primary location",
                state=OnboardingStepState.COMPLETE
                if has_primary_location
                else OnboardingStepState.INCOMPLETE,
                blocking=True,
                detail="A primary location is set."
                if has_primary_location
                else "No location is marked primary.",
                next_action=None
                if has_primary_location
                else "Mark one location as the primary location.",
            )
        )
        if has_location and not has_primary_location:
            blockers.append("Mark one location as the primary location.")

        domains = await self.domains.list(session, organization_id)
        has_primary_domain = any(
            domain.is_primary and domain.status.value == "active" for domain in domains
        )
        steps.append(
            OnboardingStep(
                key="website_domain",
                label="Website and primary domain",
                state=OnboardingStepState.COMPLETE
                if has_primary_domain
                else OnboardingStepState.INCOMPLETE,
                blocking=True,
                detail="Primary domain configured."
                if has_primary_domain
                else "No primary domain configured.",
                next_action=None
                if has_primary_domain
                else "Add the client's primary website domain and mark it primary.",
            )
        )
        if not has_primary_domain:
            blockers.append("Configure the client's primary website domain.")

        industry_assigned = organization.industry_id is not None
        steps.append(
            OnboardingStep(
                key="industry",
                label="Industry",
                state=OnboardingStepState.COMPLETE
                if industry_assigned
                else OnboardingStepState.INCOMPLETE,
                blocking=True,
                detail="Industry assigned." if industry_assigned else "No industry assigned.",
                next_action=None if industry_assigned else "Select the client's industry.",
            )
        )
        if not industry_assigned:
            blockers.append("Select the client's industry.")

        effective_services = await self.administration.effective_services(
            session, organization_id, None
        )
        has_services = len(effective_services) > 0
        steps.append(
            OnboardingStep(
                key="services",
                label="Services",
                state=OnboardingStepState.COMPLETE
                if has_services
                else OnboardingStepState.OPTIONAL_INCOMPLETE,
                blocking=False,
                detail=f"{len(effective_services)} service(s) assigned."
                if has_services
                else "No services assigned yet.",
                next_action=None if has_services else "Assign the client's services.",
            )
        )
        if not has_services:
            warnings.append("No services have been assigned to this client yet.")

        memberships, _ = await self.access.list_memberships(
            session, organization_id, limit=100, offset=0
        )
        has_active_member = any(m.status is MembershipStatus.ACTIVE for m in memberships)
        pending_invitations, _ = await self.access.list_invitations(
            session, organization_id, limit=100, offset=0
        )
        pending_count = sum(1 for item in pending_invitations if item.status.value == "pending")
        steps.append(
            OnboardingStep(
                key="users",
                label="Users and access",
                state=OnboardingStepState.COMPLETE
                if has_active_member
                else OnboardingStepState.INCOMPLETE,
                blocking=True,
                detail=(
                    f"{sum(1 for m in memberships if m.status is MembershipStatus.ACTIVE)} "
                    f"active member(s), {pending_count} pending invitation(s)."
                    if has_active_member
                    else f"No active members yet ({pending_count} pending invitation(s))."
                ),
                next_action=None
                if has_active_member
                else "Add an existing user or invite one, then assign a role.",
            )
        )
        if not has_active_member:
            blockers.append("Assign at least one active user with organization access.")

        products: list[OnboardingProductStatus] = []
        # Group per-product blockers by their remediation text so shared
        # requirements (one approved business.name, one approval policy, one
        # connection) are surfaced as a SINGLE actionable blocker listing the
        # affected products, rather than repeated once per product.
        grouped_blockers: dict[str, list[str]] = {}
        connection_required_products: list[str] = []
        for key in CANONICAL_PRODUCT_KEYS:
            product = await self.administration.catalog.get_product_by_key(session, key)
            if product is None:
                products.append(
                    OnboardingProductStatus(
                        product_key=key,
                        product_name=key,
                        selected=False,
                        entitlement_status=None,
                        readiness_state=None,
                        ready=False,
                        blocking_findings=(),
                        external_integration_pending=False,
                        next_action="Product catalog entry is not yet seeded.",
                    )
                )
                continue
            entitlement = await self.administration.entitlements.get_by_product(
                session, organization_id, product.id
            )
            selected = (
                entitlement is not None
                and entitlement.status not in _NOT_SELECTED_ENTITLEMENT_STATUSES
            )
            if not selected:
                products.append(
                    OnboardingProductStatus(
                        product_key=key,
                        product_name=product.name,
                        selected=False,
                        entitlement_status=entitlement.status if entitlement else "not_enabled",
                        readiness_state=None,
                        ready=False,
                        blocking_findings=(),
                        external_integration_pending=False,
                        next_action="Enable this product to include it in onboarding.",
                    )
                )
                continue
            try:
                readiness = await self.administration.readiness(session, organization_id, key)
            except AdministrationNotFoundError:
                continue
            other_findings: list[ReadinessFinding] = []
            connection_required = False
            for item in readiness.blocking_requirements:
                if item.code == "CONNECTION_REQUIRED":
                    connection_required = True
                    continue
                if item.code in _NON_ACTIVATION_BLOCKING_CODES:
                    continue
                other_findings.append(item)
                grouped_blockers.setdefault(item.remediation, []).append(product.name)
            if connection_required:
                connection_required_products.append(product.name)
            products.append(
                OnboardingProductStatus(
                    product_key=key,
                    product_name=product.name,
                    selected=True,
                    entitlement_status=entitlement.status if entitlement else None,
                    readiness_state=readiness.readiness_state,
                    ready=readiness.ready,
                    blocking_findings=tuple(item.remediation for item in other_findings),
                    external_integration_pending=connection_required,
                    next_action=other_findings[0].remediation if other_findings else None,
                )
            )

        for remediation, names in grouped_blockers.items():
            unique = list(dict.fromkeys(names))
            if len(unique) == 1:
                blockers.append(f"[{unique[0]}] {remediation}")
            else:
                blockers.append(f"{remediation} (required by: {', '.join(unique)})")
        for name in connection_required_products:
            warnings.append(f"[{name}] requires a connected external integration.")

        total_steps = len(steps)
        complete_steps = sum(1 for step in steps if step.state is OnboardingStepState.COMPLETE)
        progress_percent = round((complete_steps / total_steps) * 100) if total_steps else 0
        activation_eligible = not blockers

        return OnboardingState(
            organization_id=organization.id,
            organization_name=organization.name,
            organization_status=organization.status.value,
            organization_version=organization.version,
            steps=tuple(steps),
            products=tuple(products),
            blockers=tuple(blockers),
            warnings=tuple(warnings),
            progress_percent=progress_percent,
            activation_eligible=activation_eligible,
            evaluated_at=utc_now(),
        )
