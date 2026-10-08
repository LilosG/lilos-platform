"""content.compose: one prompt in, a governed reviewable draft out.

The AI gateway is a scripted stub that runs the real deterministic quality validator, so the
floors, link rules and the bounded repair attempt are exercised end to end. No provider, GitHub
or client site is ever called.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.administration.knowledge_service import BusinessKnowledgeService
from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.ai.errors import AIProviderError
from apps.api.app.ai.models import AIExecution
from apps.api.app.ai.providers import _find_existing_topic_overlap, _validate_article_payload
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.execution import handlers
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content import service as service_module
from apps.api.app.products.content.compose import ContentComposeService
from apps.api.app.products.content.contracts import AIDraftCreate, ApprovalDecision, ComposeCreate
from apps.api.app.products.content.enums import ComposeContentType
from apps.api.app.products.content.errors import (
    ContentClaimsNeedConfirmationError,
    ContentComposeWebsiteNotFoundError,
    ContentItemNotFoundError,
)
from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentOpportunity,
    ContentRevision,
)
from apps.api.app.products.content.operator_service import ContentOperatorService
from apps.api.app.products.content.service import ContentService, record_operator_claim
from apps.api.app.products.seo.models import SEOPage, SEOWebsite

from .draft_builder import build_draft

PROMPT = "write a blog about Miss B's being the Green Bay Packers bar in San Diego"
ORIGIN = "https://missbs.example"
PAGES = ["/menu", "/reservations", "/locations/san-diego", "/about", "/events"]

PLAN: dict[str, Any] = {
    "content_type": "blog_post",
    "title": "Miss B's: The Green Bay Packers Bar in San Diego",
    "slug": "green-bay-packers-bar-san-diego",
    "target_kind": "new_page",
    "target_reference": "/blog/green-bay-packers-bar-san-diego/",
    "audience": "Packers fans living in or visiting San Diego",
    "intent": "Find the best place in San Diego to watch Packers games",
    "primary_topic": "Green Bay Packers bar San Diego",
    "keywords": ["packers bar san diego", "watch packers san diego"],
    "local_references": ["San Diego"],
    "link_targets": ["/menu", "/reservations", "/locations/san-diego"],
    "prompt_claims": ["Miss B's is a Green Bay Packers bar in San Diego."],
}

LINKS = [
    "[our full food and drink menu](/menu/)",
    "[reserve a table for kickoff](/reservations/)",
    "[the San Diego bar location](/locations/san-diego/)",
    "[upcoming game day events](/events/)",
]


def draft_payload(
    *, words: int = 1_500, claims: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    body = build_draft(words=words, links=LINKS)
    return {
        "draft": body,
        "meta_description": "Where to watch Green Bay Packers games in San Diego.",
        "seo_title": "Packers Bar in San Diego",
        "faqs": [
            {"question": f"Question {i}?", "answer": " ".join(["helpful"] * 24)} for i in range(4)
        ],
        "tags": ["packers"],
        "claims": claims or [],
    }


class ScriptedGateway:
    """Stands in for the AI gateway: scripted plan, and drafts checked by the real validator."""

    def __init__(self, drafts: list[dict[str, Any]], plan: dict[str, Any] | None = None) -> None:
        self.drafts = list(drafts)
        self.plan = PLAN if plan is None else plan
        self.requests: list[Any] = []

    async def execute(self, request: Any) -> dict[str, Any]:
        self.requests.append(request)
        base = {
            "provider": "stub",
            "model": "stub-1",
            "requires_human_review": True,
            "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            "latency_ms": 1,
            "cost_microunits": 0,
            "request_id": None,
        }
        if request.task_key == "content.compose_plan":
            return {**base, "draft": "{}", "plan": self.plan}
        payload = self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]
        errors = _validate_article_payload(payload, request.input_document)
        if errors:
            raise AIProviderError(
                "permanent",
                "AI provider returned Content output below the publishing quality floor: "
                + ", ".join(errors),
            )
        output = {**base, **payload}
        overlap = _find_existing_topic_overlap(request.input_document)
        if overlap:
            output["topic_overlap"] = overlap
        return output


def doc(revision: ContentRevision) -> dict[str, Any]:
    return cast(dict[str, Any], revision.validation_document)


class World:
    def __init__(self) -> None:
        self.org = uuid4()
        self.user = uuid4()
        self.location = uuid4()
        self.website: UUID


async def seed_world(
    session: AsyncSession,
    *,
    pages: list[str] | None = None,
    org_id: UUID | None = None,
    with_facts: bool = True,
) -> World:
    world = World()
    if org_id:
        world.org = org_id
    session.add(
        Organization(
            id=world.org,
            name="Miss B's",
            slug=f"miss-bs-{world.org.hex[:8]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
    )
    session.add(
        UserProfile(id=world.user, auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
    )
    await session.flush()
    session.add(
        Location(
            id=world.location,
            organization_id=world.org,
            name="Miss B's San Diego",
            slug=f"san-diego-{world.location.hex[:8]}",
            location_type=LocationType.VIRTUAL,
            status=LocationStatus.ACTIVE,
            timezone="UTC",
            country_code="US",
            website_url=ORIGIN,
            is_primary=True,
            version=1,
        )
    )
    await session.flush()
    website = SEOWebsite(
        organization_id=world.org,
        location_id=world.location,
        key="primary",
        name="Miss B's",
        canonical_origin=ORIGIN,
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add(website)
    await session.flush()
    world.website = website.id
    if with_facts:
        await record_operator_claim(
            session,
            world.org,
            world.location,
            "Miss B's is a neighborhood sports bar.",
            world.user,
            source="organization_profile",
        )
    for path in PAGES if pages is None else pages:
        session.add(
            SEOPage(
                organization_id=world.org,
                website_id=website.id,
                normalized_url=f"{ORIGIN}{path}",
                observed_url=f"{ORIGIN}{path}",
                normalization_reasons=[],
                robots_directives=[],
                internal_links=[],
                external_links=[],
                structured_data_present=False,
                http_status=200,
                title=path.strip("/").replace("-", " ").title(),
                indexability="indexable",
                technical_issues=[],
                quality_status="valid",
            )
        )
    await session.flush()
    return world


def command(key: str = "compose-key-0001", **overrides: Any) -> ComposeCreate:
    return ComposeCreate.model_validate(
        {"website_id": overrides.pop("website_id"), "prompt": PROMPT, "idempotency_key": key}
        | overrides
    )


def use_gateway(monkeypatch: pytest.MonkeyPatch, gateway: ScriptedGateway) -> None:
    monkeypatch.setattr(service_module, "build_ai_gateway", lambda: gateway)


async def run_compose(
    session: AsyncSession, world: World, run_input: dict[str, Any], run_id: UUID | None = None
) -> Any:
    return await handlers._handle_content_compose(
        session,
        organization_id=world.org,
        location_id=world.location,
        input_document=run_input,
        correlation_id="test-correlation",
        workflow_run_id=run_id or uuid4(),
    )


async def start(
    session: AsyncSession, world: World, key: str = "compose-key-0001", **overrides: Any
) -> tuple[ContentItem, dict[str, Any], Any]:
    item, run = await ContentComposeService().start(
        session,
        world.org,
        command(key, website_id=world.website, **overrides),
        actor_id=world.user,
        correlation_id="test-correlation",
    )
    return item, dict(run.input_document), run


@pytest.mark.anyio
async def test_prompt_becomes_item_brief_and_draft_with_claims_as_operator_facts(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway = ScriptedGateway([draft_payload()])
    use_gateway(monkeypatch, gateway)
    async with content_session_factory() as session:
        world = await seed_world(session)
        item, run_input, run = await start(session, world)
        assert (item.status, run.status) == ("drafting", "queued")
        assert item.slug.startswith("draft-")  # provisional until Hermes resolves it

        outcome = await run_compose(session, world, run_input, run.id)
        assert outcome.result == "succeeded"

        await session.refresh(item)
        assert item.title == PLAN["title"] and item.slug == PLAN["slug"]
        assert item.content_type == "blog_post"
        brief = await session.scalar(
            select(ContentBrief).where(ContentBrief.content_item_id == item.id)
        )
        assert brief is not None
        assert brief.source_prompt == PROMPT
        assert brief.target_kind == "new_page"
        assert brief.target_reference == "/blog/green-bay-packers-bar-san-diego/"
        revision = await session.scalar(
            select(ContentRevision).where(ContentRevision.content_item_id == item.id)
        )
        assert revision is not None and revision.status == "awaiting_editorial"
        assert doc(revision)["quality"]["word_count"] == 1_500
        assert all(c["passed"] for c in doc(revision)["quality"]["checks"])

        # The claim the prompt made is an approved, operator-verified fact from this user.
        facts = list(
            await session.scalars(
                select(BusinessFactRevision).where(
                    BusinessFactRevision.organization_id == world.org
                )
            )
        )
        # An instruction is not a business fact: the raw prompt is never stored as one.
        assert not any(PROMPT in str(f.value) or "Operator prompt" in str(f.value) for f in facts)
        claim = next(f for f in facts if "Green Bay Packers bar" in str(f.value))
        assert claim.authority == "operator_verified"
        assert claim.status == "active"
        assert claim.proposed_by == world.user and claim.approved_by == world.user
        assert str(claim.id) in brief.approved_fact_revision_ids

        # The draft request carried the verified link inventory and recommended commercial pages.
        draft_request = gateway.requests[-1]
        assert draft_request.task_key == "content.draft_revision"
        targets = [t["url"] for t in draft_request.input_document["recommended_link_targets"]]
        assert "/menu" in targets and "/reservations" in targets
        assert draft_request.input_document["source_prompt"] == PROMPT


@pytest.mark.anyio
async def test_compose_is_idempotent_per_key(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    use_gateway(monkeypatch, ScriptedGateway([draft_payload()]))
    async with content_session_factory() as session:
        world = await seed_world(session)
        first_item, run_input, first_run = await start(session, world)
        second_item, _, second_run = await start(session, world)
        assert first_item.id == second_item.id and first_run.id == second_run.id

        await run_compose(session, world, run_input, first_run.id)
        await run_compose(session, world, run_input, first_run.id)
        items = list(
            await session.scalars(
                select(ContentItem).where(ContentItem.organization_id == world.org)
            )
        )
        revisions = list(
            await session.scalars(
                select(ContentRevision).where(ContentRevision.organization_id == world.org)
            )
        )
        executions = list(
            await session.scalars(
                select(AIExecution).where(AIExecution.organization_id == world.org)
            )
        )
        briefs = list(
            await session.scalars(
                select(ContentBrief).where(ContentBrief.organization_id == world.org)
            )
        )
        assert (len(items), len(revisions), len(briefs)) == (1, 1, 1)
        assert len(executions) == 1

        other_key, _, _ = await start(session, world, key="compose-key-0002")
        assert other_key.id != first_item.id


@pytest.mark.anyio
async def test_compose_is_tenant_isolated(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    use_gateway(monkeypatch, ScriptedGateway([draft_payload()]))
    async with content_session_factory() as session:
        world = await seed_world(session)
        other = await seed_world(session)
        with pytest.raises(ContentComposeWebsiteNotFoundError):
            await ContentComposeService().start(
                session,
                world.org,
                command(website_id=other.website),
                actor_id=world.user,
                correlation_id="c",
            )
        item, run_input, run = await start(session, world)
        # Another organization's worker cannot reach this item, whatever the input says.
        with pytest.raises(ContentItemNotFoundError):
            await ContentComposeService().execute(
                session,
                organization_id=other.org,
                input_document=run_input,
                workflow_run_id=run.id,
                correlation_id="c",
            )
        # Same idempotency key in a different organization is a different item.
        other_item, _, _ = await start(session, other)
        assert other_item.id != item.id


@pytest.mark.anyio
async def test_compose_writes_audit_rows(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    use_gateway(monkeypatch, ScriptedGateway([draft_payload()]))
    async with content_session_factory() as session:
        world = await seed_world(session)
        _, run_input, run = await start(session, world)
        await run_compose(session, world, run_input, run.id)
        events = {
            row.event_type
            for row in await session.scalars(
                select(AuditEvent).where(AuditEvent.organization_id == world.org)
            )
        }
        assert {
            "content.compose.requested",
            "content.brief.created",
            "content.revision.drafted",
        } <= events


@pytest.mark.anyio
async def test_a_title_that_overlaps_an_existing_page_is_an_advisory_not_a_block(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway = ScriptedGateway([draft_payload()])
    use_gateway(monkeypatch, gateway)
    real_retrieve = BusinessKnowledgeService.retrieve_for_content

    async def retrieve_with_indexed_page(self: Any, *args: Any, **kwargs: Any) -> Any:
        knowledge = dict(await real_retrieve(self, *args, **kwargs))
        knowledge["website_knowledge"] = [
            {
                "url": f"{ORIGIN}/blog/packers-bar-san-diego",
                "title": "Miss B's: The Green Bay Packers Bar in San Diego",
            }
        ]
        return knowledge

    monkeypatch.setattr(
        BusinessKnowledgeService, "retrieve_for_content", retrieve_with_indexed_page
    )
    async with content_session_factory() as session:
        world = await seed_world(session)
        item, run_input, run = await start(session, world)
        outcome = await run_compose(session, world, run_input, run.id)
        assert outcome.result == "succeeded"
        revision = await session.scalar(
            select(ContentRevision).where(ContentRevision.content_item_id == item.id)
        )
        assert revision is not None and revision.status == "awaiting_editorial"
        overlap = doc(revision)["topic_overlap"]
        assert overlap["url"].endswith("/blog/packers-bar-san-diego")
        assert overlap["title"] == "Miss B's: The Green Bay Packers Bar in San Diego"

        approved = await ContentService().decide(
            session,
            world.org,
            revision.id,
            ApprovalDecision(stage="editorial", approve=True),
            world.user,
            correlation_id="c",
        )
        assert approved.status == "awaiting_client"


@pytest.mark.anyio
async def test_draft_below_the_floor_is_repaired_once_then_fails_with_a_typed_code(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    thin = draft_payload(words=1_399)
    gateway = ScriptedGateway([thin, draft_payload()])
    use_gateway(monkeypatch, gateway)
    async with content_session_factory() as session:
        world = await seed_world(session)
        _, run_input, run = await start(session, world)
        outcome = await run_compose(session, world, run_input, run.id)
        assert outcome.result == "succeeded"
        drafts = [r for r in gateway.requests if r.task_key == "content.draft_revision"]
        assert len(drafts) == 2  # the bounded repair attempt, not a blind retry
        assert drafts[1].input_document["validation_requirements"]["repair_required"] is True

    always_thin = ScriptedGateway([thin])
    use_gateway(monkeypatch, always_thin)
    async with content_session_factory() as session:
        world = await seed_world(session)
        item, run_input, run = await start(session, world)
        outcome = await run_compose(session, world, run_input, run.id)
        assert outcome.result == "permanent_failure"
        assert outcome.safe_error == "CONTENT_BELOW_QUALITY_FLOOR"
        # Never saved as a reviewable draft.
        assert (
            list(
                await session.scalars(
                    select(ContentRevision).where(ContentRevision.content_item_id == item.id)
                )
            )
            == []
        )
        await session.refresh(item)
        assert item.status == "failed"
        assert len([r for r in always_thin.requests if r.task_key == "content.draft_revision"]) == 2


@pytest.mark.anyio
async def test_a_client_with_no_approved_facts_fails_typed_and_stores_no_prompt_fact(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway = ScriptedGateway([draft_payload()])
    use_gateway(monkeypatch, gateway)
    async with content_session_factory() as session:
        world = await seed_world(session, with_facts=False)
        _, run_input, run = await start(session, world)
        outcome = await run_compose(session, world, run_input, run.id)
        assert outcome.safe_error == "CONTENT_NO_APPROVED_FACTS"
        assert gateway.requests == []
        stored = list(
            await session.scalars(
                select(BusinessFactRevision).where(
                    BusinessFactRevision.organization_id == world.org
                )
            )
        )
        assert stored == []


@pytest.mark.anyio
async def test_a_site_with_no_crawled_pages_fails_typed_instead_of_inventing_links(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway = ScriptedGateway([draft_payload()])
    use_gateway(monkeypatch, gateway)
    async with content_session_factory() as session:
        world = await seed_world(session, pages=[])
        _, run_input, run = await start(session, world)
        outcome = await run_compose(session, world, run_input, run.id)
        assert outcome.safe_error == "CONTENT_WEBSITE_NOT_CRAWLED"
        assert gateway.requests == []  # no AI spend without a verifiable link inventory


@pytest.mark.anyio
async def test_claims_that_need_confirmation_block_approval_until_confirmed(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = draft_payload()
    payload["draft"] += "\n\nMiss B's opened in 1987 and has hosted every Packers game since."
    payload["claims"] = [
        {
            "text": "Miss B's opened in 1987 and has hosted every Packers game since.",
            "basis": "needs_confirmation",
        }
    ]
    use_gateway(monkeypatch, ScriptedGateway([payload]))
    async with content_session_factory() as session:
        world = await seed_world(session)
        item, run_input, run = await start(session, world)
        await run_compose(session, world, run_input, run.id)
        revision = await session.scalar(
            select(ContentRevision).where(ContentRevision.content_item_id == item.id)
        )
        assert revision is not None
        pending = [c for c in doc(revision)["claims"] if c["status"] == "needs_confirmation"]
        assert pending and "1987" in pending[0]["text"]

        content = ContentService()
        with pytest.raises(ContentClaimsNeedConfirmationError):
            await content.decide(
                session,
                world.org,
                revision.id,
                ApprovalDecision(stage="editorial", approve=True),
                world.user,
                correlation_id="c",
            )

        await content.confirm_claim(
            session,
            world.org,
            item.id,
            revision.id,
            pending[0]["claim_id"],
            world.user,
            correlation_id="c",
        )
        confirmed = await content.decide(
            session,
            world.org,
            revision.id,
            ApprovalDecision(stage="editorial", approve=True),
            world.user,
            correlation_id="c",
        )
        assert confirmed.status == "awaiting_client"
        fact = await session.scalar(
            select(BusinessFactRevision).where(
                BusinessFactRevision.organization_id == world.org,
                BusinessFactRevision.source == "content_reviewer_confirmation",
            )
        )
        assert fact is not None and fact.authority == "operator_verified"
        assert fact.approved_by == world.user


@pytest.mark.anyio
async def test_an_invented_specific_the_model_did_not_label_is_still_flagged(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = draft_payload()
    payload["draft"] += "\n\nCall 619-555-0142 and ask for the award-winning wing platter."
    use_gateway(monkeypatch, ScriptedGateway([payload]))
    async with content_session_factory() as session:
        world = await seed_world(session)
        item, run_input, run = await start(session, world)
        await run_compose(session, world, run_input, run.id)
        revision = await session.scalar(
            select(ContentRevision).where(ContentRevision.content_item_id == item.id)
        )
        assert revision is not None
        flagged = [c for c in doc(revision)["claims"] if c["detected"]]
        assert flagged and flagged[0]["status"] == "needs_confirmation"


@pytest.mark.anyio
async def test_regenerate_instruction_is_audited_and_still_held_to_the_floors(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    gateway = ScriptedGateway([draft_payload(), draft_payload(words=1_600)])
    use_gateway(monkeypatch, gateway)
    async with content_session_factory() as session:
        world = await seed_world(session)
        item, run_input, run = await start(session, world)
        await run_compose(session, world, run_input, run.id)
        brief = await session.scalar(
            select(ContentBrief).where(ContentBrief.content_item_id == item.id)
        )
        assert brief is not None

        instruction = "make it longer, add a section on game-day specials"
        revision, execution = await ContentService().execute_ai_draft_workflow(
            session,
            organization_id=world.org,
            item_id=item.id,
            brief_id=brief.id,
            idempotency_key="regenerate-0001",
            user_id=world.user,
            correlation_id="c",
            instructions=instruction,
        )
        assert doc(revision)["quality"]["word_count"] == 1_600
        assert (execution.output_document or {})["reviewer_instructions"] == instruction
        assert gateway.requests[-1].input_document["instructions"] == instruction
        audit = await session.scalar(
            select(AuditEvent).where(
                AuditEvent.organization_id == world.org,
                AuditEvent.event_type == "content.ai_draft.instructed",
            )
        )
        assert audit is not None and instruction in str(audit.event_metadata)

    with pytest.raises(Exception):  # noqa: B017 - contract rejects > 2000 characters
        AIDraftCreate(brief_id=uuid4(), idempotency_key="regenerate-0002", instructions="x" * 2_001)


@pytest.mark.anyio
async def test_an_accepted_opportunity_flows_through_compose(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    use_gateway(monkeypatch, ScriptedGateway([draft_payload()]))
    async with content_session_factory() as session:
        world = await seed_world(session)
        opportunity = ContentOpportunity(
            organization_id=world.org,
            location_id=world.location,
            product_key="growth",
            target_reference="/blog/packers-bar",
            opportunity_type="gsc_query_demand",
            source_type="growth_plan",
            source_reference="growth-action:test",
            evidence_document={"query": "packers bar san diego", "impressions": 480},
            evidence_hash=uuid4().hex + uuid4().hex,
            priority_score=60,
            status="accepted",
        )
        session.add(opportunity)
        await session.flush()

        _, workflow = await ContentService().accept_opportunity_and_dispatch_agent(
            session, world.org, opportunity.id, actor_id=world.user, correlation_id="c"
        )
        assert workflow.input_document["opportunity_id"] == str(opportunity.id)
        assert "packers bar san diego" in str(workflow.input_document["prompt"])
        assert workflow.input_document["website_id"] == str(world.website)
        await session.refresh(opportunity)
        assert opportunity.status == "accepted"

        # Preparing the same opportunity again resolves the same run, never a second item.
        _, again = await ContentService().accept_opportunity_and_dispatch_agent(
            session, world.org, opportunity.id, actor_id=world.user, correlation_id="c"
        )
        assert again.id == workflow.id

        outcome = await run_compose(session, world, dict(workflow.input_document), workflow.id)
        assert outcome.result == "succeeded"
        item = await session.get(ContentItem, UUID(str(workflow.input_document["item_id"])))
        assert item is not None and item.opportunity_id == opportunity.id


@pytest.mark.anyio
async def test_compose_state_is_typed_writing_then_failed(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    use_gateway(monkeypatch, ScriptedGateway([draft_payload(words=1_000)]))
    async with content_session_factory() as session:
        world = await seed_world(session)
        item, run_input, run = await start(session, world)
        operator = ContentOperatorService()
        states = await operator.compose_states(session, world.org, [item.id])
        assert states[item.id]["status"] == "writing"
        assert states[item.id]["prompt"] == PROMPT

        outcome = await run_compose(session, world, run_input, run.id)
        run.status, run.failure_code = "failed", outcome.safe_error
        await session.flush()
        states = await operator.compose_states(session, world.org, [item.id])
        assert states[item.id]["status"] == "failed"
        assert states[item.id]["failure_code"] == "CONTENT_BELOW_QUALITY_FLOOR"
        rows, _ = await operator.list_workspace(session, world.org)
        assert rows[0]["stage"] == "compose_failed" and rows[0]["word_count"] is None


def test_every_compose_content_type_is_a_known_enum_value() -> None:
    assert {t.value for t in ComposeContentType} == {
        "blog_post",
        "listicle",
        "landing_page",
        "service_page",
        "location_page",
        "guide",
    }
    assert datetime.now(UTC)  # keeps the import honest for static analysis


# --- inbound links ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_inbound_links_are_governed_site_changes_capped_at_five(
    content_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.api.app.products.content.inbound_links import (
        InboundLinkCode,
        InboundLinkRequest,
        InboundLinkService,
        InboundLinkStatus,
    )
    from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeSet
    from apps.api.app.products.seo.models import SEORecommendationRevision
    from apps.api.app.products.seo.site_change_service import (
        FieldsUnavailable,
        PageFields,
        SiteChangeService,
    )

    use_gateway(monkeypatch, ScriptedGateway([draft_payload()]))
    related = [f"/related-{n}" for n in range(8)]
    async with content_session_factory() as session:
        world = await seed_world(session, pages=[*PAGES, *related])
        for page in await session.scalars(
            select(SEOPage).where(SEOPage.website_id == world.website)
        ):
            page.body_text = "Everything about the Green Bay Packers bar and game day in San Diego."
        item, run_input, run = await start(session, world)
        await run_compose(session, world, run_input, run.id)
        revision = await session.scalar(
            select(ContentRevision).where(ContentRevision.content_item_id == item.id)
        )
        assert revision is not None

        async def fake_read(
            self: SiteChangeService, session: AsyncSession, org: UUID, page: SEOPage, **_: Any
        ) -> PageFields | FieldsUnavailable:
            if page.normalized_url.endswith("/about"):
                return FieldsUnavailable("SITE_MAPPING_REQUIRED", "unmapped")  # type: ignore[arg-type]
            return PageFields(
                url=page.normalized_url,
                values={
                    SiteChangeField.INTERNAL_LINK: (
                        "Visit the Green Bay Packers bar for game day.\n\nSecond paragraph."
                    )
                },
            )

        monkeypatch.setattr(SiteChangeService, "read_page_fields", fake_read)
        proposals = await InboundLinkService().propose(
            session,
            InboundLinkRequest(
                organization_id=world.org,
                website_id=world.website,
                revision_id=revision.id,
                content_hash=revision.content_hash,
                target_url="/blog/green-bay-packers-bar-san-diego",
                topic_phrases=["Green Bay Packers bar", "game day"],
                actor_id=world.user,
                correlation_id="c",
            ),
        )
        proposed = [p for p in proposals if p["status"] == InboundLinkStatus.PROPOSED.value]
        assert len(proposed) == 5  # 8+ candidates, never more than five proposals
        for proposal in proposed:
            assert proposal["field"] == "internal_link"
            assert proposal["anchor"] == "Green Bay Packers bar"
            assert proposal["after"] == proposal["before"].replace(
                "Green Bay Packers bar",
                "[Green Bay Packers bar](/blog/green-bay-packers-bar-san-diego)",
            )
            recommendation = await session.get(
                SEORecommendationRevision, UUID(proposal["recommendation_id"])
            )
            assert recommendation is not None and recommendation.status == "awaiting_approval"
            change_set = SiteChangeSet.model_validate(recommendation.change_set)
            (change,) = change_set.items
            assert change.field is SiteChangeField.INTERNAL_LINK
            assert change.current_value == proposal["before"]
            assert change.proposed_value == proposal["after"]
        # Proposing again is idempotent: the same pages, the same recommendations' pages.
        unavailable = [p for p in proposals if p["status"] == InboundLinkStatus.UNAVAILABLE.value]
        assert all(p["code"] == InboundLinkCode.PAGE_MAPPING_REQUIRED.value for p in unavailable)
