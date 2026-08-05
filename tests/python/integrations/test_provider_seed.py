"""Deterministic tests for the explicit, idempotent provider-registry seed."""

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.integrations.models import Provider
from apps.api.app.integrations.provider_seed import (
    INITIAL_PROVIDERS,
    ProviderCatalogSeeder,
    ProviderSeedConflictError,
)


@pytest.mark.integration
@pytest.mark.anyio
async def test_seed_creates_google_business_profile_once(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with integrations_session_factory.begin() as session:
        result = await ProviderCatalogSeeder().run(session)
        assert result.created == ("google_business_profile",)
        assert result.existing == ()

        stored = await session.scalar(
            select(Provider).where(Provider.key == "google_business_profile")
        )
        assert stored is not None
        assert stored.status == "active"
        assert stored.capabilities == ["profile.read", "profile.write"]

    async with integrations_session_factory.begin() as session:
        second = await ProviderCatalogSeeder().run(session)
        assert second.created == ()
        assert second.existing == ("google_business_profile",)


@pytest.mark.integration
@pytest.mark.anyio
async def test_seed_rejects_a_conflicting_existing_row(
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    key, _, capabilities = INITIAL_PROVIDERS[0]
    async with integrations_session_factory.begin() as session:
        session.add(
            Provider(
                key=key,
                name="A Different Name",
                status="active",
                capabilities=list(capabilities),
            )
        )

    async with integrations_session_factory.begin() as session:
        with pytest.raises(ProviderSeedConflictError):
            await ProviderCatalogSeeder().run(session)
