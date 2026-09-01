"""Composes existing domain services into one client-onboarding read model.

No authoritative business rule is duplicated here: every step's completion
state is derived by calling the owning service (or reading the same rows it
would read) at request time.

Three responsibility modes operate over ONE engine:
- managed:   agency performs every step; client sees status only
- co_managed: agency preconfigures; client completes bounded assigned steps
- self_service: client completes the full safe path independently

The mode controls who may perform each step; it does NOT alter the
underlying definition of completion/readiness.

Co-managed step assignments are persisted in the
``onboarding_step_assignments`` table so that onboarding is fully resumable
from authoritative database state after browser close, API restart, or
worker redeployment.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import MembershipStatus
from apps.api.app.access_control.service import AccessControlService
from apps.api.app.administration.contracts import ReadinessFinding
from apps.api.app.administration.enums import NOT_SELECTED_ENTITLEMENT_STATUSES
from apps.api.app.administration.errors import AdministrationNotFoundError
from apps.api.app.administration.service import AdministrationService
from apps.api.app.database.base import utc_now
from apps.api.app.domains.service import OrganizationDomainService
from apps.api.app.locations.service import LocationService
from apps.api.app.onboarding.contracts import (
    OnboardingBlocker,
    OnboardingClientState,
    OnboardingModeControl,
    OnboardingProductStatus,
    OnboardingResponsibilityMode,
    OnboardingState,
    OnboardingStep,
    OnboardingStepAssignment,
    OnboardingStepState,
)
from apps.api.app.onboarding.models import OnboardingStepAssignmentRecord
from apps.api.app.onboarding.resolution import STEP_RESOLUTIONS
from apps.api.app.organizations.service import OrganizationService
from apps.api.app.profiles.errors import OrganizationProfileNotFoundError
from apps.api.app.profiles.service import OrganizationProfileService

CANONICAL_PRODUCT_KEYS: tuple[str, ...] = (
    "gbp",
    "reviews",
    "leads",
    "content",
    "seo",
    "automations",
    "insights",
)

_ALL_STEP_KEYS: tuple[str, ...] = (
    "organization_profile",
    "locations",
    "primary_location",
    "website_domain",
    "industry",
    "services",
    "users",
    "products",
)

# ---------------------------------------------------------------------------
# Responsibility-mode step control map
# ---------------------------------------------------------------------------

RESPONSIBILITY_CONTROLS: tuple[OnboardingModeControl, ...] = (
    OnboardingModeControl(
        step_key="organization_profile",
        managed=True,
        co_managed_client=True,
        self_service_client=True,
    ),
    OnboardingModeControl(
        step_key="locations",
        managed=True,
        co_managed_client=True,
        self_service_client=True,
    ),
    OnboardingModeControl(
        step_key="primary_location",
        managed=True,
        co_managed_client=False,
        self_service_client=True,
    ),
    OnboardingModeControl(
        step_key="website_domain",
        managed=True,
        co_managed_client=True,
        self_service_client=True,
    ),
    OnboardingModeControl(
        step_key="industry",
        managed=True,
        co_managed_client=False,
        self_service_client=True,
    ),
    OnboardingModeControl(
        step_key="services",
        managed=True,
        co_managed_client=False,
        self_service_client=False,
    ),
    OnboardingModeControl(
        step_key="users",
        managed=True,
        co_managed_client=False,
        self_service_client=True,
    ),
    OnboardingModeControl(
        step_key="products",
        managed=True,
        co_managed_client=False,
        self_service_client=True,
    ),
)

_CONTROLS_BY_KEY: dict[str, OnboardingModeControl] = {
    ctrl.step_key: ctrl for ctrl in RESPONSIBILITY_CONTROLS
}

_CLIENT_VISIBLE_STEP_KEYS: frozenset[str] = frozenset(
    ctrl.step_key for ctrl in RESPONSIBILITY_CONTROLS if ctrl.self_service_client
)

_COMANAGED_CLIENTABLE_STEP_KEYS: frozenset[str] = frozenset(
    ctrl.step_key for ctrl in RESPONSIBILITY_CONTROLS if ctrl.co_managed_client
)


def _resolve_mode(raw: str | None) -> OnboardingResponsibilityMode:
    """Resolve a raw column value to a typed mode.

    Deterministic legacy contract: NULL organisations predating Packet 2
    resolve to ``managed``. The API never returns an ambiguous mode.
    """
    if raw is None:
        return OnboardingResponsibilityMode.MANAGED
    try:
        return OnboardingResponsibilityMode(raw)
    except ValueError:
        return OnboardingResponsibilityMode.MANAGED


@dataclass(frozen=True, slots=True)
class OnboardingOrchestrationService:
    organizations: OrganizationService = field(default_factory=OrganizationService)
    locations: LocationService = field(default_factory=LocationService)
    domains: OrganizationDomainService = field(default_factory=OrganizationDomainService)
    profiles: OrganizationProfileService = field(default_factory=OrganizationProfileService)
    access: AccessControlService = field(default_factory=AccessControlService)
    administration: AdministrationService = field(default_factory=AdministrationService)

    # ------------------------------------------------------------------
    # Public: agency / platform-admin view
    # ------------------------------------------------------------------

    async def get_state(self, session: AsyncSession, organization_id: UUID) -> OnboardingState:
        """Full onboarding state — agency/platform-admin view."""
        organization = await self.organizations.get(session, organization_id)
        mode = _resolve_mode(organization.onboarding_mode)

        steps, blockers, warnings = await self._evaluate_steps(session, organization)
        products = await self._evaluate_products(session, organization_id, warnings)

        required_steps = [step for step in steps if step.blocking]
        total_steps = len(required_steps)
        complete_steps = sum(
            1 for step in required_steps if step.state is OnboardingStepState.COMPLETE
        )
        progress_percent = round((complete_steps / total_steps) * 100) if total_steps else 0
        activation_eligible = not blockers

        return OnboardingState(
            organization_id=organization.id,
            organization_name=organization.name,
            organization_status=organization.status.value,
            organization_version=organization.version,
            responsibility_mode=mode,
            steps=tuple(steps),
            products=tuple(products),
            blockers=tuple(item.message for item in blockers),
            blocker_details=tuple(blockers),
            warnings=tuple(warnings),
            progress_percent=progress_percent,
            activation_eligible=activation_eligible,
            evaluated_at=utc_now(),
        )

    # ------------------------------------------------------------------
    # Public: client view (filtered by mode and persisted assignments)
    # ------------------------------------------------------------------

    async def get_client_state(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        is_platform_admin: bool = False,
    ) -> OnboardingClientState:
        """Client-visible onboarding state, filtered by responsibility mode.

        - managed:   client sees nothing actionable (progress + status only)
        - co_managed: client sees only persisted agency-assigned clientable steps
        - self_service: client sees all client-safe steps
        - Platform admins always see the full state
        """
        organization = await self.organizations.get(session, organization_id)
        mode = _resolve_mode(organization.onboarding_mode)

        steps, blockers, warnings = await self._evaluate_steps(session, organization)
        await self._evaluate_products(session, organization_id, warnings)

        if is_platform_admin:
            visible_steps = steps
        elif mode is OnboardingResponsibilityMode.MANAGED:
            visible_steps = []
        elif mode is OnboardingResponsibilityMode.CO_MANAGED:
            assigned = await self._load_assigned_keys(session, organization_id)
            visible_steps = [
                step for step in steps if step.key in assigned and assigned[step.key] == "client"
            ]
        elif mode is OnboardingResponsibilityMode.SELF_SERVICE:
            visible_steps = [step for step in steps if step.key in _CLIENT_VISIBLE_STEP_KEYS]
        else:
            visible_steps = []

        if (
            mode is OnboardingResponsibilityMode.SELF_SERVICE
            or mode is OnboardingResponsibilityMode.CO_MANAGED
        ):
            accessible_product_keys = CANONICAL_PRODUCT_KEYS
        else:
            accessible_product_keys = ()

        required_visible_steps = [step for step in visible_steps if step.blocking]
        total_steps = len(required_visible_steps) if required_visible_steps else 1
        complete_steps = (
            sum(1 for step in required_visible_steps if step.state is OnboardingStepState.COMPLETE)
            if required_visible_steps
            else 0
        )
        progress_percent = round((complete_steps / total_steps) * 100) if total_steps else 0
        activation_eligible = not blockers

        return OnboardingClientState(
            organization_id=organization.id,
            organization_name=organization.name,
            responsibility_mode=mode,
            visible_steps=tuple(visible_steps),
            accessible_product_keys=accessible_product_keys,
            activation_eligible=activation_eligible,
            progress_percent=progress_percent,
            evaluated_at=utc_now(),
        )

    # ------------------------------------------------------------------
    # Co-managed step assignment — DATABASE-PERSISTED
    # ------------------------------------------------------------------

    async def assign_step(
        self,
        session: AsyncSession,
        organization_id: UUID,
        step_key: str,
        assigned_to: str,
    ) -> OnboardingStepAssignment:
        """Persist a co-managed step assignment to the database.

        Only steps declared ``co_managed_client``-eligible may be assigned
        to "client". Agency may take any step. Duplicate assignments are
        upserted (the unique constraint prevents duplicates per org+step).
        """
        if assigned_to == "client" and step_key not in _COMANAGED_CLIENTABLE_STEP_KEYS:
            raise ValueError(f"Step '{step_key}' cannot be delegated to the client.")
        if assigned_to not in ("agency", "client"):
            raise ValueError(f"assigned_to must be 'agency' or 'client', got '{assigned_to}'.")

        # Upsert: delete any prior row for this org+step, then insert
        await session.execute(
            delete(OnboardingStepAssignmentRecord).where(
                OnboardingStepAssignmentRecord.organization_id == organization_id,
                OnboardingStepAssignmentRecord.step_key == step_key,
            )
        )
        row = OnboardingStepAssignmentRecord(
            organization_id=organization_id,
            step_key=step_key,
            assigned_to=assigned_to,
        )
        session.add(row)
        await session.flush()

        return OnboardingStepAssignment(
            step_key=step_key,
            assigned_to=assigned_to,
            assigned_at=row.created_at,
        )

    async def get_assignments(
        self,
        session: AsyncSession,
        organization_id: UUID,
    ) -> tuple[OnboardingStepAssignment, ...]:
        """Return all persisted step assignments for this organization."""
        rows = await session.scalars(
            select(OnboardingStepAssignmentRecord).where(
                OnboardingStepAssignmentRecord.organization_id == organization_id,
            )
        )
        return tuple(
            OnboardingStepAssignment(
                step_key=row.step_key,
                assigned_to=row.assigned_to,
                assigned_at=row.created_at,
            )
            for row in rows
        )

    async def clear_assignments(
        self,
        session: AsyncSession,
        organization_id: UUID,
    ) -> None:
        """Remove ALL persisted step assignments for an organization."""
        await session.execute(
            delete(OnboardingStepAssignmentRecord).where(
                OnboardingStepAssignmentRecord.organization_id == organization_id,
            )
        )

    async def set_onboarding_mode(
        self,
        session: AsyncSession,
        organization_id: UUID,
        mode: OnboardingResponsibilityMode,
    ) -> None:
        """Persist the responsibility mode on the organization row."""
        org = await self.organizations.get(session, organization_id)
        org.onboarding_mode = mode.value
        session.add(org)

    # ------------------------------------------------------------------
    # Private: load persisted assigned keys for co-managed
    # ------------------------------------------------------------------

    async def _load_assigned_keys(
        self, session: AsyncSession, organization_id: UUID
    ) -> dict[str, str]:
        """Return a dict of {step_key: assigned_to} for one organization."""
        rows = await session.scalars(
            select(OnboardingStepAssignmentRecord).where(
                OnboardingStepAssignmentRecord.organization_id == organization_id,
            )
        )
        return {row.step_key: row.assigned_to for row in rows}

    # ------------------------------------------------------------------
    # Private: step evaluation
    # ------------------------------------------------------------------

    async def _evaluate_steps(
        self, session: AsyncSession, organization: Any
    ) -> tuple[list[OnboardingStep], list[OnboardingBlocker], list[str]]:
        """Evaluate all canonical onboarding steps from domain state."""
        steps: list[OnboardingStep] = []
        blockers: list[OnboardingBlocker] = []
        warnings: list[str] = []
        organization_id = organization.id

        # --- organization profile ---
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
                # Names the fields the profile contract actually has. The old
                # copy asked for a legal name, contact and locale details, none
                # of which exist on the profile, so an operator following it
                # looked for form fields that were never there.
                else (
                    "Create the organization profile — brand name, business description "
                    "and default call to action. Every field is optional; saving the "
                    "profile completes this step."
                ),
            )
        )
        if not has_profile:
            blockers.append(
                OnboardingBlocker(
                    message="Complete the organization profile.",
                    resolution=STEP_RESOLUTIONS["organization_profile"],
                )
            )

        # --- locations ---
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
            blockers.append(
                OnboardingBlocker(
                    message="Add at least one business location.",
                    resolution=STEP_RESOLUTIONS["locations"],
                )
            )
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
            blockers.append(
                OnboardingBlocker(
                    message="Mark one location as the primary location.",
                    resolution=STEP_RESOLUTIONS["primary_location"],
                )
            )

        # --- website / domain ---
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
            blockers.append(
                OnboardingBlocker(
                    message="Configure the client's primary website domain.",
                    resolution=STEP_RESOLUTIONS["website_domain"],
                )
            )

        # --- industry ---
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
            blockers.append(
                OnboardingBlocker(
                    message="Select the client's industry.",
                    resolution=STEP_RESOLUTIONS["industry"],
                )
            )

        # --- services ---
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

        # --- users ---
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
            blockers.append(
                OnboardingBlocker(
                    message="Assign at least one active user with organization access.",
                    resolution=STEP_RESOLUTIONS["users"],
                )
            )

        # --- products ---
        # Check whether any canonical product has a selected entitlement.
        # Full readiness is evaluated separately in _evaluate_products().
        products_selected = 0
        for key in CANONICAL_PRODUCT_KEYS:
            product = await self.administration.catalog.get_product_by_key(session, key)
            if product is None:
                continue
            entitlement = await self.administration.entitlements.get_by_product(
                session, organization_id, product.id
            )
            if (
                entitlement is not None
                and entitlement.status not in NOT_SELECTED_ENTITLEMENT_STATUSES
            ):
                products_selected += 1

        has_products = products_selected > 0
        steps.append(
            OnboardingStep(
                key="products",
                label="Products and entitlements",
                state=OnboardingStepState.COMPLETE
                if has_products
                else OnboardingStepState.OPTIONAL_INCOMPLETE,
                blocking=False,
                detail=(
                    f"{products_selected} product(s) enabled."
                    if has_products
                    else "No products are enabled yet."
                ),
                next_action=(None if has_products else "Enable at least one product."),
            )
        )
        if not has_products:
            warnings.append("No products have been enabled for this client yet.")

        # Attach each step's destination here rather than at the eight
        # construction sites, so a new step cannot be added without one: a
        # missing key surfaces as None and the deadlock-freedom suite fails.
        steps = [
            step.model_copy(update={"resolution": STEP_RESOLUTIONS.get(step.key)}) for step in steps
        ]
        return steps, blockers, warnings

    # ------------------------------------------------------------------
    # Private: product evaluation
    # ------------------------------------------------------------------

    async def _evaluate_products(
        self,
        session: AsyncSession,
        organization_id: UUID,
        warnings: list[str],
    ) -> list[OnboardingProductStatus]:
        """Evaluate product entitlement and readiness for all canonical products."""
        products: list[OnboardingProductStatus] = []
        grouped_product_work: dict[str, list[str]] = {}
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
                and entitlement.status not in NOT_SELECTED_ENTITLEMENT_STATUSES
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
                if item.code in {
                    "ORGANIZATION_NOT_ACTIVE",
                    "ENTITLEMENT_NOT_EFFECTIVE",
                }:
                    continue
                other_findings.append(item)
                grouped_product_work.setdefault(item.remediation, []).append(product.name)
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

        # Product readiness is deliberately separate from organization
        # activation. A client account should become active once its core
        # identity, location, domain, industry, and owner are confirmed; a
        # selected product may still need facts, a profile, policy, or provider
        # mapping before that product can run. Promoting those findings into
        # organization blockers created circular onboarding gates and made the
        # lifecycle of one product hold the entire client account hostage.
        for remediation, names in grouped_product_work.items():
            unique = list(dict.fromkeys(names))
            product_names = unique[0] if len(unique) == 1 else ", ".join(unique)
            warnings.append(f"[{product_names}] Product setup still needs: {remediation}")
        for name in connection_required_products:
            warnings.append(f"[{name}] requires a connected external integration.")

        return products


# ---------------------------------------------------------------------------
# Public module helpers
# ---------------------------------------------------------------------------


def step_control(step_key: str) -> OnboardingModeControl | None:
    """Return the responsibility control for a single step, or None."""
    return _CONTROLS_BY_KEY.get(step_key)


def is_client_visible(step_key: str) -> bool:
    """Return True when the step is visible to clients in self-service mode."""
    return step_key in _CLIENT_VISIBLE_STEP_KEYS


def is_co_managed_clientable(step_key: str) -> bool:
    """Return True when the step may be delegated to client in co-managed mode."""
    return step_key in _COMANAGED_CLIENTABLE_STEP_KEYS
