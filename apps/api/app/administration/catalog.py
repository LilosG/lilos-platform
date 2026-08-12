"""Deterministic product and configuration-definition catalogs."""

from dataclasses import dataclass, field
from typing import cast
from uuid import UUID, uuid5

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.errors import CatalogMismatchError
from apps.api.app.administration.models import ConfigurationDefinition, Product
from apps.api.app.administration.repository import AdministrationCatalogRepository
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService

ADMINISTRATION_CATALOG_NAMESPACE = UUID("1ea5dc73-7766-5e29-8da0-acde9a88feca")

PRODUCT_CATALOG: dict[str, dict[str, object]] = {
    "seo": {
        "name": "LILOs SEO",
        "description": "Search visibility and optimization opportunities.",
        "required_configuration_keys": ["seo.general"],
        "required_business_fact_keys": ["business.name", "business.address"],
        # The self-contained crawl/analysis path requires NO external
        # integration.  Google Search Console and Google Analytics are
        # optional, separately-classified enhancements (SEOSearchProperty) and
        # must NOT block the crawl path or mark the SEO product unavailable.
        "required_integrations": [],
        "requires_location_profile": True,
    },
    "gbp": {
        "name": "LILOs GBP",
        "description": "Google Business Profile operations.",
        "required_configuration_keys": ["gbp.general"],
        "required_business_fact_keys": ["business.name", "business.address", "business.hours"],
        "required_integrations": ["google_business_profile"],
        # GBP operates from the Core Platform Organization/Location model,
        # shared business facts, and provider state mapped to that Location.
        # It does not consume the separate LocationProfile content/configuration
        # entity.
        "requires_location_profile": False,
    },
    "reviews": {
        "name": "LILOs Reviews",
        "description": "Customer review operations.",
        "required_configuration_keys": ["reviews.general"],
        "required_business_fact_keys": ["business.name"],
        "required_integrations": ["google_business_profile"],
        # Reviews operates from confirmed GBP mappings and provider state.
        # It does not consume the platform LocationProfile entity.
        "requires_location_profile": False,
    },
    "content": {
        "name": "LILOs Content",
        "description": "Governed content creation and publication preparation.",
        "required_configuration_keys": ["content.general"],
        "required_business_fact_keys": ["business.name", "brand.approved_claims"],
        "required_integrations": [],
        "requires_location_profile": False,
    },
    "insights": {
        "name": "LILOs Insights",
        "description": "Cross-product reporting and insight preparation.",
        "required_configuration_keys": ["insights.general"],
        "required_business_fact_keys": ["business.name"],
        "required_integrations": [],
        "requires_location_profile": False,
    },
    "leads": {
        "name": "LILOs Leads",
        "description": "Lead intake and follow-up coordination.",
        "required_configuration_keys": ["leads.general"],
        "required_business_fact_keys": ["business.name"],
        "required_integrations": [],
        "requires_location_profile": False,
    },
    "automations": {
        "name": "LILOs Automations",
        "description": "Controlled shared workflow templates.",
        "required_configuration_keys": ["automations.general"],
        "required_business_fact_keys": ["business.name"],
        "required_integrations": [],
        "requires_location_profile": False,
    },
}

CONFIGURATION_CATALOG: dict[str, dict[str, object]] = {
    key: {
        "owning_module": key.split(".")[0],
        "schema_version": 1,
        "value_type": "object",
        "schema_document": {
            "type": "object",
            "properties": {
                "enabled_features": {"type": "array", "items": {"type": "string"}, "maxItems": 50}
            },
            "additionalProperties": False,
        },
        "platform_default": {"enabled_features": []},
        "industry_defaults": {},
        "allowed_scopes": ["organization", "location", "product"],
        "merge_strategy": "object_merge",
        "lower_scope_override_allowed": True,
        "approval_required": True,
        "sensitivity": "business",
        "deprecated": False,
    }
    for key in (
        "seo.general",
        "gbp.general",
        "reviews.general",
        "content.general",
        "insights.general",
        "leads.general",
        "automations.general",
    )
}


def catalog_id(kind: str, key: str) -> UUID:
    return uuid5(ADMINISTRATION_CATALOG_NAMESPACE, f"{kind}:{key}")


@dataclass(frozen=True, slots=True)
class AdministrationSeedResult:
    products_created: int
    configuration_definitions_created: int


@dataclass(frozen=True, slots=True)
class AdministrationCatalogSeeder:
    repository: AdministrationCatalogRepository = field(
        default_factory=AdministrationCatalogRepository
    )
    audit: AuditEventService = field(default_factory=AuditEventService)

    async def seed(self, session: AsyncSession, *, correlation_id: str) -> AdministrationSeedResult:
        products = {item.key: item for item in await self.repository.list_products(session)}
        definitions = {item.key: item for item in await self.repository.list_definitions(session)}
        if set(products) - set(PRODUCT_CATALOG) or set(definitions) - set(CONFIGURATION_CATALOG):
            raise CatalogMismatchError
        products_created = definitions_created = 0
        for key, spec in PRODUCT_CATALOG.items():
            expected = Product(
                id=catalog_id("product", key),
                key=key,
                name=str(spec["name"]),
                description=str(spec["description"]),
                owning_module=f"products.{key}",
                current_product_version="1.0",
                status="registered",
                required_capabilities=[],
                required_configuration_keys=list(
                    cast(list[str], spec["required_configuration_keys"])
                ),
                required_business_fact_keys=list(
                    cast(list[str], spec["required_business_fact_keys"])
                ),
                required_integrations=list(cast(list[str], spec["required_integrations"])),
                requires_organization_profile=True,
                requires_location_profile=bool(spec["requires_location_profile"]),
                requires_approval_policy=True,
                runtime_control_namespace=f"product.{key}",
                version=1,
            )
            current = products.get(key)
            if current is None:
                await self.repository.seed_add(session, expected)
                products[key] = expected
                products_created += 1
            elif self._product_signature(current) != self._product_signature(expected):
                raise CatalogMismatchError
        for key, spec in CONFIGURATION_CATALOG.items():
            expected_definition = ConfigurationDefinition(
                id=catalog_id("configuration", key), key=key, **spec
            )
            current_definition = definitions.get(key)
            if current_definition is None:
                await self.repository.seed_add(session, expected_definition)
                definitions[key] = expected_definition
                definitions_created += 1
            elif self._definition_signature(current_definition) != self._definition_signature(
                expected_definition
            ):
                raise CatalogMismatchError
        for resource_type, count in (
            ("product_catalog", products_created),
            ("configuration_catalog", definitions_created),
        ):
            if count:
                await self.audit.record(
                    session,
                    AuditEventCreate(
                        event_type=f"platform.{resource_type}.seeded",
                        action=f"{resource_type}.seed",
                        result=AuditResult.SUCCEEDED,
                        actor_type=AuditActorType.SYSTEM,
                        product_key="platform",
                        resource_type=resource_type,
                        correlation_id=correlation_id,
                        summary="Immutable Phase 4 catalog records seeded.",
                        metadata={"operation": "seeded", "records_created": count},
                    ),
                )
        return AdministrationSeedResult(products_created, definitions_created)

    @staticmethod
    def _product_signature(item: Product) -> tuple[object, ...]:
        return (
            item.id,
            item.name,
            item.description,
            item.owning_module,
            item.current_product_version,
            item.status,
            item.required_capabilities,
            item.required_configuration_keys,
            item.required_business_fact_keys,
            item.required_integrations,
            item.requires_organization_profile,
            item.requires_location_profile,
            item.requires_approval_policy,
            item.runtime_control_namespace,
            item.version,
        )

    @staticmethod
    def _definition_signature(item: ConfigurationDefinition) -> tuple[object, ...]:
        return (
            item.id,
            item.owning_module,
            item.schema_version,
            item.value_type,
            item.schema_document,
            item.platform_default,
            item.industry_defaults,
            item.allowed_scopes,
            item.merge_strategy,
            item.lower_scope_override_allowed,
            item.approval_required,
            item.sensitivity,
            item.deprecated,
        )
