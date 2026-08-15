"""Packet 9B — claim/reclaim/sweep lease-expiry reconciliation tests.

These tests prove that a job whose lease expired is never reclaimed past
``max_attempts`` (the poison-job bug), that reclaiming closes the abandoned
attempt before opening a new one, and that the bounded sweep reconciles
abandoned leases without operator intervention.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.execution.models import (
    Job,
    JobAttempt,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from apps.api.app.execution.service import ExecutionService
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


async def _seed(
    session: AsyncSession,
    *,
    suffix: str | None = None,
    status: str,
    attempt_count: int,
    max_attempts: int,
    lease_owner: str | None,
    lease_expires_at: datetime | None,
    attempts: int,
) -> tuple[UUID, UUID]:
    _suffix = suffix or uuid4().hex[:8]
    org = Organization(
        name="Reclaim Test",
        slug=f"reclaim-test-{_suffix}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()

    definition = WorkflowDefinition(
        key=f"test.reclaim.{_suffix}", name="Reclaim Test", owner="test", status="active"
    )
    session.add(definition)
    await session.flush()
    version = WorkflowVersion(
        definition_id=definition.id,
        version=1,
        status="approved",
        input_schema={},
        output_schema={},
        step_specification=[],
        retry_policy={},
        timeout_seconds=30,
    )
    session.add(version)
    await session.flush()
    run = WorkflowRun(
        organization_id=org.id,
        workflow_version_id=version.id,
        product_key="test",
        status="queued",
        trigger_type="api",
        idempotency_key=f"reclaim-run-{_suffix}",
        request_hash="c" * 64,
        input_document={},
        correlation_id="reclaim-test",
    )
    session.add(run)
    await session.flush()
    job = Job(
        organization_id=org.id,
        workflow_run_id=run.id,
        job_type="workflow.execute",
        status=status,
        idempotency_key=f"reclaim-job-{_suffix}",
        payload={"run_id": str(run.id)},
        attempt_count=attempt_count,
        max_attempts=max_attempts,
        lease_owner=lease_owner,
        lease_expires_at=lease_expires_at,
        available_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(job)
    await session.flush()
    for number in range(1, attempts + 1):
        session.add(
            JobAttempt(
                organization_id=org.id,
                job_id=job.id,
                attempt_number=number,
                status="running",
                worker_id=f"worker-{_suffix}-{number}",
            )
        )
    await session.flush()
    return org.id, job.id


@pytest.mark.integration
@pytest.mark.anyio
async def test_job_at_max_attempts_is_dead_lettered_not_reclaimed(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    svc = ExecutionService()
    async with workflows_session_factory.begin() as session:
        _org_id, job_id = await _seed(
            session,
            status="claimed",
            attempt_count=3,
            max_attempts=3,
            lease_owner="old-worker",
            lease_expires_at=datetime.now(UTC) - timedelta(seconds=60),
            attempts=3,
        )

        claimed = await svc.claim(session, "new-worker")

        assert claimed is None, "a job at max_attempts must never be reclaimed"

        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "dead_lettered"
        assert job.lease_owner is None
        assert job.lease_expires_at is None
        assert job.attempt_count == 3, "attempt_count must not exceed max_attempts"

        attempts = (
            (
                await session.execute(
                    select(JobAttempt)
                    .where(JobAttempt.job_id == job_id)
                    .order_by(JobAttempt.attempt_number)
                )
            )
            .scalars()
            .all()
        )
        assert len(attempts) == 3
        assert all(a.status == "timed_out" for a in attempts)
        assert all(a.safe_error == "LEASE_EXPIRED" for a in attempts)
        assert all(a.completed_at is not None for a in attempts)


@pytest.mark.integration
@pytest.mark.anyio
async def test_reclaim_closes_abandoned_attempt_before_opening_new(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    svc = ExecutionService()
    async with workflows_session_factory.begin() as session:
        _org_id, job_id = await _seed(
            session,
            status="claimed",
            attempt_count=2,
            max_attempts=3,
            lease_owner="old-worker",
            lease_expires_at=datetime.now(UTC) - timedelta(seconds=60),
            attempts=2,
        )

        claimed = await svc.claim(session, "new-worker")

        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.attempt_count == 3
        assert claimed.status == "claimed"
        assert claimed.lease_owner == "new-worker"

        attempts = (
            (
                await session.execute(
                    select(JobAttempt)
                    .where(JobAttempt.job_id == job_id)
                    .order_by(JobAttempt.attempt_number)
                )
            )
            .scalars()
            .all()
        )
        assert [a.attempt_number for a in attempts] == [1, 2, 3]
        assert attempts[0].status == "timed_out"
        assert attempts[1].status == "timed_out"
        assert attempts[0].safe_error == "LEASE_EXPIRED"
        assert attempts[1].safe_error == "LEASE_EXPIRED"
        assert attempts[2].status == "running"
        assert attempts[2].worker_id == "new-worker"


@pytest.mark.integration
@pytest.mark.anyio
async def test_sweep_requeues_within_max_and_dead_letters_beyond(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    svc = ExecutionService()
    async with workflows_session_factory.begin() as session:
        _org_id, within_job_id = await _seed(
            session,
            status="claimed",
            attempt_count=2,
            max_attempts=3,
            lease_owner="worker-a",
            lease_expires_at=datetime.now(UTC) - timedelta(seconds=60),
            attempts=2,
        )
        _org_id, exhausted_job_id = await _seed(
            session,
            status="claimed",
            attempt_count=3,
            max_attempts=3,
            lease_owner="worker-b",
            lease_expires_at=datetime.now(UTC) - timedelta(seconds=60),
            attempts=3,
        )

        reconciled = await svc.sweep_abandoned_leases(session)

        assert reconciled == 2

        within = await session.get(Job, within_job_id)
        exhausted = await session.get(Job, exhausted_job_id)
        assert within is not None and exhausted is not None
        assert within.status == "retry_scheduled"
        assert within.attempt_count == 2
        assert within.lease_owner is None
        assert within.lease_expires_at is None
        assert exhausted.status == "dead_lettered"
        assert exhausted.attempt_count == 3
        assert exhausted.lease_owner is None
        assert exhausted.lease_expires_at is None

        within_attempts = (
            (await session.execute(select(JobAttempt).where(JobAttempt.job_id == within_job_id)))
            .scalars()
            .all()
        )
        exhausted_attempts = (
            (await session.execute(select(JobAttempt).where(JobAttempt.job_id == exhausted_job_id)))
            .scalars()
            .all()
        )
        assert all(a.status == "timed_out" for a in within_attempts)
        assert all(a.status == "timed_out" for a in exhausted_attempts)


@pytest.mark.integration
@pytest.mark.anyio
async def test_sweep_ignores_live_leases(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    svc = ExecutionService()
    async with workflows_session_factory.begin() as session:
        _org_id, job_id = await _seed(
            session,
            status="claimed",
            attempt_count=1,
            max_attempts=3,
            lease_owner="live-worker",
            lease_expires_at=datetime.now(UTC) + timedelta(seconds=60),
            attempts=1,
        )

        reconciled = await svc.sweep_abandoned_leases(session)

        assert reconciled == 0
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "claimed"
        assert job.lease_owner == "live-worker"
        attempts = (
            (await session.execute(select(JobAttempt).where(JobAttempt.job_id == job_id)))
            .scalars()
            .all()
        )
        assert all(a.status == "running" for a in attempts)
