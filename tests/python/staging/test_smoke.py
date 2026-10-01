"""Scheduled read-only smoke resolves canonical scoped mappings and adapters."""

import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.execution.provider_sync_handlers import (
    live_smoke_authorized,
    scheduled_property_id,
)
from apps.api.app.integrations.errors import IntegrationReconnectRequiredError
from apps.api.app.staging.provider_fixtures import fixture_token

from .test_isolation import staging_values


def test_live_smoke_is_explicitly_scoped() -> None:
    allowed = uuid4()
    values = staging_values() | {"staging_live_google_organization_ids": str(allowed)}
    settings = Settings(**values)
    assert live_smoke_authorized(settings, allowed)
    assert not live_smoke_authorized(settings, uuid4())
    assert not live_smoke_authorized(Settings(environment=EnvironmentName.TEST), allowed)


def test_schedule_rejects_missing_and_cross_scope() -> None:
    async def run() -> None:
        session = AsyncMock()
        assert await scheduled_property_id(session, uuid4(), {}, analytics=False) is None
        session.scalar.assert_not_called()
        session.scalar.return_value = None
        assert (
            await scheduled_property_id(
                session, uuid4(), {"schedule_id": str(uuid4())}, analytics=True
            )
            is None
        )
        session.scalars.assert_not_called()

    asyncio.run(run())


def test_expired_fixture_requires_reconnect() -> None:
    with pytest.raises(IntegrationReconnectRequiredError):
        fixture_token("fixture:expired:reconnect")
