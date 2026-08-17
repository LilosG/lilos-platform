"""Packet 5 — SC5-SCHEDULED-EXECUTION end-to-end acceptance.

Proves the complete durable background execution chain against PostgreSQL:

    schedule configured
        → schedule becomes due
        → scheduler dispatches WITHOUT dashboard/browser open
        → durable workflow/job created
        → worker claims job
        → registered handler executes
        → result persists
        → workflow reaches terminal success
        → run history reflects authoritative result
        → last run updates
        → next run advances
        → no duplicate execution occurs

The chosen workflow is ``gbp.sync`` — a READ-ONLY provider workflow. The
provider boundary is replaced with a recording fake (no external provider
call, no customer-visible write), while every durable-runtime component is
real: SchedulerBackend, WorkerBackend, ExecutionService, lease claiming,
the registered handler, and the persisted models.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from pydantic import PostgresDsn, TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.execution import handlers as handlers_module
from apps.api.app.execution.contracts import ScheduleCreate
from apps.api.app.execution.models import Job, Schedule, WorkflowRun
from apps.api.app.execution.runtime import (
    RuntimeOptions,
    SchedulerBackend,
    WorkerBackend,
)
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.discovery_service import GBPDiscoveryService
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation

ROOT = Path(__file__).resolve().parents[3]
POSTGRES_DSN = TypeAdapter(PostgresDsn)

OPTIONS = RuntimeOptions(
    minimum_poll_seconds=0.01,
    maximum_poll_seconds=0.02,
    heartbeat_seconds=0.01,
    lease_seconds=60,
    shutdown_seconds=5,
)


def _build_settings(postgresql_test_url: str) -> Settings:
    return Settings(
        environment=EnvironmentName.TEST,
        database_url=POSTGRES_DSN.validate_python(postgresql_test_url),
        release="p5-scheduled-test",
    )


async def _seed_org(
    session: AsyncSession, name: str, slug: str
) -> tuple[Organization, Location, GBPLocation, Provider, IntegrationConnection]:
    org = Organization(
        name=name,
        slug=slug,
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()

    location = Location(
        organization_id=org.id,
        name="Downtown",
        slug=f"{slug}-downtown",
        location_type=LocationType.VIRTUAL,
        status=LocationStatus.ACTIVE,
        timezone="UTC",
        country_code="US",
        website_url="https://example.invalid",
        is_primary=True,
        version=1,
    )
    session.add(location)
    await session.flush()

    provider = await session.scalar(select(Provider).where(Provider.key == "google"))
    if provider is None:
        provider = Provider(
            key="google",
            name="Google",
            status="active",
            capabilities=["business_profile", "reviews"],
            manifest_version=1,
        )
        session.add(provider)
        await session.flush()

    connection = IntegrationConnection(
        organization_id=org.id,
        provider_id=provider.id,
        external_account_reference="accounts/test-account",
        status="connected",
        version=1,
    )
    session.add(connection)
    await session.flush()

    account = GBPAccount(
        organization_id=org.id,
        connection_id=connection.id,
        external_account_id="accounts/test-account",
        display_name="Test Account",
        status="selected",
    )
    session.add(account)
    await session.flush()

    gbp_location = GBPLocation(
        organization_id=org.id,
        location_id=location.id,
        connection_id=connection.id,
        account_id=account.id,
        external_location_id="locations/test-location",
        business_name="Test Business",
        mapping_status="confirmed",
        write_enabled=False,
    )
    session.add(gbp_location)
    await session.flush()
    return org, location, gbp_location, provider, connection


@pytest.mark.integration
@pytest.mark.anyio
async def test_scheduled_execution_end_to_end(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove the full durable chain: schedule → dispatch → job → worker → handler → terminal."""
    import asyncio

    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    await asyncio.to_thread(command.upgrade, config, "head")

    # ── Seed org + confirmed GBP location ─────────────────────────────
    async with workflows_session_factory.begin() as session:
        org, location, _gbp, _provider, _connection = await _seed_org(
            session, "Scheduled Test Org", f"scheduled-{uuid4().hex[:12]}"
        )
        other_org, _other_loc, _other_gbp, _p2, _c2 = await _seed_org(
            session, "Other Org", f"other-{uuid4().hex[:12]}"
        )
        org_id = org.id
        other_org_id = other_org.id
        location_id = location.id

    # ── Replace provider boundary with recording fakes (READ-ONLY) ────
    discover_calls: list[dict[str, Any]] = []

    async def fake_token_resolver(
        session: AsyncSession, organization_id: Any
    ) -> tuple[str, IntegrationConnection]:
        return "fake-token", _connection

    async def fake_discover_and_sync(
        self: GBPDiscoveryService,
        session: AsyncSession,
        settings: Settings,
        organization_id: Any,
        *,
        actor_id: Any,
        correlation_id: str,
    ) -> None:
        discover_calls.append(
            {"organization_id": organization_id, "correlation_id": correlation_id}
        )

    monkeypatch.setattr(handlers_module, "_token_resolver", fake_token_resolver)
    monkeypatch.setattr(GBPDiscoveryService, "discover_and_sync", fake_discover_and_sync)

    # ── Create an active schedule that is ALREADY DUE ─────────────────
    due_at = datetime.now(UTC) - timedelta(minutes=1)
    service = ExecutionService()
    async with workflows_session_factory.begin() as session:
        schedule_cmd = ScheduleCreate(
            workflow_key="gbp.sync",
            key=f"p5-sched-{uuid4().hex[:12]}",
            cron_expression="0 * * * *",
            timezone="UTC",
            next_run_at=due_at,
            location_id=location_id,
        )
        await service.create_schedule(
            session, org_id, schedule_cmd, correlation_id="p5-sched-create"
        )

    # ── Scheduler dispatches (no dashboard/browser anywhere) ──────────
    settings = _build_settings(postgresql_test_url)
    runtime = create_database_runtime(settings)
    try:
        scheduler = SchedulerBackend(settings, OPTIONS, runtime)
        await scheduler.startup()
        dispatched = await scheduler.cycle()
        assert dispatched is True, "scheduler must dispatch the due schedule"

        async with workflows_session_factory() as session:
            schedule = await session.scalar(select(Schedule).where(Schedule.key.like("p5-sched-%")))
            assert schedule is not None
            schedule_id = schedule.id
            # Authoritative schedule state advanced atomically
            assert schedule.last_run_at is not None
            assert abs((schedule.last_run_at - due_at).total_seconds()) < 5
            assert schedule.next_run_at is not None
            assert schedule.next_run_at > schedule.last_run_at

            # Durable run + job created by dispatch
            run = await session.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.organization_id == org_id,
                    WorkflowRun.trigger_type == "schedule",
                )
            )
            assert run is not None
            run_id = run.id
            assert run.status == "queued"
            assert run.location_id == location_id
            job = await session.scalar(select(Job).where(Job.workflow_run_id == run_id))
            assert job is not None
            assert job.status == "queued"
            assert job.job_type == "workflow.execute"

        # ── Duplicate dispatch protection ─────────────────────────────
        dispatched_again = await scheduler.cycle()
        assert dispatched_again is False, "no schedule is due again — no duplicate dispatch"
        async with workflows_session_factory() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(WorkflowRun)
                .where(
                    WorkflowRun.organization_id == org_id,
                    WorkflowRun.trigger_type == "schedule",
                )
            )
            assert count == 1, "exactly one run per due schedule — no duplicates"

        # ── Worker claims and executes the registered handler ─────────
        worker = WorkerBackend(settings, OPTIONS, runtime)
        await worker.startup()
        worked = await worker.cycle()
        assert worked is True, "worker must claim and complete the job"

        async with workflows_session_factory() as session:
            job = await session.scalar(select(Job).where(Job.workflow_run_id == run_id))
            assert job.status == "completed", f"job terminal state: {job.status}"
            run = await session.get(WorkflowRun, run_id)
            assert run is not None
            assert run.status == "completed", f"run terminal state: {run.status}"
            assert run.started_at is not None
            assert run.completed_at is not None
            assert run.output_reference is not None

        # ── Registered handler really executed (provider boundary fake) ──
        assert len(discover_calls) == 1, "handler must have executed exactly once"
        assert discover_calls[0]["organization_id"] == org_id
        assert discover_calls[0]["correlation_id"] == f"workflow-{run_id}"

        # ── Run history is authoritative via the read-model service ───
        async with workflows_session_factory() as session:
            runs, total = await service.list_runs(session, org_id)
            assert total >= 1
            scheduled_runs = [r for r in runs if r["trigger_type"] == "schedule"]
            assert len(scheduled_runs) == 1
            row = scheduled_runs[0]
            assert row["workflow_key"] == "gbp.sync"
            assert row["status"] == "completed"
            assert row["started_at"] is not None
            assert row["completed_at"] is not None
            assert row["job_status"] == "completed"

            # ── Tenant isolation: other org sees nothing ─────────────
            other_runs, other_total = await service.list_runs(session, other_org_id)
            assert other_total == 0
            assert other_runs == []

            # ── Schedule read model reflects authoritative state ─────
            schedules = await service.list_schedules(session, org_id)
            mine = [s for s in schedules if s["id"] == str(schedule_id)]
            assert len(mine) == 1
            assert mine[0]["workflow_key"] == "gbp.sync"
            assert mine[0]["status"] == "active"
            assert mine[0]["last_run_at"] is not None
            assert mine[0]["next_run_at"] is not None
            other_schedules = await service.list_schedules(session, other_org_id)
            assert other_schedules == []

    finally:
        await runtime.dispose()


@pytest.mark.integration
@pytest.mark.anyio
async def test_schedule_dispatch_idempotency_key_is_deterministic(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-dispatching the same scheduled moment yields the same idempotency key."""
    import asyncio

    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    await asyncio.to_thread(command.upgrade, config, "head")

    async with workflows_session_factory.begin() as session:
        org, location, _gbp, _provider, _connection = await _seed_org(
            session, "Idem Test Org", f"idem-{uuid4().hex[:12]}"
        )
        org_id = org.id
        location_id = location.id

    due_at = datetime.now(UTC) - timedelta(minutes=2)
    service = ExecutionService()
    async with workflows_session_factory.begin() as session:
        await service.create_schedule(
            session,
            org_id,
            ScheduleCreate(
                workflow_key="gbp.sync",
                key=f"p5-idem-{uuid4().hex[:12]}",
                cron_expression="0 * * * *",
                timezone="UTC",
                next_run_at=due_at,
                location_id=location_id,
            ),
            correlation_id="p5-idem-create",
        )

    settings = _build_settings(postgresql_test_url)
    runtime = create_database_runtime(settings)
    try:
        scheduler = SchedulerBackend(settings, OPTIONS, runtime)
        await scheduler.startup()
        assert await scheduler.cycle() is True

        async with workflows_session_factory() as session:
            run = await session.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.organization_id == org_id,
                    WorkflowRun.trigger_type == "schedule",
                )
            )
            assert run is not None
            expected_key = (
                f"schedule:{run.input_document['schedule_id']}:"
                f"{run.input_document['scheduled_for']}"
            )
            assert run.idempotency_key == expected_key
    finally:
        await runtime.dispose()


@pytest.mark.integration
@pytest.mark.anyio
async def test_scheduled_gbp_sync_requires_location_resolution(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A schedule without a resolvable location fails cleanly, never executes the provider."""
    import asyncio

    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    await asyncio.to_thread(command.upgrade, config, "head")

    async with workflows_session_factory.begin() as session:
        org, _location, _gbp, _provider, _connection = await _seed_org(
            session, "No-Location Org", f"noloc-{uuid4().hex[:12]}"
        )
        org_id = org.id

    # Handler failure path: no gbp_location_id, no location_id
    from apps.api.app.execution.handlers import _handle_gbp_sync

    async with workflows_session_factory() as session:
        outcome = await _handle_gbp_sync(
            session,
            organization_id=org_id,
            location_id=None,
            input_document={},
            correlation_id="p5-noloc",
        )
        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "LOCATION_ID_MISSING"
