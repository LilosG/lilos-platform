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
