"""Explicit idempotent role, permission, and mapping catalog seed."""

import asyncio
from uuid import uuid4

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.access_control.models import OrganizationMembership, Role
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.industries.models import Industry
from apps.api.app.locations.models import Location
from apps.api.app.organizations.models import Organization

assert (
    AuditEvent.metadata
    is OrganizationMembership.metadata
    is Role.metadata
    is UserProfile.metadata
    is Industry.metadata
    is Location.metadata
    is Organization.metadata
)


async def main() -> None:
    runtime = create_database_runtime(Settings())
    session_factory = runtime.require_session_factory()
    try:
        async with session_factory() as session, session.begin():
            result = await AccessCatalogSeeder().seed(session, correlation_id=str(uuid4()))
        print(
            f"roles_created={result.roles_created} "
            f"permissions_created={result.permissions_created} "
            f"mappings_created={result.mappings_created}"
        )
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    asyncio.run(main())
