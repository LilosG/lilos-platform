"""A busy Hermes scoped session must not consume a job's claim attempt.

Before this, `HERMES_SCOPED_SESSION_BUSY` was only discovered after
`claim()` already incremented `attempt_count` and opened a `JobAttempt`, so
a sibling action in the same (organization, location, skill) scope burned
through its bounded retries while the winning Hermes run was still active.
`ExecutionService.claim` now checks the scope before claiming and defers the
job instead.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.agents.models import AgentRun, AgentSession
from apps.api.app.execution.models import Job, WorkflowDefinition, WorkflowRun, WorkflowVersion
from apps.api.app.execution.service import ExecutionService
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization


async def _seed_agent_job(
    session: AsyncSession,
    *,
    workflow_key: str = "agent.seo",
    skill_key: str = "seo.operator",
) -> tuple[UUID, UUID, UUID]:
    """Seed one organization with an active Hermes scoped session and one
    queued `agent.*` job targeting that same scope. Returns
    (organization_id, job_id, agent_session_id)."""
    suffix = uuid4().hex[:8]
    org = Organization(
        name="Hermes Scope Claim",
        slug=f"hermes-scope-{suffix}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()

    definition = await session.scalar(
        select(WorkflowDefinition).where(WorkflowDefinition.key == workflow_key)
    )
    if definition is None:
        definition = WorkflowDefinition(
            key=workflow_key, name="Test Agent Workflow", owner="test", status="active"
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
        timeout_seconds=900,
    )
    session.add(version)
    await session.flush()

    now = datetime.now(UTC)
    agent_session = AgentSession(
        organization_id=org.id,
        location_id=None,
        skill_key=skill_key,
        namespace_hash=f"hash-{suffix}",
        hermes_session_key=f"lilos_mem_{suffix}",
        status="active",
        expires_at=now + timedelta(days=1),
        version=1,
    )
    session.add(agent_session)
    await session.flush()

    busy_run = WorkflowRun(
        organization_id=org.id,
        workflow_version_id=version.id,
        product_key="seo",
        status="running",
        trigger_type="api",
        idempotency_key=f"hermes-scope-busy-{suffix}",
        request_hash="a" * 64,
        input_document={},
        correlation_id="hermes-scope-busy",
    )
    session.add(busy_run)
    await session.flush()
    session.add(
        AgentRun(
            organization_id=org.id,
            location_id=None,
            workflow_run_id=busy_run.id,
            agent_session_id=agent_session.id,
            skill_key=skill_key,
            skill_version=1,
            hermes_session_id=agent_session.hermes_session_key,
            correlation_id="hermes-scope-busy",
            status="running",
            capability_snapshot={},
            output_references=[],
        )
    )

    waiting_run = WorkflowRun(
        organization_id=org.id,
        workflow_version_id=version.id,
        product_key="seo",
        status="queued",
        trigger_type="api",
        idempotency_key=f"hermes-scope-waiting-{suffix}",
        request_hash="b" * 64,
        input_document={},
        correlation_id="hermes-scope-waiting",
    )
    session.add(waiting_run)
    await session.flush()
    job = Job(
        organization_id=org.id,
        workflow_run_id=waiting_run.id,
        job_type="workflow.execute",
        status="queued",
        idempotency_key=f"hermes-scope-waiting-job-{suffix}",
        payload={"run_id": str(waiting_run.id)},
        attempt_count=0,
        max_attempts=5,
        available_at=now - timedelta(seconds=1),
    )
    session.add(job)
    await session.flush()
    return org.id, job.id, agent_session.id


@pytest.mark.integration
@pytest.mark.anyio
async def test_claim_defers_job_blocked_by_busy_scoped_session_without_consuming_attempt(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        _org_id, job_id, _agent_session_id = await _seed_agent_job(session)

    service = ExecutionService()
    async with workflows_session_factory.begin() as session:
        claimed = await service.claim(session, worker_id="worker-1")

    assert claimed is None

    async with workflows_session_factory() as session:
        job = await session.get(Job, job_id)
        assert job is not None
        assert job.status == "queued"
        assert job.attempt_count == 0
        assert job.lease_owner is None
        assert job.available_at > datetime.now(UTC)


@pytest.mark.integration
@pytest.mark.anyio
async def test_claim_succeeds_once_the_scoped_session_frees_up(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        _org_id, job_id, _agent_session_id = await _seed_agent_job(session)

    # The busy run completes.
    async with workflows_session_factory.begin() as session:
        busy_agent_run = await session.scalar(
            select(AgentRun).where(AgentRun.status == "running")
        )
        assert busy_agent_run is not None
        busy_agent_run.status = "completed"

    service = ExecutionService()
    async with workflows_session_factory.begin() as session:
        claimed = await service.claim(session, worker_id="worker-1")

    assert claimed is not None
    assert claimed.id == job_id
    assert claimed.status == "claimed"
    assert claimed.attempt_count == 1
