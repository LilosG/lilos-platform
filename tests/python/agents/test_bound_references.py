"""Evidence LILOs binds a run to is observed at start; empty-source briefs never reach drafting."""

import asyncio
from collections.abc import Callable
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.agents.bound_references import bound_source_references
from apps.api.app.agents.tools import AgentToolDeniedError, AgentToolService
from apps.api.app.products.content.contracts import BriefCreate, ItemCreate
from apps.api.app.products.content.enums import ContentTargetKind
from apps.api.app.products.content.models import ContentOpportunity
from apps.api.app.products.content.service import ContentService

from .test_hermes_bound_flow_e2e import (
    World,
    _call,
    _complete,
    _seed,
    _start_run,
    stub_decisions,  # noqa: F401 - fixture
)


@pytest.mark.integration
def test_a_content_run_is_given_its_opportunity_evidence_without_reading_it(
    agent_session_factory: async_sessionmaker[AsyncSession],
    stub_decisions: Callable[[World], None],  # noqa: F811
) -> None:
    async def scenario() -> None:
        world = await _seed(agent_session_factory)
        stub_decisions(world)
        async with agent_session_factory() as session:
            references = await bound_source_references(
                session,
                world.org,
                {"context_reference": f"content-opportunity:{world.content_opportunity}"},
            )
            expected = cast(list[str], world.decisions[world.query_only]["evidence_references"])
            assert f"content-opportunity:{world.content_opportunity}" in references
            assert set(expected) <= set(references)
            assert any(ref.startswith("seo-search-observation:") for ref in references)

            # Organization-scoped: another tenant's id yields nothing, not an error.
            assert (
                await bound_source_references(
                    session,
                    uuid4(),
                    {"context_reference": f"content-opportunity:{world.content_opportunity}"},
                )
                == []
            )
            # Prose and malformed references never contribute anything.
            assert (
                await bound_source_references(
                    session, world.org, {"context_reference": "content-opportunity:not-a-uuid"}
                )
                == []
            )

    asyncio.run(scenario())


@pytest.mark.integration
def test_a_brief_without_sources_is_regenerated_or_blocked_never_ready_and_empty(
    agent_session_factory: async_sessionmaker[AsyncSession],
    stub_decisions: Callable[[World], None],  # noqa: F811
) -> None:
    async def scenario() -> None:
        world = await _seed(agent_session_factory)
        stub_decisions(world)
        service = ContentService()

        async def brief_for(opportunity_id: UUID) -> tuple[str, str | None, list[object]]:
            async with agent_session_factory.begin() as session:
                item = await service.create_item(
                    session,
                    world.org,
                    ItemCreate(
                        opportunity_id=opportunity_id,
                        location_id=world.location,
                        content_type="blog",
                        title=f"Item {uuid4().hex[:6]}",
                        slug=f"item-{uuid4().hex[:6]}",
                    ),
                    actor_id=None,
                    correlation_id="e2e",
                )
                brief = await service.create_brief(
                    session,
                    world.org,
                    item.id,
                    BriefCreate(
                        audience="Locals",
                        intent="Plan",
                        target_kind=ContentTargetKind.NEW_PAGE,
                        target_reference="/guide",
                        approved_fact_revision_ids=[world.fact],
                    ),
                    actor_id=None,
                    correlation_id="e2e",
                )
                return (
                    brief.status,
                    brief.blocked_reason_code,
                    list(brief.source_evidence_references),
                )

        # An SEO-sourced opportunity: sources regenerated from its governed evidence.
        status, reason, sources = await brief_for(world.content_opportunity)
        assert status == "ready" and reason is None
        assert f"seo-opportunity:{world.query_only}" in sources

        # An opportunity with no SEO evidence: blocked with a typed reason.
        async with agent_session_factory.begin() as session:
            manual = ContentOpportunity(
                organization_id=world.org,
                location_id=world.location,
                product_key="content",
                target_reference="manual",
                opportunity_type="manual",
                source_type="manual",
                source_reference="manual:note",
                evidence_document={},
                evidence_hash=uuid4().hex + uuid4().hex,
                priority_score=1,
                status="accepted",
            )
            session.add(manual)
            await session.flush()
            manual_id = manual.id
        status, reason, sources = await brief_for(manual_id)
        assert (status, reason, sources) == ("blocked", "CONTENT_BRIEF_SOURCES_MISSING", [])

    asyncio.run(scenario())


@pytest.mark.integration
def test_a_bound_run_that_made_nothing_is_failed_but_an_unbound_one_completes(
    agent_session_factory: async_sessionmaker[AsyncSession],
    stub_decisions: Callable[[World], None],  # noqa: F811
) -> None:
    async def scenario() -> None:
        world = await _seed(agent_session_factory)
        stub_decisions(world)
        bound = await _start_run(
            agent_session_factory,
            world,
            workflow_key="agent.content",
            skill_key="content.operator",
            input_document={
                "context_reference": f"content-opportunity:{world.content_opportunity}"
            },
        )
        unbound = await _start_run(
            agent_session_factory,
            world,
            workflow_key="agent.content",
            skill_key="content.operator",
            input_document={},
        )
        bound_final = await _complete(agent_session_factory, bound)
        unbound_final = await _complete(agent_session_factory, unbound)
        assert (bound_final.status, bound_final.safe_error_code) == (
            "failed",
            "AGENT_REQUIRED_OUTPUT_MISSING",
        )
        assert unbound_final.status == "completed"

    asyncio.run(scenario())


@pytest.mark.integration
def test_the_draft_tool_never_accepts_a_blocked_brief(
    agent_session_factory: async_sessionmaker[AsyncSession],
    stub_decisions: Callable[[World], None],  # noqa: F811
) -> None:
    async def scenario() -> None:
        world = await _seed(agent_session_factory)
        stub_decisions(world)
        run_id = await _start_run(
            agent_session_factory,
            world,
            workflow_key="agent.content",
            skill_key="content.operator",
            input_document={
                "context_reference": f"content-opportunity:{world.content_opportunity}"
            },
        )
        with pytest.raises(AgentToolDeniedError, match="ready Content brief"):
            await _call(
                agent_session_factory,
                AgentToolService(),
                run_id,
                "generate_content_draft_proposal",
                {
                    "content_item_id": str(uuid4()),
                    "content_brief_id": str(uuid4()),
                    "approved_fact_revision_ids": [str(world.fact)],
                    "source_evidence_references": [f"seo-opportunity:{world.query_only}"],
                },
            )

    asyncio.run(scenario())
