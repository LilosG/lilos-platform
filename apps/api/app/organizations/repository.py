"""Controlled PostgreSQL access for organizations."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.base import utc_now
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.naming import normalize_organization_name

MAX_ORGANIZATION_LIST_LIMIT = 100


class OrganizationRepository:
    """Create, retrieve, list, and atomically transition organizations without deletion."""

    async def add(self, session: AsyncSession, organization: Organization) -> Organization:
        """Add and flush an organization inside the caller-owned transaction."""
        session.add(organization)
        await session.flush()
        return organization

    async def get_by_id(
        self,
        session: AsyncSession,
        organization_id: UUID,
    ) -> Organization | None:
        """Return exactly one organization by its stable internal identifier."""
        return await session.get(Organization, organization_id)

    async def get_by_slug(self, session: AsyncSession, slug: str) -> Organization | None:
        """Return exactly one organization by its immutable slug."""
        return cast(
            Organization | None,
            await session.scalar(select(Organization).where(Organization.slug == slug)),
        )

    async def get_by_normalized_name(
        self, session: AsyncSession, normalized_name: str
    ) -> Organization | None:
        """Return an organization whose name matches ignoring case and spacing.

        Name is not unique in the database and should not become so — two real
        clients may legitimately share a name. This exists so creation can warn
        about a collision rather than silently produce a duplicate.
        """
        candidates = await session.scalars(
            select(Organization).where(Organization.status != OrganizationStatus.ARCHIVED)
        )
        for organization in candidates:
            if normalize_organization_name(organization.name) == normalized_name:
                return organization
        return None

    async def list(
        self,
        session: AsyncSession,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[Organization], bool]:
        """Return a bounded deterministic administrative page."""
        if not 1 <= limit <= MAX_ORGANIZATION_LIST_LIMIT:
            raise ValueError(f"Organization list limit must be 1-{MAX_ORGANIZATION_LIST_LIMIT}")
        if offset < 0:
            raise ValueError("Organization list offset must not be negative")
        result = await session.scalars(
            select(Organization)
            .order_by(Organization.created_at.asc(), Organization.id.asc())
            .offset(offset)
            .limit(limit + 1)
        )
        organizations = list(result)
        return organizations[:limit], len(organizations) > limit

    async def transition_status(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        expected_status: OrganizationStatus,
        expected_version: int,
        target_status: OrganizationStatus,
        archived_at: datetime | None = None,
    ) -> Organization | None:
        """Apply one compare-and-swap lifecycle transition and increment its version."""
        values: dict[str, object] = {
            "status": target_status,
            "version": Organization.version + 1,
            "updated_at": utc_now(),
        }
        if target_status is OrganizationStatus.ARCHIVED:
            values["archived_at"] = archived_at or utc_now()
        statement = (
            update(Organization)
            .where(
                Organization.id == organization_id,
                Organization.status == expected_status,
                Organization.version == expected_version,
            )
            .values(**values)
            .returning(Organization)
        )
        return cast(Organization | None, await session.scalar(statement))

    async def set_industry(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        industry_id: UUID,
        expected_version: int,
    ) -> Organization | None:
        """Assign one primary industry through a compare-and-swap update."""
        statement = (
            update(Organization)
            .where(
                Organization.id == organization_id,
                Organization.version == expected_version,
            )
            .values(
                industry_id=industry_id,
                version=Organization.version + 1,
                updated_at=utc_now(),
            )
            .returning(Organization)
        )
        return cast(Organization | None, await session.scalar(statement))
