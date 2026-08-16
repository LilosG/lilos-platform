"""Packet 9C — lease renewal regression test.

Proves that a job whose handler runs longer than lease_seconds is renewed
successfully and completes without LEASE_EXPIRED. This test must fail
against the FOR UPDATE-based renew_lease that blocks on the executing
transaction.
"""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.execution import handlers
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.models import Job
from apps.api.app.execution.runtime import RuntimeOptions, WorkerBackend
from apps.api.app.execution.service import ExecutionService
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


async def _sleeping_handler(
    session: AsyncSession,
    *,
    organization_id: object,
    location_id: object,
    input_document: object,
    correlation_id: object,
) -> JobOutcome:
    del session, organization_id, location_id, input_document, correlation_id
    await asyncio.sleep(7.0)
    return JobOutcome(result="succeeded", result_reference="sleeping:done")


@pytest.mark.integration
@pytest.mark.anyio
async def test_long_running_job_renews_lease_and_completes(
    workflows_session_factory: async_sessionmaker[AsyncSession],
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A job whose handler runs longer than lease_seconds must renew
    successfully and reach ``completed`` — not ``LEASE_EXPIRED``."""
    key = "seo.crawl_or_analysis"
    previous = handlers._REGISTRY.get(key)
    handlers.register_workflow_handler(key, _sleeping_handler)
    svc = ExecutionService()
    try:
        async with workflows_session_factory.begin() as session:
            org = Organization(
                name="Lease Renewal",
                slug=f"lease-renew-{uuid4().hex[:8]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(org)
            await session.flush()
            await svc.start_named(
                session,
                org.id,
                key,
                f"lease-renew-{uuid4().hex[:8]}",
                correlation_id="lease-renew-test",
                location_id=None,
            )

        monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
        settings = Settings(
            environment=EnvironmentName.TEST,
            database_url=postgresql_test_url,
            release="lease-renew-test",
        )
        runtime = create_database_runtime(settings)
        options = RuntimeOptions(
            minimum_poll_seconds=0.01,
            maximum_poll_seconds=0.02,
            heartbeat_seconds=1,
            lease_seconds=5,
            shutdown_seconds=30,
        )
        worker = WorkerBackend(settings, options, runtime)
        await worker.startup()
        try:
            worked = await worker.cycle()
            assert worked is True
        finally:
            await worker.close()
            await runtime.dispose()

        async with workflows_session_factory.begin() as session:
            job = (
                (
                    await session.execute(
                        select(Job).where(Job.organization_id == org.id).order_by(Job.created_at)
                    )
                )
                .scalars()
                .first()
            )
            assert job is not None
            assert job.status == "completed", (
                f"expected completed, got {job.status} (attempt {job.attempt_count})"
            )
            assert job.lease_owner is None
            assert job.lease_expires_at is None
    finally:
        if previous is None:
            handlers._REGISTRY.pop(key, None)
        else:
            handlers._REGISTRY[key] = previous
