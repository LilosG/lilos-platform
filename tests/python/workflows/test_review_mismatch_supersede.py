"""A mismatched review reply is retired automatically only when the review is already answered."""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision
from apps.api.app.products.reviews.service import ReviewService
from apps.worker.recovery import REVIEW_REPLY_SUPERSEDED, settle_confirmed_review_replies

from .test_review_reply_run_outcome import _seed


async def _park_as_mismatch(session: AsyncSession, response_id: UUID) -> ReviewResponseRevision:
    response = await session.get(ReviewResponseRevision, response_id)
    assert response is not None
    response.status = "reconciliation_required"
    response.safe_error_code = "VERIFICATION_CONTENT_MISMATCH"
    review = await session.get(Review, response.review_id)
    assert review is not None
    review.status = "publication_failed"
    return response


def _published_revision(response: ReviewResponseRevision) -> ReviewResponseRevision:
    return ReviewResponseRevision(
        organization_id=response.organization_id,
        location_id=response.location_id,
        review_id=response.review_id,
        review_revision_id=response.review_revision_id,
        revision_number=response.revision_number + 1,
        response_text="Thanks for visiting.",
        content_hash="c" * 64,
        status="published",
        generated_by_type="manual",
        approved_fact_revision_ids=[],
        external_response_id="accounts/1/locations/1/reviews/r1",
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_mismatch_beside_a_published_revision_is_superseded_with_an_audit_entry(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, response_id, _, _ = await _seed(session)
        response = await _park_as_mismatch(session, response_id)
        session.add(_published_revision(response))
        review_id = response.review_id

    async with workflows_session_factory.begin() as session:
        assert await ReviewService().supersede_mismatched_responses(session) == 1

    async with workflows_session_factory() as session:
        retired = await session.get(ReviewResponseRevision, response_id)
        review = await session.get(Review, review_id)
        audits = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.organization_id == org_id,
                AuditEvent.event_type == "reviews.response.superseded_by_published_revision",
                AuditEvent.resource_id == response_id,
            )
        )
    assert retired is not None and review is not None
    assert (retired.status, retired.safe_error_code) == ("superseded", None)
    assert review.status == "responded"
    assert audits == 1

    # Idempotent: nothing left to retire, and no second audit entry.
    async with workflows_session_factory.begin() as session:
        assert await ReviewService().supersede_mismatched_responses(session) == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_mismatch_with_no_published_revision_stays_for_a_person(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        _, response_id, _, _ = await _seed(session)
        await _park_as_mismatch(session, response_id)

    async with workflows_session_factory.begin() as session:
        assert await ReviewService().supersede_mismatched_responses(session) == 0

    async with workflows_session_factory() as session:
        response = await session.get(ReviewResponseRevision, response_id)
    assert response is not None
    assert (response.status, response.safe_error_code) == (
        "reconciliation_required",
        "VERIFICATION_CONTENT_MISMATCH",
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_published_revision_of_another_review_does_not_supersede_a_mismatch(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        _, mismatched_id, _, _ = await _seed(session)
        await _park_as_mismatch(session, mismatched_id)
        _, other_id, _, _ = await _seed(session)
        other = await session.get(ReviewResponseRevision, other_id)
        assert other is not None
        other.status = "published"

    async with workflows_session_factory.begin() as session:
        assert await ReviewService().supersede_mismatched_responses(session) == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_the_failed_run_of_a_superseded_reply_is_settled_with_a_typed_code(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, response_id, run_id, _ = await _seed(session)
        response = await _park_as_mismatch(session, response_id)
        session.add(_published_revision(response))
        run = await session.get(WorkflowRun, run_id)
        assert run is not None
        run.status = "failed"
        run.failure_code = "VERIFICATION_CONTENT_MISMATCH"

    # Before the reply is superseded the run stays failed: a person still owns it.
    async with workflows_session_factory.begin() as session:
        assert await settle_confirmed_review_replies(session) == 0

    async with workflows_session_factory.begin() as session:
        assert await ReviewService().supersede_mismatched_responses(session) == 1
    async with workflows_session_factory.begin() as session:
        assert await settle_confirmed_review_replies(session) == 1

    async with workflows_session_factory() as session:
        run = await session.get(WorkflowRun, run_id)
        audit = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.organization_id == org_id,
                AuditEvent.event_type == "workflow.run.completed",
                AuditEvent.resource_id == run_id,
            )
        )
    assert run is not None and audit is not None
    assert (run.status, run.failure_code) == ("completed", None)
    assert audit.event_metadata["safe_error"] == REVIEW_REPLY_SUPERSEDED

    # Settled once; not a workflow failure any more, and a second pass changes nothing.
    async with workflows_session_factory.begin() as session:
        assert await settle_confirmed_review_replies(session) == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_superseded_reply_with_no_published_revision_keeps_its_run_failed(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        _, response_id, run_id, _ = await _seed(session)
        response = await session.get(ReviewResponseRevision, response_id)
        run = await session.get(WorkflowRun, run_id)
        assert response is not None and run is not None
        response.status = "superseded"
        run.status = "failed"
        run.failure_code = "VERIFICATION_CONTENT_MISMATCH"

    async with workflows_session_factory.begin() as session:
        assert await settle_confirmed_review_replies(session) == 0
