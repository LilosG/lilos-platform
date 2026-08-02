"""Controlled persistence for the global industry registry."""

from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.base import utc_now
from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.models import Industry

MAX_INDUSTRY_LIST_LIMIT = 100


class IndustryRepository:
    """Create, retrieve, list, and transition industries without broad mutation methods."""

    async def add(self, session: AsyncSession, industry: Industry) -> Industry:
        session.add(industry)
        await session.flush()
        return industry

    async def get_by_id(self, session: AsyncSession, industry_id: UUID) -> Industry | None:
        return await session.get(Industry, industry_id)

    async def get_by_key(self, session: AsyncSession, key: str) -> Industry | None:
        return cast(
            Industry | None,
            await session.scalar(select(Industry).where(Industry.key == key)),
        )

    async def list(
        self, session: AsyncSession, *, limit: int, offset: int
    ) -> tuple[list[Industry], bool]:
        if not 1 <= limit <= MAX_INDUSTRY_LIST_LIMIT:
            raise ValueError(f"Industry list limit must be 1-{MAX_INDUSTRY_LIST_LIMIT}")
        if offset < 0:
            raise ValueError("Industry list offset must not be negative")
        result = await session.scalars(
            select(Industry)
            .order_by(Industry.created_at.asc(), Industry.id.asc())
            .offset(offset)
            .limit(limit + 1)
        )
        industries = list(result)
        return industries[:limit], len(industries) > limit

    async def transition_status(
        self,
        session: AsyncSession,
        industry_id: UUID,
        *,
        expected_status: IndustryStatus,
        expected_version: int,
        target_status: IndustryStatus,
    ) -> Industry | None:
        values: dict[str, object] = {
            "status": target_status,
            "version": Industry.version + 1,
            "updated_at": utc_now(),
        }
        if target_status is IndustryStatus.ARCHIVED:
            values["archived_at"] = utc_now()
        statement = (
            update(Industry)
            .where(
                Industry.id == industry_id,
                Industry.status == expected_status,
                Industry.version == expected_version,
            )
            .values(**values)
            .returning(Industry)
        )
        return cast(Industry | None, await session.scalar(statement))
