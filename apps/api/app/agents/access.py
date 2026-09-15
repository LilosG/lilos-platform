"""Canonical product capability resolver for governed agent execution.

The UI, API start boundary, and future schedulers must consume the same decision
instead of independently inferring readiness from location, entitlement, or
provider rows. Provider-specific state is resolved here from canonical mappings.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.service import AdministrationService
from apps.api.app.integrations.models import ProviderResourceMapping
from apps.api.app.locations.enums import LocationStatus
from apps.api.app.locations.models import Location
from apps.api.app.products.gbp.models import GBPLocation

NOT_EFFECTIVE_ENTITLEMENT_STATUSES = frozenset({"not_enabled", "archived", "suspended"})
GROWTH_SOURCE_PRODUCT_KEYS = ("seo", "content", "gbp", "reviews")
GBP_OPERABLE_LOCATION_STATUSES = frozenset({LocationStatus.SETUP_REQUIRED, LocationStatus.ACTIVE})


@dataclass(frozen=True, slots=True)
class AgentAccessDecision:
    eligible: bool
    reason_code: str | None = None
    status_code: int = 200
    detail: str | None = None


class AgentAccessService:
    """Resolve whether one governed product agent may run for one location."""

    def __init__(self, administration: AdministrationService | None = None) -> None:
        self.administration = administration or AdministrationService()

    async def _entitlement_allows_location(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        product_key: str,
    ) -> bool:
        product = await self.administration.catalog.get_product_by_key(session, product_key)
        if product is None:
            return False
        entitlement = await self.administration.entitlements.get_by_product(
            session, organization_id, product.id
        )
        if entitlement is None or entitlement.status in NOT_EFFECTIVE_ENTITLEMENT_STATUSES:
            return False
        selected_locations = await self.administration.entitlements.locations(
            session, organization_id, entitlement.id
        )
        return not selected_locations or location_id in {
            item.location_id for item in selected_locations
        }

    async def _entitlement_decision(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        product_key: str,
    ) -> AgentAccessDecision:
        product = await self.administration.catalog.get_product_by_key(session, product_key)
        entitlement = (
            await self.administration.entitlements.get_by_product(
                session, organization_id, product.id
            )
            if product is not None
            else None
        )

        if product_key == "growth":
            if (
                entitlement is not None
                and entitlement.status not in NOT_EFFECTIVE_ENTITLEMENT_STATUSES
            ):
                selected_locations = await self.administration.entitlements.locations(
                    session, organization_id, entitlement.id
                )
                if selected_locations and location_id not in {
                    item.location_id for item in selected_locations
                }:
                    return AgentAccessDecision(
                        False,
                        "LOCATION_OUTSIDE_GROWTH_ENTITLEMENT",
                        403,
                        "Location is outside the Growth product entitlement",
                    )
                return AgentAccessDecision(True)

            for source_product_key in GROWTH_SOURCE_PRODUCT_KEYS:
                if await self._entitlement_allows_location(
                    session, organization_id, location_id, source_product_key
                ):
                    return AgentAccessDecision(True)
            return AgentAccessDecision(
                False,
                "GROWTH_ENTITLEMENT_NOT_EFFECTIVE",
                409,
                (
                    "Growth planner requires an effective Growth entitlement or at least one "
                    "effective SEO, Content, GBP, or Reviews entitlement for this location"
                ),
            )

        if entitlement is None or entitlement.status in NOT_EFFECTIVE_ENTITLEMENT_STATUSES:
            return AgentAccessDecision(
                False,
                "PRODUCT_ENTITLEMENT_NOT_EFFECTIVE",
                409,
                "Product entitlement is not effective",
            )
        selected_locations = await self.administration.entitlements.locations(
            session, organization_id, entitlement.id
        )
        if selected_locations and location_id not in {
            item.location_id for item in selected_locations
        }:
            return AgentAccessDecision(
                False,
                "LOCATION_OUTSIDE_PRODUCT_ENTITLEMENT",
                403,
                "Location is outside the product entitlement",
            )
        return AgentAccessDecision(True)

    async def _has_canonical_gbp_mapping(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
    ) -> bool:
        mapping_id = await session.scalar(
            select(ProviderResourceMapping.id)
            .join(
                GBPLocation,
                and_(
                    GBPLocation.organization_id == ProviderResourceMapping.organization_id,
                    GBPLocation.connection_id == ProviderResourceMapping.connection_id,
                    GBPLocation.external_location_id
                    == ProviderResourceMapping.external_resource_id,
                ),
            )
            .where(
                ProviderResourceMapping.organization_id == organization_id,
                ProviderResourceMapping.resource_type == "location",
                ProviderResourceMapping.platform_resource_id == location_id,
                ProviderResourceMapping.status == "active",
                GBPLocation.mapping_status != "archived",
            )
            .limit(1)
        )
        return mapping_id is not None

    async def decision(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID,
        product_key: str,
    ) -> AgentAccessDecision:
        location = await session.scalar(
            select(Location).where(
                Location.organization_id == organization_id,
                Location.id == location_id,
            )
        )
        if location is None:
            return AgentAccessDecision(
                False,
                "LOCATION_NOT_FOUND",
                404,
                "Location not found",
            )

        entitlement = await self._entitlement_decision(
            session, organization_id, location_id, product_key
        )
        if not entitlement.eligible:
            return entitlement

        if product_key == "gbp":
            if location.status not in GBP_OPERABLE_LOCATION_STATUSES:
                return AgentAccessDecision(
                    False,
                    "LOCATION_NOT_OPERABLE",
                    409,
                    "Location is not operable for the Business Profile agent",
                )
            if await self._has_canonical_gbp_mapping(session, organization_id, location_id):
                return AgentAccessDecision(True)
            return AgentAccessDecision(
                False,
                "GBP_MAPPING_NOT_CONFIRMED",
                409,
                "A canonical Business Profile mapping is required for this location",
            )

        if location.status != LocationStatus.ACTIVE:
            return AgentAccessDecision(
                False,
                "LOCATION_NOT_ACTIVE",
                409,
                "Location must be active for this product agent",
            )
        return AgentAccessDecision(True)
