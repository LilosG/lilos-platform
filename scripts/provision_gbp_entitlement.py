"""One-off, idempotent, production-safe GBP integration-entitlement provisioning.

`POST /api/v1/organizations/{organization_id}/integrations/google/connect`
requires an effective `gbp` `ProductEntitlement`
(`apps.api.app.routes.integrations._require_effective_entitlement`): any
status except `not_enabled`/`archived`/`suspended`, including the entitlement
row's own default `setup_required`. A newly onboarded organization has no
entitlement row at all until one is explicitly created -- there is no
automatic provisioning path -- so "Connect Google" returns 409 even when the
OAuth client, provider seed, and callback route are all correctly configured.

This reuses the exact same repositories the existing, already-deployed
`AdministrationService.create_entitlement` production route uses
(`EntitlementRepository`, `AdministrationCatalogRepository`), constructing the
row directly rather than through that route because it requires a human
`actor_id` to attribute the mutation to -- there is no natural human actor for
a one-off provisioning script, so this attributes the audit event to the
system, exactly as `scripts/seed_integration_providers.py` does for its own
`Provider` row. It does not modify Google Cloud, OAuth credentials, or
provider registration.

Never mounted as an HTTP route. Run manually with direct access to the target
database (`LILOS_DATABASE_URL` already present in the process environment),
for example as a Render one-off Job on the `lilos-api` service.

Required environment variables:
    GBP_ENTITLEMENT_ORGANIZATION_ID   UUID of the organization to provision.

Idempotent: if an effective `gbp` entitlement already exists, nothing is
created and the existing entitlement id/status is reported. If an existing
entitlement is `not_enabled`/`archived`/`suspended`, this script refuses to
override what was a deliberate decision -- resolving that is a separate,
explicit operator action.
"""

import asyncio
import os
from uuid import UUID

from apps.api.app.administration.models import ProductEntitlement
from apps.api.app.administration.repository import (
    AdministrationCatalogRepository,
    EntitlementRepository,
)
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.models import AuditEvent
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.database.base import utc_now
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.locations.models import Location
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.repository import OrganizationRepository

assert (
    AuditEvent.metadata is ProductEntitlement.metadata is Location.metadata is Organization.metadata
)

NOT_EFFECTIVE_ENTITLEMENT_STATUSES = frozenset({"not_enabled", "archived", "suspended"})


def _required_uuid(name: str) -> UUID:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"provisioning blocked: missing required environment variable {name}")
    return UUID(value)


async def provision() -> None:
    organization_id = _required_uuid("GBP_ENTITLEMENT_ORGANIZATION_ID")
    correlation_id = "provision-gbp-entitlement"

    runtime = create_database_runtime(Settings())
    session_factory = runtime.require_session_factory()
    organizations = OrganizationRepository()
    catalog = AdministrationCatalogRepository()
    entitlements = EntitlementRepository()
    audit = AuditEventService()

    try:
        async with session_factory.begin() as session:
            organization = await organizations.get_by_id(session, organization_id)
            if organization is None:
                raise SystemExit(f"provisioning blocked: organization {organization_id} not found")

            product = await catalog.get_product_by_key(session, "gbp")
            if product is None:
                raise SystemExit(
                    "provisioning blocked: product 'gbp' is not seeded; "
                    "run the administration catalog seed first"
                )

            existing = await entitlements.get_by_product(session, organization_id, product.id)
            if existing is not None:
                if existing.status in NOT_EFFECTIVE_ENTITLEMENT_STATUSES:
                    raise SystemExit(
                        f"provisioning blocked: existing GBP entitlement {existing.id} is "
                        f"{existing.status}; resolve explicitly, this script will not "
                        "override a deliberate suspend/archive/disable"
                    )
                print(
                    "GBP entitlement already effective: "
                    f"entitlement_id={existing.id} status={existing.status}"
                )
                return

            item = ProductEntitlement(
                organization_id=organization_id,
                product_id=product.id,
                status="setup_required",
                source="pilot_provisioning",
                reason="GBP OAuth connection pilot enablement",
                effective_from=utc_now(),
                version=1,
            )
            await entitlements.add(session, item)
            await audit.record(
                session,
                AuditEventCreate(
                    event_type="product.entitlement_created",
                    action="product.entitlement_created",
                    result=AuditResult.SUCCEEDED,
                    actor_type=AuditActorType.SYSTEM,
                    organization_id=organization_id,
                    product_key="platform",
                    resource_type="product_entitlement",
                    resource_id=item.id,
                    correlation_id=correlation_id,
                    summary="GBP entitlement provisioned for pilot enablement.",
                    metadata={"product_key": "gbp", "status": item.status},
                ),
            )
        print(f"GBP entitlement created: entitlement_id={item.id} status={item.status}")
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    asyncio.run(provision())
