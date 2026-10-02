"""scripts.recover_stuck_publications: Business Profile posts and review replies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import Settings
from apps.api.app.execution import handlers as handlers_module
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.gbp.discovery_service import GBPDiscoveryService
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.gbp.operations_models import (
    GBPPostPublication,
    GBPPostRevision,
    GBPProviderPost,
)
from apps.api.app.products.reviews.models import ReviewResponseRevision
from scripts.recover_stuck_publications import Action, Kind, recover_stuck_publications

from .test_review_reply_run_outcome import APPROVED, GoogleStub, _seed  # noqa: F401

CONTENT = "Fresh gumbo and live music this Friday."


async def _gbp_post(
    session: AsyncSession, *, name: str = "Louisiana Purchase"
) -> tuple[UUID, UUID, UUID, UUID]:
    org = Organization(
        name=name,
        slug=f"gbp-recovery-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    profile = UserProfile(auth_user_id=uuid4(), status="active", version=1)
    session.add_all([org, profile])
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
        capabilities=[],
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
    session.add(account)
    await session.flush()
    gbp_location = GBPLocation(
        organization_id=org.id,
        location_id=location.id,
        connection_id=connection.id,
        account_id=account.id,
        external_location_id="locations/1",
        business_name="Business",
        mapping_status="confirmed",
        write_enabled=True,
        confirmed_by_user_id=profile.id,
        confirmed_at=datetime.now(UTC),
    )
    session.add(gbp_location)
    await session.flush()
    revision = GBPPostRevision(
        organization_id=org.id,
        gbp_location_id=gbp_location.id,
        post_key=uuid4(),
        revision=1,
        post_type="STANDARD",
        content=CONTENT,
        status="approved",
        created_at=datetime.now(UTC),
    )
    session.add(revision)
    version = await ExecutionService()._resolve_workflow_version(session, "gbp.publish_post")
    await session.flush()
    run = WorkflowRun(
        organization_id=org.id,
        location_id=location.id,
        workflow_version_id=version.id,
        product_key="gbp",
        status="escalated",
        failure_code="PROVIDER_WRITE_AMBIGUOUS",
        trigger_type="api",
        idempotency_key=f"gbp-run-{uuid4().hex[:8]}",
        request_hash="c" * 64,
        input_document={},
        correlation_id="gbp-recovery",
    )
    session.add(run)
    await session.flush()
    dispatched = datetime.now(UTC) - timedelta(hours=2)
    publication = GBPPostPublication(
        organization_id=org.id,
        post_revision_id=revision.id,
        workflow_run_id=run.id,
        idempotency_key=f"gbp-pub-{uuid4().hex[:8]}",
        status="reconciliation_required",
        safe_error_code="PROVIDER_WRITE_AMBIGUOUS",
        dispatched_at=dispatched,
    )
    session.add(publication)
    await session.flush()
    run.input_document = {"publication_id": str(publication.id)}
    return org.id, publication.id, run.id, gbp_location.id


def _provider_post(
    organization_id: UUID, gbp_location_id: UUID, *, name: str, summary: str
) -> GBPProviderPost:
    created = datetime.now(UTC) - timedelta(hours=2) + timedelta(seconds=5)
    return GBPProviderPost(
        organization_id=organization_id,
        gbp_location_id=gbp_location_id,
        provider_post_name=name,
        post_type="STANDARD",
        state="LIVE",
        summary=summary,
        provider_payload={"createTime": created.isoformat()},
        content_hash=uuid4().hex + uuid4().hex,
        status="present",
        first_seen_at=created,
        observed_at=created,
    )


@pytest.fixture
def no_google_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Local Posts read is out of scope; the provider posts are seeded as already read."""

    async def reconciled(*args: object, **kwargs: object) -> dict[str, int | str]:
        return {}

    monkeypatch.setattr(GBPDiscoveryService, "reconcile_local_posts", reconciled)


async def _state(
    factory: async_sessionmaker[AsyncSession], publication_id: UUID, run_id: UUID
) -> tuple[str, str | None, str, int]:
    async with factory() as session:
        publication = await session.get(GBPPostPublication, publication_id)
        run = await session.get(WorkflowRun, run_id)
        jobs = list(await session.scalars(select(Job).where(Job.workflow_run_id == run_id)))
        assert publication is not None and run is not None
        return publication.status, publication.provider_post_id, run.status, len(jobs)


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_post_google_shows_is_matched_and_its_run_resumed_only_on_apply(
    workflows_session_factory: async_sessionmaker[AsyncSession], no_google_read: None
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, publication_id, run_id, gbp_location_id = await _gbp_post(session)
        session.add(
            _provider_post(
                org_id, gbp_location_id, name="accounts/1/locations/1/localPosts/9", summary=CONTENT
            )
        )

    dry = await recover_stuck_publications(
        workflows_session_factory, Settings(), apply=False, organization_id=org_id
    )

    [item] = dry.items
    assert (item.kind, item.action) == (Kind.GBP_POST, Action.RESUME)
    assert "provider_match" in item.detail
    assert await _state(workflows_session_factory, publication_id, run_id) == (
        "reconciliation_required",
        None,
        "escalated",
        0,
    )

    applied = await recover_stuck_publications(
        workflows_session_factory,
        Settings(),
        apply=True,
        actor_id=uuid4(),
        organization_id=org_id,
    )

    assert [i.action for i in applied.items] == [Action.RESUME]
    status, provider_post_id, run_status, jobs = await _state(
        workflows_session_factory, publication_id, run_id
    )
    assert provider_post_id == "accounts/1/locations/1/localPosts/9"
    assert (run_status, jobs) == ("queued", 1)
    assert status == "reconciliation_required"  # the resumed run verifies it, not the script


@pytest.mark.integration
@pytest.mark.anyio
async def test_an_ambiguous_google_result_is_left_for_an_operator(
    workflows_session_factory: async_sessionmaker[AsyncSession], no_google_read: None
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, publication_id, run_id, gbp_location_id = await _gbp_post(session)
        # Google shows nothing that matches this revision.
        session.add(
            _provider_post(
                org_id,
                gbp_location_id,
                name="accounts/1/locations/1/localPosts/1",
                summary="Something else entirely",
            )
        )

    report = await recover_stuck_publications(
        workflows_session_factory,
        Settings(),
        apply=True,
        actor_id=uuid4(),
        organization_id=org_id,
    )

    [item] = report.items
    assert (item.action, item.detail) == (Action.OPERATOR, "denial=AMBIGUOUS_PROVIDER_RESULT")
    assert await _state(workflows_session_factory, publication_id, run_id) == (
        "reconciliation_required",
        None,
        "escalated",
        0,
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_review_reply_google_now_shows_is_resumed_for_verification_only(
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, response_id, run_id, connection = await _seed(session)
        response = await session.get(ReviewResponseRevision, response_id)
        assert response is not None
        response.status = "reconciliation_required"
        response.safe_error_code = "VERIFICATION_CONTENT_PENDING"
        response.external_response_id = "accounts/1/locations/1/reviews/r"
        run = await session.get(WorkflowRun, run_id)
        assert run is not None
        run.status = "failed"
        run.failure_code = "VERIFICATION_CONTENT_PENDING"
        # Its job ran out of attempts, as in production.
        for job in await session.scalars(select(Job).where(Job.workflow_run_id == run.id)):
            job.status = "dead_lettered"

    google = GoogleStub()

    async def token(
        session: AsyncSession, organization_id: UUID
    ) -> tuple[str, IntegrationConnection]:
        return "token", connection

    monkeypatch.setattr(handlers_module, "_adapter_factory", lambda: google)
    monkeypatch.setattr(handlers_module, "_token_resolver", token)
    monkeypatch.setattr(handlers_module, "_google_writes_enabled", lambda: True)

    # Google does not show the reply yet: nothing to resume.
    waiting = await recover_stuck_publications(
        workflows_session_factory,
        Settings(),
        apply=True,
        actor_id=uuid4(),
        organization_id=org_id,
    )
    [item] = waiting.items
    assert (item.kind, item.action) == (Kind.REVIEW_REPLY, Action.WAIT)
    assert item.detail == "VERIFICATION_CONTENT_PENDING"

    google.visible = True
    dry = await recover_stuck_publications(
        workflows_session_factory, Settings(), apply=False, organization_id=org_id
    )
    assert [i.action for i in dry.items] == [Action.RESUME]
    async with workflows_session_factory() as session:
        assert (await session.get(WorkflowRun, run_id)).status == "failed"  # type: ignore[union-attr]

    resumed = await recover_stuck_publications(
        workflows_session_factory,
        Settings(),
        apply=True,
        actor_id=uuid4(),
        organization_id=org_id,
    )
    assert [i.action for i in resumed.items] == [Action.RESUME]
    async with workflows_session_factory() as session:
        run = await session.get(WorkflowRun, run_id)
        assert run is not None and run.status == "queued"

    # The resumed run only verifies: it publishes the response without sending a reply.
    from apps.api.app.products.reviews.publish_handler import handle_reviews_publish_response

    async with workflows_session_factory() as session:
        outcome = await handle_reviews_publish_response(
            session,
            organization_id=org_id,
            location_id=None,
            input_document={"response_id": str(response_id)},
            correlation_id="recovery",
            workflow_run_id=run_id,
        )
    assert outcome.result == "succeeded"
    assert google.updates == 0
    async with workflows_session_factory() as session:
        response = await session.get(ReviewResponseRevision, response_id)
        assert response is not None and response.status == "published"


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_failing_provider_read_is_reported_per_item_and_does_not_stop_the_rest(
    workflows_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, publication_id, run_id, gbp_location_id = await _gbp_post(session)
        other_org, other_pub, other_run, other_location = await _gbp_post(session, name="Other")
        session.add(
            _provider_post(
                other_org,
                other_location,
                name="accounts/1/locations/1/localPosts/2",
                summary=CONTENT,
            )
        )

    async def read(
        self: Any, session: Any, settings: Any, organization_id: UUID, *a: Any, **k: Any
    ) -> Any:
        if organization_id == org_id:
            raise RuntimeError("Google is down")
        return {}

    monkeypatch.setattr(GBPDiscoveryService, "reconcile_local_posts", read)

    report = await recover_stuck_publications(
        workflows_session_factory, Settings(), apply=True, actor_id=uuid4()
    )

    by_org = {item.organization_id: item for item in report.items}
    assert by_org[org_id].action is Action.ERROR
    assert by_org[org_id].detail == "RuntimeError"
    assert by_org[other_org].action is Action.RESUME
    assert (await _state(workflows_session_factory, publication_id, run_id))[3] == 0
    assert (await _state(workflows_session_factory, other_pub, other_run))[3] == 1
