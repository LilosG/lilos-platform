"""Posts Google accepted but has not confirmed LIVE settle themselves, and are never re-created."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import Settings
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.integrations.errors import IntegrationReconnectRequiredError
from apps.api.app.products.gbp import operations_service as operations_module
from apps.api.app.products.gbp.operations_models import GBPPostPublication
from apps.api.app.products.gbp.operations_service import (
    AMBIGUOUS_POST_REREAD_DELAY,
    GBPOperationsService,
)
from apps.api.app.products.gbp.post_publish_handler import handle_gbp_publish_post
from apps.worker.recovery import reconcile_ambiguous_gbp_posts

from .test_recover_stuck_publications_gbp_reviews import CONTENT, _gbp_post

PROVIDER_POST = "accounts/1/locations/1/localPosts/9"
service = GBPOperationsService()


class FakeConnection:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    async def get_connection(self, session: AsyncSession, organization_id: UUID) -> object:
        return object()

    async def ensure_fresh_token(
        self, session: AsyncSession, settings: Settings, connection: object
    ) -> str:
        if self.error is not None:
            raise self.error
        return "fixture-token"


class FakeAdapter:
    """Answers get_local_post only; any create is a test failure."""

    def __init__(self, answer: dict[str, Any] | Exception) -> None:
        self.answer = answer
        self.reads: list[str] = []
        self.create_calls = 0

    async def get_local_post(self, access_token: str, post_name: str) -> dict[str, Any]:
        self.reads.append(post_name)
        if isinstance(self.answer, Exception):
            raise self.answer
        return {"name": post_name, **self.answer}

    async def create_local_post(self, *args: object, **kwargs: object) -> dict[str, Any]:
        self.create_calls += 1
        raise AssertionError("reconciliation must never create a post")


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.invalid")
    return httpx.HTTPStatusError(
        "provider error", request=request, response=httpx.Response(status, request=request)
    )


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    *,
    dispatched_ago: timedelta = timedelta(hours=2),
    checked_ago: timedelta = timedelta(hours=1),
) -> tuple[UUID, UUID, UUID]:
    async with factory.begin() as session:
        org_id, pub_id, run_id, _ = await _gbp_post(session)
        publication = await session.get(GBPPostPublication, pub_id)
        assert publication is not None
        publication.status = "reconciliation_required"
        publication.safe_error_code = "POST_NOT_YET_LIVE"
        publication.provider_post_id = PROVIDER_POST
        publication.dispatched_at = datetime.now(UTC) - dispatched_ago
        publication.updated_at = datetime.now(UTC) - checked_ago
    return org_id, pub_id, run_id


async def _reconcile(
    factory: async_sessionmaker[AsyncSession],
    org_id: UUID,
    pub_id: UUID,
    adapter: FakeAdapter,
    connection: FakeConnection | None = None,
) -> str:
    async with factory.begin() as session:
        return await service.auto_reconcile_accepted_post(
            session,
            Settings(),
            org_id,
            pub_id,
            adapter=adapter,  # type: ignore[arg-type]
            connection=connection or FakeConnection(),  # type: ignore[arg-type]
        )


async def _publication(
    factory: async_sessionmaker[AsyncSession], publication_id: UUID
) -> GBPPostPublication:
    async with factory() as session:
        publication = await session.get(GBPPostPublication, publication_id)
        assert publication is not None
        return publication


async def _audits(factory: async_sessionmaker[AsyncSession], org_id: UUID, event: str) -> int:
    async with factory() as session:
        return (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.organization_id == org_id, AuditEvent.event_type == event)
            )
            or 0
        )


async def _candidates(factory: async_sessionmaker[AsyncSession]) -> list[tuple[UUID, UUID]]:
    async with factory() as session:
        return await service.accepted_post_publication_ids(session)


@pytest.fixture
def patch_google(monkeypatch: pytest.MonkeyPatch) -> Callable[[FakeAdapter, FakeConnection], None]:
    def install(adapter: FakeAdapter, connection: FakeConnection) -> None:
        monkeypatch.setattr(operations_module, "gbp_adapter", lambda: adapter)
        monkeypatch.setattr(operations_module, "GBPConnectionService", lambda: connection)

    return install


@pytest.mark.integration
@pytest.mark.anyio
async def test_live_hands_off_to_the_handler_which_verifies_it(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_id, pub_id, run_id = await _seed(workflows_session_factory)
    adapter = FakeAdapter({"state": "LIVE", "postType": "STANDARD", "summary": CONTENT})

    assert await _reconcile(workflows_session_factory, org_id, pub_id, adapter) == "verifying"

    # Verification is not duplicated here: the run is resumed, nothing is marked verified yet.
    publication = await _publication(workflows_session_factory, pub_id)
    assert publication.status == "reconciliation_required"
    assert publication.verified_at is None
    async with workflows_session_factory() as session:
        run = await session.get(WorkflowRun, run_id)
        jobs = list((await session.scalars(select(Job).where(Job.workflow_run_id == run_id))).all())
    assert run is not None and run.status == "queued" and len(jobs) == 1
    assert await _audits(workflows_session_factory, org_id, "gbp.post.auto_reconciled_live") == 1

    # The resumed handler run is what settles it, from the same provider resource.
    async def token(session: AsyncSession, organization_id: UUID) -> tuple[str, object]:
        return "fixture-token", object()

    async with workflows_session_factory() as session:
        outcome = await handle_gbp_publish_post(
            session,
            organization_id=org_id,
            location_id=None,
            input_document={"publication_id": str(pub_id)},
            correlation_id="accepted-live",
            workflow_run_id=run_id,
            adapter_factory=lambda: adapter,  # type: ignore[arg-type,return-value]
            token_resolver=token,
            provider_writes_enabled=lambda: True,
        )
    assert outcome.result == "succeeded"
    publication = await _publication(workflows_session_factory, pub_id)
    assert (publication.status, publication.safe_error_code) == ("verified", None)
    assert adapter.create_calls == 0

    # Already handed off and verified: another pass changes nothing.
    assert await _reconcile(workflows_session_factory, org_id, pub_id, adapter) == "skipped"
    assert await _candidates(workflows_session_factory) == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_the_worker_loop_settles_a_production_shaped_row_on_its_first_read(
    workflows_session_factory: async_sessionmaker[AsyncSession],
    patch_google: Callable[[FakeAdapter, FakeConnection], None],
) -> None:
    # Days old, provider_post_id set, dispatched long ago: Louisiana Purchase / Miss B's.
    org_id, pub_id, run_id = await _seed(
        workflows_session_factory, dispatched_ago=timedelta(days=9), checked_ago=timedelta(days=9)
    )
    adapter = FakeAdapter({"state": "LIVE", "postType": "STANDARD", "summary": CONTENT})
    patch_google(adapter, FakeConnection())

    assert await reconcile_ambiguous_gbp_posts(workflows_session_factory, Settings()) == 1
    assert adapter.reads == [PROVIDER_POST]
    async with workflows_session_factory() as session:
        jobs = list((await session.scalars(select(Job).where(Job.workflow_run_id == run_id))).all())
    assert len(jobs) == 1
    # The second tick has nothing to do.
    assert await reconcile_ambiguous_gbp_posts(workflows_session_factory, Settings()) == 0
    assert adapter.reads == [PROVIDER_POST]
    assert adapter.create_calls == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_an_old_post_google_never_made_live_is_still_read_once_then_parked(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_id, pub_id, _ = await _seed(
        workflows_session_factory, dispatched_ago=timedelta(hours=25), checked_ago=timedelta(days=1)
    )
    adapter = FakeAdapter({"state": "PROCESSING"})

    assert await _reconcile(workflows_session_factory, org_id, pub_id, adapter) == "needs_operator"

    assert adapter.reads == [PROVIDER_POST]
    publication = await _publication(workflows_session_factory, pub_id)
    assert (publication.status, publication.safe_error_code) == (
        "reconciliation_required",
        "POST_NOT_LIVE_TIMEOUT",
    )
    assert await _candidates(workflows_session_factory) == []
    assert (
        await _audits(workflows_session_factory, org_id, "gbp.post.auto_reconcile_needs_operator")
        == 1
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_rejected_fails_the_post_and_settles_its_run(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_id, pub_id, run_id = await _seed(workflows_session_factory)
    adapter = FakeAdapter({"state": "REJECTED"})

    assert await _reconcile(workflows_session_factory, org_id, pub_id, adapter) == "failed"

    publication = await _publication(workflows_session_factory, pub_id)
    assert (publication.status, publication.safe_error_code) == (
        "failed",
        "POST_REJECTED_BY_PROVIDER",
    )
    async with workflows_session_factory() as session:
        run = await session.get(WorkflowRun, run_id)
    assert run is not None
    assert (run.status, run.failure_code) == ("cancelled", "GBP_POST_REJECTED")
    assert await _audits(workflows_session_factory, org_id, "gbp.post.auto_reconciled_rejected") == 1
    assert await _candidates(workflows_session_factory) == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_post_missing_on_google_becomes_not_published(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_id, pub_id, run_id = await _seed(workflows_session_factory)
    adapter = FakeAdapter(_http_error(404))

    assert await _reconcile(workflows_session_factory, org_id, pub_id, adapter) == "not_published"

    publication = await _publication(workflows_session_factory, pub_id)
    assert (publication.status, publication.safe_error_code) == (
        "not_published",
        "POST_NOT_ON_GOOGLE",
    )
    async with workflows_session_factory() as session:
        run = await session.get(WorkflowRun, run_id)
    assert run is not None and run.status == "cancelled"
    assert (
        await _audits(workflows_session_factory, org_id, "gbp.post.auto_reconciled_not_published")
        == 1
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_processing_post_inside_the_deadline_waits_and_is_spaced(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_id, pub_id, _ = await _seed(workflows_session_factory)
    adapter = FakeAdapter({"state": "PROCESSING"})

    assert await _reconcile(workflows_session_factory, org_id, pub_id, adapter) == "waiting"

    publication = await _publication(workflows_session_factory, pub_id)
    assert (publication.status, publication.safe_error_code) == (
        "reconciliation_required",
        "POST_NOT_YET_LIVE",
    )
    # The check was recorded, so the next one waits out the delay instead of hot-looping.
    assert datetime.now(UTC) - publication.updated_at < AMBIGUOUS_POST_REREAD_DELAY
    assert await _candidates(workflows_session_factory) == []
    assert await _reconcile(workflows_session_factory, org_id, pub_id, adapter) == "skipped"
    assert adapter.reads == [PROVIDER_POST]


@pytest.mark.integration
@pytest.mark.anyio
@pytest.mark.parametrize("error", [_http_error(503), _http_error(429), RuntimeError("boom")])
async def test_a_transient_read_failure_never_parks_the_post(
    workflows_session_factory: async_sessionmaker[AsyncSession], error: Exception
) -> None:
    # Even past the deadline, a failed read decides nothing.
    org_id, pub_id, _ = await _seed(workflows_session_factory, dispatched_ago=timedelta(hours=30))

    outcome = await _reconcile(workflows_session_factory, org_id, pub_id, FakeAdapter(error))

    assert outcome == "read_failed"
    publication = await _publication(workflows_session_factory, pub_id)
    assert (publication.status, publication.safe_error_code) == (
        "reconciliation_required",
        "POST_NOT_YET_LIVE",
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_required_reconnect_parks_the_post_for_a_person(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_id, pub_id, _ = await _seed(workflows_session_factory)
    adapter = FakeAdapter({"state": "LIVE"})

    outcome = await _reconcile(
        workflows_session_factory,
        org_id,
        pub_id,
        adapter,
        FakeConnection(IntegrationReconnectRequiredError()),
    )

    assert outcome == "needs_operator"
    assert adapter.reads == []
    publication = await _publication(workflows_session_factory, pub_id)
    assert publication.safe_error_code == "GOOGLE_RECONNECT_REQUIRED"
    assert await _candidates(workflows_session_factory) == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_two_workers_at_once_enqueue_one_recovery(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_id, pub_id, run_id = await _seed(workflows_session_factory)
    adapter = FakeAdapter({"state": "LIVE", "postType": "STANDARD", "summary": CONTENT})

    outcomes = await asyncio.gather(
        _reconcile(workflows_session_factory, org_id, pub_id, adapter),
        _reconcile(workflows_session_factory, org_id, pub_id, adapter),
    )

    assert sorted(outcomes) == ["skipped", "verifying"]
    async with workflows_session_factory() as session:
        jobs = list((await session.scalars(select(Job).where(Job.workflow_run_id == run_id))).all())
    assert len(jobs) == 1
    assert adapter.create_calls == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_only_posts_google_accepted_and_due_are_selected_and_tenant_scoped(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    org_id, pub_id, _ = await _seed(workflows_session_factory)
    other_org, other_pub, _ = await _seed(workflows_session_factory, checked_ago=timedelta(minutes=1))
    async with workflows_session_factory.begin() as session:
        never_confirmed, *_ = await _gbp_post(session)  # ambiguous: no provider_post_id
        del never_confirmed

    assert await _candidates(workflows_session_factory) == [(org_id, pub_id)]

    # Another tenant's identifiers never reach this publication.
    adapter = FakeAdapter({"state": "LIVE"})
    assert await _reconcile(workflows_session_factory, other_org, pub_id, adapter) == "skipped"
    assert await _reconcile(workflows_session_factory, org_id, other_pub, adapter) == "skipped"
    assert adapter.reads == []
