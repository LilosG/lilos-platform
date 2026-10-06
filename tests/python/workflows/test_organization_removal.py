"""organization.remove: stop, purge, integrations, storage, finish; resumable and tenant-safe."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table, func, select, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.administration.models import Product, ProductEntitlement
from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.contracts import ScheduleCreate
from apps.api.app.execution.models import Job, Schedule, WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.integrations.secrets import ProviderSecret
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.contracts import OrganizationRemove
from apps.api.app.organizations.enums import (
    OrganizationRemovalState,
    OrganizationStatus,
    OrganizationType,
)
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.removal import (
    REMOVAL_REQUESTED_EVENT,
    REMOVED_EVENT,
    OrganizationRemovalService,
    RemovalCode,
    RemovalProgress,
    _scope,
    purge_plan,
)
from apps.api.app.organizations.service import OrganizationService
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.seo.models import SEOSearchProperty, SEOWebsite
from apps.api.app.storage.objects import StorageNotConfiguredError, StorageRequestError
from scripts.ensure_client_schedules import ensure_client_schedules

NOW = datetime(2026, 10, 6, 12, 0, tzinfo=UTC)
# What a removal leaves of the organization's operational tables: the executing run and its
# job, and the one location an audit event still points at.
KEPT = {"workflow_runs": 1, "jobs": 1, "locations": 1}


class FakeStorage:
    """Records deletions; ``fail`` makes every call raise like an unreachable service."""

    def __init__(self, *, objects: int = 3, fail: bool = False) -> None:
        self.objects = objects
        self.fail = fail
        self.prefixes: list[tuple[str, str]] = []
        self.deleted: list[tuple[str, str]] = []

    async def delete_prefix(self, bucket: str, prefix: str) -> int:
        if self.fail:
            raise StorageRequestError
        self.prefixes.append((bucket, prefix))
        return self.objects

    async def delete(self, bucket: str, path: str) -> None:
        if self.fail:
            raise StorageRequestError
        self.deleted.append((bucket, path))

    async def put(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        raise AssertionError("a removal never writes to storage")

    async def signed_url(self, bucket: str, path: str, expires_in: int = 900) -> str:
        raise AssertionError("a removal never signs a URL")


def service_with(storage: Any, **options: Any) -> OrganizationRemovalService:
    return OrganizationRemovalService(storage_factory=lambda: storage, **options)


async def populate(
    session: AsyncSession,
    name: str,
    *,
    status: OrganizationStatus,
    secret_id: UUID | None = None,
) -> tuple[Organization, UUID]:
    """A client with an integration, mapped GBP locations, a site, schedules and queued work."""
    organization = Organization(
        name=name,
        slug=f"{name.lower().replace(' ', '-')}-{uuid4().hex[:6]}",
        organization_type=OrganizationType.TEST,
        status=status,
        timezone="America/Los_Angeles",
        default_currency="USD",
        legal_name=f"{name} LLC",
        website_url="https://client.example.invalid",
        primary_contact_name="Contact",
        primary_contact_email="contact@example.invalid",
        billing_email="billing@example.invalid",
        archived_at=NOW if status is OrganizationStatus.ARCHIVED else None,
        version=1,
    )
    session.add(organization)
    await session.flush()
    secret_id = secret_id or uuid4()
    if await session.get(ProviderSecret, secret_id) is None:
        session.add(ProviderSecret(id=secret_id, ciphertext="encrypted", key_version=1))
    provider = Provider(
        key=f"google-{uuid4().hex[:6]}",
        name="Google",
        status="active",
        capabilities=[],
        manifest_version=1,
    )
    session.add(provider)
    await session.flush()
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider_id=provider.id,
        external_account_reference="google",
        credential_reference=str(secret_id),
        status="connected",
        version=1,
    )
    session.add(connection)
    await session.flush()
    account = GBPAccount(
        organization_id=organization.id,
        connection_id=connection.id,
        external_account_id="accounts/1",
        display_name="Account",
        status="selected",
    )
    website = SEOWebsite(
        organization_id=organization.id,
        location_id=None,
        key="primary",
        name="Primary",
        canonical_origin=f"https://{uuid4().hex[:8]}.example.invalid",
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add_all([account, website])
    await session.flush()
    session.add_all(
        [
            SEOSearchProperty(
                organization_id=organization.id,
                website_id=website.id,
                connection_id=connection.id,
                provider="google_search_console",
                external_property_id=f"sc-domain:{uuid4().hex[:6]}",
                property_type="domain",
                mapping_status="mapped",
                freshness_status="fresh",
            ),
            AnalyticsProperty(
                organization_id=organization.id,
                connection_id=connection.id,
                website_id=website.id,
                provider="google_analytics",
                external_property_id=f"properties/{uuid4().hex[:6]}",
                property_number="123",
                display_name="GA4",
                mapping_status="mapped",
                freshness_status="never_synced",
            ),
        ]
    )
    location_ids: list[UUID] = []
    for index in range(2):
        location = Location(
            organization_id=organization.id,
            name=f"Location {index}",
            slug=f"location-{index}",
            location_type=LocationType.VIRTUAL,
            status=LocationStatus.ACTIVE,
            timezone="UTC",
            country_code="US",
            website_url="https://example.invalid",
            is_primary=index == 0,
            version=1,
        )
        session.add(location)
        await session.flush()
        mapping = ProviderResourceMapping(
            organization_id=organization.id,
            connection_id=connection.id,
            resource_type="location",
            external_resource_id=f"locations/{index}",
            platform_resource_id=location.id,
            status="active",
        )
        session.add(mapping)
        await session.flush()
        session.add(
            GBPLocation(
                organization_id=organization.id,
                location_id=location.id,
                connection_id=connection.id,
                account_id=account.id,
                integration_resource_id=mapping.id,
                external_location_id=f"locations/{index}",
                business_name=f"Business {index}",
                mapping_status="confirmed",
                write_enabled=True,
            )
        )
        location_ids.append(location.id)
    await session.flush()
    # Governed history: product_entitlements refuses every DELETE except a removal's.
    product = Product(
        key=f"product_{uuid4().hex[:8]}",
        name="Product",
        description="A product",
        owning_module="tests",
        current_product_version="1.0.0",
        runtime_control_namespace=f"tests_{uuid4().hex[:8]}",
    )
    session.add(product)
    await session.flush()
    session.add(
        ProductEntitlement(
            organization_id=organization.id,
            product_id=product.id,
            status="active",
            source="test",
            reason="test",
        )
    )
    await session.flush()
    execution = ExecutionService()
    # Only location 0 is named by an audit event, so location 1 can be deleted outright.
    await execution.create_schedule(
        session,
        organization.id,
        ScheduleCreate(
            workflow_key="gbp.sync",
            key="ensure:gbp.sync",
            cron_expression="0 5 * * *",
            timezone="UTC",
            next_run_at=NOW + timedelta(days=1),
            location_id=location_ids[0],
        ),
        correlation_id="removal-test",
    )
    await execution.create_schedule(
        session,
        organization.id,
        ScheduleCreate(
            workflow_key="seo.sync_search_console",
            key="ensure:seo.sync_search_console",
            cron_expression="30 5 * * *",
            timezone="UTC",
            next_run_at=NOW + timedelta(days=1),
        ),
        correlation_id="removal-test",
    )
    await execution.start_named(
        session,
        organization.id,
        "gbp.sync",
        f"queued-{uuid4().hex}",
        correlation_id="removal-test",
    )
    return organization, secret_id


async def request_removal(
    factory: async_sessionmaker[AsyncSession], organization_id: UUID, name: str
) -> tuple[UUID, dict[str, Any]]:
    async with factory.begin() as session:
        _, state, run_id = await OrganizationService().request_removal(
            session,
            organization_id,
            OrganizationRemove(confirm_name=name),
            actor_id=None,
            correlation_id="removal-request",
        )
        assert state is OrganizationRemovalState.REQUESTED
        assert run_id is not None
        run = await session.get(WorkflowRun, run_id)
        assert run is not None
        return run_id, dict(run.input_document)


async def execute(
    factory: async_sessionmaker[AsyncSession],
    service: OrganizationRemovalService,
    organization_id: UUID,
    run_id: UUID,
    document: dict[str, Any],
) -> Any:
    async with factory() as session:
        run = await session.get(WorkflowRun, run_id)
        assert run is not None
        return await service.run(
            session,
            organization_id=organization_id,
            workflow_run_id=run_id,
            input_document=dict(run.input_document or document),
            correlation_id=f"workflow-{run_id}",
        )


async def counts(
    factory: async_sessionmaker[AsyncSession], organization_id: UUID
) -> dict[str, int]:
    """Rows the organization owns in every table the purge plan covers."""
    plan = purge_plan()
    scope = set(plan)
    async with factory() as session:
        return {
            table.name: int(
                await session.scalar(
                    select(func.count())
                    .select_from(table)
                    .where(_scope(table, organization_id, scope))
                )
                or 0
            )
            for table in plan
        }


async def archived_client(
    factory: async_sessionmaker[AsyncSession], name: str = "Remove Me"
) -> tuple[UUID, UUID]:
    async with factory.begin() as session:
        organization, secret_id = await populate(session, name, status=OrganizationStatus.ARCHIVED)
        return organization.id, secret_id


@pytest.mark.integration
@pytest.mark.anyio
async def test_removal_deletes_the_client_and_leaves_every_other_client_untouched(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = workflows_session_factory
    organization_id, secret_id = await archived_client(factory)
    async with factory.begin() as session:
        other, other_secret = await populate(session, "Keep Me", status=OrganizationStatus.ACTIVE)
        other_id = other.id
    other_before = await counts(factory, other_id)
    assert sum(other_before.values()) > 10, "the second client must own rows to be protected"
    before = await counts(factory, organization_id)
    assert before["gbp_locations"] == 2 and before["workflow_schedules"] == 2

    run_id, document = await request_removal(factory, organization_id, "REMOVE me")
    storage = FakeStorage(objects=4)
    outcome = await execute(factory, service_with(storage), organization_id, run_id, document)

    assert outcome.result == "succeeded", outcome
    after = await counts(factory, organization_id)
    assert {name: count for name, count in after.items() if count} == KEPT
    assert await counts(factory, other_id) == other_before

    async with factory() as session:
        organization = await session.get(Organization, organization_id)
        assert organization is not None
        assert organization.status is OrganizationStatus.ARCHIVED
        assert organization.removed_at is not None
        assert organization.name == "Remove Me" and organization.slug.startswith("remove-me-")
        assert organization.archived_at is not None
        for column in (
            "legal_name",
            "website_url",
            "primary_contact_name",
            "primary_contact_email",
            "primary_contact_phone",
            "billing_email",
            "external_reference",
            "onboarding_status",
            "onboarding_mode",
            "industry_id",
        ):
            assert getattr(organization, column) is None, column
        tombstone = await session.scalar(
            select(Location).where(Location.organization_id == organization_id)
        )
        assert tombstone is not None
        assert tombstone.name == "Removed location" and tombstone.website_url is None
        assert await session.get(ProviderSecret, secret_id) is None
        assert await session.get(ProviderSecret, other_secret) is not None
        # Everything the audit trail recorded about the client is still there, plus the two
        # events that describe the removal.
        events = list(
            await session.scalars(
                select(AuditEvent).where(AuditEvent.organization_id == organization_id)
            )
        )
        types = {event.event_type for event in events}
        assert {REMOVAL_REQUESTED_EVENT, REMOVED_EVENT, "workflow.schedule.created"} <= types
        removed = next(event for event in events if event.event_type == REMOVED_EVENT)
        reported = {
            table: count
            for part in removed.event_metadata["deleted_rows"].values()
            for table, count in part.items()
        }
        assert reported["gbp_locations"] == 2
        assert reported["product_entitlements"] == 1
        assert reported["integration_connections"] == 1
        assert reported["provider_resource_mappings"] == 2
        assert reported["workflow_schedules"] == 2
        assert reported["locations"] == 1
        assert removed.event_metadata["locations_tombstoned"] == 1
        assert removed.event_metadata["provider_secrets_deleted"] == 1
        assert removed.event_metadata["storage_objects_deleted"] == 4
        assert removed.event_metadata["rows_deleted"] == sum(reported.values())
        # Counts and codes only: nothing the client owned is quoted back.
        assert "Remove Me" not in str(removed.event_metadata) and "example.invalid" not in str(
            removed.event_metadata
        )
    assert storage.prefixes == [("gbp-media", str(organization_id))]


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_credential_another_organization_uses_is_kept(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = workflows_session_factory
    shared = uuid4()
    async with factory.begin() as session:
        removed, _ = await populate(
            session, "Remove Shared", status=OrganizationStatus.ARCHIVED, secret_id=shared
        )
        await populate(session, "Keep Shared", status=OrganizationStatus.ACTIVE, secret_id=shared)
        removed_id = removed.id
    run_id, document = await request_removal(factory, removed_id, "Remove Shared")

    outcome = await execute(factory, service_with(FakeStorage()), removed_id, run_id, document)

    assert outcome.result == "succeeded"
    async with factory() as session:
        assert await session.get(ProviderSecret, shared) is not None
        removed_event = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.organization_id == removed_id, AuditEvent.event_type == REMOVED_EVENT
            )
        )
        assert removed_event is not None
        assert removed_event.event_metadata["provider_secrets_deleted"] == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_running_it_again_changes_nothing(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = workflows_session_factory
    organization_id, _ = await archived_client(factory)
    run_id, document = await request_removal(factory, organization_id, "Remove Me")
    service = service_with(FakeStorage())
    first = await execute(factory, service, organization_id, run_id, document)
    snapshot = await counts(factory, organization_id)

    again = await execute(factory, service, organization_id, run_id, document)

    assert first.result == again.result == "succeeded"
    assert await counts(factory, organization_id) == snapshot
    async with factory() as session:
        removed_events = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.event_type == REMOVED_EVENT,
            )
        )
        assert removed_events == 1
        # Asking the API again is also a no-op that reports the finished removal.
        _, state, _ = await OrganizationService().request_removal(
            session,
            organization_id,
            OrganizationRemove(confirm_name="anything"),
            actor_id=None,
            correlation_id="again",
        )
        assert state is OrganizationRemovalState.COMPLETED


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_failure_part_way_through_the_purge_resumes_where_it_stopped(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = workflows_session_factory
    organization_id, _ = await archived_client(factory)
    async with factory.begin() as session:
        other, _ = await populate(session, "Bystander", status=OrganizationStatus.ACTIVE)
        other_id = other.id
    other_before = await counts(factory, other_id)
    run_id, document = await request_removal(factory, organization_id, "Remove Me")

    class Crashes(OrganizationRemovalService):
        """Dies after the child tables of GBP are gone, before the tables they point at."""

        crashed = False

        async def _empty_table(self, session: AsyncSession, table: Table, *args: Any) -> None:
            if table.name == "provider_resource_mappings" and not self.crashed:
                self.crashed = True
                raise RuntimeError("worker lost")
            await super()._empty_table(session, table, *args)

    crashing = Crashes(storage_factory=lambda: FakeStorage())
    with pytest.raises(RuntimeError):
        await execute(factory, crashing, organization_id, run_id, document)
    partial = await counts(factory, organization_id)
    assert partial["gbp_locations"] == 0, "the batches before the crash stay committed"
    assert partial["provider_resource_mappings"] == 2
    async with factory() as session:
        organization = await session.get(Organization, organization_id)
        assert organization is not None and organization.removed_at is None

    outcome = await execute(factory, crashing, organization_id, run_id, document)

    assert outcome.result == "succeeded"
    assert {n: c for n, c in (await counts(factory, organization_id)).items() if c} == KEPT
    assert await counts(factory, other_id) == other_before
    async with factory() as session:
        removed = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.event_type == REMOVED_EVENT,
            )
        )
        assert removed is not None
        reported = {
            t: c
            for part in removed.event_metadata["deleted_rows"].values()
            for t, c in part.items()
        }
        # Counted across both attempts, not only the one that finished.
        assert reported["gbp_locations"] == 2 and reported["provider_resource_mappings"] == 2


@pytest.mark.integration
@pytest.mark.anyio
async def test_it_refuses_an_organization_that_is_not_archived_or_was_never_requested(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = workflows_session_factory
    organization_id, _ = await archived_client(factory)
    run_id, document = await request_removal(factory, organization_id, "Remove Me")

    # A run that does not carry the audited request of an administrator is refused, however
    # it was started.
    async with factory.begin() as session:
        run = await session.get(WorkflowRun, run_id)
        assert run is not None
        run.input_document = {"request_audit_event_id": str(uuid4())}
    unrequested = await execute(
        factory, service_with(FakeStorage()), organization_id, run_id, document
    )
    assert unrequested.safe_error == RemovalCode.NOT_REQUESTED
    assert (await counts(factory, organization_id))["gbp_locations"] == 2

    async with factory.begin() as session:
        live, _ = await populate(session, "Still Live", status=OrganizationStatus.ACTIVE)
        live_id = live.id
        live_run = await ExecutionService().start_named(
            session, live_id, "organization.remove", f"x-{uuid4().hex}", correlation_id="x"
        )
        live_run_id = live_run.id
    refused = await execute(
        factory, service_with(FakeStorage()), live_id, live_run_id, {"request_audit_event_id": "x"}
    )
    assert refused.safe_error == RemovalCode.NOT_ARCHIVED
    assert sum((await counts(factory, live_id)).values()) > 10


@pytest.mark.integration
@pytest.mark.anyio
async def test_unreachable_storage_is_retried_and_nothing_is_deleted_yet(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = workflows_session_factory
    organization_id, _ = await archived_client(factory)
    run_id, document = await request_removal(factory, organization_id, "Remove Me")

    outcome = await execute(
        factory, service_with(FakeStorage(fail=True)), organization_id, run_id, document
    )

    assert outcome.result == "retryable_failure"
    assert outcome.safe_error == RemovalCode.STORAGE_UNAVAILABLE
    assert (await counts(factory, organization_id))["gbp_locations"] == 2
    async with factory() as session:
        organization = await session.get(Organization, organization_id)
        assert organization is not None and organization.removed_at is None


@pytest.mark.integration
@pytest.mark.anyio
async def test_storage_that_is_not_configured_only_matters_when_objects_are_referenced(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = workflows_session_factory
    organization_id, _ = await archived_client(factory)
    run_id, document = await request_removal(factory, organization_id, "Remove Me")

    def unconfigured() -> Any:
        raise StorageNotConfiguredError

    outcome = await execute(
        factory,
        OrganizationRemovalService(storage_factory=unconfigured),
        organization_id,
        run_id,
        document,
    )

    assert outcome.result == "succeeded"


@pytest.mark.integration
@pytest.mark.anyio
async def test_work_a_worker_is_running_right_now_holds_the_removal_back(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = workflows_session_factory
    organization_id, _ = await archived_client(factory)
    async with factory.begin() as session:
        job = await session.scalar(select(Job).where(Job.organization_id == organization_id))
        assert job is not None
        job.status = "claimed"
        job.lease_owner = "worker-1"
        job.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
    run_id, document = await request_removal(factory, organization_id, "Remove Me")

    waiting = await execute(factory, service_with(FakeStorage()), organization_id, run_id, document)

    assert waiting.result == "retryable_failure"
    assert waiting.safe_error == RemovalCode.WAITING_FOR_ACTIVE_JOBS
    counted = await counts(factory, organization_id)
    assert counted["gbp_locations"] == 2, "nothing is deleted under a running provider call"
    assert counted["workflow_schedules"] == 0, "but schedules are stopped at once"


@pytest.mark.integration
@pytest.mark.anyio
async def test_queued_work_and_schedules_are_stopped_before_anything_is_deleted(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = workflows_session_factory
    organization_id, _ = await archived_client(factory)
    run_id, document = await request_removal(factory, organization_id, "Remove Me")

    class StopsAfterStopping(OrganizationRemovalService):
        async def _delete_provider_secrets(self, *args: Any) -> None:
            raise RuntimeError("halt after the stop phase")

    with pytest.raises(RuntimeError):
        await execute(
            factory,
            StopsAfterStopping(storage_factory=lambda: FakeStorage()),
            organization_id,
            run_id,
            document,
        )

    async with factory() as session:
        jobs = list(
            await session.scalars(
                select(Job).where(
                    Job.organization_id == organization_id, Job.workflow_run_id != run_id
                )
            )
        )
        runs = list(
            await session.scalars(
                select(WorkflowRun).where(
                    WorkflowRun.organization_id == organization_id, WorkflowRun.id != run_id
                )
            )
        )
        assert jobs and all(j.status == "cancelled" and j.cancellation_requested_at for j in jobs)
        assert runs and all(r.status == "cancelled" for r in runs)
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Schedule)
                .where(Schedule.organization_id == organization_id)
            )
            == 0
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_schedules_are_never_recreated_for_a_removed_client(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = workflows_session_factory
    organization_id, _ = await archived_client(factory)
    async with factory.begin() as session:
        other, _ = await populate(session, "Scheduled", status=OrganizationStatus.ACTIVE)
        other_id = other.id
        await session.execute(
            text("DELETE FROM workflow_schedules WHERE organization_id = :id"), {"id": other_id}
        )
    run_id, document = await request_removal(factory, organization_id, "Remove Me")
    assert (
        await execute(factory, service_with(FakeStorage()), organization_id, run_id, document)
    ).result == "succeeded"

    report = await ensure_client_schedules(factory, apply=True, now=NOW)

    assert report.organizations == 1
    assert {change.organization_id for change in report.changes} == {other_id}
    async with factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Schedule)
                .where(Schedule.organization_id == organization_id)
            )
            == 0
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_self_referencing_table_is_emptied_leaf_first_in_batches(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Revision chains point at their predecessor with ON DELETE RESTRICT."""
    factory = workflows_session_factory
    metadata = MetaData()
    tree = Table(
        "removal_test_tree",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("organization_id", PGUUID(as_uuid=True), nullable=False),
        Column("parent_id", Integer, ForeignKey("removal_test_tree.id", ondelete="RESTRICT")),
    )
    organization_id, _ = await archived_client(factory)
    run_id, _ = await request_removal(factory, organization_id, "Remove Me")
    mine, theirs = uuid4(), uuid4()
    async with factory.begin() as session:
        await session.run_sync(lambda sync: metadata.create_all(sync.connection()))
        # A chain of 12 rows whose children have LOWER ids than their parents, so id order is
        # the wrong delete order; plus an unrelated organization's rows in the same table.
        for index in range(12, 0, -1):
            await session.execute(
                tree.insert().values(
                    id=index, organization_id=mine, parent_id=index + 1 if index < 12 else None
                )
            )
        await session.execute(tree.insert().values(id=100, organization_id=theirs, parent_id=None))
    tracker = RemovalProgress()
    try:
        async with factory() as session:
            await OrganizationRemovalService(batch_size=3)._empty_table(
                session, tree, tree.c.organization_id == mine, run_id, tracker
            )
        assert tracker.deleted_rows["removal_test_tree"] == 12
        async with factory() as session:
            assert await session.scalar(select(func.count()).select_from(tree)) == 1
    finally:
        async with factory.begin() as session:
            await session.execute(text("DROP TABLE IF EXISTS removal_test_tree"))


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_trigger_that_still_refuses_a_delete_fails_the_removal_with_a_typed_code(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The database guard allows governed deletes; anything else that refuses is reported."""
    factory = workflows_session_factory
    organization_id, _ = await archived_client(factory)
    run_id, document = await request_removal(factory, organization_id, "Remove Me")
    async with factory.begin() as session:
        await session.execute(
            text(
                "CREATE FUNCTION removal_test_refuse() RETURNS trigger LANGUAGE plpgsql AS "
                "$$ BEGIN RAISE EXCEPTION 'unexpected' USING ERRCODE = '23514'; END $$"
            )
        )
        await session.execute(
            text(
                "CREATE TRIGGER removal_test_refuse BEFORE DELETE ON gbp_accounts "
                "FOR EACH ROW EXECUTE FUNCTION removal_test_refuse()"
            )
        )
    try:
        outcome = await execute(
            factory, service_with(FakeStorage()), organization_id, run_id, document
        )
    finally:
        async with factory.begin() as session:
            await session.execute(text("DROP TRIGGER removal_test_refuse ON gbp_accounts"))
            await session.execute(text("DROP FUNCTION removal_test_refuse()"))

    assert outcome.result == "permanent_failure"
    assert outcome.safe_error == RemovalCode.PROTECTED_HISTORY
    async with factory() as session:
        organization = await session.get(Organization, organization_id)
        assert organization is not None and organization.removed_at is None
