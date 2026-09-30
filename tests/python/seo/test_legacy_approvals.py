"""Approvals that predate attribution, and recommendations on archived opportunities.

Neither can ever execute, so neither may sit in the queue looking actionable: they are
superseded or withdrawn through `SEOService`, with audit events, and every read surface
(workspace, summary, Overview) excludes archived opportunities and withdrawn work.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.service import ExecutionService
from apps.api.app.insights.aggregation_service import InsightsService
from apps.api.app.products.seo.models import (
    SEOImplementationTask,
    SEOOpportunity,
    SEORecommendationRevision,
)
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.service import SEOService
from apps.api.app.routes import seo as seo_routes

from .test_orchestration import (
    FakePageSpeedService,
    _legacy_query_only_row,
    _seed_attributed_query,
)


def revision_for(
    organization_id: UUID, opportunity_id: UUID, status: str, number: int = 1
) -> SEORecommendationRevision:
    return SEORecommendationRevision(
        organization_id=organization_id,
        opportunity_id=opportunity_id,
        revision_number=number,
        proposed_action="Rewrite the title.",
        evidence_references=[],
        expected_result_hypothesis="More clicks.",
        risk="low",
        effort="low",
        status=status,
        created_at=datetime.now(UTC),
    )


async def events(session: AsyncSession, organization_id: UUID, event_type: str) -> list[AuditEvent]:
    return list(
        await session.scalars(
            select(AuditEvent).where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.event_type == event_type,
            )
        )
    )


async def analyze(session: AsyncSession, organization_id: UUID, label: str) -> dict[str, Any]:
    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    return cast(
        dict[str, Any],
        await service.analyze(session, organization_id, location_id=None, correlation_id=label),
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_legacy_approved_work_is_superseded_when_an_attributed_replacement_exists(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, website, _, _ = await _seed_attributed_query(session)
        legacy = _legacy_query_only_row(organization, website, status="approved")
        session.add(legacy)
        await session.flush()
        approved = revision_for(organization.id, legacy.id, "approved")
        session.add(approved)
        await session.flush()

        result = await analyze(session, organization.id, "legacy-superseded")

        await session.refresh(legacy)
        await session.refresh(approved)
        assert legacy.status == "archived" and legacy.active_marker != "active"
        assert approved.status == "withdrawn"
        assert result["legacy_approved"]["superseded"] == 1
        live = await session.scalars(
            select(SEOOpportunity).where(
                SEOOpportunity.organization_id == organization.id,
                SEOOpportunity.opportunity_type == "gsc_striking_distance",
                SEOOpportunity.active_marker == "active",
            )
        )
        replacement = list(live)
        assert len(replacement) == 1 and replacement[0].attribution_state == "attributed"
        archived = [
            event
            for event in await events(session, organization.id, "seo.opportunity.archived")
            if event.resource_id == legacy.id
        ]
        assert len(archived) == 1
        assert archived[0].event_metadata["reason"] == "legacy_approval_superseded"
        assert archived[0].event_metadata["superseded_by"] == str(replacement[0].id)
        assert archived[0].event_metadata["recommendations_withdrawn"] == 1
        withdrawn = [
            event
            for event in await events(session, organization.id, "seo.recommendation.withdrawn")
            if event.event_metadata["revision_id"] == str(approved.id)
        ]
        assert len(withdrawn) == 1
        assert withdrawn[0].event_metadata["previous_status"] == "approved"


@pytest.mark.integration
@pytest.mark.anyio
async def test_legacy_approval_without_a_replacement_returns_to_identified(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, website, _, _ = await _seed_attributed_query(session)
        lonely = _legacy_query_only_row(organization, website, status="approved")
        lonely.evidence = {"source": "google_search_console", "query": "a query nobody ranks for"}
        lonely.deduplication_key = uuid4().hex + uuid4().hex
        session.add(lonely)
        await session.flush()
        approved = revision_for(organization.id, lonely.id, "approved")
        session.add(approved)
        await session.flush()

        result = await analyze(session, organization.id, "legacy-withdrawn")

        await session.refresh(lonely)
        await session.refresh(approved)
        assert lonely.status == "identified" and lonely.active_marker == "active"
        assert lonely.version == 2
        assert approved.status == "withdrawn"
        assert result["legacy_approved"]["approval_withdrawn"] == 1
        audit = [
            event
            for event in await events(
                session, organization.id, "seo.opportunity.approval_withdrawn"
            )
            if event.resource_id == lonely.id
        ]
        assert len(audit) == 1
        assert audit[0].event_metadata["reason"] == "unattributed_approval_cannot_execute"


@pytest.mark.integration
@pytest.mark.anyio
async def test_legacy_approval_with_work_in_flight_is_left_alone_and_listed(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, website, _, _ = await _seed_attributed_query(session)
        busy = _legacy_query_only_row(organization, website, status="approved")
        session.add(busy)
        await session.flush()
        approved = revision_for(organization.id, busy.id, "approved")
        session.add(approved)
        await session.flush()
        run = await ExecutionService().start_named(
            session,
            organization.id,
            "seo.crawl_or_analysis",
            f"in-flight-{uuid4().hex}",
            correlation_id="in-flight",
            enqueue_job=False,
        )
        session.add(
            SEOImplementationTask(
                organization_id=organization.id,
                recommendation_revision_id=approved.id,
                workflow_run_id=run.id,
                target_type="opportunity",
                target_reference=f"seo-opportunity:{busy.id}",
                status="pending",
            )
        )
        await session.flush()

        result = await analyze(session, organization.id, "legacy-busy")

        await session.refresh(busy)
        await session.refresh(approved)
        assert busy.status == "approved" and busy.active_marker == "active"
        assert approved.status == "approved"
        assert result["legacy_approved"]["left_in_flight"] == [
            {"opportunity_id": str(busy.id), "reason": "implementation_task:pending"}
        ]
        assert result["legacy_approved"]["superseded"] == 0
        assert result["legacy_approved"]["approval_withdrawn"] == 0


@pytest.mark.integration
@pytest.mark.anyio
async def test_archiving_withdraws_live_recommendations_in_the_same_transition(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    async with seo_session_factory.begin() as session:
        organization, website, _, _ = await _seed_attributed_query(session)
        stale = _legacy_query_only_row(organization, website, status="recommended")
        session.add(stale)
        await session.flush()
        awaiting = revision_for(organization.id, stale.id, "awaiting_approval")
        rejected = revision_for(organization.id, stale.id, "rejected", number=2)
        session.add_all([awaiting, rejected])
        await session.flush()

        await service.archive_opportunity(
            session,
            organization.id,
            stale,
            reason="stale",
            superseded_by=None,
            correlation_id="archive",
        )

        await session.refresh(awaiting)
        await session.refresh(rejected)
        assert stale.status == "archived"
        assert awaiting.status == "withdrawn"
        assert rejected.status == "rejected"  # already terminal: left exactly as it was


@pytest.mark.integration
@pytest.mark.anyio
async def test_recommendations_orphaned_on_archived_opportunities_are_withdrawn(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, website, _, _ = await _seed_attributed_query(session)
        ghost = _legacy_query_only_row(organization, website, status="archived")
        ghost.active_marker = uuid4().hex[:8]
        ghost.deduplication_key = uuid4().hex + uuid4().hex
        session.add(ghost)
        await session.flush()
        pending = revision_for(organization.id, ghost.id, "awaiting_approval")
        approved = revision_for(organization.id, ghost.id, "approved", number=2)
        session.add_all([pending, approved])
        await session.flush()

        result = await analyze(session, organization.id, "orphans")
        again = await analyze(session, organization.id, "orphans-again")

        await session.refresh(pending)
        await session.refresh(approved)
        assert (pending.status, approved.status) == ("withdrawn", "withdrawn")
        assert result["orphaned_recommendations_withdrawn"] == 2
        assert again["orphaned_recommendations_withdrawn"] == 0  # converged
        assert len(await events(session, organization.id, "seo.recommendation.withdrawn")) == 2


@pytest.mark.integration
@pytest.mark.anyio
async def test_withdrawn_is_terminal_and_other_edits_to_decided_work_stay_refused(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, website, _, _ = await _seed_attributed_query(session)
        opportunity = _legacy_query_only_row(organization, website, status="approved")
        session.add(opportunity)
        await session.flush()
        approved = revision_for(organization.id, opportunity.id, "approved")
        session.add(approved)
        await session.flush()
        revision_id = approved.id

    async def attempt(statement: Any) -> type[BaseException] | None:
        try:
            async with seo_session_factory.begin() as session:
                await session.execute(statement)
        except IntegrityError:
            return IntegrityError
        return None

    table = SEORecommendationRevision
    # An approved recommendation still cannot be edited...
    assert (
        await attempt(
            update(table).where(table.id == revision_id).values(proposed_action="Something else")
        )
        is IntegrityError
    )
    # ...nor withdrawn while also changing what it says.
    assert (
        await attempt(
            update(table)
            .where(table.id == revision_id)
            .values(status="withdrawn", proposed_action="Something else")
        )
        is IntegrityError
    )
    # The one exception: a status-only move to withdrawn.
    assert (
        await attempt(update(table).where(table.id == revision_id).values(status="withdrawn"))
        is None
    )
    # Withdrawn is terminal: it cannot be revived, and nothing can be deleted.
    assert (
        await attempt(update(table).where(table.id == revision_id).values(status="approved"))
        is IntegrityError
    )
    assert (
        await attempt(text(f"DELETE FROM seo_recommendation_revisions WHERE id = '{revision_id}'"))
        is IntegrityError
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_workspace_summary_and_overview_exclude_archived_and_withdrawn(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, website, _, _ = await _seed_attributed_query(session)
        await analyze(session, organization.id, "current")
        current = cast(
            SEOOpportunity,
            await session.scalar(
                select(SEOOpportunity).where(
                    SEOOpportunity.organization_id == organization.id,
                    SEOOpportunity.opportunity_type == "gsc_striking_distance",
                    SEOOpportunity.active_marker == "active",
                )
            ),
        )
        # 1. archived, with recommendations still (wrongly) live in the database
        ghost = _legacy_query_only_row(organization, website, status="archived")
        ghost.active_marker = uuid4().hex[:8]
        ghost.deduplication_key = uuid4().hex + uuid4().hex
        session.add(ghost)
        await session.flush()
        session.add(revision_for(organization.id, ghost.id, "approved"))
        # 2. a live opportunity whose only recommendation was withdrawn
        session.add(revision_for(organization.id, current.id, "withdrawn", number=99))
        await session.flush()
        organization_id, ghost_id, current_id = organization.id, ghost.id, current.id

    request = cast(
        Request,
        SimpleNamespace(
            state=SimpleNamespace(correlation_id="workspace"),
            headers={},
            app=SimpleNamespace(state=SimpleNamespace()),
            url=SimpleNamespace(path="/"),
        ),
    )
    async with seo_session_factory() as session:
        response = await seo_routes.search_intelligence_workspace(
            request, organization_id, session, cast(Any, None), None, 50, 0
        )
        summary = await SEOService().summary(session, organization_id)
        overview = await InsightsService().summary(session, organization_id)

    items = cast(list[dict[str, Any]], cast(dict[str, Any], response["data"])["items"])
    ids = {item["opportunity"]["id"] for item in items}
    assert str(ghost_id) not in ids  # archived: not rendered at all
    assert str(current_id) in ids
    live_item = next(item for item in items if item["opportunity"]["id"] == str(current_id))
    # Its newest revision is withdrawn, so the workspace shows the deterministic one (or
    # none) -- never the withdrawn recommendation.
    shown = live_item["recommendation"]
    assert shown is None or shown["status"] != "withdrawn"

    assert "archived" not in summary["by_status"]  # type: ignore[operator]
    seo_overview = cast(dict[str, Any], overview["seo"])
    assert "archived" not in seo_overview["opportunities"]
