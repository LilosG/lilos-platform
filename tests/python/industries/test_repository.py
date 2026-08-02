"""Industry repository boundary and PostgreSQL enforcement tests."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.industries.enums import IndustryStatus
from apps.api.app.industries.models import Industry
from apps.api.app.industries.repository import IndustryRepository


def industry(key: str, identifier: UUID) -> Industry:
    return Industry(
        id=identifier,
        key=key,
        name=f"Fabricated {key}",
        status=IndustryStatus.ACTIVE,
        default_configuration={},
        default_risk_policy={},
        default_content_policy={},
        created_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        version=1,
    )


@pytest.mark.integration
def test_repository_lookup_and_deterministic_pagination(
    industry_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        repository = IndustryRepository()
        ids = [UUID(f"00000000-0000-4000-8000-{value:012d}") for value in range(1, 4)]
        async with industry_session_factory.begin() as session:
            for key, identifier in zip(
                ("industry_one", "industry_two", "industry_three"), ids, strict=True
            ):
                await repository.add(session, industry(key, identifier))
        async with industry_session_factory() as session:
            assert (await repository.get_by_key(session, "industry_two")).id == ids[1]  # type: ignore[union-attr]
            first, more = await repository.list(session, limit=2, offset=0)
            second, final_more = await repository.list(session, limit=2, offset=2)
        assert [item.id for item in first] == ids[:2]
        assert [item.id for item in second] == ids[2:]
        assert more and not final_more

    asyncio.run(exercise())


@pytest.mark.integration
def test_database_rejects_key_mutation(
    industry_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        repository = IndustryRepository()
        identifier = UUID("00000000-0000-4000-8000-000000000010")
        async with industry_session_factory.begin() as session:
            await repository.add(session, industry("immutable_industry", identifier))
        with pytest.raises(DBAPIError):
            async with industry_session_factory.begin() as session:
                await session.execute(
                    update(Industry).where(Industry.id == identifier).values(key="changed_industry")
                )

    asyncio.run(exercise())


def test_repository_surface_is_narrow() -> None:
    public = {name for name in dir(IndustryRepository) if not name.startswith("_")}
    assert public == {"add", "get_by_id", "get_by_key", "list", "transition_status"}
