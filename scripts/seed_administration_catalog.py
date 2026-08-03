"""Explicit idempotent Phase 4 product and configuration catalog seed."""

import asyncio

from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.models import Product
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.industries.models import Industry
from apps.api.app.locations.models import Location
from apps.api.app.organizations.models import Organization

assert (
    Product.metadata
    is AuditEvent.metadata
    is UserProfile.metadata
    is Industry.metadata
    is Location.metadata
    is Organization.metadata
)


async def main() -> None:
    runtime = create_database_runtime(Settings())
    factory = runtime.require_session_factory()
    try:
        async with factory() as session, session.begin():
            result = await AdministrationCatalogSeeder().seed(
                session, correlation_id="administration-catalog-seed"
            )
            print(
                "Phase 4 catalogs seeded: "
                f"products={result.products_created}, "
                f"configuration_definitions={result.configuration_definitions_created}"
            )
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    asyncio.run(main())
