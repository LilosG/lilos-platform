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
from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.contracts import EntitlementCreate
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


# ── Hotfix B: business.hours derivation from GBP regularHours ─────────────


async def _seed_gbp_test_context(
    session: AsyncSession,
    org_id: UUID,
    actor_id: UUID,
    location_id: UUID,
    *,
    brand_name: str = "Test Business",
    address_line_1: str = "123 Main St",
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
