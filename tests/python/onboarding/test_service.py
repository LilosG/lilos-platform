"""Onboarding read-model composition, progress, and activation-eligibility tests."""

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
from apps.api.app.onboarding.contracts import OnboardingStepState
from apps.api.app.onboarding.service import OnboardingOrchestrationService
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.profiles.models import OrganizationProfile


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
            )
            session.add(organization)
            await session.flush()
            organization_id = organization.id

        async with onboarding_session_factory() as session:
            initial = await service.get_state(session, organization_id)
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
            step.state is OnboardingStepState.INCOMPLETE for step in initial.steps if step.blocking
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
        # Industry still unassigned — the only remaining blocker.
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
        # "services" remains an optional, non-blocking step (no service was
        # assigned in this fixture), so progress is high but not 100%.
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
