"""Fabricated organizations for organization-domain tests."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

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
        name="Fabricated Domain Organization",
        slug=f"domain-org-{uuid4().hex[:12]}",
        organization_type=OrganizationType.TEST,
        status=status,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(organization)
    await session.flush()
    return organization
