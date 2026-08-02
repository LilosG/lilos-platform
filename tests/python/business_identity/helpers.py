"""Fabricated records for deterministic business-identity tests."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.base import utc_now
from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.models import Industry
from apps.api.app.location_groups.enums import LocationGroupStatus
from apps.api.app.location_groups.models import LocationGroup, LocationGroupMembership
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.profiles.models import LocationProfile, OrganizationProfile


async def add_industry(
    session: AsyncSession, *, status: IndustryStatus = IndustryStatus.ACTIVE
) -> Industry:
    industry = Industry(
        id=uuid4(),
        key=f"fabricated_{uuid4().hex[:8]}",
        name="Fabricated Industry",
        status=status,
        default_configuration={},
        default_risk_policy={},
        default_content_policy={},
        archived_at=utc_now() if status is IndustryStatus.ARCHIVED else None,
        version=1,
    )
    session.add(industry)
    await session.flush()
    return industry


async def add_organization(
    session: AsyncSession,
    *,
    industry_id: UUID | None = None,
    status: OrganizationStatus = OrganizationStatus.ACTIVE,
) -> Organization:
    organization = Organization(
        id=uuid4(),
        name="Fabricated Identity Organization",
        slug=f"identity-{uuid4().hex[:12]}",
        organization_type=OrganizationType.TEST,
        status=status,
        timezone="UTC",
        default_currency="USD",
        industry_id=industry_id,
        archived_at=utc_now() if status is OrganizationStatus.ARCHIVED else None,
        version=1,
    )
    session.add(organization)
    await session.flush()
    return organization


async def add_location(
    session: AsyncSession,
    organization_id: UUID,
    *,
    status: LocationStatus = LocationStatus.ACTIVE,
) -> Location:
    location = Location(
        id=uuid4(),
        organization_id=organization_id,
        name="Fabricated Identity Location",
        slug=f"identity-{uuid4().hex[:12]}",
        location_type=LocationType.PHYSICAL,
        status=status,
        timezone="America/Los_Angeles",
        address_line_1="1 Fabricated Way",
        city="Example",
        region="CA",
        postal_code="00000",
        country_code="US",
        is_primary=False,
        archived_at=utc_now() if status is LocationStatus.ARCHIVED else None,
        version=1,
    )
    session.add(location)
    await session.flush()
    return location


async def add_organization_profile(
    session: AsyncSession, organization_id: UUID
) -> OrganizationProfile:
    profile = OrganizationProfile(
        id=uuid4(),
        organization_id=organization_id,
        brand_name="Fabricated Brand",
        brand_summary="Shared summary",
        business_description="Shared description",
        value_proposition="Shared value",
        target_customer="Shared customer",
        primary_services=["Organization Service"],
        approved_claims=["Organization approved"],
        prohibited_claims=["Organization prohibited"],
        tone_guidelines=["Organization tone"],
        legal_disclaimers=["Organization disclaimer"],
        default_call_to_action="Organization CTA",
        version=1,
    )
    session.add(profile)
    await session.flush()
    return profile


async def add_location_profile(
    session: AsyncSession,
    organization_id: UUID,
    location_id: UUID,
    *,
    call_to_action_override: str | None = "Location CTA",
) -> LocationProfile:
    profile = LocationProfile(
        id=uuid4(),
        organization_id=organization_id,
        location_id=location_id,
        local_description="Local description",
        primary_services=["Location Service"],
        service_area="Local service area",
        local_landmarks=["Local landmark"],
        local_references=["Local reference"],
        approved_claims=["Location approved"],
        prohibited_claims=["Location prohibited"],
        tone_overrides=["Location tone"],
        call_to_action_override=call_to_action_override,
        version=1,
    )
    session.add(profile)
    await session.flush()
    return profile


async def add_group_membership(
    session: AsyncSession,
    organization_id: UUID,
    location_id: UUID,
    *,
    status: LocationGroupStatus,
) -> None:
    group = LocationGroup(
        id=uuid4(),
        organization_id=organization_id,
        name="Identity-excluded group",
        key=f"group-{uuid4().hex[:8]}",
        status=status,
        archived_at=utc_now() if status is LocationGroupStatus.ARCHIVED else None,
        version=1,
    )
    session.add(group)
    await session.flush()
    session.add(
        LocationGroupMembership(
            organization_id=organization_id,
            location_group_id=group.id,
            location_id=location_id,
        )
    )
    await session.flush()
