"""Fabricated organizations, locations, and location-group commands."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.base import utc_now
from apps.api.app.location_groups.contracts import LocationGroupCreate
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


async def add_organization(
    session: AsyncSession,
    *,
    status: OrganizationStatus = OrganizationStatus.ACTIVE,
    identifier: UUID | None = None,
) -> Organization:
    organization = Organization(
        id=identifier or uuid4(),
        name="Fabricated Group Organization",
        slug=f"group-{uuid4().hex[:12]}",
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
        name="Fabricated Group Location",
        slug=f"group-{uuid4().hex[:12]}",
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


def group_command(*, key: str | None = None, name: str = "Fabricated Group") -> LocationGroupCreate:
    return LocationGroupCreate(
        name=name,
        key=key or f"group-{uuid4().hex[:12]}",
        description="Fabricated administrative grouping",
    )
