"""Explicit controlled seed command for the initial provider registry."""

import asyncio

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.integrations.models import Provider
from apps.api.app.integrations.provider_seed import ProviderCatalogSeeder

assert AuditEvent.metadata is Provider.metadata


async def seed() -> None:
    runtime = create_database_runtime(Settings())
    session_factory = runtime.require_session_factory()
    try:
        async with session_factory.begin() as session:
            result = await ProviderCatalogSeeder().run(session)
        print(
            "Provider seed complete: "
            f"created={','.join(result.created) or 'none'}; "
            f"existing={','.join(result.existing) or 'none'}"
        )
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
