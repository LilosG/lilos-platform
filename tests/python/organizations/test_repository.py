"""PostgreSQL organization repository tests."""

import asyncio
from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy import update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.repository import OrganizationRepository


def organization(slug: str, identifier: UUID) -> Organization:
    return Organization(
        id=identifier,
        name=f"Fabricated {slug}",
        slug=slug,
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.PROSPECT,
        timezone="UTC",
        default_currency="USD",
        created_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
        version=1,
    )


@pytest.mark.integration
def test_repository_retrieval_is_record_specific_and_pagination_is_deterministic(
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        repository = OrganizationRepository()
        first_id = UUID("00000000-0000-4000-8000-000000000001")
        second_id = UUID("00000000-0000-4000-8000-000000000002")
        third_id = UUID("00000000-0000-4000-8000-000000000003")
        async with organization_session_factory.begin() as session:
            for item in (
                organization("fabricated-three", third_id),
                organization("fabricated-one", first_id),
                organization("fabricated-two", second_id),
            ):
                await repository.add(session, item)

        async with organization_session_factory() as session:
            selected = await repository.get_by_id(session, second_id)
            missing = await repository.get_by_id(
                session, UUID("00000000-0000-4000-8000-000000000099")
            )
            page_one, has_more = await repository.list(session, limit=2, offset=0)
            page_two, final_has_more = await repository.list(session, limit=2, offset=2)

        assert selected is not None and selected.id == second_id
        assert missing is None
        assert [item.id for item in page_one] == [first_id, second_id]
        assert [item.id for item in page_two] == [third_id]
        assert has_more is True
        assert final_has_more is False

    asyncio.run(exercise())


@pytest.mark.integration
def test_database_rejects_organization_slug_mutation(
    organization_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        repository = OrganizationRepository()
        organization_id = UUID("00000000-0000-4000-8000-000000000010")
        async with organization_session_factory.begin() as session:
            await repository.add(session, organization("immutable-slug", organization_id))

        with pytest.raises(DBAPIError):
            async with organization_session_factory.begin() as session:
                await session.execute(
                    update(Organization)
                    .where(Organization.id == organization_id)
                    .values(slug="changed-slug")
                )

        async with organization_session_factory() as session:
            stored = await repository.get_by_id(session, organization_id)
            assert stored is not None and stored.slug == "immutable-slug"

    asyncio.run(exercise())


def test_repository_exposes_no_delete_or_general_update_method() -> None:
    public_methods = {name for name in dir(OrganizationRepository) if not name.startswith("_")}
    assert "delete" not in public_methods
    assert "update" not in public_methods
    assert "update_slug" not in public_methods
