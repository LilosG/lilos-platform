"""Real disposable PostgreSQL seed reruns and refusal boundaries."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import apps.worker.bootstrap  # noqa: F401
from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import Settings
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.locations.models import Location
from apps.api.app.organizations.models import Organization
from apps.api.app.products.seo.models import SEOWebsite
from apps.api.app.staging.seed import SHAPES, seed_staging
from scripts.configure_staging_smoke import configure

from .test_isolation import staging_values


def test_seed_and_smoke_refuse_production_before_session_use() -> None:
    async def run() -> None:
        session = AsyncMock(spec=AsyncSession)
        values: dict[str, Any] = dict(
            _env_file=None,
            environment="production",
            release="test-sha",
            telemetry_export_endpoint="https://telemetry.invalid",
        )
        settings = Settings(**values)
        with pytest.raises(ValueError):
            await seed_staging(session, settings)
        with pytest.raises(ValueError):
            await configure(session, settings)
        session.execute.assert_not_called()
        session.scalar.assert_not_called()

    asyncio.run(run())


@pytest.mark.integration
def test_seed_is_idempotent(staging_test_database: str) -> None:
    async def run() -> None:
        engine = create_async_engine(staging_test_database, poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        settings = Settings(**staging_values())
        try:
            async with sessions.begin() as session:
                first = await seed_staging(session, settings)
            async with sessions.begin() as session:

                async def counts() -> tuple[Any, ...]:
                    return tuple(
                        [
                            await session.scalar(select(func.count()).select_from(model))
                            for model in (
                                Organization,
                                Location,
                                SEOWebsite,
                                IntegrationConnection,
                                AuditEvent,
                            )
                        ]
                    )

                before = await counts()
                second = await seed_staging(session, settings)
                assert first == second and len(first) == len(SHAPES)
                assert await counts() == before
                assert before[:4] == (9, 11, 9, 9)
                reconnect = await session.scalar(
                    select(IntegrationConnection).where(
                        IntegrationConnection.organization_id == first["reconnect"]
                    )
                )
                assert reconnect is not None and reconnect.status == "reconnect_required"
                settings_smoke = Settings(
                    **(
                        staging_values()
                        | {"staging_live_google_organization_ids": first["hospitality"]}
                    )
                )
                with pytest.raises(ValueError, match="independently authorized"):
                    await configure(session, settings_smoke)
                # Simulate an independently connected staging account in this disposable DB.
                # No live token or provider call; only schedule/mapping persistence is tested.
                connection = await session.scalar(
                    select(IntegrationConnection).where(
                        IntegrationConnection.organization_id == first["hospitality"]
                    )
                )
                assert connection is not None
                connection.credential_reference = "secret:synthetic-independent-staging"
                await session.flush()
                assert await configure(session, settings_smoke) == 2
                assert await configure(session, settings_smoke) == 0
                from apps.api.app.execution.provider_sync_handlers import scheduled_property_id
                from apps.api.app.execution.service import ExecutionService

                run = await ExecutionService().dispatch_due_schedule(session, "staging-smoke-test")
                assert run is not None
                property_id = await scheduled_property_id(
                    session, run.organization_id, run.input_document, analytics=False
                )
                assert property_id is not None

        finally:
            await engine.dispose()

    asyncio.run(run())
