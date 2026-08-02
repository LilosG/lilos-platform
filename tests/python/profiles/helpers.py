"""Fabricated parent records and typed profile commands for tests."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.base import utc_now
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.profiles.contracts import LocationProfileCreate, OrganizationProfileCreate


async def add_organization(
    session: AsyncSession,
    *,
    status: OrganizationStatus = OrganizationStatus.ACTIVE,
    identifier: UUID | None = None,
) -> Organization:
    organization = Organization(
        id=identifier or uuid4(),
        name="Fabricated Profile Organization",
        slug=f"profile-{uuid4().hex[:12]}",
        organization_type=OrganizationType.TEST,
        status=status,
        timezone="UTC",
        default_currency="USD",
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
    identifier: UUID | None = None,
) -> Location:
    location = Location(
        id=identifier or uuid4(),
        organization_id=organization_id,
        name="Fabricated Profile Location",
        slug=f"profile-{uuid4().hex[:12]}",
        location_type=LocationType.PHYSICAL,
        status=status,
        timezone="UTC",
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


def organization_profile() -> OrganizationProfileCreate:
    return OrganizationProfileCreate(
        brand_name="Fabricated Brand",
        brand_summary="Controlled summary",
        primary_services=["Service One", "Service Two"],
        approved_claims=["Client-approved claim"],
        prohibited_claims=["Unsupported guarantee"],
        tone_guidelines=["Clear and factual"],
    )


def location_profile() -> LocationProfileCreate:
    return LocationProfileCreate(
        local_description="Controlled local description",
        primary_services=["Local Service"],
        service_area="Fabricated service area",
        local_landmarks=["Fabricated Landmark"],
        local_references=["Manually approved local reference"],
        approved_claims=["Approved local claim"],
        prohibited_claims=["Unsupported local guarantee"],
        tone_overrides=["Use local factual context"],
    )
