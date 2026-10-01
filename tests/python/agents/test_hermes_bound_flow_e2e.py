"""A Coco Maya-shaped bound Hermes flow, end to end, on fixtures only.

SEO recommendation with a change set -> content draft for a `new_page` target ->
growth plan from the approved decision. The three production failures this guards
against: read tools denied to bound skills, citations of evidence LILOs itself bound the
run to being rejected as "not observed", and runs ending `completed` with nothing made.
"""

import asyncio
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.agents.bound_references import bound_source_references
from apps.api.app.agents.models import AgentRun, AgentSession
from apps.api.app.agents.service import AgentRuntimeService
from apps.api.app.agents.tools import AgentToolDeniedError, AgentToolService
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.execution.service import ExecutionService
from apps.api.app.growth.models import GrowthAction, GrowthInitiative
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.models import ContentBrief, ContentOpportunity
from apps.api.app.products.seo import decision as decision_module
from apps.api.app.products.seo.models import (
    SEOOpportunity,
    SEOPage,
    SEORecommendationRevision,
    SEOWebsite,
)
from apps.api.app.products.seo.site_change_service import SiteChangeService

READ_TOOLS = (
    "read_client_business_facts",
    "read_website_knowledge",
    "read_cross_product_summary",
    "inspect_workflow",
)
TITLE = "Best Brunch Spots in San Diego | Little Italy"
DESCRIPTION = "Our guide to the best brunch in San Diego, from rooftop patios to classics."
UNOBSERVED_OR_DENIED = {"HERMES_TOOL_DENIED", "EVIDENCE_NOT_OBSERVED"}
SETTINGS = Settings.model_validate({"environment": EnvironmentName.TEST, "ai_provider": "hermes"})


class World:
    def __init__(self) -> None:
        self.org: UUID
        self.location: UUID
        self.fact: UUID
        self.attributed: UUID
        self.query_only: UUID
        self.content_opportunity: UUID
        self.decisions: dict[UUID, dict[str, object]] = {}


def _decision(world: World, opportunity_id: UUID, *, page_id: UUID | None) -> dict[str, object]:
    reference = f"seo-opportunity:{opportunity_id}"
    return {
        "contract_version": "seo_decision.v1",
        "organization_id": str(world.org),
        "location_id": str(world.location),
        "website_id": str(uuid4()),
        "page_id": str(page_id) if page_id else None,
        "page_mapping_state": "mapped" if page_id else "unknown",
        "opportunity_id": str(opportunity_id),
        "recommendation_class": "technical_regression",
        "target_metric": None,
        "evidence_references": [reference, f"seo-search-observation:{uuid4()}"],
    }


async def _seed(factory: async_sessionmaker[AsyncSession]) -> World:
    world = World()
    async with factory.begin() as session:
        profile = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
        organization = Organization(
            name="Coco Maya Fixture",
            slug=f"coco-fixture-{uuid4().hex[:6]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add_all([profile, organization])
        await session.flush()
        location = Location(
            organization_id=organization.id,
            name="Coco Maya",
            slug=f"coco-{uuid4().hex[:6]}",
            location_type=LocationType.VIRTUAL,
            status=LocationStatus.ACTIVE,
            timezone="UTC",
            country_code="US",
            website_url="https://example.invalid",
            is_primary=True,
            version=1,
        )
        session.add(location)
        await session.flush()
        fact = BusinessFactRevision(
            organization_id=organization.id,
            location_id=location.id,
            fact_identity=uuid4(),
            fact_key="business.name",
            value_type="string",
            value="Coco Maya",
            source="client_input",
            authority="client_approved",
            status="active",
            effective_from=datetime(2026, 1, 1, tzinfo=UTC),
            revision=1,
            proposed_by=profile.id,
            approved_by=profile.id,
            approved_at=datetime.now(UTC),
            change_reason="e2e fixture",
        )
        website = SEOWebsite(
            organization_id=organization.id,
            location_id=location.id,
            key=f"coco-{uuid4().hex[:6]}",
            name="Coco Maya site",
            canonical_origin="https://example.invalid",
            status="active",
            ownership_status="verified",
            version=1,
        )
        session.add_all([fact, website])
        await session.flush()
        page = SEOPage(
            organization_id=organization.id,
            website_id=website.id,
            normalized_url="https://example.invalid/blog/best-brunch",
            observed_url="https://example.invalid/blog/best-brunch",
            normalization_reasons=[],
            robots_directives=[],
            internal_links=[],
            external_links=[],
            structured_data_present=False,
            indexability="indexable",
            technical_issues=[],
            quality_status="clean",
        )
        session.add(page)
        await session.flush()

        def opportunity(key: str, state: str) -> SEOOpportunity:
            return SEOOpportunity(
                organization_id=organization.id,
                location_id=location.id,
                website_id=website.id,
                page_id=page.id if state == "attributed" else None,
                attribution_state=state,
                opportunity_type="gsc_low_ctr",
                deduplication_key=key,
                active_marker="active",
                evidence={"query": key, "source": "google_search_console"},
                source_versions=["gsc.v1"],
                score_version=1,
                priority_score=80,
                score_explanation={"score_policy_version": "opportunity_score.v2"},
                status="identified",
                version=1,
            )

        attributed = opportunity("best brunch", "attributed")
        query_only = opportunity("date night guide", "query_only")
        session.add_all([attributed, query_only])
        await session.flush()
        content_opportunity = ContentOpportunity(
            organization_id=organization.id,
            location_id=location.id,
            product_key="seo",
            target_reference=f"seo-opportunity:{query_only.id}",
            opportunity_type="seo",
            source_type="seo_analysis",
            source_reference=f"seo-opportunity:{query_only.id}",
            evidence_document={},
            evidence_hash=uuid4().hex + uuid4().hex,
            priority_score=60,
            status="accepted",
        )
        session.add(content_opportunity)
        await session.flush()
        world.org, world.location, world.fact = organization.id, location.id, fact.id
        world.attributed, world.query_only = attributed.id, query_only.id
        world.content_opportunity = content_opportunity.id
        world.decisions[attributed.id] = _decision(world, attributed.id, page_id=page.id)
        world.decisions[query_only.id] = _decision(world, query_only.id, page_id=None)
    return world


async def _start_run(
    factory: async_sessionmaker[AsyncSession],
    world: World,
    *,
    workflow_key: str,
    skill_key: str,
    input_document: dict[str, object],
) -> UUID:
    async with factory.begin() as session:
        workflow = await ExecutionService().start_named(
            session,
            world.org,
            workflow_key,
            f"e2e-{uuid4().hex}",
            location_id=world.location,
            input_document=input_document,
            correlation_id="e2e",
            enqueue_job=False,
        )
        agent_session = AgentSession(
            organization_id=world.org,
            location_id=world.location,
            skill_key=skill_key,
            namespace_hash=uuid4().hex + uuid4().hex,
            hermes_session_key=uuid4().hex,
            status="active",
            expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            version=1,
        )
        session.add(agent_session)
        await session.flush()
        run = AgentRun(
            organization_id=world.org,
            location_id=world.location,
            workflow_run_id=workflow.id,
            agent_session_id=agent_session.id,
            skill_key=skill_key,
            skill_version=1,
            hermes_session_id=agent_session.hermes_session_key,
            hermes_run_id=f"hermes-e2e-{uuid4().hex}",
            correlation_id="e2e",
            status="running",
            capability_snapshot={},
            output_references=[],
            # Exactly what AgentRuntimeService._prepare records at run creation.
            source_references=await bound_source_references(session, world.org, input_document),
            event_count=0,
        )
        session.add(run)
        await session.flush()
        return run.id


async def _call(
    factory: async_sessionmaker[AsyncSession],
    tools: AgentToolService,
    run_id: UUID,
    tool: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, object]:
    """One tool call as the route makes it: its own transaction, committed afterwards."""
    failure: Exception | None = None
    result: dict[str, object] = {}
    async with factory.begin() as session:
        run = await session.get(AgentRun, run_id)
        assert run is not None
        try:
            result = await tools.invoke(session, run, tool, arguments or {})
        except Exception as exc:  # noqa: BLE001
            # The route turns a failed tool into a JSON error, so its audit event and
            # any run stop are committed. Do the same, then re-raise for the test.
            failure = exc
    if failure is not None:
        raise failure
    return result


async def _read_tools_are_not_denied(
    factory: async_sessionmaker[AsyncSession], tools: AgentToolService, run_id: UUID
) -> None:
    for tool in READ_TOOLS:
        try:
            await _call(factory, tools, run_id, tool)
        except AgentToolDeniedError as exc:
            assert exc.code not in UNOBSERVED_OR_DENIED, f"{tool}: {exc}"
        except Exception:  # noqa: BLE001 - other failures are not what this asserts
            pass


def _proposal_ref(result: dict[str, object], prefix: str) -> str:
    references = cast(list[str], result["proposal_references"])
    return next(ref for ref in references if ref.startswith(prefix))


async def _complete(factory: async_sessionmaker[AsyncSession], run_id: UUID) -> AgentRun:
    async with factory.begin() as session:
        run = await session.get(AgentRun, run_id)
        assert run is not None
        await AgentRuntimeService()._persist_event(
            session,
            SETTINGS,
            run,
            {
                "event": "run.completed",
                "output": "done",
                "timestamp": datetime.now(UTC).timestamp(),
            },
        )
    async with factory() as session:
        final = await session.get(AgentRun, run_id)
        assert final is not None
        return final


@pytest.fixture
def stub_decisions(monkeypatch: pytest.MonkeyPatch) -> Callable[[World], None]:
    """LILOs derives decisions from GSC observations; fixtures supply them directly."""

    def install(world: World) -> None:
        original = decision_module.resolve_decision

        async def resolve(
            _session: object, _org: UUID, opportunity: SEOOpportunity, _refs: list[str]
        ) -> dict[str, object]:
            return world.decisions[opportunity.id]

        for module in list(sys.modules.values()):
            if getattr(module, "resolve_decision", None) is original:
                monkeypatch.setattr(module, "resolve_decision", resolve)

        async def no_quality(*_args: object) -> Any:
            from apps.api.app.products.seo.change_quality import QualityContext

            return QualityContext()

        monkeypatch.setattr(SiteChangeService, "quality_context", no_quality)

    return install


@pytest.mark.integration
def test_bound_seo_content_and_growth_runs_complete_without_denials_or_unobserved_citations(
    agent_session_factory: async_sessionmaker[AsyncSession],
    stub_decisions: Callable[[World], None],
) -> None:
    factory = agent_session_factory

    async def scenario() -> None:
        world = await _seed(factory)
        stub_decisions(world)
        tools = AgentToolService()
        runs: list[UUID] = []

        # --- 1. SEO: a recommendation with an exact change set -------------------------
        seo_run = await _start_run(
            factory,
            world,
            workflow_key="agent.seo",
            skill_key="seo.operator",
            input_document={
                "seo_opportunity_id": str(world.attributed),
                "seo_decision_snapshot": world.decisions[world.attributed],
                "site_change_context": {
                    "status": "available",
                    "page_id": world.decisions[world.attributed]["page_id"],
                    "page_url": "/blog/best-brunch",
                    "fields": {"seo_title": TITLE, "meta_description": DESCRIPTION},
                    "limits": {"seo_title": 60, "meta_description": 160},
                },
            },
        )
        runs.append(seo_run)
        await _read_tools_are_not_denied(factory, tools, seo_run)
        proposed = await _call(
            factory,
            tools,
            seo_run,
            "create_seo_recommendation_proposal",
            {
                "proposed_action": "Lead the title with the target query.",
                "expected_result_hypothesis": "A clearer title lifts click-through.",
                "risk": "low",
                "effort": "low",
                "site_changes": [
                    {
                        "field": "seo_title",
                        "proposed_value": "Best Brunch in San Diego: Little Italy Guide",
                        "rationale": "Front-loads the query.",
                    }
                ],
            },
        )
        assert proposed["data"] == {"accepted": True}
        seo_final = await _complete(factory, seo_run)
        assert seo_final.status == "completed", seo_final.safe_error_code
        revision_ref = next(
            str(ref) for ref in seo_final.output_references if str(ref).startswith("seo-rec")
        )
        revision_id = UUID(revision_ref.removeprefix("seo-recommendation:"))
        async with factory.begin() as session:
            revision = await session.get(SEORecommendationRevision, revision_id)
            assert revision is not None and revision.change_set is not None
            revision.status = "approved"  # the human approval, as a fixture

        # --- 2. Content: a new_page draft from a query-only opportunity ---------------
        content_run = await _start_run(
            factory,
            world,
            workflow_key="agent.content",
            skill_key="content.operator",
            input_document={
                "context_reference": f"content-opportunity:{world.content_opportunity}"
            },
        )
        runs.append(content_run)
        await _read_tools_are_not_denied(factory, tools, content_run)
        query_reference = f"seo-opportunity:{world.query_only}"
        item = await _call(
            factory,
            tools,
            content_run,
            "create_content_proposal",
            {
                "content_opportunity_id": str(world.content_opportunity),
                "content_type": "blog",
                "title": "A Date Night Guide",
                "slug": "date-night-guide",
            },
        )
        item_id = _proposal_ref(item, "content-item:").removeprefix("content-item:")
        brief = await _call(
            factory,
            tools,
            content_run,
            "create_content_brief",
            {
                "content_item_id": item_id,
                "audience": "Couples planning a night out",
                "intent": "Help locals plan a date night",
                "target_kind": "new_page",
                "target_reference": "/date-night-guide",
                "approved_fact_revision_ids": [str(world.fact)],
                "source_evidence_references": [query_reference],
            },
        )
        brief_id = _proposal_ref(brief, "content-brief:").removeprefix("content-brief:")
        draft = await _call(
            factory,
            tools,
            content_run,
            "generate_content_draft_proposal",
            {
                "content_item_id": item_id,
                "content_brief_id": brief_id,
                "approved_fact_revision_ids": [str(world.fact)],
                "source_evidence_references": [query_reference],
            },
        )
        assert _proposal_ref(draft, "content-revision:")
        content_final = await _complete(factory, content_run)
        assert content_final.status == "completed", content_final.safe_error_code
        async with factory() as session:
            stored = await session.get(ContentBrief, UUID(brief_id))
            assert stored is not None
            assert (stored.target_kind, stored.status) == ("new_page", "ready")

        # --- 3. Growth: a plan generated from the approved decision --------------------
        growth_run = await _start_run(
            factory,
            world,
            workflow_key="agent.growth",
            skill_key="growth.planner",
            input_document={"context_reference": revision_ref},
        )
        runs.append(growth_run)
        await _read_tools_are_not_denied(factory, tools, growth_run)
        search_observation = next(
            str(ref)
            for ref in cast(list[str], world.decisions[world.attributed]["evidence_references"])
            if str(ref).startswith("seo-search-observation:")
        )
        plan = await _call(
            factory,
            tools,
            growth_run,
            "create_growth_plan",
            {
                "objective": "Lift click-through on the brunch guide",
                "rationale": "The approved title change is ready to implement.",
                # Cited without a read: bound to the run, so already observed.
                "source_references": [revision_ref, search_observation],
                "priority_score": 70,
                "confidence": 0.7,
                "actions": [
                    {
                        "action_key": "apply-title",
                        "product_key": "seo",
                        "action_type": "site_implementation",
                        # Paraphrased on purpose: LILOs takes these from the decision.
                        "target_reference": "the brunch page",
                        "execution_mode": "workflow",
                        "evidence_references": [revision_ref],
                        "expected_result_hypothesis": "more clicks",
                        "verification_plan": {},
                        "risk": "low",
                        "effort": "low",
                    }
                ],
            },
        )
        assert _proposal_ref(plan, "growth-initiative:")
        growth_final = await _complete(factory, growth_run)
        assert growth_final.status == "completed", growth_final.safe_error_code
        async with factory() as session:
            action = await session.scalar(
                select(GrowthAction).where(GrowthAction.action_key == "apply-title")
            )
            assert action is not None
            page_id = world.decisions[world.attributed]["page_id"]
            assert action.target_reference == f"seo-page:{page_id}"
            assert action.expected_result_hypothesis == "A clearer title lifts click-through."
            assert await session.scalar(
                select(GrowthInitiative.id).where(GrowthInitiative.id == action.initiative_id)
            )

            # Zero denials and zero unobserved-citation errors across all three runs.
            events = list(
                await session.scalars(
                    select(AuditEvent).where(
                        AuditEvent.organization_id == world.org,
                        AuditEvent.event_type == "agent.tool.invoked",
                        AuditEvent.resource_id.in_(runs),
                    )
                )
            )
            assert events
            offending = [
                (e.event_metadata["tool_name"], e.event_metadata.get("error_code"))
                for e in events
                if e.event_metadata.get("error_code") in UNOBSERVED_OR_DENIED
            ]
            assert offending == []

    asyncio.run(scenario())


@pytest.mark.integration
def test_an_unobserved_citation_still_fails_and_stops_the_run_on_repeat(
    agent_session_factory: async_sessionmaker[AsyncSession],
    stub_decisions: Callable[[World], None],
) -> None:
    factory = agent_session_factory

    async def scenario() -> None:
        world = await _seed(factory)
        stub_decisions(world)
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
        item = await _call(
            factory,
            tools,
            run_id,
            "create_content_proposal",
            {
                "content_opportunity_id": str(world.content_opportunity),
                "content_type": "blog",
                "title": "Guide",
                "slug": "guide",
            },
        )
        item_id = _proposal_ref(item, "content-item:").removeprefix("content-item:")
        arguments = {
            "content_item_id": item_id,
            "audience": "Locals",
            "intent": "Plan",
            "target_kind": "new_page",
            "target_reference": "/guide",
            "approved_fact_revision_ids": [str(world.fact)],
            "source_evidence_references": [f"seo-search-observation:{uuid4()}"],  # never observed
        }
        for _ in range(2):
            with pytest.raises(AgentToolDeniedError) as denied:
                await _call(factory, tools, run_id, "create_content_brief", arguments)
            assert denied.value.code == "EVIDENCE_NOT_OBSERVED"
        async with factory() as session:
            run = await session.get(AgentRun, run_id)
            assert run is not None
            assert (run.status, run.safe_error_code) == ("failed", "EVIDENCE_NOT_OBSERVED")
        final = await _complete(factory, run_id)
        assert final.status == "failed"  # a late completion cannot revive a stopped run

    asyncio.run(scenario())
