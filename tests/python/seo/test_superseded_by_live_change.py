"""A newer live duplicate closes the older opportunity; nothing publishes over a live change."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.testclient import TestClient

from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.service import ExecutionService
from apps.api.app.products.content.models import ContentPublication
from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeItem, SiteChangeSet
from apps.api.app.products.seo.decision import SEOEvidenceInvalidError
from apps.api.app.products.seo.limitation_codes import LIMITATION_COPY, SEOLimitationCode
from apps.api.app.products.seo.models import (
    SEOImplementationTask,
    SEOOpportunity,
    SEORecommendationRevision,
)
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.site_change_service import (
    SiteChangeService,
    live_change_superseding,
)

from .test_opportunity_polish import add_target, opportunity, seed_website
from .test_seo_api import seo_client

__all__ = ["seo_client"]

THEN = datetime(2026, 9, 1, 12, tzinfo=UTC)


def change_set(page: UUID) -> SiteChangeSet:
    return SiteChangeSet(
        items=[
            SiteChangeItem(
                page_id=page,
                field=SiteChangeField.SEO_TITLE,
                current_value="Brunch",
                proposed_value="Best Brunch Spots in San Diego | Coco Maya",
                rationale="Matches the query.",
            )
        ]
    )


def revision(
    ids: dict[str, UUID], opportunity_id: UUID, number: int, status: str, at: datetime, page: UUID
) -> SEORecommendationRevision:
    return SEORecommendationRevision(
        organization_id=ids["organization"],
        opportunity_id=opportunity_id,
        revision_number=number,
        proposed_action="Rewrite the title",
        evidence_references=[],
        expected_result_hypothesis="More clicks",
        risk="low",
        effort="low",
        status=status,
        created_at=at,
        change_set=change_set(page).model_dump(mode="json"),
    )


async def seed_case(
    factory: async_sessionmaker[AsyncSession], ids: dict[str, UUID]
) -> dict[str, UUID]:
    """Coco Maya's shape: an older opportunity with unpublished work, a newer one live."""
    website, page = await seed_website(factory, ids)
    target = await add_target(factory, ids)
    async with factory.begin() as session:
        older = opportunity(ids, website, None, status="approved", active_marker="active")
        newer = opportunity(ids, website, page, status="approved", active_marker="active")
        session.add_all([older, newer])
        await session.flush()
        older.created_at = THEN
        newer.created_at = THEN + timedelta(days=3)
        old_revisions = [
            revision(ids, older.id, n, status, THEN + timedelta(hours=n), page)
            for n, status in (
                (1, "approved"),
                (2, "approved"),
                (3, "approved"),
                (4, "awaiting_approval"),
            )
        ]
        live = revision(ids, newer.id, 1, "approved", THEN + timedelta(days=3, hours=1), page)
        session.add_all([*old_revisions, live])
        await session.flush()
        run = await ExecutionService().start_named(
            session,
            ids["organization"],
            "seo.crawl_or_analysis",
            f"stale-task-{uuid4().hex}",
            correlation_id="stale-task",
            enqueue_job=False,
        )
        session.add(
            SEOImplementationTask(
                organization_id=ids["organization"],
                recommendation_revision_id=old_revisions[0].id,
                workflow_run_id=run.id,
                target_type="opportunity",
                target_reference=f"seo-opportunity:{older.id}",
                status="verification_pending",
            )
        )
        session.add(
            ContentPublication(
                organization_id=ids["organization"],
                publication_kind="site_change",
                seo_recommendation_revision_id=live.id,
                publishing_target_id=target,
                workflow_run_id=ids["workflow_run"],
                idempotency_key=f"live-{live.id}",
                status="verified",
                target_path="src/content/menu.json",
                verification_status="verified",
                verified_at=THEN + timedelta(days=4),
            )
        )
        return {
            "older": older.id,
            "newer": newer.id,
            "page": page,
            "live": live.id,
            **{f"old{i}": r.id for i, r in enumerate(old_revisions, 1)},
        }


@pytest.mark.integration
def test_sweep_closes_the_older_duplicate_and_withdraws_its_unpublished_revisions(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, ids = seo_client
    seeded = asyncio.run(seed_case(seo_session_factory, ids))

    async def sweep() -> tuple[int, int]:
        async with seo_session_factory.begin() as session:
            first = await SEOOrchestrationService().supersede_by_live_change(
                session, correlation_id="test-sweep"
            )
        async with seo_session_factory.begin() as session:
            again = await SEOOrchestrationService().supersede_by_live_change(
                session, correlation_id="test-sweep"
            )
        return first, again

    first, again = asyncio.run(sweep())
    assert (first, again) == (1, 0)

    async def check() -> None:
        async with seo_session_factory() as session:
            older = await session.get(SEOOpportunity, seeded["older"])
            newer = await session.get(SEOOpportunity, seeded["newer"])
            assert older is not None and newer is not None
            assert older.status == "archived" and older.active_marker != "active"
            assert newer.status == "approved" and newer.active_marker == "active"
            for key in ("old1", "old2", "old3", "old4"):
                row = await session.get(SEORecommendationRevision, seeded[key])
                assert row is not None and row.status == "withdrawn"
            live = await session.get(SEORecommendationRevision, seeded["live"])
            assert live is not None and live.status == "approved"
            archived = (
                await session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.organization_id == ids["organization"],
                        AuditEvent.event_type == "seo.opportunity.archived",
                        AuditEvent.resource_id == seeded["older"],
                    )
                )
            ).all()
            assert len(archived) == 1
            assert archived[0].event_metadata["reason"] == "SUPERSEDED_BY_LIVE_CHANGE"
            assert archived[0].event_metadata["superseded_by"] == str(seeded["newer"])
            assert archived[0].event_metadata["recommendations_withdrawn"] == 4

    asyncio.run(check())


@pytest.mark.integration
def test_sweep_leaves_a_different_page_or_query_alone(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, ids = seo_client
    seeded = asyncio.run(seed_case(seo_session_factory, ids))

    async def run() -> None:
        async with seo_session_factory.begin() as session:
            other = await session.get(SEOOpportunity, seeded["older"])
            assert other is not None
            other.evidence = {"query": "a different query", "source": "gsc"}
        async with seo_session_factory.begin() as session:
            assert (
                await SEOOrchestrationService().supersede_by_live_change(
                    session, correlation_id="test-sweep"
                )
                == 0
            )

    asyncio.run(run())


@pytest.mark.integration
def test_an_approved_revision_cannot_publish_over_a_newer_live_change(
    seo_client: tuple[TestClient, dict[str, UUID]],
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    _, ids = seo_client
    seeded = asyncio.run(seed_case(seo_session_factory, ids))

    async def run() -> None:
        async with seo_session_factory.begin() as session:
            stale = await session.get(SEORecommendationRevision, seeded["old1"])
            live = await session.get(SEORecommendationRevision, seeded["live"])
            assert stale is not None and live is not None
            assert stale.change_set is not None
            blocker = await live_change_superseding(
                session, ids["organization"], stale, SiteChangeSet.model_validate(stale.change_set)
            )
            assert blocker == live.id
            # The newest revision is not blocked by an older live one.
            assert (
                await live_change_superseding(
                    session,
                    ids["organization"],
                    live,
                    SiteChangeSet.model_validate(live.change_set),
                )
                is None
            )
            with pytest.raises(SEOEvidenceInvalidError) as raised:
                await SiteChangeService().reserve_publication(
                    session,
                    ids["organization"],
                    stale,
                    None,  # type: ignore[arg-type]  # refused before the run is read
                    actor_id=None,
                    correlation_id="test-guard",
                    audit=None,  # type: ignore[arg-type]
                    location_id=ids["location"],
                )
            assert str(raised.value) == LIMITATION_COPY[SEOLimitationCode.SUPERSEDED_BY_LIVE_CHANGE]

    asyncio.run(run())
