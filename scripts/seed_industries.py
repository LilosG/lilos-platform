"""Explicit controlled seed command for the initial industry registry."""

import asyncio

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.industries.models import Industry
from apps.api.app.industries.seed import IndustrySeeder
from apps.api.app.locations.models import Location
from apps.api.app.organizations.models import Organization

assert AuditEvent.metadata is Industry.metadata is Location.metadata is Organization.metadata


async def seed() -> None:
    runtime = create_database_runtime(Settings())
    session_factory = runtime.require_session_factory()
    try:
        async with session_factory.begin() as session:
            result = await IndustrySeeder().run(session)
        print(
            "Industry seed complete: "
            f"created={','.join(result.created) or 'none'}; "
            f"existing={','.join(result.existing) or 'none'}"
        )
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
