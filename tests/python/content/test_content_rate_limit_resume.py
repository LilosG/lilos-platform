"""A rate-limited content deploy resumes once after the provider's window, then stops."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.products.content.models import ContentPublication
from apps.worker.recovery import (
    CONTENT_DEPLOY_RATE_LIMIT_WINDOW,
    resume_rate_limited_content_deploys,
)

from .test_content_publish_replay import COCO_MAYA_CONTRACT, _seed


async def _rate_limited_run(
    session: AsyncSession, *, limited_ago: timedelta
) -> tuple[UUID, UUID, UUID]:
    org_id, publication_id, _item_id, _revision_id = await _seed(
        session,
        contract=COCO_MAYA_CONTRACT,
        target_path="src/content/blog/happy-hour.mdx",
        frontmatter={"title": "Happy Hour", "description": "Find a happy hour."},
    )
    publication = await session.get(ContentPublication, publication_id)
    assert publication is not None
    publication.status = "deployment_pending"
    publication.safe_error_code = "CONTENT_DEPLOYMENT_RATE_LIMITED"
    run = await session.get(WorkflowRun, publication.workflow_run_id)
    assert run is not None
    version = await ExecutionService()._resolve_workflow_version(  # noqa: SLF001
        session, "content.publish"
    )
    run.workflow_version_id = version.id
    run.status = "failed"
    run.failure_code = "CONTENT_DEPLOYMENT_RATE_LIMITED"
    run.completed_at = datetime.now(UTC) - limited_ago
    await session.flush()
    return org_id, publication_id, run.id


async def _jobs(factory: async_sessionmaker[AsyncSession], run_id: UUID) -> list[Job]:
    async with factory() as session:
        return list(await session.scalars(select(Job).where(Job.workflow_run_id == run_id)))


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_rate_limited_deploy_waits_out_the_window_before_resuming(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with content_session_factory.begin() as session:
        _, _, run_id = await _rate_limited_run(session, limited_ago=timedelta(hours=3))

    async with content_session_factory.begin() as session:
        assert await resume_rate_limited_content_deploys(session) == 0

    assert await _jobs(content_session_factory, run_id) == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_rate_limited_deploy_resumes_exactly_once_and_never_loops(
    content_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with content_session_factory.begin() as session:
        org_id, _, run_id = await _rate_limited_run(
            session, limited_ago=CONTENT_DEPLOY_RATE_LIMIT_WINDOW + timedelta(minutes=1)
        )

    async with content_session_factory.begin() as session:
        assert await resume_rate_limited_content_deploys(session) == 1

    [job] = await _jobs(content_session_factory, run_id)
    assert job.status == "queued"
    assert job.max_attempts == 30
    async with content_session_factory() as session:
        run = await session.get(WorkflowRun, run_id)
        assert run is not None and run.status == "queued"
        audits = list(
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.organization_id == org_id,
                    AuditEvent.event_type == "workflow.run.automatic_resume_enqueued",
                )
            )
        )
        assert len(audits) == 1

    # Vercel limits it again: the run fails with the same code. It is not resumed a second time.
    async with content_session_factory.begin() as session:
        run = await session.get(WorkflowRun, run_id)
        assert run is not None
        run.status = "failed"
        run.failure_code = "CONTENT_DEPLOYMENT_RATE_LIMITED"
        run.completed_at = datetime.now(UTC) - CONTENT_DEPLOY_RATE_LIMIT_WINDOW - timedelta(hours=1)
        job_row = await session.get(Job, job.id)
        assert job_row is not None
        job_row.status = "dead_lettered"
    async with content_session_factory.begin() as session:
        assert await resume_rate_limited_content_deploys(session) == 0
    assert len(await _jobs(content_session_factory, run_id)) == 1
