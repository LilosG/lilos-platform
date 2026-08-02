"""Strictly organization-scoped persistence for locations."""

from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.base import utc_now
from apps.api.app.locations.enums import LocationStatus
from apps.api.app.locations.models import Location

MAX_LOCATION_LIST_LIMIT = 100


class LocationRepository:
    """Create, retrieve, list, and transition locations without broad mutation methods."""

    async def add(
        self, session: AsyncSession, organization_id: UUID, location: Location
    ) -> Location:
        if location.organization_id != organization_id:
            raise ValueError("Location ownership does not match repository scope")
        session.add(location)
        await session.flush()
        return location

    async def get_by_id(
        self, session: AsyncSession, organization_id: UUID, location_id: UUID
    ) -> Location | None:
        return cast(
            Location | None,
            await session.scalar(
                select(Location).where(
                    Location.organization_id == organization_id, Location.id == location_id
                )
            ),
        )

    async def get_by_slug(
        self, session: AsyncSession, organization_id: UUID, slug: str
    ) -> Location | None:
        return cast(
            Location | None,
            await session.scalar(
                select(Location).where(
                    Location.organization_id == organization_id, Location.slug == slug
                )
            ),
        )

    async def get_primary(self, session: AsyncSession, organization_id: UUID) -> Location | None:
        return cast(
            Location | None,
            await session.scalar(
                select(Location).where(
                    Location.organization_id == organization_id, Location.is_primary.is_(True)
                )
            ),
        )

    async def list(
        self, session: AsyncSession, organization_id: UUID, *, limit: int, offset: int
    ) -> tuple[list[Location], bool]:
        if not 1 <= limit <= MAX_LOCATION_LIST_LIMIT:
            raise ValueError(f"Location list limit must be 1-{MAX_LOCATION_LIST_LIMIT}")
        if offset < 0:
            raise ValueError("Location list offset must not be negative")
        result = await session.scalars(
            select(Location)
            .where(Location.organization_id == organization_id)
            .order_by(Location.created_at.asc(), Location.id.asc())
            .offset(offset)
            .limit(limit + 1)
        )
        locations = list(result)
        return locations[:limit], len(locations) > limit

    async def transition_status(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        *,
        expected_status: LocationStatus,
        expected_version: int,
        target_status: LocationStatus,
    ) -> Location | None:
        values: dict[str, object] = {
            "status": target_status,
            "version": Location.version + 1,
            "updated_at": utc_now(),
        }
        if target_status is LocationStatus.ARCHIVED:
            values["archived_at"] = utc_now()
        statement = (
            update(Location)
            .where(
                Location.organization_id == organization_id,
                Location.id == location_id,
                Location.status == expected_status,
                Location.version == expected_version,
            )
            .values(**values)
            .returning(Location)
        )
        return cast(Location | None, await session.scalar(statement))
