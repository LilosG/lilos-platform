"""Backend tests for the effective business facts list endpoint."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.access_control.catalog import AccessCatalogSeeder
from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.administration.service import AdministrationService
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


def test_effective_facts_returns_active_current_facts(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_effective_returns_active(administration_session_factory))


async def _effective_returns_active(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    now = datetime.now(UTC)

    async with factory() as session, session.begin():
        session.add_all(
            [
                UserProfile(
                    id=actor_id,
                    auth_user_id=uuid4(),
                    email="op@example.invalid",
                    display_name="Op",
                    status=UserStatus.ACTIVE,
                    version=1,
                ),
                Organization(
                    id=org_id,
                    name="Effective Test",
                    slug="effective-test",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()

        # Active fact
        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                fact_identity=uuid4(),
                fact_key="business.name",
                value_type="string",
                value="Test Business",
                source="organization_profile",
                authority="system_derived",
                status="active",
                revision=1,
                effective_from=now - timedelta(days=30),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=29),
                change_reason="test",
            )
        )
        # Proposed (pending) fact — must NOT appear in effective list
        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                fact_identity=uuid4(),
                fact_key="business.hours",
                value_type="object",
                value={"periods": []},
                source="gbp_profile_snapshot",
                authority="system_derived",
                status="proposed",
                revision=1,
                effective_from=now,
                proposed_by=actor_id,
                change_reason="test",
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="effective-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="effective-test")

    async with factory() as session:
        effective = await service.effective_facts(session, org_id)
    assert len(effective) == 1
    assert effective[0].fact_key == "business.name"
    assert effective[0].value == "Test Business"


def test_effective_facts_excludes_expired_superseded(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_effective_excludes_expired(administration_session_factory))


async def _effective_excludes_expired(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    now = datetime.now(UTC)

    async with factory() as session, session.begin():
        session.add_all(
            [
                UserProfile(
                    id=actor_id,
                    auth_user_id=uuid4(),
                    email="op@example.invalid",
                    display_name="Op",
                    status=UserStatus.ACTIVE,
                    version=1,
                ),
                Organization(
                    id=org_id,
                    name="Expiry Test",
                    slug="expiry-test",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()

        # Expired fact
        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                fact_identity=uuid4(),
                fact_key="business.name",
                value_type="string",
                value="Expired Name",
                source="organization_profile",
                authority="system_derived",
                status="active",
                revision=1,
                effective_from=now - timedelta(days=60),
                effective_until=now - timedelta(days=1),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=59),
                change_reason="test",
            )
        )
        # Superseded fact
        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                fact_identity=uuid4(),
                fact_key="business.name",
                value_type="string",
                value="Superseded Name",
                source="organization_profile",
                authority="system_derived",
                status="superseded",
                revision=2,
                effective_from=now - timedelta(days=30),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=29),
                change_reason="test",
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="effective-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="effective-test")

    async with factory() as session:
        effective = await service.effective_facts(session, org_id)
    assert len(effective) == 0


def test_effective_facts_preserves_location_scope(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_effective_location_scope(administration_session_factory))


async def _effective_location_scope(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    loc_id = uuid4()
    now = datetime.now(UTC)

    async with factory() as session, session.begin():
        session.add_all(
            [
                UserProfile(
                    id=actor_id,
                    auth_user_id=uuid4(),
                    email="op@example.invalid",
                    display_name="Op",
                    status=UserStatus.ACTIVE,
                    version=1,
                ),
                Organization(
                    id=org_id,
                    name="Location Test",
                    slug="location-test",
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
                id=loc_id,
                organization_id=org_id,
                name="Main",
                slug="main",
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
        await session.flush()

        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                location_id=loc_id,
                fact_identity=uuid4(),
                fact_key="business.hours",
                value_type="object",
                value={"periods": []},
                source="gbp_profile_snapshot",
                authority="system_derived",
                status="active",
                revision=1,
                effective_from=now - timedelta(days=30),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=29),
                change_reason="test",
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="effective-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="effective-test")

    async with factory() as session:
        effective = await service.effective_facts(session, org_id)
    assert len(effective) == 1
    assert effective[0].fact_key == "business.hours"
    assert effective[0].location_id == loc_id


def test_effective_facts_cross_tenant_isolation(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_effective_cross_tenant(administration_session_factory))


async def _effective_cross_tenant(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_a = uuid4()
    org_b = uuid4()
    now = datetime.now(UTC)

    async with factory() as session, session.begin():
        session.add_all(
            [
                UserProfile(
                    id=actor_id,
                    auth_user_id=uuid4(),
                    email="op@example.invalid",
                    display_name="Op",
                    status=UserStatus.ACTIVE,
                    version=1,
                ),
                Organization(
                    id=org_a,
                    name="Org A",
                    slug="org-a",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
                Organization(
                    id=org_b,
                    name="Org B",
                    slug="org-b",
                    organization_type=OrganizationType.CLIENT,
                    status=OrganizationStatus.ACTIVE,
                    timezone="UTC",
                    default_currency="USD",
                    version=1,
                ),
            ]
        )
        await session.flush()

        # Org A fact
        session.add(
            BusinessFactRevision(
                organization_id=org_a,
                fact_identity=uuid4(),
                fact_key="business.name",
                value_type="string",
                value="Org A Name",
                source="organization_profile",
                authority="system_derived",
                status="active",
                revision=1,
                effective_from=now - timedelta(days=30),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=29),
                change_reason="test",
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="effective-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="effective-test")

    async with factory() as session:
        a = await service.effective_facts(session, org_a)
        b = await service.effective_facts(session, org_b)
    assert len(a) == 1
    assert a[0].value == "Org A Name"
    assert len(b) == 0


def test_effective_facts_preserves_multi_location_scope(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_effective_multi_location(administration_session_factory))


async def _effective_multi_location(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    loc_a = uuid4()
    loc_b = uuid4()
    now = datetime.now(UTC)

    async with factory() as session, session.begin():
        session.add_all(
            [
                UserProfile(
                    id=actor_id,
                    auth_user_id=uuid4(),
                    email="op@example.invalid",
                    display_name="Op",
                    status=UserStatus.ACTIVE,
                    version=1,
                ),
                Organization(
                    id=org_id,
                    name="Multi-Location Test",
                    slug="multi-location-test",
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
                id=loc_a,
                organization_id=org_id,
                name="Location A",
                slug="location-a",
                location_type=LocationType.PHYSICAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                address_line_1="100 A St",
                city="Springfield",
                region="IL",
                postal_code="62704",
                version=1,
            )
        )
        session.add(
            Location(
                id=loc_b,
                organization_id=org_id,
                name="Location B",
                slug="location-b",
                location_type=LocationType.PHYSICAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                address_line_1="200 B St",
                city="Springfield",
                region="IL",
                postal_code="62704",
                version=1,
            )
        )
        await session.flush()

        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                location_id=loc_a,
                fact_identity=uuid4(),
                fact_key="business.hours",
                value_type="object",
                value={
                    "periods": [
                        {
                            "openDay": "MONDAY",
                            "closeDay": "MONDAY",
                            "openTime": {"hours": 9},
                            "closeTime": {"hours": 17},
                        }
                    ]
                },
                source="gbp_profile_snapshot",
                authority="system_derived",
                status="active",
                revision=1,
                effective_from=now - timedelta(days=30),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=29),
                change_reason="test",
            )
        )
        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                location_id=loc_b,
                fact_identity=uuid4(),
                fact_key="business.hours",
                value_type="object",
                value={
                    "periods": [
                        {
                            "openDay": "TUESDAY",
                            "closeDay": "TUESDAY",
                            "openTime": {"hours": 10},
                            "closeTime": {"hours": 18},
                        }
                    ]
                },
                source="gbp_profile_snapshot",
                authority="system_derived",
                status="active",
                revision=1,
                effective_from=now - timedelta(days=30),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=29),
                change_reason="test",
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="effective-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="effective-test")

    async with factory() as session:
        effective = await service.effective_facts(session, org_id)
    hours_facts = [f for f in effective if f.fact_key == "business.hours"]
    assert len(hours_facts) == 2
    loc_ids = {f.location_id for f in hours_facts}
    assert loc_ids == {loc_a, loc_b}


def test_effective_facts_org_and_location_scopes_remain_distinct(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_effective_org_loc_distinct(administration_session_factory))


async def _effective_org_loc_distinct(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    loc_id = uuid4()
    now = datetime.now(UTC)

    async with factory() as session, session.begin():
        session.add_all(
            [
                UserProfile(
                    id=actor_id,
                    auth_user_id=uuid4(),
                    email="op@example.invalid",
                    display_name="Op",
                    status=UserStatus.ACTIVE,
                    version=1,
                ),
                Organization(
                    id=org_id,
                    name="Scope Test",
                    slug="scope-test",
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
                id=loc_id,
                organization_id=org_id,
                name="Main",
                slug="main",
                location_type=LocationType.PHYSICAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                address_line_1="123 Main St",
                city="Springfield",
                region="IL",
                postal_code="62704",
                version=1,
            )
        )
        await session.flush()

        # Org-scoped fact
        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                fact_identity=uuid4(),
                fact_key="business.website",
                value_type="string",
                value="https://example.com",
                source="organization_domain",
                authority="system_derived",
                status="active",
                revision=1,
                effective_from=now - timedelta(days=30),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=29),
                change_reason="test",
            )
        )
        # Location-scoped fact with same key — must remain distinct
        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                location_id=loc_id,
                fact_identity=uuid4(),
                fact_key="business.website",
                value_type="string",
                value="https://location.example.com",
                source="gbp_profile_snapshot",
                authority="operator_verified",
                status="active",
                revision=1,
                effective_from=now - timedelta(days=30),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=29),
                change_reason="test",
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="effective-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="effective-test")

    async with factory() as session:
        effective = await service.effective_facts(session, org_id)
    website_facts = [f for f in effective if f.fact_key == "business.website"]
    assert len(website_facts) == 2
    org_scoped = [f for f in website_facts if f.location_id is None]
    loc_scoped = [f for f in website_facts if f.location_id == loc_id]
    assert len(org_scoped) == 1
    assert len(loc_scoped) == 1
    assert org_scoped[0].value == "https://example.com"
    assert loc_scoped[0].value == "https://location.example.com"


def test_effective_facts_winner_within_scope_by_authority_and_revision(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    asyncio.run(_effective_winner_within_scope(administration_session_factory))


async def _effective_winner_within_scope(
    factory: async_sessionmaker[AsyncSession],
) -> None:
    service = AdministrationService()
    actor_id = uuid4()
    org_id = uuid4()
    loc_id = uuid4()
    now = datetime.now(UTC)

    async with factory() as session, session.begin():
        session.add_all(
            [
                UserProfile(
                    id=actor_id,
                    auth_user_id=uuid4(),
                    email="op@example.invalid",
                    display_name="Op",
                    status=UserStatus.ACTIVE,
                    version=1,
                ),
                Organization(
                    id=org_id,
                    name="Winner Test",
                    slug="winner-test",
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
                id=loc_id,
                organization_id=org_id,
                name="Main",
                slug="main",
                location_type=LocationType.PHYSICAL,
                status=LocationStatus.ACTIVE,
                timezone="UTC",
                country_code="US",
                address_line_1="123 Main St",
                city="Springfield",
                region="IL",
                postal_code="62704",
                version=1,
            )
        )
        await session.flush()

        identity = uuid4()
        # Lower-authority revision — must lose to operator_verified
        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                location_id=loc_id,
                fact_identity=identity,
                fact_key="business.hours",
                value_type="object",
                value={"periods": []},
                source="gbp_profile_snapshot",
                authority="system_derived",
                status="active",
                revision=1,
                effective_from=now - timedelta(days=30),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=29),
                change_reason="test",
            )
        )
        # Higher-authority revision — must win for same (key, location_id) scope
        session.add(
            BusinessFactRevision(
                organization_id=org_id,
                location_id=loc_id,
                fact_identity=identity,
                fact_key="business.hours",
                value_type="object",
                value={
                    "periods": [
                        {
                            "openDay": "MONDAY",
                            "closeDay": "MONDAY",
                            "openTime": {"hours": 9},
                            "closeTime": {"hours": 17},
                        }
                    ]
                },
                source="gbp_profile_snapshot",
                authority="operator_verified",
                status="active",
                revision=2,
                effective_from=now - timedelta(days=10),
                proposed_by=actor_id,
                approved_by=actor_id,
                approved_at=now - timedelta(days=9),
                change_reason="operator confirmed",
            )
        )
        await session.flush()
        await AccessCatalogSeeder().seed(session, correlation_id="effective-test")
        await AdministrationCatalogSeeder().seed(session, correlation_id="effective-test")

    async with factory() as session:
        effective = await service.effective_facts(session, org_id)
    hours = [f for f in effective if f.fact_key == "business.hours"]
    assert len(hours) == 1
    assert hours[0].authority.value == "operator_verified"
    assert hours[0].revision == 2
    assert hours[0].location_id == loc_id
