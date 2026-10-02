"""Ambiguous GBP post results settle themselves; `not_published` posts get Repost and Discard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import Settings
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.products.gbp.discovery_service import GBPDiscoveryService
from apps.api.app.products.gbp.models import GBPLocation
from apps.api.app.products.gbp.operations_errors import (
    GBPPostPublicationNotActionableError,
    GBPPostRevisionNotFoundError,
)
from apps.api.app.products.gbp.operations_models import GBPPostPublication, GBPPostRevision
from apps.api.app.products.gbp.operations_service import GBPOperationsService
from apps.worker.recovery import reconcile_ambiguous_gbp_posts

from .test_recover_stuck_publications_gbp_reviews import CONTENT, _gbp_post, _provider_post

PROVIDER_POST = "accounts/1/locations/1/localPosts/9"
service = GBPOperationsService()


@pytest.fixture
def no_google_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Local Posts read is out of scope; provider posts are seeded as already read."""

    async def reconciled(*args: object, **kwargs: object) -> dict[str, int | str]:
        return {}

    monkeypatch.setattr(GBPDiscoveryService, "reconcile_local_posts", reconciled)


async def _settle(factory: async_sessionmaker[AsyncSession], org_id: UUID, pub_id: UUID) -> str:
    async with factory.begin() as session:
        return await service.auto_reconcile_ambiguous_post(session, Settings(), org_id, pub_id)


async def _publication(
    factory: async_sessionmaker[AsyncSession], publication_id: UUID
) -> GBPPostPublication:
    async with factory() as session:
        publication = await session.get(GBPPostPublication, publication_id)
        assert publication is not None
        return publication


async def _audit_count(
    factory: async_sessionmaker[AsyncSession], org_id: UUID, event_type: str
) -> int:
    async with factory() as session:
        return (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.organization_id == org_id, AuditEvent.event_type == event_type)
            )
            or 0
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_post_google_shows_exactly_once_is_resumed_for_verification(
    workflows_session_factory: async_sessionmaker[AsyncSession], no_google_read: None
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, pub_id, run_id, gbp_location_id = await _gbp_post(session)
        session.add(_provider_post(org_id, gbp_location_id, name=PROVIDER_POST, summary=CONTENT))

    assert await _settle(workflows_session_factory, org_id, pub_id) == "published"

    publication = await _publication(workflows_session_factory, pub_id)
    assert publication.provider_post_id == PROVIDER_POST
    async with workflows_session_factory() as session:
        run = await session.get(WorkflowRun, run_id)
        jobs = list(await session.scalars(select(Job).where(Job.workflow_run_id == run_id)))
    assert run is not None and run.status == "queued" and len(jobs) == 1
    assert (
        await _audit_count(workflows_session_factory, org_id, "gbp.post.auto_reconciled_published")
        == 1
    )
    # Already resolved: a second pass does nothing and queues nothing more.
    assert await _settle(workflows_session_factory, org_id, pub_id) == "skipped"


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_post_google_does_not_show_becomes_not_published(
    workflows_session_factory: async_sessionmaker[AsyncSession], no_google_read: None
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, pub_id, run_id, gbp_location_id = await _gbp_post(session)
        session.add(
            _provider_post(org_id, gbp_location_id, name=PROVIDER_POST, summary="Something else")
        )

    assert await _settle(workflows_session_factory, org_id, pub_id) == "not_published"

    publication = await _publication(workflows_session_factory, pub_id)
    assert (publication.status, publication.safe_error_code) == (
        "not_published",
        "POST_NOT_ON_GOOGLE",
    )
    async with workflows_session_factory() as session:
        jobs = list(await session.scalars(select(Job).where(Job.workflow_run_id == run_id)))
    assert jobs == []
    assert (
        await _audit_count(
            workflows_session_factory, org_id, "gbp.post.auto_reconciled_not_published"
        )
        == 1
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_two_matching_posts_stay_for_a_person_with_a_reason(
    workflows_session_factory: async_sessionmaker[AsyncSession], no_google_read: None
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, pub_id, _, gbp_location_id = await _gbp_post(session)
        for name in (PROVIDER_POST, PROVIDER_POST + "0"):
            session.add(_provider_post(org_id, gbp_location_id, name=name, summary=CONTENT))

    assert await _settle(workflows_session_factory, org_id, pub_id) == "needs_operator"

    publication = await _publication(workflows_session_factory, pub_id)
    assert (publication.status, publication.safe_error_code) == (
        "reconciliation_required",
        "AMBIGUOUS_PROVIDER_MATCH",
    )
    # It is no longer an automatic candidate, so the sweep cannot loop on it.
    async with workflows_session_factory() as session:
        assert await service.ambiguous_post_publication_ids(session) == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_an_unreadable_google_keeps_the_post_for_a_person(
    workflows_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def unreadable(*args: object, **kwargs: object) -> dict[str, int | str]:
        raise RuntimeError("Google returned 503")

    monkeypatch.setattr(GBPDiscoveryService, "reconcile_local_posts", unreadable)
    async with workflows_session_factory.begin() as session:
        org_id, pub_id, _, _ = await _gbp_post(session)

    assert await _settle(workflows_session_factory, org_id, pub_id) == "needs_operator"

    publication = await _publication(workflows_session_factory, pub_id)
    assert (publication.status, publication.safe_error_code) == (
        "reconciliation_required",
        "GOOGLE_READ_FAILED",
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_fresh_ambiguous_post_is_given_time_before_it_is_judged(
    workflows_session_factory: async_sessionmaker[AsyncSession], no_google_read: None
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, pub_id, _, _ = await _gbp_post(session)
        publication = await session.get(GBPPostPublication, pub_id)
        assert publication is not None
        publication.dispatched_at = datetime.now(UTC) - timedelta(minutes=1)

    async with workflows_session_factory() as session:
        assert await service.ambiguous_post_publication_ids(session) == []
    assert (await reconcile_ambiguous_gbp_posts(workflows_session_factory, Settings())) == 0
    assert (await _publication(workflows_session_factory, pub_id)).status == (
        "reconciliation_required"
    )


async def _location_of(factory: async_sessionmaker[AsyncSession], gbp_location_id: UUID) -> UUID:
    async with factory() as session:
        gbp_location = await session.get(GBPLocation, gbp_location_id)
        assert gbp_location is not None and gbp_location.location_id is not None
        return gbp_location.location_id


async def _not_published(
    factory: async_sessionmaker[AsyncSession], no_google_read: None
) -> tuple[UUID, UUID, UUID, UUID]:
    async with factory.begin() as session:
        org_id, pub_id, _, gbp_location_id = await _gbp_post(session)
    assert await _settle(factory, org_id, pub_id) == "not_published"
    return org_id, pub_id, gbp_location_id, await _location_of(factory, gbp_location_id)


@pytest.mark.integration
@pytest.mark.anyio
async def test_repost_creates_one_new_revision_awaiting_approval_and_is_idempotent(
    workflows_session_factory: async_sessionmaker[AsyncSession], no_google_read: None
) -> None:
    org_id, pub_id, _, location_id = await _not_published(workflows_session_factory, no_google_read)
    actor = uuid4()

    async with workflows_session_factory.begin() as session:
        first = await service.repost_publication(
            session, org_id, location_id, pub_id, actor_id=actor, correlation_id="repost-1"
        )
        first_id = first.id
        assert (first.status, first.revision, first.content) == ("awaiting_approval", 2, CONTENT)
    async with workflows_session_factory.begin() as session:
        again = await service.repost_publication(
            session, org_id, location_id, pub_id, actor_id=actor, correlation_id="repost-2"
        )
        assert again.id == first_id

    async with workflows_session_factory() as session:
        revisions = list(
            await session.scalars(
                select(GBPPostRevision).where(GBPPostRevision.organization_id == org_id)
            )
        )
    assert sorted(revision.revision for revision in revisions) == [1, 2]
    publication = await _publication(workflows_session_factory, pub_id)
    assert (publication.status, publication.safe_error_code) == (
        "discarded",
        "REPOSTED_AS_NEW_REVISION",
    )
    assert await _audit_count(workflows_session_factory, org_id, "gbp.post.reposted") == 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_discard_is_idempotent_and_audited_once(
    workflows_session_factory: async_sessionmaker[AsyncSession], no_google_read: None
) -> None:
    org_id, pub_id, _, location_id = await _not_published(workflows_session_factory, no_google_read)
    actor = uuid4()
    for correlation in ("discard-1", "discard-2"):
        async with workflows_session_factory.begin() as session:
            result = await service.discard_publication(
                session, org_id, location_id, pub_id, actor_id=actor, correlation_id=correlation
            )
            assert result.status == "discarded"

    assert await _audit_count(workflows_session_factory, org_id, "gbp.post.discarded") == 1
    # A discarded post cannot then be reposted.
    with pytest.raises(GBPPostPublicationNotActionableError):
        async with workflows_session_factory.begin() as session:
            await service.repost_publication(
                session, org_id, location_id, pub_id, actor_id=actor, correlation_id="late"
            )


@pytest.mark.integration
@pytest.mark.anyio
async def test_repost_and_discard_only_apply_to_a_post_google_does_not_show(
    workflows_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with workflows_session_factory.begin() as session:
        org_id, pub_id, _, gbp_location_id = await _gbp_post(session)  # still ambiguous
    location_id = await _location_of(workflows_session_factory, gbp_location_id)
    for action in (service.repost_publication, service.discard_publication):
        with pytest.raises(GBPPostPublicationNotActionableError):
            async with workflows_session_factory.begin() as session:
                await action(
                    session, org_id, location_id, pub_id, actor_id=uuid4(), correlation_id="x"
                )


@pytest.mark.integration
@pytest.mark.anyio
async def test_repost_and_discard_are_tenant_and_location_scoped(
    workflows_session_factory: async_sessionmaker[AsyncSession], no_google_read: None
) -> None:
    org_id, pub_id, _, location_id = await _not_published(workflows_session_factory, no_google_read)
    for action in (service.repost_publication, service.discard_publication):
        for wrong_org, wrong_location in ((uuid4(), location_id), (org_id, uuid4())):
            with pytest.raises(GBPPostRevisionNotFoundError):
                async with workflows_session_factory.begin() as session:
                    await action(
                        session,
                        wrong_org,
                        wrong_location,
                        pub_id,
                        actor_id=uuid4(),
                        correlation_id="x",
                    )
    assert (await _publication(workflows_session_factory, pub_id)).status == "not_published"
