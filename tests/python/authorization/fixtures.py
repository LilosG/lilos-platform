"""Authorization-local fixtures for product API tests with entitled tenants."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.enums import EntitlementStatus
from apps.api.app.administration.models import ProductEntitlement
from apps.api.app.administration.repository import AdministrationCatalogRepository


async def add_effective_product_entitlement(
    session: AsyncSession,
    organization_id: UUID,
    product_key: str,
    *,
    correlation_id: str,
) -> ProductEntitlement:
    """Give a product API fixture the entitlement its scenario assumes."""

    await AdministrationCatalogSeeder().seed(session, correlation_id=correlation_id)
    product = await AdministrationCatalogRepository().get_product_by_key(session, product_key)
    assert product is not None
    entitlement = ProductEntitlement(
        organization_id=organization_id,
        product_id=product.id,
        status=EntitlementStatus.SETUP_REQUIRED.value,
        source="authorization_test_fixture",
        reason="Product API authorization fixture.",
        version=1,
    )
    session.add(entitlement)
    await session.flush()
    return entitlement
