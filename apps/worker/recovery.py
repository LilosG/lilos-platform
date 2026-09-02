"""Self-healing reconciliation for the production durable worker.

The worker queue and Hermes agent projection are deliberately separate durable
state machines. A process loss can therefore leave a workflow/job terminal
while its AgentRun still looks active. This module reconciles those boundaries
without weakening the one-active-Hermes-run safety invariant.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.agents.hermes_client import HermesRuntimeError
from apps.api.app.agents.models import AgentRun, AgentSession
from apps.api.app.agents.safety import safe_event_document
from apps.api.app.agents.service import ACTIVE_AGENT_STATUSES, build_hermes_runs_client
from apps.api.app.agents.skills import skill_for_workflow
from apps.api.app.ai.models import AIExecution
from apps.api.app.config import Settings
from apps.api.app.execution.models import (
    Job,
    JobAttempt,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowVersion,
)
from apps.api.app.products.seo.models import SEOWebsite

ACTIVE_JOB_STATUSES = {
    "queued",
    "claimed",
    "running",
    "retry_scheduled",
    "waiting_approval",
}
TERMINAL_JOB_STATUSES = {"completed", "cancelled", "failed", "dead_lettered"}
RECOVERABLE_FAILURES = {"HERMES_SCOPED_SESSION_BUSY", "SEO_ACTIVE_WEBSITE_MISSING"}


def _job_is_active(job: Job | None, now: datetime) -> bool:
    if job is None or job.cancellation_requested_at is not None:
        return False
    if job.status not in ACTIVE_JOB_STATUSES:
        return False
    if job.attempt_count >= job.max_attempts and job.status in {"queued", "retry_scheduled"}:
        return False
    if job.status == "claimed" and job.lease_expires_at is not None:
        return job.lease_expires_at >= now
    return True


async def _latest_job(session: AsyncSession, run: WorkflowRun) -> Job | None:
    return await session.scalar(
        select(Job)
        .where(
            Job.organization_id == run.organization_id,
            Job.workflow_run_id == run.id,
        )
        .order_by(Job.created_at.desc())
        .limit(1)
    )


async def _latest_error(session: AsyncSession, job: Job) -> str | None:
    attempt = await session.scalar(
        select(JobAttempt)
        .where(
            JobAttempt.organization_id == job.organization_id,
            JobAttempt.job_id == job.id,
        )
        .order_by(JobAttempt.attempt_number.desc())
        .limit(1)
    )
    return attempt.safe_error if attempt is not None else None


async def reconcile_exhausted_workflows(
    session: AsyncSession,
    *,
    limit: int = 200,
) -> int:
    """Close impossible retries and make workflow state agree with terminal jobs."""
    now = datetime.now(UTC)
    changed = 0

    exhausted_jobs = (
        await session.scalars(
            select(Job)
            .where(
                Job.status == "retry_scheduled",
                Job.attempt_count >= Job.max_attempts,
            )
            .order_by(Job.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    ).all()
    for job in exhausted_jobs:
        job.status = "dead_lettered"
        job.lease_owner = None
        job.lease_expires_at = None
        changed += 1

    runs = (
        await session.scalars(
            select(WorkflowRun)
            .where(WorkflowRun.status.in_(("queued", "running", "retry_scheduled")))
            .order_by(WorkflowRun.updated_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    ).all()
    for run in runs:
        job = await _latest_job(session, run)
        if job is None or _job_is_active(job, now) or job.status not in TERMINAL_JOB_STATUSES:
            continue
        if job.status == "completed":
            run.status = "completed"
            run.completed_at = run.completed_at or now
            run.output_reference = run.output_reference or job.result_reference
            run.failure_code = None
        elif job.status == "cancelled":
            run.status = "cancelled"
            run.cancelled_at = run.cancelled_at or now
        else:
            run.status = "failed"
            run.completed_at = run.completed_at or now
            run.failure_code = (await _latest_error(session, job)) or run.failure_code
        changed += 1

    await session.flush()
    return changed


async def _orphan_snapshot(
    sessions: async_sessionmaker[AsyncSession],
    agent_run_id: UUID,
) -> tuple[UUID, UUID, str | None] | None:
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        agent_run = await session.scalar(
            select(AgentRun).where(AgentRun.id == agent_run_id).with_for_update()
        )
        if agent_run is None or agent_run.status not in ACTIVE_AGENT_STATUSES:
            return None
        workflow = await session.get(WorkflowRun, agent_run.workflow_run_id)
        if workflow is None:
            return None
        job = await _latest_job(session, workflow)
        if _job_is_active(job, now):
            return None
        return agent_run.organization_id, workflow.id, agent_run.hermes_run_id


async def _apply_agent_terminal(
    sessions: async_sessionmaker[AsyncSession],
    agent_run_id: UUID,
    remote_status: str,
    *,
    safe_error: str | None = None,
    remote: dict[str, Any] | None = None,
) -> bool:
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        agent_run = await session.scalar(
            select(AgentRun).where(AgentRun.id == agent_run_id).with_for_update()
        )
        if agent_run is None or agent_run.status not in ACTIVE_AGENT_STATUSES:
            return False
        workflow = await session.get(WorkflowRun, agent_run.workflow_run_id)
        if workflow is None:
            return False
        job = await _latest_job(session, workflow)
        if _job_is_active(job, now):
            return False

        if remote_status == "completed":
            agent_run.status = "completed"
            agent_run.safe_error_code = None
            workflow.status = "completed"
            workflow.failure_code = None
            workflow.output_reference = f"agent-run:{agent_run.id}"
            workflow.completed_at = now
            if remote is not None:
                document = safe_event_document(
                    {
                        "event": "run.completed",
                        "output": remote.get("output"),
                        "usage": remote.get("usage", {}),
                    }
                )
                if document is not None:
                    output = document.get("output")
                    agent_run.final_output = (
                        {"text": output} if output is not None else {"text": ""}
                    )
                    usage = document.get("usage")
                    if isinstance(usage, dict):
                        input_tokens = usage.get("input_tokens")
                        output_tokens = usage.get("output_tokens")
                        agent_run.input_tokens = (
                            int(input_tokens) if isinstance(input_tokens, int) else None
                        )
                        agent_run.output_tokens = (
                            int(output_tokens) if isinstance(output_tokens, int) else None
                        )
        elif remote_status == "cancelled":
            agent_run.status = "cancelled"
            agent_run.safe_error_code = safe_error
            workflow.status = "cancelled"
            workflow.cancelled_at = now
            workflow.failure_code = safe_error
        else:
            agent_run.status = "failed"
            agent_run.safe_error_code = safe_error or "HERMES_ORPHANED_RUN"
            workflow.status = "failed"
            workflow.failure_code = agent_run.safe_error_code
            workflow.completed_at = now

        agent_run.completed_at = now
        if remote_status != "completed":
            scoped_session = await session.get(AgentSession, agent_run.agent_session_id)
            if scoped_session is not None:
                scoped_session.status = "expired"

        if agent_run.ai_execution_id is not None:
            execution = await session.get(AIExecution, agent_run.ai_execution_id)
            if execution is not None:
                execution.status = (
                    "completed" if remote_status == "completed" else "provider_failed"
                )
                execution.safe_error_code = agent_run.safe_error_code
                execution.output_document = agent_run.final_output
                execution.completed_at = now
        await session.flush()
        return True


async def _mark_agent_recovery_state(
    sessions: async_sessionmaker[AsyncSession],
    agent_run_id: UUID,
    *,
    status: str | None = None,
    safe_error: str,
) -> None:
    now = datetime.now(UTC)
    async with sessions() as session, session.begin():
        agent_run = await session.scalar(
            select(AgentRun).where(AgentRun.id == agent_run_id).with_for_update()
        )
        if agent_run is None or agent_run.status not in ACTIVE_AGENT_STATUSES:
            return
        workflow = await session.get(WorkflowRun, agent_run.workflow_run_id)
        if workflow is None:
            return
        job = await _latest_job(session, workflow)
        if _job_is_active(job, now):
            return
        if status is not None:
            agent_run.status = status
        agent_run.safe_error_code = safe_error
        await session.flush()


async def reconcile_orphaned_agent_runs(
    sessions: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    limit: int = 50,
) -> int:
    """Recover active AgentRuns whose durable worker job no longer exists.

    A known remote run is reconciled or stopped before the local scoped-session
    lock is released. An AgentRun with no remote identity is failed closed and
    its transcript is expired so the next legitimate run gets a clean session.
    """
    async with sessions() as session:
        candidate_ids = list(
            await session.scalars(
                select(AgentRun.id)
                .where(AgentRun.status.in_(ACTIVE_AGENT_STATUSES))
                .order_by(AgentRun.created_at)
                .limit(limit)
            )
        )

    if not candidate_ids:
        return 0

    try:
        client = build_hermes_runs_client(settings)
    except HermesRuntimeError:
        return 0

    changed = 0
    for agent_run_id in candidate_ids:
        snapshot = await _orphan_snapshot(sessions, agent_run_id)
        if snapshot is None:
            continue
        _organization_id, _workflow_run_id, hermes_run_id = snapshot
        if not hermes_run_id:
            if await _apply_agent_terminal(
                sessions,
                agent_run_id,
                "failed",
                safe_error="HERMES_ORPHANED_LOCAL_RUN",
            ):
                changed += 1
            continue

        try:
            remote = await client.get_run(hermes_run_id)
        except HermesRuntimeError:
            await _mark_agent_recovery_state(
                sessions,
                agent_run_id,
                safe_error="HERMES_RECOVERY_UNAVAILABLE",
            )
            continue

        remote_status = str(remote.get("status") or "")
        if remote_status in {"completed", "failed", "cancelled"}:
            if await _apply_agent_terminal(
                sessions,
                agent_run_id,
                remote_status,
                safe_error="HERMES_RUN_FAILED" if remote_status == "failed" else None,
                remote=remote,
            ):
                changed += 1
            continue

        try:
            await client.stop(hermes_run_id)
        except HermesRuntimeError:
            await _mark_agent_recovery_state(
                sessions,
                agent_run_id,
                safe_error="HERMES_RECOVERY_STOP_FAILED",
            )
            continue
        await _mark_agent_recovery_state(
            sessions,
            agent_run_id,
            status="stopping",
            safe_error="HERMES_ORPHANED_REMOTE_RUN_STOPPING",
        )
        changed += 1

    return changed


async def _workflow_definition(
    session: AsyncSession,
    run: WorkflowRun,
) -> tuple[WorkflowVersion, WorkflowDefinition] | None:
    version = await session.get(WorkflowVersion, run.workflow_version_id)
    if version is None:
        return None
    definition = await session.get(WorkflowDefinition, version.definition_id)
    if definition is None:
        return None
    return version, definition


async def _has_active_agent_for_workflow(
    session: AsyncSession,
    run: WorkflowRun,
    workflow_key: str,
) -> bool:
    if not workflow_key.startswith("agent."):
        return False
    skill = skill_for_workflow(workflow_key)
    active = await session.scalar(
        select(func.count())
        .select_from(AgentRun)
        .where(
            AgentRun.organization_id == run.organization_id,
            AgentRun.location_id == run.location_id,
            AgentRun.skill_key == skill.key,
            AgentRun.status.in_(ACTIVE_AGENT_STATUSES),
        )
    )
    return bool(active)


async def requeue_recoverable_failures(
    session: AsyncSession,
    *,
    limit: int = 50,
) -> int:
    """Retry failures whose prerequisite is now demonstrably healthy.

    This is intentionally narrow. Provider writes are never auto-replayed.
    Scoped-session contention is safe after its blocker has been reconciled,
    and an SEO crawl that previously had no website is safe once an active
    website exists.
    """
    runs = (
        await session.scalars(
            select(WorkflowRun)
            .where(
                WorkflowRun.status == "failed",
                WorkflowRun.failure_code.in_(RECOVERABLE_FAILURES),
            )
            .order_by(WorkflowRun.updated_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    ).all()
    created = 0
    for run in runs:
        resolved = await _workflow_definition(session, run)
        if resolved is None:
            continue
        version, definition = resolved
        if run.failure_code == "HERMES_SCOPED_SESSION_BUSY":
            if not definition.key.startswith("agent."):
                continue
            if await _has_active_agent_for_workflow(session, run, definition.key):
                continue
        elif run.failure_code == "SEO_ACTIVE_WEBSITE_MISSING":
            if definition.key != "seo.crawl_or_analysis":
                continue
            website_scope = (
                SEOWebsite.location_id == run.location_id
                if run.location_id is not None
                else SEOWebsite.location_id.is_(None)
            )
            website = await session.scalar(
                select(SEOWebsite.id).where(
                    SEOWebsite.organization_id == run.organization_id,
                    SEOWebsite.status == "active",
                    website_scope,
                )
            )
            if website is None:
                continue

        failure_code = run.failure_code
        if failure_code is None:
            continue
        recovery_key = f"run:{run.id}:auto-recovery:{failure_code.lower()}"
        existing = await session.scalar(
            select(Job.id).where(
                Job.organization_id == run.organization_id,
                Job.idempotency_key == recovery_key,
            )
        )
        if existing is not None:
            continue
        active_job = await _latest_job(session, run)
        if _job_is_active(active_job, datetime.now(UTC)):
            continue

        is_agent = definition.key.startswith("agent.")
        max_attempts = 5 if is_agent else 3
        timeout_seconds = max(version.timeout_seconds, 900) if is_agent else version.timeout_seconds
        session.add(
            Job(
                organization_id=run.organization_id,
                workflow_run_id=run.id,
                job_type="workflow.execute",
                status="queued",
                idempotency_key=recovery_key,
                payload={"run_id": str(run.id), "automatic_recovery": True},
                max_attempts=max_attempts,
                timeout_seconds=timeout_seconds,
            )
        )
        run.status = "queued"
        run.failure_code = None
        run.completed_at = None
        created += 1

    await session.flush()
    return created


async def reconcile_worker_state(
    sessions: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> dict[str, int]:
    """Run all bounded recovery passes in dependency order."""
    async with sessions() as session, session.begin():
        workflows = await reconcile_exhausted_workflows(session)

    agents = await reconcile_orphaned_agent_runs(sessions, settings)

    # Agent reconciliation may have released a scoped-session blocker. Normalize
    # workflow state once more, then safely requeue only the whitelisted cases.
    async with sessions() as session, session.begin():
        workflows += await reconcile_exhausted_workflows(session)
        requeued = await requeue_recoverable_failures(session)

    return {"workflows": workflows, "agents": agents, "requeued": requeued}
