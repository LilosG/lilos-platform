"""Dedicated tests for GBPDiscoveryService.

Exercises the complete discovery lifecycle (account discovery, location
discovery, profile sync, discover_and_sync) against a real PostgreSQL
database with a fake GBPAdapter (no real Google HTTP calls) and a fake
connection service (no real token refresh HTTP calls).  Verifies idempotent
persistence, audit event generation, tenant isolation, stale-resource
marking, and truthful error/empty-state handling.
"""

import asyncio
from collections.abc import Iterator
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.integrations.connection_service import GBPConnectionService
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.discovery_service import GBPDiscoveryService
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation, GBPProfileSnapshot


class FakeGBPAdapter:
    """Deterministic fake adapter implementing the GBPAdapter protocol."""

    def __init__(
        self,
        *,
        accounts: list[dict[str, Any]] | None = None,
        locations_by_account: dict[str, list[dict[str, Any]]] | None = None,
        location_details: dict[str, dict[str, Any]] | None = None,
        account_error: Exception | None = None,
        location_error: Exception | None = None,
        location_detail_error: Exception | None = None,
    ) -> None:
        self._accounts = accounts or []
        self._locations_by_account = locations_by_account or {}
        self._location_details = location_details or {}
        self._account_error = account_error
        self._location_error = location_error
        self._location_detail_error = location_detail_error

    async def list_accounts(self, access_token: str) -> list[dict[str, Any]]:
        del access_token
        if self._account_error:
            raise self._account_error
        return list(self._accounts)

    async def list_locations(self, access_token: str, account_name: str) -> list[dict[str, Any]]:
        del access_token
        if self._location_error:
            raise self._location_error
        return list(self._locations_by_account.get(account_name, []))

    async def get_location(self, access_token: str, location_name: str) -> dict[str, Any]:
        del access_token
        if location_name in self._location_details:
            return dict(self._location_details[location_name])
        if self._location_detail_error:
            raise self._location_detail_error
        return {"name": location_name}

    async def patch_location(
        self,
        access_token: str,
        location_name: str,
        fields: dict[str, Any],
        update_mask: list[str],
        idempotency_key: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def update_review_reply(
        self, access_token: str, review_name: str, comment: str
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_review(self, access_token: str, review_name: str) -> dict[str, Any]:
        raise NotImplementedError

    async def create_local_post(
        self, access_token: str, location_name: str, post_body: dict[str, Any]
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def get_local_post(self, access_token: str, post_name: str) -> dict[str, Any]:
        raise NotImplementedError

    async def list_local_posts(self, access_token: str, location_name: str) -> list[dict[str, Any]]:
        raise NotImplementedError


class FakeConnectionService(GBPConnectionService):
    """Bypasses token refresh; delegates get_connection to the real service."""

    async def get_connection(self, session: AsyncSession, organization_id: UUID) -> Any:
        return await super().get_connection(session, organization_id)

    async def ensure_fresh_token(
        self, session: AsyncSession, settings: Settings, connection: Any
    ) -> str:
        return "fake-access-token"


@pytest.fixture
def discovery_session_factory(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[async_sessionmaker[AsyncSession]]:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    ROOT = Path(__file__).resolve().parents[3]
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    engine = create_async_engine(postgresql_test_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        asyncio.run(engine.dispose())


def _settings(postgresql_test_url: str) -> Settings:
    return Settings.model_validate(
        {"environment": EnvironmentName.TEST, "database_url": postgresql_test_url}
    )


async def _setup_org_with_connection(
    factory: async_sessionmaker[AsyncSession],
    *,
    slug: str = "discovery-test-org",
) -> tuple[UUID, UUID]:
    """Create an org, provider, and connected integration. Return (org_id, connection_id)."""
    async with factory.begin() as session:
        org = Organization(
            name="Discovery Test Org",
            slug=slug,
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(org)
        await session.flush()

        provider = await session.scalar(
            select(Provider).where(Provider.key == "google_business_profile")
        )
        if provider is None:
            provider = Provider(
                key="google_business_profile",
                name="Google Business Profile",
                status="active",
                capabilities=["profile.read", "profile.write"],
            )
            session.add(provider)
            await session.flush()

        connection = IntegrationConnection(
            organization_id=org.id,
            provider_id=provider.id,
            external_account_reference="accounts/test-account",
            status="connected",
        )
        session.add(connection)
        await session.flush()
        return org.id, connection.id


SetupTuple = tuple[async_sessionmaker[AsyncSession], str, UUID, UUID]
SyncSetupTuple = tuple[async_sessionmaker[AsyncSession], str, UUID, UUID, UUID]


@pytest.mark.integration
class TestGBPDiscoveryAccounts:
    """Account discovery: idempotent upsert, stale marking, audit, tenant isolation."""

    @pytest.fixture
    def setup(
        self, discovery_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
    ) -> SetupTuple:
        org_id, connection_id = asyncio.run(_setup_org_with_connection(discovery_session_factory))
        return discovery_session_factory, postgresql_test_url, org_id, connection_id

    def test_discover_accounts_upserts_and_audits(self, setup: SetupTuple) -> None:
        factory, db_url, org_id, _conn_id = setup
        adapter = FakeGBPAdapter(
            accounts=[
                {"name": "accounts/111", "accountName": "Business A", "accountType": "BUSINESS"},
                {"name": "accounts/222", "accountName": "Business B", "accountType": "PERSONAL"},
            ]
        )
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> list[GBPAccount]:
            async with factory() as session, session.begin():
                return await service.discover_accounts(
                    session,
                    _settings(db_url),
                    org_id,
                    actor_id=uuid4(),
                    correlation_id="test-discover-accounts",
                )

        accounts = asyncio.run(run())
        assert len(accounts) == 2
        ext_ids = {a.external_account_id for a in accounts}
        assert ext_ids == {"111", "222"}
        assert all(a.status == "discovered" for a in accounts)

        async def check_audit() -> list[AuditEvent]:
            async with factory() as session:
                rows = list(
                    await session.scalars(
                        select(AuditEvent).where(
                            AuditEvent.organization_id == org_id,
                            AuditEvent.event_type == "gbp.discovery.accounts_discovered",
                        )
                    )
                )
                return rows

        events = asyncio.run(check_audit())
        assert len(events) == 1
        assert events[0].result.value == "succeeded"

    def test_discover_accounts_idempotent_on_rerun(self, setup: SetupTuple) -> None:
        factory, db_url, org_id, _conn_id = setup
        adapter = FakeGBPAdapter(accounts=[{"name": "accounts/111", "accountName": "Business A"}])
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> list[GBPAccount]:
            async with factory() as session, session.begin():
                return await service.discover_accounts(
                    session,
                    _settings(db_url),
                    org_id,
                    actor_id=None,
                    correlation_id="test-idempotent",
                )

        first = asyncio.run(run())
        second = asyncio.run(run())
        assert len(first) == 1
        assert len(second) == 1
        assert first[0].id == second[0].id
        assert first[0].external_account_id == "111"

    def test_discover_accounts_marks_missing_as_unavailable(self, setup: SetupTuple) -> None:
        factory, db_url, org_id, _conn_id = setup

        async def seed_existing() -> None:
            async with factory.begin() as session:
                from sqlalchemy import select as sa_select

                conn = await session.scalar(
                    sa_select(IntegrationConnection).where(
                        IntegrationConnection.organization_id == org_id
                    )
                )
                assert conn is not None
                existing = GBPAccount(
                    organization_id=org_id,
                    connection_id=conn.id,
                    external_account_id="old",
                    display_name="Old Account",
                    status="discovered",
                )
                session.add(existing)

        asyncio.run(seed_existing())

        adapter = FakeGBPAdapter(accounts=[{"name": "accounts/111", "accountName": "New Account"}])
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> list[GBPAccount]:
            async with factory() as session, session.begin():
                return await service.discover_accounts(
                    session,
                    _settings(db_url),
                    org_id,
                    actor_id=None,
                    correlation_id="test-stale",
                )

        accounts = asyncio.run(run())
        by_ext = {a.external_account_id: a for a in accounts}
        assert "old" in by_ext
        assert by_ext["old"].status == "unavailable"
        assert "111" in by_ext
        assert by_ext["111"].status == "discovered"

    def test_discover_accounts_provider_error_audits_failure(self, setup: SetupTuple) -> None:
        factory, db_url, org_id, _conn_id = setup
        adapter = FakeGBPAdapter(account_error=RuntimeError("Google API down"))
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> None:
            async with factory() as session, session.begin():
                with pytest.raises(RuntimeError, match="Google API down"):
                    await service.discover_accounts(
                        session,
                        _settings(db_url),
                        org_id,
                        actor_id=None,
                        correlation_id="test-error",
                    )

        asyncio.run(run())

        async def check_audit() -> list[AuditEvent]:
            async with factory() as session:
                return list(
                    await session.scalars(
                        select(AuditEvent).where(
                            AuditEvent.organization_id == org_id,
                            AuditEvent.event_type == "gbp.discovery.accounts_failed",
                        )
                    )
                )

        events = asyncio.run(check_audit())
        assert len(events) == 1
        assert events[0].result.value == "failed"

    def test_discover_accounts_tenant_isolated(
        self, discovery_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
    ) -> None:
        org_a, _ = asyncio.run(_setup_org_with_connection(discovery_session_factory, slug="org-a"))
        org_b, _ = asyncio.run(_setup_org_with_connection(discovery_session_factory, slug="org-b"))

        adapter = FakeGBPAdapter(
            accounts=[{"name": "accounts/org-a-only", "accountName": "Org A Account"}]
        )
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run_for(org_id: UUID) -> list[GBPAccount]:
            async with discovery_session_factory() as session, session.begin():
                return await service.discover_accounts(
                    session,
                    _settings(postgresql_test_url),
                    org_id,
                    actor_id=None,
                    correlation_id="test-iso",
                )

        # Discover for org A: stores the account under org A's connection.
        accounts_a = asyncio.run(run_for(org_a))
        assert len(accounts_a) == 1
        assert accounts_a[0].external_account_id == "org-a-only"

        # Org A's discovery must not create any accounts visible under org B.
        async def query_b() -> list[GBPAccount]:
            async with discovery_session_factory() as session:
                return list(
                    await session.scalars(
                        select(GBPAccount).where(GBPAccount.organization_id == org_b)
                    )
                )

        accounts_b_db = asyncio.run(query_b())
        assert len(accounts_b_db) == 0


@pytest.mark.integration
class TestGBPDiscoveryLocations:
    """Location discovery: idempotent upsert, stale marking, no-accounts, audit."""

    @pytest.fixture
    def setup(
        self, discovery_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
    ) -> SetupTuple:
        org_id, connection_id = asyncio.run(_setup_org_with_connection(discovery_session_factory))

        async def seed_account() -> None:
            async with discovery_session_factory.begin() as session:
                conn = await session.scalar(
                    select(IntegrationConnection).where(
                        IntegrationConnection.organization_id == org_id
                    )
                )
                assert conn is not None
                acct = GBPAccount(
                    organization_id=org_id,
                    connection_id=conn.id,
                    external_account_id="111",
                    display_name="Test Account",
                    status="discovered",
                )
                session.add(acct)

        asyncio.run(seed_account())
        return discovery_session_factory, postgresql_test_url, org_id, connection_id

    def test_discover_locations_upserts_and_audits(self, setup: SetupTuple) -> None:
        factory, db_url, org_id, _ = setup
        adapter = FakeGBPAdapter(
            locations_by_account={
                "accounts/111": [
                    {"name": "accounts/111/locations/loc-a", "title": "Location A"},
                    {"name": "accounts/111/locations/loc-b", "title": "Location B"},
                ]
            }
        )
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> list[GBPLocation]:
            async with factory() as session, session.begin():
                return await service.discover_locations(
                    session,
                    _settings(db_url),
                    org_id,
                    actor_id=uuid4(),
                    correlation_id="test-discover-locations",
                )

        locations = asyncio.run(run())
        assert len(locations) == 2
        ext_ids = {loc.external_location_id for loc in locations}
        assert ext_ids == {"loc-a", "loc-b"}
        assert all(loc.mapping_status == "unmapped" for loc in locations)

        async def check_audit() -> list[AuditEvent]:
            async with factory() as session:
                return list(
                    await session.scalars(
                        select(AuditEvent).where(
                            AuditEvent.organization_id == org_id,
                            AuditEvent.event_type == "gbp.discovery.locations_discovered",
                        )
                    )
                )

        events = asyncio.run(check_audit())
        assert len(events) == 1
        assert events[0].result.value == "succeeded"

    def test_discover_locations_idempotent_on_rerun(self, setup: SetupTuple) -> None:
        factory, db_url, org_id, _ = setup
        adapter = FakeGBPAdapter(
            locations_by_account={
                "accounts/111": [
                    {"name": "accounts/111/locations/loc-a", "title": "Location A"},
                ]
            }
        )
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> list[GBPLocation]:
            async with factory() as session, session.begin():
                return await service.discover_locations(
                    session,
                    _settings(db_url),
                    org_id,
                    actor_id=None,
                    correlation_id="test-loc-idempotent",
                )

        first = asyncio.run(run())
        second = asyncio.run(run())
        assert len(first) == 1
        assert len(second) == 1
        assert first[0].id == second[0].id

    def test_discover_locations_no_accounts_returns_empty(
        self, discovery_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
    ) -> None:
        org_id, _ = asyncio.run(
            _setup_org_with_connection(discovery_session_factory, slug="no-acct-org")
        )
        adapter = FakeGBPAdapter()
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> list[GBPLocation]:
            async with discovery_session_factory() as session, session.begin():
                return await service.discover_locations(
                    session,
                    _settings(postgresql_test_url),
                    org_id,
                    actor_id=None,
                    correlation_id="test-no-accts",
                )

        locations = asyncio.run(run())
        assert len(locations) == 0

        async def check_audit() -> list[AuditEvent]:
            async with discovery_session_factory() as session:
                return list(
                    await session.scalars(
                        select(AuditEvent).where(
                            AuditEvent.organization_id == org_id,
                            AuditEvent.event_type == "gbp.discovery.locations_no_accounts",
                        )
                    )
                )

        events = asyncio.run(check_audit())
        assert len(events) == 1

    def test_discover_locations_marks_missing_as_archived(self, setup: SetupTuple) -> None:
        factory, db_url, org_id, _ = setup

        async def seed_existing_location() -> None:
            async with factory.begin() as session:
                conn = await session.scalar(
                    select(IntegrationConnection).where(
                        IntegrationConnection.organization_id == org_id
                    )
                )
                assert conn is not None
                acct = await session.scalar(
                    select(GBPAccount).where(
                        GBPAccount.organization_id == org_id,
                        GBPAccount.external_account_id == "111",
                    )
                )
                assert acct is not None
                loc = GBPLocation(
                    organization_id=org_id,
                    connection_id=conn.id,
                    account_id=acct.id,
                    external_location_id="loc-old",
                    business_name="Old Location",
                    mapping_status="unmapped",
                )
                session.add(loc)

        asyncio.run(seed_existing_location())

        adapter = FakeGBPAdapter(
            locations_by_account={
                "accounts/111": [
                    {"name": "accounts/111/locations/loc-new", "title": "New Location"},
                ]
            }
        )
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> list[GBPLocation]:
            async with factory() as session, session.begin():
                return await service.discover_locations(
                    session,
                    _settings(db_url),
                    org_id,
                    actor_id=None,
                    correlation_id="test-stale-loc",
                )

        locations = asyncio.run(run())
        by_ext = {loc.external_location_id: loc for loc in locations}
        assert "loc-old" in by_ext
        assert by_ext["loc-old"].mapping_status == "archived"
        assert "loc-new" in by_ext
        assert by_ext["loc-new"].mapping_status == "unmapped"


@pytest.mark.integration
class TestGBPProfileSync:
    """Profile sync: idempotent snapshot storage, error handling, audit."""

    @pytest.fixture
    def setup(
        self, discovery_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
    ) -> SyncSetupTuple:
        org_id, connection_id = asyncio.run(
            _setup_org_with_connection(discovery_session_factory, slug="sync-test-org")
        )

        async def seed_account_and_location() -> UUID:
            async with discovery_session_factory.begin() as session:
                conn = await session.scalar(
                    select(IntegrationConnection).where(
                        IntegrationConnection.organization_id == org_id
                    )
                )
                assert conn is not None
                acct = GBPAccount(
                    organization_id=org_id,
                    connection_id=conn.id,
                    external_account_id="111",
                    display_name="Sync Test Account",
                    status="discovered",
                )
                session.add(acct)
                await session.flush()
                loc = GBPLocation(
                    organization_id=org_id,
                    connection_id=conn.id,
                    account_id=acct.id,
                    external_location_id="loc-a",
                    business_name="Location A",
                    mapping_status="unmapped",
                )
                session.add(loc)
                await session.flush()
                return loc.id

        loc_id = asyncio.run(seed_account_and_location())
        return discovery_session_factory, postgresql_test_url, org_id, connection_id, loc_id

    def test_sync_profile_stores_snapshot(self, setup: SyncSetupTuple) -> None:
        factory, db_url, org_id, _, loc_id = setup
        adapter = FakeGBPAdapter(
            location_details={
                "accounts/111/locations/loc-a": {
                    "name": "accounts/111/locations/loc-a",
                    "title": "My Business",
                    "storefrontAddress": {"locality": "San Diego"},
                    "phoneNumbers": {"primaryPhone": "+16195551234"},
                }
            }
        )
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> GBPProfileSnapshot:
            async with factory() as session, session.begin():
                return await service.sync_profile(
                    session,
                    _settings(db_url),
                    org_id,
                    loc_id,
                    actor_id=uuid4(),
                    correlation_id="test-sync-profile",
                )

        snapshot = asyncio.run(run())
        assert snapshot.content_hash is not None
        assert snapshot.normalized_profile.get("title") == "My Business"
        assert snapshot.completeness == "full"

        async def check_audit() -> list[AuditEvent]:
            async with factory() as session:
                return list(
                    await session.scalars(
                        select(AuditEvent).where(
                            AuditEvent.organization_id == org_id,
                            AuditEvent.event_type == "gbp.sync.profile_synced",
                        )
                    )
                )

        events = asyncio.run(check_audit())
        assert len(events) == 1

    def test_sync_profile_idempotent_same_hash(self, setup: SyncSetupTuple) -> None:
        factory, db_url, org_id, _, loc_id = setup
        profile = {
            "name": "accounts/111/locations/loc-a",
            "title": "Consistent Business",
        }
        adapter = FakeGBPAdapter(location_details={"accounts/111/locations/loc-a": profile})
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> GBPProfileSnapshot:
            async with factory() as session, session.begin():
                return await service.sync_profile(
                    session,
                    _settings(db_url),
                    org_id,
                    loc_id,
                    actor_id=None,
                    correlation_id="test-idempotent-snapshot",
                )

        first = asyncio.run(run())
        second = asyncio.run(run())
        assert first.id == second.id
        assert first.content_hash == second.content_hash

    def test_sync_profile_provider_error_audits_failure(self, setup: SyncSetupTuple) -> None:
        factory, db_url, org_id, _, loc_id = setup
        adapter = FakeGBPAdapter(location_detail_error=RuntimeError("Profile fetch failed"))
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> None:
            async with factory() as session, session.begin():
                with pytest.raises(RuntimeError, match="Profile fetch failed"):
                    await service.sync_profile(
                        session,
                        _settings(db_url),
                        org_id,
                        loc_id,
                        actor_id=None,
                        correlation_id="test-sync-error",
                    )

        asyncio.run(run())

        async def check_audit() -> list[AuditEvent]:
            async with factory() as session:
                return list(
                    await session.scalars(
                        select(AuditEvent).where(
                            AuditEvent.organization_id == org_id,
                            AuditEvent.event_type == "gbp.sync.profile_failed",
                        )
                    )
                )

        events = asyncio.run(check_audit())
        assert len(events) == 1
        assert events[0].result.value == "failed"


@pytest.mark.integration
class TestDiscoverAndSync:
    """Combined discover_and_sync: full flow with individual sync failure tolerance."""

    def test_discover_and_sync_chains_all_three_phases(
        self, discovery_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
    ) -> None:
        org_id, _ = asyncio.run(
            _setup_org_with_connection(discovery_session_factory, slug="full-flow-org")
        )
        adapter = FakeGBPAdapter(
            accounts=[{"name": "accounts/111", "accountName": "Full Flow Account"}],
            locations_by_account={
                "accounts/111": [
                    {"name": "accounts/111/locations/loc-a", "title": "Full Flow Location"},
                ]
            },
            location_details={
                "accounts/111/locations/loc-a": {
                    "name": "accounts/111/locations/loc-a",
                    "title": "Full Flow Location",
                    "storefrontAddress": {"locality": "Portland"},
                }
            },
        )
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> dict[str, Any]:
            async with discovery_session_factory() as session, session.begin():
                return await service.discover_and_sync(
                    session,
                    _settings(postgresql_test_url),
                    org_id,
                    actor_id=uuid4(),
                    correlation_id="test-full-flow",
                )

        summary = asyncio.run(run())
        assert summary["accounts_discovered"] == 1
        assert summary["locations_discovered"] == 1
        assert summary["profiles_synced"] == 1

    def test_discover_and_sync_tolerates_individual_sync_failures(
        self, discovery_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
    ) -> None:
        org_id, _ = asyncio.run(
            _setup_org_with_connection(discovery_session_factory, slug="sync-fail-org")
        )
        adapter = FakeGBPAdapter(
            accounts=[{"name": "accounts/111", "accountName": "Account"}],
            locations_by_account={
                "accounts/111": [
                    {"name": "accounts/111/locations/loc-a", "title": "Loc A"},
                    {"name": "accounts/111/locations/loc-b", "title": "Loc B"},
                ]
            },
            location_details={
                "accounts/111/locations/loc-a": {
                    "name": "accounts/111/locations/loc-a",
                    "title": "Loc A",
                },
            },
            location_detail_error=RuntimeError("loc-b fetch failed"),
        )
        service = GBPDiscoveryService(
            adapter=adapter,
            connection=FakeConnectionService(),
        )

        async def run() -> dict[str, Any]:
            async with discovery_session_factory() as session, session.begin():
                return await service.discover_and_sync(
                    session,
                    _settings(postgresql_test_url),
                    org_id,
                    actor_id=None,
                    correlation_id="test-sync-tolerance",
                )

        summary = asyncio.run(run())
        assert summary["accounts_discovered"] == 1
        assert summary["locations_discovered"] == 2
        assert summary["profiles_synced"] == 1
