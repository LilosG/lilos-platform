"""A retired GBP post settles its escalated publish run with a typed code, so it stops counting."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.products.gbp.operations_models import GBPPostPublication
from apps.worker.recovery import settle_unpublished_gbp_post_runs

from .test_recover_stuck_publications_gbp_reviews import _gbp_post


@pytest.mark.integration
@pytest.mark.anyio
@pytest.mark.parametrize(
    ("status", "safe_error", "code"),
    [
        ("not_published", "POST_NOT_ON_GOOGLE", "GBP_POST_NOT_PUBLISHED"),
        ("discarded", "DISCARDED_BY_OPERATOR", "GBP_POST_DISCARDED"),
        ("discarded", "REPOSTED_AS_NEW_REVISION", "GBP_POST_REPOSTED"),
    ],
)
async def test_sweep_settles_the_run_of_a_retired_post_once(
    workflows_session_factory: async_sessionmaker[AsyncSession],
    status: str,
    safe_error: str,
    code: str,
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, publication_id, run_id, _ = await _gbp_post(session)
        publication = await session.get(GBPPostPublication, publication_id)
        assert publication is not None
        publication.status = status
        publication.safe_error_code = safe_error

    async with workflows_session_factory.begin() as session:
        assert await settle_unpublished_gbp_post_runs(session) == 1

    async with workflows_session_factory() as session:
        run = await session.get(WorkflowRun, run_id)
        audits = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.organization_id == org_id,
                AuditEvent.event_type == "workflow.run.settled_cancelled",
                AuditEvent.resource_id == run_id,
            )
        )
    assert run is not None
    # Settled, not failed and not completed: it is neither a failure nor a publication.
    assert (run.status, run.failure_code) == ("cancelled", code)
    assert run.cancelled_at is not None
    assert audits == 1

    # Idempotent: nothing left to settle, and no second audit entry.
    async with workflows_session_factory.begin() as session:
        assert await settle_unpublished_gbp_post_runs(session) == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_sweep_leaves_a_run_whose_post_is_still_live(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        _, _, run_id, _ = await _gbp_post(session)  # reconciliation_required, run escalated

    async with workflows_session_factory.begin() as session:
        assert await settle_unpublished_gbp_post_runs(session) == 0

    async with workflows_session_factory() as session:
        run = await session.get(WorkflowRun, run_id)
    assert run is not None
    assert (run.status, run.failure_code) == ("escalated", "PROVIDER_WRITE_AMBIGUOUS")
