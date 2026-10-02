"""Hermes tool recovery and Content drafting on the Coco Maya shapes that failed in production.

PRK101 run b68ee232 (unbound SEO recommendation), Coco Maya item 9d57d18b (attributed
existing_page draft) and /brunch, /happy-hour (crawled pages with no attribution).
"""

import asyncio
from collections.abc import Callable
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.agents.models import AgentRun
from apps.api.app.agents.service import AgentRuntimeService
from apps.api.app.agents.skills import SKILLS
from apps.api.app.agents.tools import (
    TOOL_ARGUMENT_INVALID,
    AgentToolDeniedError,
    AgentToolService,
)
from apps.api.app.audit.models import AuditEvent
from apps.api.app.execution.handlers import _handle_content_draft_revision
from apps.api.app.products.content.errors import ContentSEOTargetUnresolvedError
from apps.api.app.products.content.models import ContentBrief, ContentOpportunity
from apps.api.app.products.seo.models import SEOOpportunity, SEOPage

from .test_hermes_bound_flow_e2e import (  # noqa: F401 - stub_decisions is a fixture
    World,
    _call,
    _proposal_ref,
    _seed,
    _start_run,
    stub_decisions,
)

SOURCES = [f"seo-search-observation:{uuid4()}" for _ in range(10)]


async def _extra_world(factory: async_sessionmaker[AsyncSession], world: World) -> dict[str, Any]:
    """Four more approved facts (five in all), an accepted attributed Content opportunity
    and two crawled pages that no SEO opportunity is attributed to."""
    async with factory.begin() as session:
        fact = await session.get(BusinessFactRevision, world.fact)
        assert fact is not None
        facts = [world.fact]
        for index in range(4):
            extra = BusinessFactRevision(
                organization_id=world.org,
                location_id=world.location,
                fact_identity=uuid4(),
                fact_key=f"business.fact_{index}",
                value_type="string",
                value=f"value {index}",
                source="client_input",
                authority="client_approved",
                status="active",
                effective_from=fact.effective_from,
                revision=1,
                proposed_by=fact.proposed_by,
                approved_by=fact.approved_by,
                approved_at=fact.approved_at,
                change_reason="recovery fixture",
            )
            session.add(extra)
            await session.flush()
            facts.append(extra.id)
        attributed = await session.get(SEOOpportunity, world.attributed)
        assert attributed is not None and attributed.page_id is not None
        attributed_page = await session.get(SEOPage, attributed.page_id)
        assert attributed_page is not None
        for path in ("/brunch", "/happy-hour"):
            session.add(
                SEOPage(
                    organization_id=world.org,
                    website_id=attributed.website_id,
                    normalized_url=f"https://example.invalid{path}",
                    observed_url=f"https://example.invalid{path}",
                    normalization_reasons=[],
                    robots_directives=[],
                    internal_links=[],
                    external_links=[],
                    structured_data_present=False,
                    indexability="indexable",
                    technical_issues=[],
                    quality_status="clean",
                )
            )
        opportunity = ContentOpportunity(
            organization_id=world.org,
            location_id=world.location,
            product_key="seo",
            target_reference=f"seo-opportunity:{world.attributed}",
            opportunity_type="seo",
            source_type="seo_analysis",
            source_reference=f"seo-opportunity:{world.attributed}",
            evidence_document={},
            evidence_hash=uuid4().hex + uuid4().hex,
            priority_score=70,
            status="accepted",
        )
        second = ContentOpportunity(
            organization_id=world.org,
            location_id=world.location,
            product_key="seo",
            target_reference=f"seo-opportunity:{world.attributed}",
            opportunity_type="seo",
            source_type="seo_analysis",
            source_reference=f"seo-opportunity:{world.attributed}",
            evidence_document={},
            evidence_hash=uuid4().hex + uuid4().hex,
            priority_score=70,
            status="accepted",
        )
        session.add_all([opportunity, second])
        await session.flush()
        return {
            "second_opportunity": second.id,
            "facts": facts,
            "attributed_url": attributed_page.normalized_url,
            "opportunity": opportunity.id,
            "query_only_content_opportunity": world.content_opportunity,
        }


async def _observe(
    factory: async_sessionmaker[AsyncSession], run_id: UUID, refs: list[str]
) -> None:
    """Record what the read tools would have shown the run."""
    async with factory.begin() as session:
        run = await session.get(AgentRun, run_id)
        assert run is not None
        run.source_references = list(dict.fromkeys([*run.source_references, *refs]))


async def _bind_agent_execution(
    factory: async_sessionmaker[AsyncSession], world: World, run_id: UUID
) -> None:
    """Production gives every agent run its own AIExecution on the same workflow run."""
    async with factory.begin() as session:
        run = await session.get(AgentRun, run_id)
        assert run is not None
        execution = await AgentRuntimeService()._task_and_execution(
            session, world.org, world.location, run.workflow_run_id, SKILLS[run.skill_key]
        )
        run.ai_execution_id = execution.id


async def _draft(
    factory: async_sessionmaker[AsyncSession],
    world: World,
    extra: dict[str, Any],
    *,
    opportunity: UUID,
    target_kind: str,
    target_reference: str,
    audience: str = "Locals planning a weekend brunch",
    run_draft: bool = True,
) -> tuple[UUID, str, str, dict[str, object]]:
    tools = AgentToolService()
    run_id = await _start_run(
        factory,
        world,
        workflow_key="agent.content",
        skill_key="content.operator",
        input_document={"context_reference": f"content-opportunity:{opportunity}"},
    )
    await _observe(factory, run_id, SOURCES)
    await _bind_agent_execution(factory, world, run_id)
    item = await _call(
        factory,
        tools,
        run_id,
        "create_content_proposal",
        {
            # The reference exactly as the read tool returns it.
            "content_opportunity_id": f"content-opportunity:{opportunity}",
            "content_type": "page",
            "title": "Brunch at Coco Maya",
            "slug": f"brunch-{uuid4().hex[:6]}",
        },
    )
    item_id = _proposal_ref(item, "content-item:").removeprefix("content-item:")
    brief = await _call(
        factory,
        tools,
        run_id,
        "create_content_brief",
        {
            "content_item_id": f"content-item:{item_id}",
            "audience": audience,
            "intent": "Show the brunch menu and hours",
            "target_kind": target_kind,
            "target_reference": target_reference,
            "approved_fact_revision_ids": [str(value) for value in extra["facts"]],
            "source_evidence_references": SOURCES,
        },
    )
    brief_id = _proposal_ref(brief, "content-brief:").removeprefix("content-brief:")
    if not run_draft:
        return run_id, item_id, brief_id, {}
    draft = await _call(
        factory,
        tools,
        run_id,
        "generate_content_draft_proposal",
        {
            "content_item_id": f"content-item:{item_id}",
            "content_brief_id": f"content-brief:{brief_id}",
            "approved_fact_revision_ids": [f"business-fact:{value}" for value in extra["facts"]],
            "source_evidence_references": SOURCES,
        },
    )
    return run_id, item_id, brief_id, draft


@pytest.mark.integration
def test_an_attributed_existing_page_brief_drafts_through_the_tool_and_the_handler(
    agent_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = agent_session_factory

    async def scenario() -> None:
        world = await _seed(factory)
        extra = await _extra_world(factory, world)
        run_id, item_id, brief_id, draft = await _draft(
            factory,
            world,
            extra,
            opportunity=extra["opportunity"],
            target_kind="existing_page",
            target_reference=extra["attributed_url"],
        )
        assert _proposal_ref(draft, "content-revision:")
        async with factory() as session:
            brief = await session.get(ContentBrief, UUID(brief_id))
            assert brief is not None
            assert brief.validation_requirements["target_resolution"] == "attributed"

        # The same shape through the durable content.draft_revision handler.
        run_id, item_id, brief_id, _ = await _draft(
            factory,
            world,
            extra,
            opportunity=extra["second_opportunity"],
            target_kind="existing_page",
            target_reference=extra["attributed_url"],
            audience="Visitors comparing happy hours",
            run_draft=False,
        )
        async with factory.begin() as session:
            run = await session.get(AgentRun, run_id)
            assert run is not None
            outcome = await _handle_content_draft_revision(
                session,
                organization_id=world.org,
                location_id=world.location,
                input_document={
                    "item_id": item_id,
                    "brief_id": brief_id,
                    "idempotency_key": f"handler-{uuid4().hex}",
                },
                correlation_id="recovery",
                workflow_run_id=run.workflow_run_id,
            )
        assert outcome.result == "succeeded", outcome.safe_error

    asyncio.run(scenario())


@pytest.mark.integration
@pytest.mark.parametrize("path", ["/brunch", "/happy-hour"])
def test_a_crawled_page_with_no_attribution_is_an_allowed_existing_page_target(
    agent_session_factory: async_sessionmaker[AsyncSession], path: str
) -> None:
    factory = agent_session_factory

    async def scenario() -> None:
        world = await _seed(factory)
        extra = await _extra_world(factory, world)
        # The query-only opportunity has no attributed page.
        _run, _item, brief_id, draft = await _draft(
            factory,
            world,
            extra,
            opportunity=world.content_opportunity,
            target_kind="existing_page",
            target_reference=f"https://example.invalid{path}",
        )
        assert _proposal_ref(draft, "content-revision:")
        async with factory() as session:
            brief = await session.get(ContentBrief, UUID(brief_id))
            assert brief is not None
            assert brief.validation_requirements["target_resolution"] == "selected"

    asyncio.run(scenario())


@pytest.mark.integration
def test_a_url_that_is_not_a_crawled_page_is_still_rejected(
    agent_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = agent_session_factory

    async def scenario() -> None:
        world = await _seed(factory)
        extra = await _extra_world(factory, world)
        with pytest.raises(ContentSEOTargetUnresolvedError):
            await _draft(
                factory,
                world,
                extra,
                opportunity=world.content_opportunity,
                target_kind="existing_page",
                target_reference="https://example.invalid/never-crawled",
            )

    asyncio.run(scenario())


@pytest.mark.integration
def test_unbound_recommendation_recovers_from_argument_errors_and_the_breaker_waits_for_three(
    agent_session_factory: async_sessionmaker[AsyncSession],
    stub_decisions: Callable[[World], None],  # noqa: F811 - the imported fixture
) -> None:
    factory = agent_session_factory

    async def scenario() -> None:
        world = await _seed(factory)
        stub_decisions(world)
        tools = AgentToolService()
        run_id = await _start_run(
            factory,
            world,
            workflow_key="agent.seo",
            skill_key="seo.operator",
            input_document={},
        )
        reference = f"seo-opportunity:{world.query_only}"
        await _observe(factory, run_id, [reference])
        base = {
            "proposed_action": "Add a brunch section to the page.",
            "expected_result_hypothesis": "More qualified clicks.",
            "risk": "low",
            "effort": "low",
        }

        # 1. opportunity_id missing: a typed, field-naming argument error.
        with pytest.raises(AgentToolDeniedError) as missing:
            await _call(factory, tools, run_id, "create_seo_recommendation_proposal", base)
        assert missing.value.code == TOOL_ARGUMENT_INVALID
        assert "opportunity_id" in str(missing.value)

        # 2. A second, different argument error does not stop the run.
        with pytest.raises(AgentToolDeniedError) as malformed:
            await _call(
                factory,
                tools,
                run_id,
                "create_seo_recommendation_proposal",
                {**base, "opportunity_id": "brunch"},
            )
        assert malformed.value.code == TOOL_ARGUMENT_INVALID
        assert "seo-opportunity:" in str(malformed.value)
        async with factory() as session:
            run = await session.get(AgentRun, run_id)
            assert run is not None and run.status == "running"

        # 3. The prefixed reference with evidence omitted creates the recommendation.
        created = await _call(
            factory,
            tools,
            run_id,
            "create_seo_recommendation_proposal",
            {**base, "opportunity_id": reference},
        )
        assert _proposal_ref(created, "seo-recommendation:")

        async with factory() as session:
            events = list(
                await session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.resource_id == run_id,
                        AuditEvent.event_type == "agent.tool.invoked",
                    )
                )
            )
        fingerprints = {
            e.event_metadata["message_fingerprint"]
            for e in events
            if e.event_metadata["error_code"]
        }
        assert len(fingerprints) == 2

    asyncio.run(scenario())


@pytest.mark.integration
def test_a_content_opportunity_that_is_not_accepted_names_the_real_reason_and_the_accepted_ones(
    agent_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    factory = agent_session_factory

    async def scenario() -> None:
        world = await _seed(factory)
        tools = AgentToolService()
        run_id = await _start_run(
            factory,
            world,
            workflow_key="agent.content",
            skill_key="content.operator",
            input_document={
                "context_reference": f"content-opportunity:{world.content_opportunity}"
            },
        )
        async with factory.begin() as session:
            await session.execute(
                update(ContentOpportunity)
                .where(ContentOpportunity.id == world.content_opportunity)
                .values(status="identified")
            )
        arguments = {
            "content_opportunity_id": f"content-opportunity:{world.content_opportunity}",
            "content_type": "page",
            "title": "T",
            "slug": "t",
        }
        with pytest.raises(AgentToolDeniedError) as raised:
            await _call(factory, tools, run_id, "create_content_proposal", arguments)
        message = str(raised.value)
        assert "outside the bound location" not in message
        assert "status 'identified'" in message and "must accept it in Content" in message
        assert "no accepted content opportunities" in message

        missing = {**arguments, "content_opportunity_id": str(uuid4())}
        with pytest.raises(AgentToolDeniedError) as absent:
            await _call(factory, tools, run_id, "create_content_proposal", missing)
        assert "was not found" in str(absent.value)

    asyncio.run(scenario())


def test_the_typed_argument_error_is_the_one_the_route_reports() -> None:
    from apps.api.app.agents.tools import ToolArgumentError, _uuid_reference

    with pytest.raises(ToolArgumentError) as raised:
        _uuid_reference("lead:nope", "lead_id", accepted_prefixes=("lead:",))
    assert raised.value.code == TOOL_ARGUMENT_INVALID == "TOOL_ARGUMENT_INVALID"
    assert str(raised.value) == (
        "lead_id must be a bare UUID or a lead:<uuid> reference; received 'nope'"
    )
    assert cast(Any, _uuid_reference)(f"lead:{uuid4()}", "lead_id", accepted_prefixes=("lead:",))
