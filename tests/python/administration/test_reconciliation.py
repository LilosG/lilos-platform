"""Business-fact reconciliation and default-policy recovery tests.

Covers the operator-facing recovery paths for existing clients:

- ``reconcile_business_facts`` derives ``system_derived`` candidates from
  authoritative client data (org profile, primary location, primary domain)
  without auto-approving, and is idempotent.
- ``reconcile_defaults`` provisions the intended safe default approval policy
  for an existing organization that predates the entitlement-time provisioning,
  without overwriting a custom policy.
- The readiness engine aggregates unresolved business facts into a single
  actionable "Review N business details" finding rather than one internal
  record per fact key.
"""

import asyncio
from typing import cast
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.contracts import EntitlementCreate
from apps.api.app.administration.service import AdministrationService
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.database.base import utc_now
from apps.api.app.domains.models import OrganizationDomain
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.profiles.models import OrganizationProfile


def test_reconcile_business_facts_derives_candidates_without_auto_approving(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_reconcile_derives_candidates(administration_session_factory))


async def _reconcile_derives_candidates(factory: async_sessionmaker[AsyncSession]) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    async with factory() as session, session.begin():
        session.add_all(
            [
                UserProfile(
                    id=actor_id,
                    auth_user_id=uuid4(),
                    email="operator@example.invalid",
                    display_name="Operator",
                    status=UserStatus.ACTIVE,
                    version=1,
                ),
                Organization(
                    id=org_id,
                    name="Wheyland Electric",
                    slug="wheyland-electric",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                Location(
                    id=location_id,
                    organization_id=org_id,
                    name="Main Location",
                    slug="main-location",
                    location_type=LocationType.PHYSICAL,
                    status=LocationStatus.ACTIVE,
                    timezone="UTC",
                    country_code="US",
                    address_line_1="123 Main St",
                    city="Springfield",
                    region="IL",
                    postal_code="62704",
                    is_primary=True,
                    version=1,
                ),
                OrganizationProfile(
                    organization_id=org_id,
                    brand_name="Wheyland Electric",
                    approved_claims=["Licensed", "Bonded"],
                    version=1,
                ),
                OrganizationDomain(
                    organization_id=org_id,
                    domain="wheylandelectric.example",
                    is_primary=True,
                    status="active",
                    version=1,
                ),
            ]
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    async with factory() as session, session.begin():
        result = await service.reconcile_business_facts(
            session,
            org_id,
            actor_id=actor_id,
            correlation_id="reconcile-test",
        )
    proposed = cast(list[dict[str, object]], result["proposed"])
    proposed_keys = {item["fact_key"] for item in proposed}
    assert "business.name" in proposed_keys
    assert "business.address" in proposed_keys
    assert "business.website" in proposed_keys
    assert "brand.approved_claims" in proposed_keys
    address_candidate = next(item for item in proposed if item["fact_key"] == "business.address")
    assert address_candidate["location_id"] == str(location_id)
    # Candidates are proposed, NOT auto-approved.
    async with factory() as session:
        name_resolution = await service.resolve_fact(session, org_id, "business.name")
        address_at_organization = await service.resolve_fact(session, org_id, "business.address")
        address_at_location = await service.resolve_fact(
            session, org_id, "business.address", location_id=location_id
        )
    assert name_resolution.state == "missing"
    assert address_at_organization.state == "missing"
    # The derived address intentionally remains a location-scoped candidate;
    # rendering it correctly never promotes or approves it.
    assert address_at_location.state == "missing"

    # Idempotent: a second reconciliation proposes no new duplicates.
    async with factory() as session, session.begin():
        second = await service.reconcile_business_facts(
            session,
            org_id,
            actor_id=actor_id,
            correlation_id="reconcile-test",
        )
    assert second["proposed"] == []


def test_reconcile_defaults_provisions_approval_policy_for_existing_client(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_reconcile_defaults(administration_session_factory))


async def _reconcile_defaults(factory: async_sessionmaker[AsyncSession]) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    async with factory() as session, session.begin():
        session.add_all(
            [
                UserProfile(
                    id=actor_id,
                    auth_user_id=uuid4(),
                    email="admin@example.invalid",
                    display_name="Admin",
                    status=UserStatus.ACTIVE,
                    version=1,
                ),
                Organization(
                    id=org_id,
                    name="Legacy Client",
                    slug="legacy-client",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    # An existing client has no approval policy.
    async with factory() as session:
        before = await service.policies.effective(session, org_id, "approval", utc_now(), None)
    assert before == []

    # Reconcile provisions the default.
    async with factory() as session, session.begin():
        result = await service.reconcile_defaults(
            session,
            org_id,
            actor_id=actor_id,
            correlation_id="reconcile-test",
        )
    assert result["approval_policy_provisioned"] is True

    # A second reconcile does not overwrite or duplicate.
    async with factory() as session, session.begin():
        second = await service.reconcile_defaults(
            session,
            org_id,
            actor_id=actor_id,
            correlation_id="reconcile-test",
        )
    assert second["approval_policy_provisioned"] is False


def test_readiness_aggregates_unresolved_business_facts(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_readiness_aggregation(administration_session_factory))


async def _readiness_aggregation(factory: async_sessionmaker[AsyncSession]) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    async with factory() as session, session.begin():
        session.add_all(
            [
                UserProfile(
                    id=actor_id,
                    auth_user_id=uuid4(),
                    email="operator@example.invalid",
                    display_name="Operator",
                    status=UserStatus.ACTIVE,
                    version=1,
                ),
                Organization(
                    id=org_id,
                    name="Aggregate Co",
                    slug="aggregate-co",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="readiness-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="readiness-test")
        # Create a GBP entitlement so readiness evaluates business facts.
        await service.create_entitlement(
            session,
            org_id,
            EntitlementCreate(product_key="gbp", source="test", reason="Test entitlement"),
            actor_id=actor_id,
            correlation_id="readiness-test",
        )

    async with factory() as session:
        readiness = await service.readiness(session, org_id, "gbp")
    fact_findings = [
        f for f in readiness.blocking_requirements if f.code == "BUSINESS_FACT_UNRESOLVED"
    ]
    # GBP requires business.name, business.address, business.hours (3 unresolved).
    assert len(fact_findings) == 1
    assert "Review 3 business details" in fact_findings[0].remediation
