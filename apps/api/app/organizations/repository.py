"""Controlled PostgreSQL access for organizations."""

from collections.abc import Sequence
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

    async def get_many(
        self, session: AsyncSession, organization_ids: Sequence[UUID]
    ) -> dict[UUID, Organization]:
        """Return the organizations that exist among the given identifiers, in one query."""
        if not organization_ids:
            return {}
        rows = await session.scalars(
            select(Organization).where(Organization.id.in_(organization_ids))
        )
        return {row.id: row for row in rows}

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
        include_removed: bool = False,
    ) -> tuple[list[Organization], bool]:
        """Return a bounded deterministic administrative page.

        A removed organization is only a tombstone kept for the audit trail, so it is left
        out unless the caller explicitly asks for it.
        """
        if not 1 <= limit <= MAX_ORGANIZATION_LIST_LIMIT:
            raise ValueError(f"Organization list limit must be 1-{MAX_ORGANIZATION_LIST_LIMIT}")
        if offset < 0:
            raise ValueError("Organization list offset must not be negative")
        statement = select(Organization)
        if not include_removed:
            statement = statement.where(Organization.removed_at.is_(None))
        result = await session.scalars(
            statement.order_by(Organization.created_at.asc(), Organization.id.asc())
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

    async def mark_removed(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        removed_at: datetime | None = None,
    ) -> Organization | None:
        """Turn an archived organization into a tombstone.

        Only id, name, slug, status, archived_at and removed_at keep their values. Every other
        identifying column is cleared; the two NOT NULL ones fall back to neutral defaults.
        """
        statement = (
            update(Organization)
            .where(
                Organization.id == organization_id,
                Organization.status == OrganizationStatus.ARCHIVED,
            )
            .values(
                removed_at=removed_at or utc_now(),
                legal_name=None,
                website_url=None,
                primary_contact_name=None,
                primary_contact_email=None,
                primary_contact_phone=None,
                billing_email=None,
                external_reference=None,
                onboarding_status=None,
                onboarding_mode=None,
                industry_id=None,
                timezone="UTC",
                default_currency="USD",
                version=Organization.version + 1,
                updated_at=utc_now(),
            )
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
