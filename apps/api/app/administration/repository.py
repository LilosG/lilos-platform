"""Narrow tenant-scoped Phase 4 persistence operations."""

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.models import (
    BusinessFactRevision,
    ConfigurationDefinition,
    ConfigurationRevision,
    FeatureFlagRevision,
    OffboardingPlan,
    OffboardingStep,
    OnboardingChecklistItem,
    PolicyRevision,
    Product,
    ProductEntitlement,
    ProductEntitlementLocation,
    RuntimeControlRevision,
    ServiceAssignment,
    ServiceDefinition,
)


class ServiceRepository:
    async def add(self, session: AsyncSession, item: object) -> None:
        session.add(item)
        await session.flush()

    async def get(
        self, session: AsyncSession, organization_id: UUID, service_id: UUID, *, lock: bool = False
    ) -> ServiceDefinition | None:
        stmt = select(ServiceDefinition).where(
            ServiceDefinition.organization_id == organization_id, ServiceDefinition.id == service_id
        )
        return cast(
            ServiceDefinition | None, await session.scalar(stmt.with_for_update() if lock else stmt)
        )

    async def list_services(
        self, session: AsyncSession, organization_id: UUID
    ) -> list[ServiceDefinition]:
        return list(
            await session.scalars(
                select(ServiceDefinition)
                .where(ServiceDefinition.organization_id == organization_id)
                .order_by(ServiceDefinition.key, ServiceDefinition.id)
            )
        )

    async def list_assignments(
        self, session: AsyncSession, organization_id: UUID, location_id: UUID | None = None
    ) -> list[ServiceAssignment]:
        stmt = select(ServiceAssignment).where(
            ServiceAssignment.organization_id == organization_id,
            ServiceAssignment.status == "active",
        )
        if location_id is None:
            stmt = stmt.where(ServiceAssignment.scope_type == "organization")
        else:
            stmt = stmt.where(
                (ServiceAssignment.scope_type == "organization")
                | (ServiceAssignment.location_id == location_id)
            )
        return list(
            await session.scalars(
                stmt.order_by(ServiceAssignment.scope_type, ServiceAssignment.service_id)
            )
        )

    async def get_assignment(
        self,
        session: AsyncSession,
        organization_id: UUID,
        assignment_id: UUID,
        *,
        lock: bool = False,
    ) -> ServiceAssignment | None:
        stmt = select(ServiceAssignment).where(
            ServiceAssignment.organization_id == organization_id,
            ServiceAssignment.id == assignment_id,
        )
        return cast(
            ServiceAssignment | None,
            await session.scalar(stmt.with_for_update() if lock else stmt),
        )


class FactRepository:
    async def add(self, session: AsyncSession, item: BusinessFactRevision) -> BusinessFactRevision:
        session.add(item)
        await session.flush()
        return item

    async def get(
        self, session: AsyncSession, organization_id: UUID, revision_id: UUID, *, lock: bool = False
    ) -> BusinessFactRevision | None:
        stmt = select(BusinessFactRevision).where(
            BusinessFactRevision.organization_id == organization_id,
            BusinessFactRevision.id == revision_id,
        )
        return cast(
            BusinessFactRevision | None,
            await session.scalar(stmt.with_for_update() if lock else stmt),
        )

    async def list_identity(
        self, session: AsyncSession, organization_id: UUID, identity: UUID, *, lock: bool = False
    ) -> list[BusinessFactRevision]:
        stmt = (
            select(BusinessFactRevision)
            .where(
                BusinessFactRevision.organization_id == organization_id,
                BusinessFactRevision.fact_identity == identity,
            )
            .order_by(BusinessFactRevision.revision)
        )
        if lock:
            stmt = stmt.with_for_update()
        return list(await session.scalars(stmt))

    async def candidates(
        self,
        session: AsyncSession,
        organization_id: UUID,
        fact_key: str,
        at: datetime,
        location_id: UUID | None,
    ) -> list[BusinessFactRevision]:
        stmt = select(BusinessFactRevision).where(
            BusinessFactRevision.organization_id == organization_id,
            BusinessFactRevision.fact_key == fact_key,
            BusinessFactRevision.status == "active",
            BusinessFactRevision.effective_from <= at,
            (
                BusinessFactRevision.effective_until.is_(None)
                | (BusinessFactRevision.effective_until > at)
            ),
        )
        if location_id is None:
            stmt = stmt.where(BusinessFactRevision.location_id.is_(None))
        else:
            stmt = stmt.where(
                BusinessFactRevision.location_id.is_(None)
                | (BusinessFactRevision.location_id == location_id)
            )
        return list(
            await session.scalars(
                stmt.order_by(BusinessFactRevision.revision.desc(), BusinessFactRevision.id)
            )
        )


class AdministrationCatalogRepository:
    async def list_products(self, session: AsyncSession) -> list[Product]:
        return list(await session.scalars(select(Product).order_by(Product.key)))

    async def get_product_by_key(self, session: AsyncSession, key: str) -> Product | None:
        return cast(Product | None, await session.scalar(select(Product).where(Product.key == key)))

    async def list_definitions(self, session: AsyncSession) -> list[ConfigurationDefinition]:
        return list(
            await session.scalars(
                select(ConfigurationDefinition).order_by(
                    ConfigurationDefinition.key, ConfigurationDefinition.schema_version
                )
            )
        )

    async def get_definition(
        self, session: AsyncSession, key: str
    ) -> ConfigurationDefinition | None:
        return cast(
            ConfigurationDefinition | None,
            await session.scalar(
                select(ConfigurationDefinition)
                .where(ConfigurationDefinition.key == key)
                .order_by(ConfigurationDefinition.schema_version.desc())
                .limit(1)
            ),
        )

    async def seed_add(self, session: AsyncSession, *items: object) -> None:
        session.add_all(items)
        await session.flush()


class EntitlementRepository:
    async def add(self, session: AsyncSession, item: object) -> None:
        session.add(item)
        await session.flush()

    async def get(
        self,
        session: AsyncSession,
        organization_id: UUID,
        entitlement_id: UUID,
        *,
        lock: bool = False,
    ) -> ProductEntitlement | None:
        stmt = select(ProductEntitlement).where(
            ProductEntitlement.organization_id == organization_id,
            ProductEntitlement.id == entitlement_id,
        )
        return cast(
            ProductEntitlement | None,
            await session.scalar(stmt.with_for_update() if lock else stmt),
        )

    async def get_by_product(
        self, session: AsyncSession, organization_id: UUID, product_id: UUID
    ) -> ProductEntitlement | None:
        return cast(
            ProductEntitlement | None,
            await session.scalar(
                select(ProductEntitlement).where(
                    ProductEntitlement.organization_id == organization_id,
                    ProductEntitlement.product_id == product_id,
                )
            ),
        )

    async def locations(
        self, session: AsyncSession, organization_id: UUID, entitlement_id: UUID
    ) -> list[ProductEntitlementLocation]:
        return list(
            await session.scalars(
                select(ProductEntitlementLocation)
                .where(
                    ProductEntitlementLocation.organization_id == organization_id,
                    ProductEntitlementLocation.entitlement_id == entitlement_id,
                    ProductEntitlementLocation.status == "active",
                )
                .order_by(ProductEntitlementLocation.location_id)
            )
        )


class ConfigurationRepository:
    async def add(self, session: AsyncSession, item: object) -> None:
        session.add(item)
        await session.flush()

    async def get(
        self, session: AsyncSession, organization_id: UUID, revision_id: UUID, *, lock: bool = False
    ) -> ConfigurationRevision | None:
        stmt = select(ConfigurationRevision).where(
            ConfigurationRevision.organization_id == organization_id,
            ConfigurationRevision.id == revision_id,
        )
        return cast(
            ConfigurationRevision | None,
            await session.scalar(stmt.with_for_update() if lock else stmt),
        )

    async def identity(
        self, session: AsyncSession, organization_id: UUID, identity: UUID, *, lock: bool = False
    ) -> list[ConfigurationRevision]:
        stmt = (
            select(ConfigurationRevision)
            .where(
                ConfigurationRevision.organization_id == organization_id,
                ConfigurationRevision.configuration_identity == identity,
            )
            .order_by(ConfigurationRevision.revision)
        )
        return list(await session.scalars(stmt.with_for_update() if lock else stmt))

    async def effective(
        self,
        session: AsyncSession,
        organization_id: UUID,
        definition_id: UUID,
        at: datetime,
        location_id: UUID | None,
        product_id: UUID | None,
    ) -> list[ConfigurationRevision]:
        stmt = select(ConfigurationRevision).where(
            ConfigurationRevision.organization_id == organization_id,
            ConfigurationRevision.definition_id == definition_id,
            ConfigurationRevision.status.in_(("active", "approved", "scheduled")),
            ConfigurationRevision.effective_from <= at,
            (
                ConfigurationRevision.effective_until.is_(None)
                | (ConfigurationRevision.effective_until > at)
            ),
        )
        allowed = ConfigurationRevision.scope_type == "organization"
        if location_id is not None:
            allowed = allowed | (
                (ConfigurationRevision.scope_type == "location")
                & (ConfigurationRevision.location_id == location_id)
            )
        if product_id is not None:
            allowed = allowed | (
                (ConfigurationRevision.scope_type == "product")
                & (ConfigurationRevision.product_id == product_id)
                & (
                    ConfigurationRevision.location_id.is_(None)
                    | (ConfigurationRevision.location_id == location_id)
                )
            )
        return list(
            await session.scalars(
                stmt.where(allowed).order_by(
                    ConfigurationRevision.revision, ConfigurationRevision.id
                )
            )
        )


class PolicyRepository:
    async def add(self, session: AsyncSession, item: PolicyRevision) -> None:
        session.add(item)
        await session.flush()

    async def get(
        self, session: AsyncSession, organization_id: UUID, revision_id: UUID, *, lock: bool = False
    ) -> PolicyRevision | None:
        stmt = select(PolicyRevision).where(
            PolicyRevision.organization_id == organization_id, PolicyRevision.id == revision_id
        )
        return cast(
            PolicyRevision | None, await session.scalar(stmt.with_for_update() if lock else stmt)
        )

    async def identity(
        self, session: AsyncSession, organization_id: UUID, identity: UUID, *, lock: bool = False
    ) -> list[PolicyRevision]:
        stmt = (
            select(PolicyRevision)
            .where(
                PolicyRevision.organization_id == organization_id,
                PolicyRevision.policy_identity == identity,
            )
            .order_by(PolicyRevision.revision)
        )
        return list(await session.scalars(stmt.with_for_update() if lock else stmt))

    async def effective(
        self,
        session: AsyncSession,
        organization_id: UUID,
        category: str,
        at: datetime,
        product_id: UUID | None = None,
    ) -> list[PolicyRevision]:
        stmt = select(PolicyRevision).where(
            PolicyRevision.organization_id == organization_id,
            PolicyRevision.category == category,
            PolicyRevision.status == "active",
            PolicyRevision.effective_from <= at,
            (PolicyRevision.effective_until.is_(None) | (PolicyRevision.effective_until > at)),
        )
        if product_id is not None:
            stmt = stmt.where(
                PolicyRevision.product_id.is_(None) | (PolicyRevision.product_id == product_id)
            )
        return list(
            await session.scalars(
                stmt.order_by(
                    PolicyRevision.scope_type, PolicyRevision.policy_key, PolicyRevision.revision
                )
            )
        )


class OperationsRepository:
    async def add(self, session: AsyncSession, item: object) -> None:
        session.add(item)
        await session.flush()

    async def controls(
        self,
        session: AsyncSession,
        organization_id: UUID,
        capability: str,
        at: datetime,
        location_id: UUID | None,
        product_id: UUID | None,
    ) -> list[RuntimeControlRevision]:
        stmt = select(RuntimeControlRevision).where(
            RuntimeControlRevision.organization_id == organization_id,
            RuntimeControlRevision.capability == capability,
            RuntimeControlRevision.effective_from <= at,
            (
                RuntimeControlRevision.effective_until.is_(None)
                | (RuntimeControlRevision.effective_until > at)
            ),
        )
        scope = RuntimeControlRevision.scope_type == "organization"
        if location_id is not None:
            scope = scope | (
                (RuntimeControlRevision.scope_type == "location")
                & (RuntimeControlRevision.location_id == location_id)
            )
        if product_id is not None:
            scope = scope | (
                (RuntimeControlRevision.scope_type == "product")
                & (RuntimeControlRevision.product_id == product_id)
            )
        return list(
            await session.scalars(
                stmt.where(scope).order_by(
                    RuntimeControlRevision.version, RuntimeControlRevision.id
                )
            )
        )

    async def flags(
        self,
        session: AsyncSession,
        organization_id: UUID,
        key: str,
        at: datetime,
        location_id: UUID | None,
    ) -> list[FeatureFlagRevision]:
        stmt = select(FeatureFlagRevision).where(
            FeatureFlagRevision.organization_id == organization_id,
            FeatureFlagRevision.flag_key == key,
            FeatureFlagRevision.effective_from <= at,
            (
                FeatureFlagRevision.effective_until.is_(None)
                | (FeatureFlagRevision.effective_until > at)
            ),
        )
        scope = FeatureFlagRevision.scope_type == "organization"
        if location_id is not None:
            scope = scope | (
                (FeatureFlagRevision.scope_type == "location")
                & (FeatureFlagRevision.location_id == location_id)
            )
        return list(
            await session.scalars(
                stmt.where(scope).order_by(FeatureFlagRevision.version, FeatureFlagRevision.id)
            )
        )

    async def checklist(
        self, session: AsyncSession, organization_id: UUID
    ) -> list[OnboardingChecklistItem]:
        return list(
            await session.scalars(
                select(OnboardingChecklistItem)
                .where(OnboardingChecklistItem.organization_id == organization_id)
                .order_by(OnboardingChecklistItem.item_key, OnboardingChecklistItem.id)
            )
        )

    async def checklist_item(
        self, session: AsyncSession, organization_id: UUID, item_id: UUID, *, lock: bool = False
    ) -> OnboardingChecklistItem | None:
        stmt = select(OnboardingChecklistItem).where(
            OnboardingChecklistItem.organization_id == organization_id,
            OnboardingChecklistItem.id == item_id,
        )
        return cast(
            OnboardingChecklistItem | None,
            await session.scalar(stmt.with_for_update() if lock else stmt),
        )

    async def plan(
        self, session: AsyncSession, organization_id: UUID, plan_id: UUID, *, lock: bool = False
    ) -> OffboardingPlan | None:
        stmt = select(OffboardingPlan).where(
            OffboardingPlan.organization_id == organization_id, OffboardingPlan.id == plan_id
        )
        return cast(
            OffboardingPlan | None, await session.scalar(stmt.with_for_update() if lock else stmt)
        )

    async def steps(
        self, session: AsyncSession, organization_id: UUID, plan_id: UUID
    ) -> list[OffboardingStep]:
        return list(
            await session.scalars(
                select(OffboardingStep)
                .where(
                    OffboardingStep.organization_id == organization_id,
                    OffboardingStep.plan_id == plan_id,
                )
                .order_by(OffboardingStep.step_key)
            )
        )

    async def step(
        self,
        session: AsyncSession,
        organization_id: UUID,
        plan_id: UUID,
        step_id: UUID,
        *,
        lock: bool = False,
    ) -> OffboardingStep | None:
        stmt = select(OffboardingStep).where(
            OffboardingStep.organization_id == organization_id,
            OffboardingStep.plan_id == plan_id,
            OffboardingStep.id == step_id,
        )
        return cast(
            OffboardingStep | None,
            await session.scalar(stmt.with_for_update() if lock else stmt),
        )
