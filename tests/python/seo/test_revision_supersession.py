"""Only the newest revision of an opportunity is ever live."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from apps.api.app.audit.models import AuditEvent
from apps.api.app.products.seo.contracts import RecommendationCreate
from apps.api.app.products.seo.models import SEORecommendationRevision
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.service import SEOService
from apps.api.app.routes import seo as seo_routes

from .test_hermes_change_set import striking_distance_opportunity
from .test_legacy_approvals import revision_for
from .test_orchestration import FakePageSpeedService, _seed_attributed_query

ROOT = Path(__file__).resolve().parents[3]


def command_for(opportunity_id: UUID, text: str) -> RecommendationCreate:
    return RecommendationCreate(
        proposed_action=text,
        evidence_references=[f"seo-opportunity:{opportunity_id}"],
        expected_result_hypothesis="More clicks.",
        risk="low",
        effort="low",
    )


async def statuses(session: AsyncSession, opportunity_id: UUID) -> dict[int, str]:
    rows = await session.execute(
        select(SEORecommendationRevision.revision_number, SEORecommendationRevision.status).where(
            SEORecommendationRevision.opportunity_id == opportunity_id
        )
    )
    return {number: status for number, status in rows}


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_new_revision_supersedes_every_older_live_revision_with_audit(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, _, _, _ = await _seed_attributed_query(session)
        await SEOOrchestrationService(pagespeed=FakePageSpeedService()).analyze(
            session, organization.id, location_id=None, correlation_id="s"
        )
        opportunity = await striking_distance_opportunity(session, organization.id)
        # The deterministic analysis already left revision 1 awaiting approval; a rejected
        # revision is already terminal and must be left exactly as it is.
        rejected = revision_for(organization.id, opportunity.id, "rejected", number=3)
        session.add(rejected)
        await session.flush()
        before = await statuses(session, opportunity.id)
        assert before[1] == "awaiting_approval"

        newest = await SEOService().create_recommendation(
            session,
            organization.id,
            opportunity.id,
            command_for(opportunity.id, "A newer proposal."),
            actor_id=None,
            correlation_id="newest",
        )

        after = await statuses(session, opportunity.id)
        assert after[1] == "superseded"
        assert after[3] == "rejected"  # already terminal: untouched
        assert after[newest.revision_number] == "awaiting_approval"
        events = list(
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.organization_id == organization.id,
                    AuditEvent.event_type == "seo.recommendation.superseded",
                )
            )
        )
        assert len(events) == 1
        assert events[0].event_metadata["superseded_by"] == str(newest.id)
        assert events[0].event_metadata["previous_status"] == "awaiting_approval"


@pytest.mark.integration
@pytest.mark.anyio
async def test_an_approved_revision_can_be_superseded_and_terminal_ones_cannot(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, _, _, _ = await _seed_attributed_query(session)
        await SEOOrchestrationService(pagespeed=FakePageSpeedService()).analyze(
            session, organization.id, location_id=None, correlation_id="a"
        )
        opportunity = await striking_distance_opportunity(session, organization.id)
        approved = revision_for(organization.id, opportunity.id, "approved", number=2)
        rejected = revision_for(organization.id, opportunity.id, "rejected", number=3)
        session.add_all([approved, rejected])
        await session.flush()
        service = SEOService()
        successor = uuid4()

        assert await service.supersede_recommendation(
            session, organization.id, approved, superseded_by=successor, correlation_id="a"
        )
        assert approved.status == "superseded"
        # Terminal revisions are never touched, and a repeat is a no-op without a second event.
        assert not await service.supersede_recommendation(
            session, organization.id, rejected, superseded_by=successor, correlation_id="a"
        )
        assert not await service.supersede_recommendation(
            session, organization.id, approved, superseded_by=successor, correlation_id="a"
        )
        assert rejected.status == "rejected"
        events = list(
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.organization_id == organization.id,
                    AuditEvent.event_type == "seo.recommendation.superseded",
                )
            )
        )
        assert [e.event_metadata["previous_status"] for e in events] == ["approved"]


@pytest.mark.integration
@pytest.mark.anyio
async def test_the_database_allows_only_one_pending_revision_per_opportunity(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, _, _, _ = await _seed_attributed_query(session)
        await SEOOrchestrationService(pagespeed=FakePageSpeedService()).analyze(
            session, organization.id, location_id=None, correlation_id="one"
        )
        opportunity = await striking_distance_opportunity(session, organization.id)
        organization_id, opportunity_id = organization.id, opportunity.id

    with pytest.raises(IntegrityError, match="uq_seo_one_pending_revision"):
        async with seo_session_factory.begin() as session:
            session.add(revision_for(organization_id, opportunity_id, "awaiting_approval", 9))
    # A terminal revision alongside the pending one is fine.
    async with seo_session_factory.begin() as session:
        session.add(revision_for(organization_id, opportunity_id, "rejected", 10))


@pytest.mark.integration
@pytest.mark.anyio
async def test_the_migration_supersedes_existing_duplicates_and_keeps_the_newest(
    seo_session_factory: async_sessionmaker[AsyncSession], postgresql_test_url: str
) -> None:
    async with seo_session_factory.begin() as session:
        organization, _, _, _ = await _seed_attributed_query(session)
        await SEOOrchestrationService(pagespeed=FakePageSpeedService()).analyze(
            session, organization.id, location_id=None, correlation_id="dup"
        )
        opportunity = await striking_distance_opportunity(session, organization.id)
        organization_id, opportunity_id = organization.id, opportunity.id

    config = Config(ROOT / "alembic.ini")
    # Back to the schema production has: no one-pending index yet, so duplicates can exist.
    await asyncio.to_thread(command.downgrade, config, "20260930_0002")
    async with seo_session_factory.begin() as session:
        for number in (5, 6):
            session.add(revision_for(organization_id, opportunity_id, "awaiting_approval", number))
        session.add(revision_for(organization_id, opportunity_id, "approved", 7))
    async with seo_session_factory() as session:
        pending = [
            n
            for n, s in (await statuses(session, opportunity_id)).items()
            if s == "awaiting_approval"
        ]
        assert sorted(pending) == [1, 5, 6]  # three live proposals for one opportunity

    await asyncio.to_thread(command.upgrade, config, "head")

    async with seo_session_factory() as session:
        after = await statuses(session, opportunity_id)
    assert after[6] == "awaiting_approval"  # only the newest stays pending
    assert after[1] == "superseded" and after[5] == "superseded"
    assert after[7] == "approved"  # approved work is not a duplicate and is left alone
    # The rule is now structural.
    with pytest.raises(IntegrityError, match="uq_seo_one_pending_revision"):
        async with seo_session_factory.begin() as session:
            session.add(revision_for(organization_id, opportunity_id, "awaiting_approval", 8))
    # Superseded is terminal: the frozen-recommendation trigger refuses to revive it.
    with pytest.raises(IntegrityError):
        async with seo_session_factory.begin() as session:
            await session.execute(
                update(SEORecommendationRevision)
                .where(
                    SEORecommendationRevision.opportunity_id == opportunity_id,
                    SEORecommendationRevision.revision_number == 1,
                )
                .values(status="awaiting_approval")
            )


@pytest.mark.integration
@pytest.mark.anyio
async def test_the_workspace_shows_the_latest_live_revision_not_a_superseded_one(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, _, _, _ = await _seed_attributed_query(session)
        await SEOOrchestrationService(pagespeed=FakePageSpeedService()).analyze(
            session, organization.id, location_id=None, correlation_id="ws"
        )
        opportunity = await striking_distance_opportunity(session, organization.id)
        newest = await SEOService().create_recommendation(
            session,
            organization.id,
            opportunity.id,
            command_for(opportunity.id, "The live proposal."),
            actor_id=None,
            correlation_id="ws-new",
        )
        # A superseded revision that is NEWER by creation time than the live one (clock skew,
        # a backfill) must still never be shown.
        stray = revision_for(organization.id, opportunity.id, "superseded", number=50)
        stray.created_at = datetime.now(UTC).replace(year=2099)
        session.add(stray)
        await session.flush()
        organization_id, opportunity_id, live_id = organization.id, opportunity.id, newest.id

    request = cast(
        Request,
        SimpleNamespace(
            state=SimpleNamespace(correlation_id="ws"),
            headers={},
            app=SimpleNamespace(state=SimpleNamespace()),
            url=SimpleNamespace(path="/"),
        ),
    )
    async with seo_session_factory() as session:
        response = await seo_routes.search_intelligence_workspace(
            request, organization_id, session, cast(Any, None), None, 50, 0
        )
    items = cast(list[dict[str, Any]], cast(dict[str, Any], response["data"])["items"])
    item = next(i for i in items if i["opportunity"]["id"] == str(opportunity_id))
    assert item["recommendation"]["id"] == str(live_id)
    assert item["recommendation"]["status"] == "awaiting_approval"
