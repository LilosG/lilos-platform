"""Business-fact reconciliation and default-policy recovery tests.

Covers the operator-facing recovery paths for existing clients:

- ``reconcile_business_facts`` derives ``system_derived`` candidates from
  authoritative client data (org profile, primary location, primary domain,
  GBP profile snapshot, SEO crawl pages) without auto-approving, and is
  idempotent.
- ``reconcile_defaults`` provisions the intended safe default approval policy
  for an existing organization that predates the entitlement-time provisioning,
  without overwriting a custom policy.
- The readiness engine aggregates unresolved business facts into a single
  actionable "Review N business details" finding rather than one internal
  record per fact key.
- Source-driven ``brand.approved_claims`` candidates are derived from GBP
  categories/serviceItems, organization profile services/claims, and SEO
  crawl page H1 signals, removing the circular requirement that an operator
  type the service list into the profile before reconciliation can propose it.
"""

import asyncio
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.contracts import (
    BusinessFactDecision,
    EntitlementCreate,
)
from apps.api.app.administration.service import AdministrationService
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.database.base import utc_now
from apps.api.app.domains.models import OrganizationDomain
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation, GBPProfileSnapshot
from apps.api.app.products.seo.models import SEOPage, SEOWebsite
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
    assert "Confirm 3 business details" in fact_findings[0].remediation
    # The count is the human sentence; the resolution is what makes the blocker
    # actionable. An operator shown this must be told where to go and be able to
    # go there, so both halves are pinned.
    resolution = fact_findings[0].resolution
    assert resolution is not None
    assert resolution.route == "/onboarding"
    assert resolution.control == "business-facts"
    assert resolution.permission == "business_facts.approve"


# ── Hotfix B: business.hours derivation from GBP regularHours ─────────────


async def _seed_gbp_test_context(
    session: AsyncSession,
    org_id: UUID,
    actor_id: UUID,
    location_id: UUID,
    *,
    brand_name: str = "Test Business",
    address_line_1: str = "123 Main St",
    primary_services: list[str] | None = None,
) -> tuple[UUID, UUID]:
    """Create the org/actor/location/plumbing fixture for a GBP reconciliation test."""
    loc = Location(
        id=location_id,
        organization_id=org_id,
        name="Main Location",
        slug="main-location",
        location_type=LocationType.PHYSICAL,
        status=LocationStatus.ACTIVE,
        timezone="UTC",
        country_code="US",
        address_line_1=address_line_1,
        city="Springfield",
        region="IL",
        postal_code="62704",
        is_primary=True,
        version=1,
    )
    profile = OrganizationProfile(
        organization_id=org_id,
        brand_name=brand_name,
        primary_services=primary_services or [],
        version=1,
    )
    session.add_all([loc, profile])
    await session.flush()

    provider = Provider(
        key="google_business_profile",
        name="Google Business Profile",
        status="active",
        capabilities=["gbp.read"],
    )
    session.add(provider)
    await session.flush()
    connection = IntegrationConnection(
        organization_id=org_id,
        provider_id=provider.id,
        external_account_reference=f"gbp-{org_id}",
        status="connected",
    )
    session.add(connection)
    await session.flush()
    account = GBPAccount(
        organization_id=org_id,
        connection_id=connection.id,
        external_account_id=f"accounts/{org_id}",
        display_name="GBP Account",
        status="selected",
    )
    session.add(account)
    await session.flush()
    return connection.id, account.id


def test_reconcile_derives_business_hours_from_gbp_regular_hours(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_reconcile_hours_from_gbp(administration_session_factory))


async def _reconcile_hours_from_gbp(factory: async_sessionmaker[AsyncSession]) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

    regular_hours = {
        "periods": [
            {"openDay": "MONDAY", "closeDay": "MONDAY", "openTime": "09:00", "closeTime": "17:00"},
            {
                "openDay": "TUESDAY",
                "closeDay": "TUESDAY",
                "openTime": "09:00",
                "closeTime": "17:00",
            },
        ]
    }

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
        connection_id, account_id = await _seed_gbp_test_context(
            session, org_id, actor_id, location_id, brand_name="Wheyland Electric"
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=org_id,
                location_id=location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/123",
                business_name="Wheyland Electric",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={"regularHours": regular_hours},
                content_hash="abc123",
                completeness="full",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
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
    assert "business.hours" in proposed_keys

    hours_candidate = next(item for item in proposed if item["fact_key"] == "business.hours")
    assert hours_candidate["location_id"] == str(location_id)

    async with factory() as session:
        revisions = await service.facts.list_for_key(
            session, org_id, "business.hours", location_id=location_id
        )
    assert revisions
    latest = revisions[0]
    assert latest.status == "proposed"
    assert latest.value == regular_hours
    assert latest.location_id == location_id
    assert latest.authority == "system_derived"
    assert latest.source == "gbp_profile_snapshot"

    # business.hours is NOT auto-approved
    async with factory() as session:
        org_level = await service.resolve_fact(session, org_id, "business.hours")
    assert org_level.state == "missing"


def test_reconcile_uses_latest_gbp_profile_snapshot(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_reconcile_uses_latest_snapshot(administration_session_factory))


async def _reconcile_uses_latest_snapshot(factory: async_sessionmaker[AsyncSession]) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

    older_hours = {
        "periods": [
            {"openDay": "MONDAY", "closeDay": "MONDAY", "openTime": "08:00", "closeTime": "16:00"}
        ]
    }
    newer_hours = {
        "periods": [
            {"openDay": "MONDAY", "closeDay": "MONDAY", "openTime": "09:00", "closeTime": "17:00"},
            {
                "openDay": "TUESDAY",
                "closeDay": "TUESDAY",
                "openTime": "09:00",
                "closeTime": "17:00",
            },
        ]
    }

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
                    name="Snapshot Test Org",
                    slug="snapshot-test-org",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        connection_id, account_id = await _seed_gbp_test_context(
            session, org_id, actor_id, location_id, brand_name="Snapshot Test"
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=org_id,
                location_id=location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/456",
                business_name="Snapshot Test",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add_all(
            [
                GBPProfileSnapshot(
                    organization_id=org_id,
                    gbp_location_id=gbp_location_id,
                    normalized_profile={"regularHours": older_hours},
                    content_hash="old456",
                    completeness="full",
                    observed_at=datetime(2026, 8, 1, 12, 0, 0, tzinfo=UTC),
                ),
                GBPProfileSnapshot(
                    organization_id=org_id,
                    gbp_location_id=gbp_location_id,
                    normalized_profile={"regularHours": newer_hours},
                    content_hash="new456",
                    completeness="full",
                    observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
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
    assert "business.hours" in {item["fact_key"] for item in proposed}

    async with factory() as session:
        revisions = await service.facts.list_for_key(
            session, org_id, "business.hours", location_id=location_id
        )
    assert revisions
    assert revisions[0].value == newer_hours


def test_missing_regular_hours_leaves_requirement_unresolved(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_missing_hours_unresolved(administration_session_factory))


async def _missing_hours_unresolved(factory: async_sessionmaker[AsyncSession]) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

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
                    name="Missing Hours Org",
                    slug="missing-hours-org",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        connection_id, account_id = await _seed_gbp_test_context(
            session, org_id, actor_id, location_id, brand_name="Missing Hours Co"
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=org_id,
                location_id=location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/789",
                business_name="Missing Hours Co",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={"name": "Missing Hours Co"},
                content_hash="nohours",
                completeness="partial",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
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
    assert "business.hours" not in proposed_keys
    unresolved = cast(list[str], result.get("unresolved", []))
    assert "business.hours" in unresolved


def test_no_cross_tenant_cross_location_leakage_for_business_hours(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_no_cross_leakage_hours(administration_session_factory))


async def _no_cross_leakage_hours(factory: async_sessionmaker[AsyncSession]) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    other_org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

    hours_data = {
        "periods": [
            {"openDay": "MONDAY", "closeDay": "MONDAY", "openTime": "09:00", "closeTime": "17:00"}
        ]
    }

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
                    name="Target Org",
                    slug="target-org",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
                Organization(
                    id=other_org_id,
                    name="Other Org",
                    slug="other-org",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        # Target org gets a location/profile but NO GBP plumbing.
        target_location = Location(
            id=location_id,
            organization_id=org_id,
            name="Target Location",
            slug="target-location",
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
        )
        target_profile = OrganizationProfile(
            organization_id=org_id,
            brand_name="Target Org",
            version=1,
        )
        session.add_all([target_location, target_profile])
        await session.flush()

        # GBP plumbing belongs to the *other* org, NOT the target.
        connection_id, account_id = await _seed_gbp_test_context(
            session, other_org_id, actor_id, uuid4(), brand_name="Other Org GBP"
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=other_org_id,
                location_id=None,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/cross-tenant",
                business_name="Other Org GBP",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=other_org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={"regularHours": hours_data},
                content_hash="cross123",
                completeness="full",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
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
    assert "business.hours" not in proposed_keys
    unresolved = cast(list[str], result.get("unresolved", []))
    assert "business.hours" in unresolved


# ── Source-driven brand.approved_claims reconciliation tests ────────────────


def _seo_page(
    website_id: UUID,
    org_id: UUID,
    normalized_url: str,
    *,
    h1: str | None = None,
    title: str | None = None,
    http_status: int = 200,
) -> SEOPage:
    """Create a minimal SEOPage row for reconciliation test fixtures."""
    return SEOPage(
        organization_id=org_id,
        website_id=website_id,
        normalized_url=normalized_url,
        observed_url=normalized_url,
        normalization_reasons=[],
        http_status=http_status,
        title=title,
        h1=h1,
        robots_directives=[],
        internal_links=[],
        external_links=[],
        structured_data_present=False,
        indexability="indexable",
        technical_issues=[],
        quality_status="clean",
    )


def test_reconcile_derives_service_claims_from_gbp_snapshot(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_derive_claims_from_gbp(administration_session_factory))


async def _derive_claims_from_gbp(factory: async_sessionmaker[AsyncSession]) -> None:
    """GBP categories and serviceItems produce brand.approved_claims candidates."""
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

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
        connection_id, account_id = await _seed_gbp_test_context(
            session, org_id, actor_id, location_id, brand_name="Wheyland Electric"
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=org_id,
                location_id=location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/123",
                business_name="Wheyland Electric",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={
                    "categories": {
                        "primaryCategory": {"displayName": "Electrician"},
                        "additionalCategories": [
                            {"displayName": "Electrical Contractor"},
                        ],
                    },
                    "serviceItems": [
                        {"displayName": "EV charger installation"},
                        {"displayName": "Electrical panel upgrades"},
                    ],
                },
                content_hash="gbp-svc-001",
                completeness="full",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    async with factory() as session, session.begin():
        result = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed = cast(list[dict[str, object]], result["proposed"])
    claims_candidate = next(
        (item for item in proposed if item["fact_key"] == "brand.approved_claims"), None
    )
    assert claims_candidate is not None, "brand.approved_claims should be proposed from GBP data"

    async with factory() as session:
        revisions = await service.facts.list_for_key(session, org_id, "brand.approved_claims")
    assert revisions
    latest = revisions[0]
    assert latest.status == "proposed"
    assert latest.authority == "system_derived"
    assert "gbp_profile_snapshot" in latest.source
    claims = cast(list[str], latest.value)
    assert "Electrician" in claims
    assert "Electrical Contractor" in claims
    assert "EV charger installation" in claims
    assert "Electrical panel upgrades" in claims

    # Candidates are proposed, NOT auto-approved.
    async with factory() as session:
        resolution = await service.resolve_fact(session, org_id, "brand.approved_claims")
    assert resolution.state == "missing"


def test_reconcile_derives_service_claims_from_seo_crawl(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_derive_claims_from_seo(administration_session_factory))


async def _derive_claims_from_seo(factory: async_sessionmaker[AsyncSession]) -> None:
    """SEO crawl pages with service-context URLs produce brand.approved_claims candidates."""
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    website_id = uuid4()

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
        session.add(
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
            )
        )
        session.add(
            OrganizationProfile(
                organization_id=org_id,
                brand_name="Wheyland Electric",
                version=1,
            )
        )
        session.add(
            OrganizationDomain(
                organization_id=org_id,
                domain="wheylandelectric.example",
                is_primary=True,
                status="active",
                version=1,
            )
        )
        await session.flush()
        session.add(
            SEOWebsite(
                id=website_id,
                organization_id=org_id,
                location_id=location_id,
                key="wheyland-main",
                name="Wheyland Electric Website",
                canonical_origin="https://www.wheylandelectric.example",
                status="active",
                ownership_status="owned",
                version=1,
            )
        )
        await session.flush()
        session.add_all(
            [
                _seo_page(
                    website_id,
                    org_id,
                    "https://www.wheylandelectric.example/services/ev-charger-installation",
                    h1="EV Charger Installation",
                ),
                _seo_page(
                    website_id,
                    org_id,
                    "https://www.wheylandelectric.example/panel-upgrades",
                    h1="Electrical Panel Upgrades",
                ),
                # Furniture page — should be excluded.
                _seo_page(
                    website_id,
                    org_id,
                    "https://www.wheylandelectric.example/",
                    h1="Welcome to Wheyland Electric",
                ),
                # Blog page — should be excluded.
                _seo_page(
                    website_id,
                    org_id,
                    "https://www.wheylandelectric.example/blog/best-tools",
                    h1="Best Tools of 2026",
                ),
                # Contact page — should be excluded.
                _seo_page(
                    website_id,
                    org_id,
                    "https://www.wheylandelectric.example/contact",
                    h1="Contact Us",
                ),
            ]
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    async with factory() as session, session.begin():
        result = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed = cast(list[dict[str, object]], result["proposed"])
    claims_candidate = next(
        (item for item in proposed if item["fact_key"] == "brand.approved_claims"), None
    )
    assert claims_candidate is not None, "brand.approved_claims should be proposed from SEO data"

    async with factory() as session:
        revisions = await service.facts.list_for_key(session, org_id, "brand.approved_claims")
    assert revisions
    latest = revisions[0]
    assert latest.status == "proposed"
    assert "seo_crawl" in latest.source
    claims = cast(list[str], latest.value)
    assert "EV Charger Installation" in claims
    assert "Electrical Panel Upgrades" in claims
    # Furniture/blog/contact pages must not produce claims.
    assert "Welcome to Wheyland Electric" not in claims
    assert "Best Tools of 2026" not in claims
    assert "Contact Us" not in claims


def test_reconcile_normalizes_duplicate_service_names_across_sources(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_normalize_duplicates(administration_session_factory))


async def _normalize_duplicates(factory: async_sessionmaker[AsyncSession]) -> None:
    """Duplicate service names from different sources are normalized into one list."""
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

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
                    name="Test Co",
                    slug="test-co",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        connection_id, account_id = await _seed_gbp_test_context(
            session,
            org_id,
            actor_id,
            location_id,
            brand_name="Test Co",
            # Profile has a case-variant duplicate of the GBP service.
            primary_services=["EV Charger Installation", "Ceiling Fan Installation"],
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=org_id,
                location_id=location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/dup",
                business_name="Test Co",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={
                    "serviceItems": [
                        {"displayName": "EV charger installation"},
                        {"displayName": "electrical panel upgrades"},
                    ],
                },
                content_hash="dup-001",
                completeness="full",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    async with factory() as session, session.begin():
        result = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed = cast(list[dict[str, object]], result["proposed"])
    claims_candidate = next(
        (item for item in proposed if item["fact_key"] == "brand.approved_claims"), None
    )
    assert claims_candidate is not None

    async with factory() as session:
        revisions = await service.facts.list_for_key(session, org_id, "brand.approved_claims")
    claims = cast(list[str], revisions[0].value)
    # "EV charger installation" and "EV Charger Installation" normalize to one entry.
    normalized_keys = {c.lower().replace(" ", "") for c in claims}
    assert len(normalized_keys) == len(claims), f"duplicates found: {claims}"
    assert "EV Charger Installation" in claims or "EV charger installation" in claims
    assert "Ceiling Fan Installation" in claims
    assert "electrical panel upgrades" in claims
    # Both source families contributed.
    assert "organization_profile" in revisions[0].source
    assert "gbp_profile_snapshot" in revisions[0].source


def test_reconcile_filters_risky_claims_from_provider_sources(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_filter_risky_claims(administration_session_factory))


async def _filter_risky_claims(factory: async_sessionmaker[AsyncSession]) -> None:
    """Risky claims from GBP/SEO sources are filtered; explicit profile claims are kept."""
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

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
                    name="Risky Co",
                    slug="risky-co",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        connection_id, account_id = await _seed_gbp_test_context(
            session, org_id, actor_id, location_id, brand_name="Risky Co"
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=org_id,
                location_id=location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/risky",
                business_name="Risky Co",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={
                    "serviceItems": [
                        {"displayName": "EV charger installation"},
                        {"displayName": "Best electrician in town"},
                        {"displayName": "24/7 emergency service"},
                        {"displayName": "Licensed and bonded"},
                        {"displayName": "Free estimates"},
                        {"displayName": "Certified technicians"},
                        {"displayName": "5 years in business"},
                        {"displayName": "50% off first service"},
                    ],
                },
                content_hash="risky-001",
                completeness="full",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    async with factory() as session, session.begin():
        result = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed = cast(list[dict[str, object]], result["proposed"])
    claims_candidate = next(
        (item for item in proposed if item["fact_key"] == "brand.approved_claims"), None
    )
    assert claims_candidate is not None

    async with factory() as session:
        revisions = await service.facts.list_for_key(session, org_id, "brand.approved_claims")
    claims = cast(list[str], revisions[0].value)
    # Safe service capability kept.
    assert "EV charger installation" in claims
    # Risky claims filtered out.
    risky = [
        "Best electrician in town",
        "24/7 emergency service",
        "Licensed and bonded",
        "Free estimates",
        "Certified technicians",
        "5 years in business",
        "50% off first service",
    ]
    for r in risky:
        assert r not in claims, f"risky claim '{r}' should have been filtered"


def test_reconcile_no_sources_leaves_approved_claims_unresolved(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_no_sources_unresolved(administration_session_factory))


async def _no_sources_unresolved(factory: async_sessionmaker[AsyncSession]) -> None:
    """When no GBP/SEO/profile service data exists, brand.approved_claims is unresolved."""
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
                    name="Empty Co",
                    slug="empty-co",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        session.add(
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
            )
        )
        session.add(
            OrganizationProfile(
                organization_id=org_id,
                brand_name="Empty Co",
                version=1,
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    async with factory() as session, session.begin():
        result = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed = cast(list[dict[str, object]], result["proposed"])
    proposed_keys = {item["fact_key"] for item in proposed}
    assert "brand.approved_claims" not in proposed_keys
    unresolved = cast(list[str], result.get("unresolved", []))
    assert "brand.approved_claims" in unresolved


def test_reconcile_does_not_auto_approve_service_claims(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_confirmation_required(administration_session_factory))


async def _confirmation_required(factory: async_sessionmaker[AsyncSession]) -> None:
    """Service claims are proposed, not active; confirmation is required."""
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

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
                    name="Confirm Co",
                    slug="confirm-co",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        connection_id, account_id = await _seed_gbp_test_context(
            session, org_id, actor_id, location_id, brand_name="Confirm Co"
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=org_id,
                location_id=location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/confirm",
                business_name="Confirm Co",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={
                    "serviceItems": [{"displayName": "EV charger installation"}],
                },
                content_hash="confirm-001",
                completeness="full",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    # Reconcile → proposed.
    async with factory() as session, session.begin():
        result = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed = cast(list[dict[str, object]], result["proposed"])
    claims_candidate = next(
        (item for item in proposed if item["fact_key"] == "brand.approved_claims"), None
    )
    assert claims_candidate is not None
    revision_id = UUID(cast(str, claims_candidate["revision_id"]))

    # Before approval: resolve → missing.
    async with factory() as session:
        resolution = await service.resolve_fact(session, org_id, "brand.approved_claims")
    assert resolution.state == "missing"

    # Approve → active.
    async with factory() as session, session.begin():
        await service.decide_fact(
            session,
            org_id,
            revision_id,
            BusinessFactDecision(decision="approve"),
            actor_id=actor_id,
            correlation_id="reconcile-test",
        )

    # After approval: resolve → resolved.
    async with factory() as session:
        resolution = await service.resolve_fact(session, org_id, "brand.approved_claims")
    assert resolution.state == "resolved"
    assert resolution.value is not None
    assert "EV charger installation" in cast(list[str], resolution.value)


def test_reconcile_conflicting_sources_are_surfaced_not_picked(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_conflicts_surfaced(administration_session_factory))


async def _conflicts_surfaced(factory: async_sessionmaker[AsyncSession]) -> None:
    """When GBP and profile sources differ, both are surfaced; neither is silently dropped."""
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

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
                    name="Conflict Co",
                    slug="conflict-co",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        connection_id, account_id = await _seed_gbp_test_context(
            session,
            org_id,
            actor_id,
            location_id,
            brand_name="Conflict Co",
            primary_services=["Residential Electrical Services"],
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=org_id,
                location_id=location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/conflict",
                business_name="Conflict Co",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={
                    "serviceItems": [{"displayName": "Electrical Services"}],
                },
                content_hash="conflict-001",
                completeness="full",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    async with factory() as session, session.begin():
        result = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed = cast(list[dict[str, object]], result["proposed"])
    claims_candidate = next(
        (item for item in proposed if item["fact_key"] == "brand.approved_claims"), None
    )
    assert claims_candidate is not None

    async with factory() as session:
        revisions = await service.facts.list_for_key(session, org_id, "brand.approved_claims")
    claims = cast(list[str], revisions[0].value)
    # Both distinct names are present — neither was silently dropped.
    assert "Electrical Services" in claims
    assert "Residential Electrical Services" in claims
    # Both source families contributed.
    assert "gbp_profile_snapshot" in revisions[0].source
    assert "organization_profile" in revisions[0].source


def test_reconcile_cross_tenant_sources_do_not_leak(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_cross_tenant_no_leak(administration_session_factory))


async def _cross_tenant_no_leak(factory: async_sessionmaker[AsyncSession]) -> None:
    """GBP and SEO data from another organization must not produce candidates."""
    service = AdministrationService()
    actor_id = uuid4()
    target_org_id = uuid4()
    other_org_id = uuid4()
    target_location_id = uuid4()
    other_location_id = uuid4()
    gbp_location_id = uuid4()
    website_id = uuid4()

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
                    id=target_org_id,
                    name="Target Org",
                    slug="target-org",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
                Organization(
                    id=other_org_id,
                    name="Other Org",
                    slug="other-org",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        # Target org: location + profile only, no GBP/SEO.
        session.add(
            Location(
                id=target_location_id,
                organization_id=target_org_id,
                name="Target Location",
                slug="target-location",
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
            )
        )
        session.add(
            OrganizationProfile(
                organization_id=target_org_id,
                brand_name="Target Org",
                version=1,
            )
        )
        await session.flush()

        # Other org: GBP plumbing + SEO website with service pages.
        connection_id, account_id = await _seed_gbp_test_context(
            session, other_org_id, actor_id, other_location_id, brand_name="Other Org"
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=other_org_id,
                location_id=other_location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/other",
                business_name="Other Org",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=other_org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={
                    "serviceItems": [{"displayName": "Other Org Service"}],
                },
                content_hash="other-001",
                completeness="full",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
        )
        session.add(
            SEOWebsite(
                id=website_id,
                organization_id=other_org_id,
                location_id=other_location_id,
                key="other-website",
                name="Other Website",
                canonical_origin="https://other.example",
                status="active",
                ownership_status="owned",
                version=1,
            )
        )
        await session.flush()
        session.add(
            _seo_page(
                website_id,
                other_org_id,
                "https://other.example/services/other-service",
                h1="Other Service",
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    # Reconcile target org — must not see other org's data.
    async with factory() as session, session.begin():
        result = await service.reconcile_business_facts(
            session, target_org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed = cast(list[dict[str, object]], result["proposed"])
    proposed_keys = {item["fact_key"] for item in proposed}
    assert "brand.approved_claims" not in proposed_keys
    unresolved = cast(list[str], result.get("unresolved", []))
    assert "brand.approved_claims" in unresolved


def test_reconcile_idempotent_with_source_driven_claims(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_idempotent_source_claims(administration_session_factory))


async def _idempotent_source_claims(factory: async_sessionmaker[AsyncSession]) -> None:
    """Repeated reconciliation with unchanged sources proposes nothing new."""
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

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
                    name="Idempotent Co",
                    slug="idempotent-co",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        connection_id, account_id = await _seed_gbp_test_context(
            session, org_id, actor_id, location_id, brand_name="Idempotent Co"
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=org_id,
                location_id=location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/idem",
                business_name="Idempotent Co",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={
                    "serviceItems": [{"displayName": "EV charger installation"}],
                },
                content_hash="idem-001",
                completeness="full",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    # First reconciliation.
    async with factory() as session, session.begin():
        first = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    first_proposed = cast(list[dict[str, object]], first["proposed"])
    assert any(item["fact_key"] == "brand.approved_claims" for item in first_proposed)

    # Second reconciliation — idempotent.
    async with factory() as session, session.begin():
        second = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    assert second["proposed"] == []

    # Verify only one revision exists.
    async with factory() as session:
        revisions = await service.facts.list_for_key(session, org_id, "brand.approved_claims")
    assert len(revisions) == 1
    assert revisions[0].status == "proposed"


def test_reconcile_source_change_creates_next_revision(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_source_change_next_revision(administration_session_factory))


async def _source_change_next_revision(factory: async_sessionmaker[AsyncSession]) -> None:
    """Source changes create a next revision via the immutable revision architecture."""
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()

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
                    name="Revision Co",
                    slug="revision-co",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()
        connection_id, account_id = await _seed_gbp_test_context(
            session, org_id, actor_id, location_id, brand_name="Revision Co"
        )
        session.add(
            GBPLocation(
                id=gbp_location_id,
                organization_id=org_id,
                location_id=location_id,
                connection_id=connection_id,
                account_id=account_id,
                external_location_id="locations/rev",
                business_name="Revision Co",
                mapping_status="confirmed",
                write_enabled=False,
            )
        )
        await session.flush()
        session.add(
            GBPProfileSnapshot(
                organization_id=org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={
                    "serviceItems": [{"displayName": "Service A"}],
                },
                content_hash="rev-001",
                completeness="full",
                observed_at=datetime(2026, 8, 10, 12, 0, 0, tzinfo=UTC),
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    # First reconciliation → revision 1.
    async with factory() as session, session.begin():
        await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )

    async with factory() as session:
        rev1_list = await service.facts.list_for_key(session, org_id, "brand.approved_claims")
    assert len(rev1_list) == 1
    assert rev1_list[0].revision == 1
    assert rev1_list[0].value == ["Service A"]

    # Approve revision 1.
    async with factory() as session, session.begin():
        await service.decide_fact(
            session,
            org_id,
            rev1_list[0].id,
            BusinessFactDecision(decision="approve"),
            actor_id=actor_id,
            correlation_id="reconcile-test",
        )

    # Add a new snapshot with an additional service.
    async with factory() as session, session.begin():
        session.add(
            GBPProfileSnapshot(
                organization_id=org_id,
                gbp_location_id=gbp_location_id,
                normalized_profile={
                    "serviceItems": [
                        {"displayName": "Service A"},
                        {"displayName": "Service B"},
                    ],
                },
                content_hash="rev-002",
                completeness="full",
                observed_at=datetime(2026, 8, 11, 12, 0, 0, tzinfo=UTC),
            )
        )
        await session.flush()

    # Second reconciliation → revision 2 (source changed).
    async with factory() as session, session.begin():
        result = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed = cast(list[dict[str, object]], result["proposed"])
    assert any(item["fact_key"] == "brand.approved_claims" for item in proposed)

    async with factory() as session:
        all_revs = await service.facts.list_for_key(session, org_id, "brand.approved_claims")
    assert len(all_revs) == 2
    rev2 = next(r for r in all_revs if r.revision == 2)
    assert rev2.status == "proposed"
    assert rev2.value == ["Service A", "Service B"]
    assert rev2.supersedes_id == rev1_list[0].id


def test_reconcile_seo_page_selection_is_deterministic(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_seo_deterministic_selection(administration_session_factory))


async def _seo_deterministic_selection(factory: async_sessionmaker[AsyncSession]) -> None:
    """SEO page LIMIT 100 with ORDER BY produces identical candidates across runs.

    When more than 100 service pages exist, the deterministic ordering
    (normalized_url ASC, id ASC) ensures the same subset is selected every
    time. Pages beyond the limit must not contribute claims.
    """
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    location_id = uuid4()
    website_id = uuid4()

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
                    name="Deterministic Co",
                    slug="deterministic-co",
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
                    brand_name="Deterministic Co",
                    version=1,
                ),
                OrganizationDomain(
                    organization_id=org_id,
                    domain="deterministic.example",
                    is_primary=True,
                    status="active",
                    version=1,
                ),
            ]
        )
        await session.flush()
        session.add(
            SEOWebsite(
                id=website_id,
                organization_id=org_id,
                location_id=location_id,
                key="deterministic-site",
                name="Deterministic Site",
                canonical_origin="https://deterministic.example",
                status="active",
                ownership_status="verified",
                version=1,
            )
        )
        await session.flush()
        # Create 105 service pages.  With LIMIT 100 + ORDER BY normalized_url,
        # pages svc-000 … svc-099 are selected; svc-100 … svc-104 are excluded.
        for i in range(105):
            session.add(
                _seo_page(
                    website_id,
                    org_id,
                    normalized_url=f"https://deterministic.example/services/svc-{i:03d}",
                    h1=f"Service {i:03d}",
                )
            )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="reconcile-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="reconcile-test")

    # First reconciliation.
    async with factory() as session, session.begin():
        result1 = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed1 = cast(list[dict[str, object]], result1["proposed"])
    claims_candidate1 = next(
        (item for item in proposed1 if item["fact_key"] == "brand.approved_claims"), None
    )
    assert claims_candidate1 is not None

    async with factory() as session:
        revisions1 = await service.facts.list_for_key(session, org_id, "brand.approved_claims")
    claims1 = cast(list[str], revisions1[0].value)

    # Second reconciliation — identical source state must propose no new
    # claim candidate (idempotency) and the persisted value must not change.
    async with factory() as session, session.begin():
        result2 = await service.reconcile_business_facts(
            session, org_id, actor_id=actor_id, correlation_id="reconcile-test"
        )
    proposed2 = cast(list[dict[str, object]], result2["proposed"])
    assert not any(item["fact_key"] == "brand.approved_claims" for item in proposed2)

    async with factory() as session:
        revisions2 = await service.facts.list_for_key(session, org_id, "brand.approved_claims")
    assert len(revisions2) == 1
    claims2 = cast(list[str], revisions2[0].value)

    # Identical across runs.
    assert claims1 == claims2

    # Only the first 100 pages (svc-000 … svc-099) are included.
    assert len(claims1) == 100
    for i in range(100):
        assert f"Service {i:03d}" in claims1
    # Pages beyond the limit must not appear.
    for i in range(100, 105):
        assert f"Service {i:03d}" not in claims1

    # Claims are in deterministic order (normalized_url ASC).
    expected_order = [f"Service {i:03d}" for i in range(100)]
    assert claims1 == expected_order
