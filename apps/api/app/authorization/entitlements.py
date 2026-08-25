"""Deterministic product-permission mapping and entitlement evaluation."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.enums import ScopeType
from apps.api.app.administration.enums import EntitlementStatus
from apps.api.app.administration.models import (
    Product,
    ProductEntitlement,
    ProductEntitlementLocation,
)

# This is intentionally exact rather than namespace- or route-derived. Adding a
# product permission requires an explicit authorization contract update.
PRODUCT_PERMISSION_TO_PRODUCT: Mapping[str, str] = MappingProxyType(
    {
        "gbp.read": "gbp",
        "gbp.connect": "gbp",
        "gbp.sync": "gbp",
        "gbp.propose": "gbp",
        "gbp.approve": "gbp",
        "gbp.publish": "gbp",
        "gbp.diagnostics": "gbp",
        "reviews.read": "reviews",
        "reviews.generate_response": "reviews",
        "reviews.approve_response": "reviews",
        "reviews.publish_response": "reviews",
        "reviews.escalate": "reviews",
        "leads.read": "leads",
        "leads.respond": "leads",
        "leads.assign": "leads",
        "leads.manage_sources": "leads",
        "leads.manage_consent": "leads",
        "content.read": "content",
        "content.create": "content",
        "content.edit": "content",
        "content.approve": "content",
        "content.publish": "content",
        "content.rollback": "content",
        "content.manage_targets": "content",
        "seo.read": "seo",
        "seo.manage": "seo",
        "seo.recommend": "seo",
        "seo.approve": "seo",
        "seo.execute": "seo",
        "insights.read": "insights",
        "insights.manage": "insights",
        "insights.publish": "insights",
    }
)


# Entitlement presence and product readiness are separate. Setup, configuration,
# connection, pause, and degradation states preserve commercial entitlement;
# unknown/new states fail closed until deliberately classified here.
EFFECTIVE_ENTITLEMENT_STATUSES: frozenset[str] = frozenset(
    {
        EntitlementStatus.SETUP_REQUIRED.value,
        EntitlementStatus.CONFIGURATION_REQUIRED.value,
        EntitlementStatus.CONNECTION_REQUIRED.value,
        EntitlementStatus.READY.value,
        EntitlementStatus.ACTIVE.value,
        EntitlementStatus.PAUSED.value,
        EntitlementStatus.DEGRADED.value,
    }
)


def product_key_for_permission(permission_key: str) -> str | None:
    """Return the exact product governed by a registered product permission."""

    return PRODUCT_PERMISSION_TO_PRODUCT.get(permission_key)


@dataclass(frozen=True, slots=True)
class ProductEntitlementAuthorizationContext:
    """One product's current entitlement state for an organization."""

    catalog_consistent: bool
    entitlement_id: UUID | None = None
    status: str | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    has_location_scope: bool = False
    active_location_ids: frozenset[UUID] = frozenset()

    def authorizes(
        self,
        request_scope: ScopeType,
        request_location_id: UUID | None,
        *,
        now: datetime,
    ) -> bool:
        """Apply lifecycle, effective-period, and optional location scope."""

        if (
            not self.catalog_consistent
            or self.entitlement_id is None
            or self.status not in EFFECTIVE_ENTITLEMENT_STATUSES
            or self.effective_from is None
            or self.effective_from > now
            or (self.effective_until is not None and self.effective_until <= now)
        ):
            return False
        if not self.has_location_scope:
            return True
        return (
            request_scope is ScopeType.LOCATION
            and request_location_id is not None
            and request_location_id in self.active_location_ids
        )


@dataclass(frozen=True, slots=True)
class ProductEntitlementAuthorizationRepository:
    """Load one product entitlement and its complete location scope in one query."""

    async def resolve(
        self,
        session: AsyncSession,
        organization_id: UUID,
        product_key: str,
    ) -> ProductEntitlementAuthorizationContext | None:
        rows = (
            (
                await session.execute(
                    select(
                        Product.status,
                        ProductEntitlement.id,
                        ProductEntitlement.status,
                        ProductEntitlement.effective_from,
                        ProductEntitlement.effective_until,
                        ProductEntitlementLocation.location_id,
                        ProductEntitlementLocation.status,
                    )
                    .outerjoin(
                        ProductEntitlement,
                        and_(
                            ProductEntitlement.product_id == Product.id,
                            ProductEntitlement.organization_id == organization_id,
                        ),
                    )
                    .outerjoin(
                        ProductEntitlementLocation,
                        and_(
                            ProductEntitlementLocation.organization_id == organization_id,
                            ProductEntitlementLocation.entitlement_id == ProductEntitlement.id,
                        ),
                    )
                    .where(Product.key == product_key)
                    .order_by(ProductEntitlementLocation.location_id)
                )
            )
            .tuples()
            .all()
        )
        if not rows:
            return None

        signatures = {(row[1], row[2], row[3], row[4]) for row in rows}
        if rows[0][0] != "registered" or len(signatures) != 1:
            return ProductEntitlementAuthorizationContext(catalog_consistent=False)

        entitlement_id, status, effective_from, effective_until = next(iter(signatures))
        location_rows = [(row[5], row[6]) for row in rows if row[5] is not None]
        if entitlement_id is None and location_rows:
            return ProductEntitlementAuthorizationContext(catalog_consistent=False)
        return ProductEntitlementAuthorizationContext(
            catalog_consistent=True,
            entitlement_id=entitlement_id,
            status=status,
            effective_from=effective_from,
            effective_until=effective_until,
            has_location_scope=bool(location_rows),
            active_location_ids=frozenset(
                location_id
                for location_id, location_status in location_rows
                if location_status == "active"
            ),
        )
