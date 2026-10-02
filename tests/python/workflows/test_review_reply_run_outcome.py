"""A review-reply run ends with the real outcome of the reply.

Production: 72 `reviews.publish_response` runs ended `failed` with VERIFICATION_CONTENT_PENDING
because Google had not shown the reply when the three attempts ran out, while 71 of those
replies were published later. Driven here through the real worker, recovery sweep and handler;
only the Google adapter is faked.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import PostgresDsn, TypeAdapter
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.execution import handlers as handlers_module
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.execution.runtime import RuntimeOptions, WorkerBackend
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import (
    IntegrationConnection,
    Provider,
    ProviderResourceMapping,
)
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.reviews.models import Review, ReviewResponseRevision, ReviewRevision
from apps.worker.recovery import reconcile_worker_state

APPROVED = "Thank you for the thoughtful review."
OPTIONS = RuntimeOptions(
    minimum_poll_seconds=0.01,
    maximum_poll_seconds=0.02,
    heartbeat_seconds=0.01,
    lease_seconds=60,
    shutdown_seconds=5,
)


class GoogleStub:
    """Google accepts the reply; whether it shows up in reads is up to the test."""

    def __init__(self) -> None:
        self.updates = 0
        self.visible = False

    async def update_review_reply(
        self, token: str, review_name: str, comment: str
    ) -> dict[str, Any]:
        self.updates += 1
        return {"comment": comment}

    async def get_review(self, token: str, review_name: str) -> dict[str, Any]:
        if not self.visible:
            return {}
        return {"reviewReply": {"comment": APPROVED, "reviewReplyState": "APPROVED"}}


async def _seed(session: AsyncSession) -> tuple[UUID, UUID, UUID, IntegrationConnection]:
    org = Organization(
        name="Reply outcome",
        slug=f"reply-outcome-{uuid4().hex[:8]}",
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
        slug="downtown",
        location_type=LocationType.VIRTUAL,
        status=LocationStatus.ACTIVE,
        timezone="UTC",
        country_code="US",
        website_url="https://example.invalid",
        is_primary=True,
        version=1,
    )
    provider = Provider(
        key=f"google-{uuid4().hex[:6]}",
        name="Google",
        status="active",
        capabilities=["reviews.read"],
        manifest_version=1,
    )
    session.add_all([location, provider])
    await session.flush()
    connection = IntegrationConnection(
        organization_id=org.id,
        provider_id=provider.id,
        external_account_reference="accounts/1",
        status="connected",
        version=1,
    )
    session.add(connection)
    await session.flush()
    account = GBPAccount(
        organization_id=org.id,
        connection_id=connection.id,
        external_account_id="accounts/1",
        display_name="Account",
        status="selected",
    )
    mapping = ProviderResourceMapping(
        organization_id=org.id,
        connection_id=connection.id,
        resource_type="location",
        external_resource_id="locations/1",
        platform_resource_id=location.id,
        status="active",
    )
    session.add_all([account, mapping])
    await session.flush()
    session.add(
        GBPLocation(
            organization_id=org.id,
            location_id=location.id,
            connection_id=connection.id,
            account_id=account.id,
            integration_resource_id=mapping.id,
            external_location_id="locations/1",
            business_name="Business",
            mapping_status="confirmed",
            write_enabled=True,
        )
    )
    review = Review(
        organization_id=org.id,
        location_id=location.id,
        integration_resource_id=mapping.id,
        external_review_id=f"review-{uuid4().hex[:6]}",
        provider="google",
        rating=5,
        status="publishing",
        review_created_at=datetime.now(UTC),
    )
    session.add(review)
    await session.flush()
    revision = ReviewRevision(
        organization_id=org.id,
        review_id=review.id,
        revision_number=1,
        rating=5,
        body="Great!",
        content_hash="a" * 64,
    )
    session.add(revision)
    await session.flush()
    response = ReviewResponseRevision(
        organization_id=org.id,
        location_id=location.id,
        review_id=review.id,
        review_revision_id=revision.id,
        revision_number=1,
        response_text=APPROVED,
        content_hash="b" * 64,
        status="publishing",
        generated_by_type="manual",
        approved_fact_revision_ids=[],
    )
    session.add(response)
    await session.flush()
    run = await ExecutionService().start_named(
        session,
        org.id,
        "reviews.publish_response",
        f"reply-{uuid4().hex}",
        location_id=location.id,
        input_document={"response_id": str(response.id)},
        correlation_id="reply-outcome",
    )
    return org.id, response.id, run.id, connection


class Harness:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        worker: WorkerBackend,
        runtime: Any,
    ) -> None:
        self.factory = factory
        self.settings = settings
        self.worker = worker
        self.runtime = runtime

    async def attempt(self) -> None:
        """Run the next job attempt now, without waiting out the retry backoff."""
        async with self.factory.begin() as session:
            await session.execute(
                update(Job)
                .where(Job.status == "retry_scheduled")
                .values(available_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        assert await self.worker.cycle() is True

    async def sweep(self) -> dict[str, int]:
        return await reconcile_worker_state(self.factory, self.settings)

    async def state(
        self, run_id: UUID, response_id: UUID
    ) -> tuple[str, str | None, str, str | None]:
        async with self.factory() as session:
            run = await session.get(WorkflowRun, run_id)
            response = await session.get(ReviewResponseRevision, response_id)
            assert run is not None and response is not None
            return run.status, run.failure_code, response.status, response.safe_error_code


@pytest.fixture
async def harness(
    postgresql_test_url: str,
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> Any:
    settings = Settings(
        environment=EnvironmentName.TEST,
        database_url=TypeAdapter(PostgresDsn).validate_python(postgresql_test_url),
        release="reply-outcome-test",
        provider_writes_enabled=True,
    )
    runtime = create_database_runtime(settings)
    worker = WorkerBackend(settings, OPTIONS, runtime)
    await worker.startup()
    try:
        yield Harness(workflows_session_factory, settings, worker, runtime)
    finally:
        await runtime.dispose()


def _google(monkeypatch: pytest.MonkeyPatch, connection: IntegrationConnection) -> GoogleStub:
    google = GoogleStub()

    async def token(
        session: AsyncSession, organization_id: UUID
    ) -> tuple[str, IntegrationConnection]:
        return "token", connection

    monkeypatch.setattr(handlers_module, "_adapter_factory", lambda: google)
    monkeypatch.setattr(handlers_module, "_token_resolver", token)
    monkeypatch.setattr(handlers_module, "_google_writes_enabled", lambda: True)
    return google


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_reply_that_appears_after_the_attempts_ran_out_completes_the_run_without_rewriting(
    harness: Harness,
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with workflows_session_factory.begin() as session:
        _org, response_id, run_id, connection = await _seed(session)
    google = _google(monkeypatch, connection)

    # Three attempts: Google accepted the reply but does not show it yet.
    for _ in range(3):
        await harness.attempt()
    assert google.updates == 1
    assert await harness.state(run_id, response_id) == (
        "retry_scheduled",
        "VERIFICATION_CONTENT_PENDING",
        "reconciliation_required",
        "VERIFICATION_CONTENT_PENDING",
    )

    # The recovery sweep sees an exhausted job, and queues one read-only verification.
    assert (await harness.sweep())["requeued"] == 1
    assert (await harness.state(run_id, response_id))[0] == "queued"

    # Google now shows the reply.
    google.visible = True
    await harness.attempt()

    assert await harness.state(run_id, response_id) == ("completed", None, "published", None)
    assert google.updates == 1  # verification never wrote a second time
    async with workflows_session_factory() as session:
        review = await session.scalar(select(Review).where(Review.status.is_not(None)))
        assert review is not None and review.status == "responded"


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_reply_that_never_appears_leaves_the_run_failed_and_is_not_asked_forever(
    harness: Harness,
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with workflows_session_factory.begin() as session:
        _org, response_id, run_id, connection = await _seed(session)
    google = _google(monkeypatch, connection)

    for _ in range(3):
        await harness.attempt()
    assert (await harness.sweep())["requeued"] == 1
    for _ in range(3):
        await harness.attempt()
    second = await harness.sweep()

    assert second["requeued"] == 0  # one automatic read-only re-verification per run
    assert await harness.state(run_id, response_id) == (
        "failed",
        "VERIFICATION_CONTENT_PENDING",
        "reconciliation_required",
        "VERIFICATION_CONTENT_PENDING",
    )
    assert google.updates == 1
    assert (await harness.sweep())["requeued"] == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_failed_run_is_completed_once_a_later_pass_confirms_the_reply(
    harness: Harness,
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with workflows_session_factory.begin() as session:
        _org, response_id, run_id, connection = await _seed(session)
        _org2, other_response_id, other_run_id, _c2 = await _seed(session)
    _google(monkeypatch, connection)
    # Two runs, three attempts each, then the one automatic re-verification, then failure.
    for _round in range(2):
        for _attempt in range(6):
            await harness.attempt()
        await harness.sweep()
    assert (await harness.state(run_id, response_id))[0] == "failed"
    assert (await harness.state(other_run_id, other_response_id))[0] == "failed"

    # Review ingestion later confirms the first reply (it has its own reconciliation).
    async with workflows_session_factory.begin() as session:
        response = await session.get(ReviewResponseRevision, response_id)
        assert response is not None
        response.status = "published"
        response.safe_error_code = None
        response.published_at = datetime.now(UTC)

    await harness.sweep()

    assert await harness.state(run_id, response_id) == ("completed", None, "published", None)
    # The reply that never published stays failed.
    assert (await harness.state(other_run_id, other_response_id))[0] == "failed"
    async with workflows_session_factory() as session:
        completed = list(
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.resource_id == run_id,
                    AuditEvent.event_type == "workflow.run.completed",
                )
            )
        )
        run = await session.get(WorkflowRun, run_id)
    assert len(completed) == 1
    assert run is not None and run.output_reference == f"response:{response_id}"
