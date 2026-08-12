"""Onboarding read-model composition, progress, activation-eligibility, and
three-mode responsibility contract tests.

Covers: SC2-MANAGED, SC2-CO-MANAGED, SC2-SELF-SERVICE, SC2-RESUMABLE,
SC2-READINESS-DERIVED, SC2-ACTIVATION.
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.enums import MembershipStatus, MembershipType
from apps.api.app.access_control.models import OrganizationMembership
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.database.base import utc_now
from apps.api.app.domains.models import OrganizationDomain
from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.models import Industry
from apps.api.app.locations.enums import LocationType
from apps.api.app.locations.models import Location
from apps.api.app.onboarding.contracts import (
    OnboardingResponsibilityMode,
    OnboardingStepState,
)
from apps.api.app.onboarding.service import (
    OnboardingOrchestrationService,
    _COMANAGED_CLIENTABLE_STEP_KEYS,
    _CLIENT_VISIBLE_STEP_KEYS,
    _resolve_mode,
)
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.profiles.models import OrganizationProfile


# ---------------------------------------------------------------------------
# Deterministic legacy NULL resolution
# ---------------------------------------------------------------------------

def test_null_onboarding_mode_resolves_to_managed() -> None:
    assert _resolve_mode(None) is OnboardingResponsibilityMode.MANAGED


def test_invalid_onboarding_mode_resolves_to_managed() -> None:
    assert _resolve_mode("bogus") is OnboardingResponsibilityMode.MANAGED


def test_explicit_modes_resolve_correctly() -> None:
    assert _resolve_mode("managed") is OnboardingResponsibilityMode.MANAGED
    assert _resolve_mode("co_managed") is OnboardingResponsibilityMode.CO_MANAGED
    assert _resolve_mode("self_service") is OnboardingResponsibilityMode.SELF_SERVICE


# ---------------------------------------------------------------------------
# Original integration test — preserved and extended
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_onboarding_state_progresses_to_activation_eligible(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        service = OnboardingOrchestrationService()
        async with onboarding_session_factory.begin() as session:
            organization = Organization(
                name="Onboarding Fixture Org",
                slug=f"onboarding-{uuid4().hex[:12]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ONBOARDING,
                timezone="UTC",
                default_currency="USD",
                version=1,
                onboarding_mode="managed",
            )
            session.add(organization)
            await session.flush()
            organization_id = organization.id

        async with onboarding_session_factory() as session:
            initial = await service.get_state(session, organization_id)
        assert initial.responsibility_mode is OnboardingResponsibilityMode.MANAGED
        assert initial.activation_eligible is False
        assert initial.progress_percent < 100
        blocking_keys = {step.key for step in initial.steps if step.blocking}
        assert blocking_keys == {
            "organization_profile",
            "locations",
            "primary_location",
            "website_domain",
            "industry",
            "users",
        }
        assert all(
            step.state is OnboardingStepState.INCOMPLETE
            for step in initial.steps
            if step.blocking
        )
        assert len(initial.blockers) >= 5

        # Complete every blocking step one at a time.
        async with onboarding_session_factory.begin() as session:
            session.add(OrganizationProfile(organization_id=organization_id, version=1))
            location = Location(
                organization_id=organization_id,
                name="Primary Site",
                slug=f"loc-{uuid4().hex[:12]}",
                location_type=LocationType.PHYSICAL,
                timezone="UTC",
                address_line_1="1 Fixture Way",
                city="Example",
                region="CA",
                postal_code="00000",
                country_code="US",
                is_primary=True,
                version=1,
            )
            session.add(location)
            session.add(
                OrganizationDomain(
                    organization_id=organization_id,
                    domain="fixture-client.com",
                    is_primary=True,
                    version=1,
                )
            )
            profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
            session.add(profile)
            await session.flush()
            session.add(
                OrganizationMembership(
                    organization_id=organization_id,
                    user_profile_id=profile.id,
                    membership_type=MembershipType.CLIENT,
                    status=MembershipStatus.ACTIVE,
                    activated_at=utc_now(),
                    version=1,
                )
            )

        async with onboarding_session_factory() as session:
            partially_complete = await service.get_state(session, organization_id)
        assert partially_complete.blockers == ("Select the client's industry.",)
        assert partially_complete.activation_eligible is False

        async with onboarding_session_factory.begin() as session:
            industry = Industry(
                key=f"fixture_{uuid4().hex[:8]}",
                name="Fixture Industry",
                status=IndustryStatus.ACTIVE,
                version=1,
            )
            session.add(industry)
            await session.flush()
            industry_id = industry.id
            await session.execute(
                update(Organization)
                .where(Organization.id == organization_id)
                .values(industry_id=industry_id)
            )

        async with onboarding_session_factory() as session:
            final_state = await service.get_state(session, organization_id)
        assert final_state.blockers == ()
        assert final_state.activation_eligible is True
        assert final_state.progress_percent >= 85
        assert all(
            step.state is OnboardingStepState.COMPLETE
            for step in final_state.steps
            if step.blocking
        )
        assert {product.product_key for product in final_state.products} == {
            "gbp",
            "reviews",
            "leads",
            "content",
            "seo",
            "insights",
        }
        assert all(product.selected is False for product in final_state.products)

    asyncio.run(exercise())


# ---------------------------------------------------------------------------
# Three-mode contract: MANAGED
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_managed_mode_client_sees_no_actionable_steps(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SC2-MANAGED: client gets zero visible steps in managed mode."""
    async def exercise() -> None:
        service = OnboardingOrchestrationService()
        async with onboarding_session_factory.begin() as session:
            org = Organization(
                name="Managed Client",
                slug=f"managed-{uuid4().hex[:12]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ONBOARDING,
                timezone="UTC",
                default_currency="USD",
                version=1,
                onboarding_mode="managed",
            )
            session.add(org)
            await session.flush()
            org_id = org.id

        async with onboarding_session_factory() as session:
            client_state = await service.get_client_state(
                session, org_id, is_platform_admin=False
            )
        assert client_state.responsibility_mode is OnboardingResponsibilityMode.MANAGED
        assert client_state.visible_steps == ()
        assert client_state.accessible_product_keys == ()

    asyncio.run(exercise())


# ---------------------------------------------------------------------------
# Three-mode contract: CO-MANAGED — persisted assignments
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_co_managed_persisted_assignments_survive_session_boundary(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SC2-RESUMABLE: co-managed step assignments persist across sessions."""
    async def exercise() -> None:
        service = OnboardingOrchestrationService()
        async with onboarding_session_factory.begin() as session:
            org = Organization(
                name="Co-Managed Client",
                slug=f"comanaged-{uuid4().hex[:12]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ONBOARDING,
                timezone="UTC",
                default_currency="USD",
                version=1,
                onboarding_mode="co_managed",
            )
            session.add(org)
            await session.flush()
            org_id = org.id

        # Session A: assign a step to client
        async with onboarding_session_factory.begin() as session_a:
            await service.assign_step(
                session_a, org_id, "organization_profile", "client"
            )
            await service.assign_step(
                session_a, org_id, "locations", "client"
            )

        # Session B: verify assignments persisted
        async with onboarding_session_factory() as session_b:
            assignments = await service.get_assignments(session_b, org_id)
            assigned_keys = {a.step_key for a in assignments}
            assert "organization_profile" in assigned_keys
            assert "locations" in assigned_keys
            assert all(a.assigned_to == "client" for a in assignments)

        # Session C: client state reflects assigned steps only
        async with onboarding_session_factory() as session_c:
            client_state = await service.get_client_state(
                session_c, org_id, is_platform_admin=False
            )
        visible_keys = {s.key for s in client_state.visible_steps}
        assert "organization_profile" in visible_keys
        assert "locations" in visible_keys
        # Steps NOT assigned should NOT be visible
        assert "industry" not in visible_keys
        assert "users" not in visible_keys
        assert "services" not in visible_keys

    asyncio.run(exercise())


@pytest.mark.integration
def test_co_managed_cannot_assign_non_clientable_step(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Only eligible steps may be delegated to client."""
    async def exercise() -> None:
        service = OnboardingOrchestrationService()
        async with onboarding_session_factory.begin() as session:
            org = Organization(
                name="No Delegation",
                slug=f"nodeleg-{uuid4().hex[:12]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ONBOARDING,
                timezone="UTC",
                default_currency="USD",
                version=1,
                onboarding_mode="co_managed",
            )
            session.add(org)
            await session.flush()
            org_id = org.id

        async with onboarding_session_factory.begin() as session:
            # industry is NOT co_managed_clientable
            with pytest.raises(ValueError, match="cannot be delegated"):
                await service.assign_step(session, org_id, "industry", "client")

            with pytest.raises(ValueError, match="cannot be delegated"):
                await service.assign_step(session, org_id, "users", "client")

            with pytest.raises(ValueError, match="cannot be delegated"):
                await service.assign_step(session, org_id, "products", "client")

            # services can't be delegated either
            with pytest.raises(ValueError, match="cannot be delegated"):
                await service.assign_step(session, org_id, "services", "client")

        # Agency can assign any step to "agency"
        async with onboarding_session_factory.begin() as session:
            await service.assign_step(session, org_id, "industry", "agency")

    asyncio.run(exercise())


@pytest.mark.integration
def test_co_managed_clear_assignments_removes_client_responsibility(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Clearing assignments reverts steps to agency control."""
    async def exercise() -> None:
        service = OnboardingOrchestrationService()
        async with onboarding_session_factory.begin() as session:
            org = Organization(
                name="Clear Assign",
                slug=f"clear-{uuid4().hex[:12]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ONBOARDING,
                timezone="UTC",
                default_currency="USD",
                version=1,
                onboarding_mode="co_managed",
            )
            session.add(org)
            await session.flush()
            org_id = org.id

        async with onboarding_session_factory.begin() as session:
            await service.assign_step(session, org_id, "organization_profile", "client")

        # Verify client sees it
        async with onboarding_session_factory() as session:
            state = await service.get_client_state(session, org_id)
            assert len(state.visible_steps) == 1

        # Clear
        async with onboarding_session_factory.begin() as session:
            await service.clear_assignments(session, org_id)

        # Now client sees nothing
        async with onboarding_session_factory() as session:
            state = await service.get_client_state(session, org_id)
            assert state.visible_steps == ()

    asyncio.run(exercise())


# ---------------------------------------------------------------------------
# Three-mode contract: SELF-SERVICE
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_self_service_client_sees_all_client_safe_steps(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SC2-SELF-SERVICE: client sees all client-safe steps."""
    async def exercise() -> None:
        service = OnboardingOrchestrationService()
        async with onboarding_session_factory.begin() as session:
            org = Organization(
                name="Self-Service Client",
                slug=f"self-{uuid4().hex[:12]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ONBOARDING,
                timezone="UTC",
                default_currency="USD",
                version=1,
                onboarding_mode="self_service",
            )
            session.add(org)
            await session.flush()
            org_id = org.id

        async with onboarding_session_factory() as session:
            client_state = await service.get_client_state(
                session, org_id, is_platform_admin=False
            )

        visible_keys = {s.key for s in client_state.visible_steps}
        for k in _CLIENT_VISIBLE_STEP_KEYS:
            assert k in visible_keys, f"Expected {k} to be visible in self-service"
        # services is NOT in _CLIENT_VISIBLE_STEP_KEYS
        assert "services" not in visible_keys

        assert client_state.accessible_product_keys == (
            "gbp", "reviews", "leads", "content", "seo", "automations", "insights",
        )

    asyncio.run(exercise())


# ---------------------------------------------------------------------------
# One engine: all modes share same completion/readiness
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_all_modes_use_same_completion_engine(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SC2-READINESS-DERIVED: completion/readiness is identical regardless of mode."""
    async def exercise() -> None:
        service = OnboardingOrchestrationService()

        for mode in ("managed", "co_managed", "self_service"):
            async with onboarding_session_factory.begin() as session:
                org = Organization(
                    name=f"OneEngine {mode}",
                    slug=f"oneeng-{mode}-{uuid4().hex[:8]}",
                    organization_type=OrganizationType.TEST,
                    status=OrganizationStatus.ONBOARDING,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                    onboarding_mode=mode,
                )
                session.add(org)
                await session.flush()
                org_id = org.id

            async with onboarding_session_factory() as session:
                state = await service.get_state(session, org_id)
            # Blocking steps are identical across all modes
            blocking_keys = {step.key for step in state.steps if step.blocking}
            assert blocking_keys == {
                "organization_profile",
                "locations",
                "primary_location",
                "website_domain",
                "industry",
                "users",
            }, f"Mode {mode} has unexpected blocking keys: {blocking_keys}"
            assert state.activation_eligible is False, f"Mode {mode} should not be eligible"
            assert state.progress_percent < 100

    asyncio.run(exercise())


# ---------------------------------------------------------------------------
# Activation: fail-closed on blockers
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_activation_fails_closed_when_blockers_remain(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SC2-ACTIVATION: activation_eligible is False when blockers exist."""
    async def exercise() -> None:
        service = OnboardingOrchestrationService()
        async with onboarding_session_factory.begin() as session:
            org = Organization(
                name="Blocked Activation",
                slug=f"blocked-{uuid4().hex[:12]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ONBOARDING,
                timezone="UTC",
                default_currency="USD",
                version=1,
                onboarding_mode="self_service",
            )
            session.add(org)
            await session.flush()
            org_id = org.id

        # No steps completed — activation must be blocked
        async with onboarding_session_factory() as session:
            state = await service.get_state(session, org_id)
        assert state.activation_eligible is False
        assert len(state.blockers) >= 5

        # Even after completing some but not all steps
        async with onboarding_session_factory.begin() as session:
            session.add(OrganizationProfile(organization_id=org_id, version=1))
            location = Location(
                organization_id=org_id,
                name="Half Done",
                slug=f"half-{uuid4().hex[:12]}",
                location_type=LocationType.PHYSICAL,
                timezone="UTC",
                address_line_1="1 Half Way",
                city="Example",
                region="CA",
                postal_code="00000",
                country_code="US",
                is_primary=True,
                version=1,
            )
            session.add(location)

        async with onboarding_session_factory() as session:
            state = await service.get_state(session, org_id)
        assert state.activation_eligible is False, "Should still be blocked"

    asyncio.run(exercise())
