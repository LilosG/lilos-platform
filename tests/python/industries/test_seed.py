"""Controlled industry seed idempotency and mismatch tests."""

import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.industries.contracts import IndustryCreate
from apps.api.app.industries.errors import IndustrySeedConflictError
from apps.api.app.industries.models import Industry
from apps.api.app.industries.seed import INITIAL_INDUSTRIES, IndustrySeeder
from apps.api.app.industries.service import IndustryService


@pytest.mark.integration
def test_seed_is_idempotent_audited_and_does_not_overwrite_policies(
    industry_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        seeder = IndustrySeeder()
        async with industry_session_factory.begin() as session:
            first = await seeder.run(session)
        assert first.created == tuple(key for key, _ in INITIAL_INDUSTRIES)
        assert first.existing == ()
        async with industry_session_factory.begin() as session:
            stored = await seeder.service.repository.get_by_key(session, "restaurant")
            assert stored is not None
            stored.default_configuration = {"preserved": True}
        async with industry_session_factory.begin() as session:
            second = await seeder.run(session)
        assert second.created == ()
        assert second.existing == tuple(key for key, _ in INITIAL_INDUSTRIES)
        async with industry_session_factory() as session:
            industry_count = await session.scalar(select(func.count()).select_from(Industry))
            audit_count = await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "platform.industry.created")
            )
            restaurant = await seeder.service.repository.get_by_key(session, "restaurant")
        assert industry_count == audit_count == 5
        assert restaurant is not None
        assert restaurant.default_configuration == {"preserved": True}

    asyncio.run(exercise())


@pytest.mark.integration
def test_seed_reports_key_name_mismatch(
    industry_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def exercise() -> None:
        async with industry_session_factory.begin() as session:
            await IndustryService().create(
                session,
                IndustryCreate(key="general_local_business", name="Mismatched Name"),
                correlation_id="mismatch-setup",
            )
        with pytest.raises(IndustrySeedConflictError):
            async with industry_session_factory.begin() as session:
                await IndustrySeeder().run(session)
        async with industry_session_factory() as session:
            industry_count = await session.scalar(select(func.count()).select_from(Industry))
            audit_count = await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.event_type == "platform.industry.created")
            )
            mismatch = await IndustrySeeder().service.repository.get_by_key(
                session, "general_local_business"
            )
            first_seed_item = await IndustrySeeder().service.repository.get_by_key(
                session, "restaurant"
            )
        assert industry_count == audit_count == 1
        assert mismatch is not None and mismatch.name == "Mismatched Name"
        assert first_seed_item is None

    asyncio.run(exercise())
