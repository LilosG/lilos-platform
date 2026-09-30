"""Hermes proposes exact page edits; LILOs supplies and checks everything else.

`current_value` is read from the client repo through the page map, never asserted by
Hermes, and every proposed value passes the same deterministic limits a search
engine or CMS would enforce. No page map means the recommendation says so with a
typed code rather than carrying a guess.
"""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.agents.tools import AgentToolService, SiteChangeInvalidError, build_change_set
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.execution import handlers
from apps.api.app.products.content.models import PublishingTarget
from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeItem, SiteChangeSet
from apps.api.app.products.seo.contracts import RecommendationCreate, RecommendationDecision
from apps.api.app.products.seo.decision import SEOEvidenceInvalidError
from apps.api.app.products.seo.models import SEOOpportunity, SEORecommendationRevision
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.service import SEOService
from apps.api.app.products.seo.site_change_service import (
    FieldsUnavailable,
    PageFields,
    SiteChangeService,
)

from .test_orchestration import FakePageSpeedService, _seed_attributed_query
from .test_site_change_executor import FakeGitHub

CURRENT_TITLE = "Best Brunch Spots in San Diego | Little Italy"
CURRENT_DESCRIPTION = "Our guide to the best brunch in San Diego, from rooftop patios to classics."
POST_PATH = "src/content/blog/best-brunch.mdx"
POST = (
    "---\n"
    'title: "Best Brunch Spots in San Diego"\n'
    f'seoTitle: "{CURRENT_TITLE}"\n'
    f'description: "{CURRENT_DESCRIPTION}"\n'
    "---\n\n# Best brunch\n\nBody.\n"
)
BLOG_PAGE_MAP = {
    "/blog/{slug}": {
        "seo_title": {
            "source_type": "frontmatter",
            "file_path": "src/content/blog/{slug}.mdx",
            "key": "seoTitle",
        },
        "meta_description": {
            "source_type": "frontmatter",
            "file_path": "src/content/blog/{slug}.mdx",
            "key": "description",
        },
    }
}


def available_context(page_id: UUID) -> dict[str, object]:
    return {
        "status": "available",
        "page_id": str(page_id),
        "page_url": "/blog/best-brunch",
        "fields": {"seo_title": CURRENT_TITLE, "meta_description": CURRENT_DESCRIPTION},
        "limits": {"seo_title": 60, "meta_description": 160},
    }


# --- the bound tool: validation and what it stages ---------------------------


def bound_tool_fixtures(
    monkeypatch: pytest.MonkeyPatch,
    make_context: Callable[[UUID], dict[str, object]] | None = None,
) -> tuple[AgentToolService, Any, Any]:
    """A bound Hermes run on an attributed opportunity; `make_context` gets its page id."""
    page_id = uuid4()
    opportunity = SEOOpportunity(
        id=uuid4(),
        organization_id=uuid4(),
        location_id=None,
        website_id=uuid4(),
        page_id=page_id,
        opportunity_type="gsc_low_ctr",
        attribution_state="attributed",
        status="identified",
        evidence={},
    )
    reference = f"seo-opportunity:{opportunity.id}"
    decision: dict[str, object] = {
        "contract_version": "seo_decision.v1",
        "organization_id": str(opportunity.organization_id),
        "location_id": None,
        "website_id": str(opportunity.website_id),
        "page_id": str(page_id),
        "opportunity_id": str(opportunity.id),
        "recommendation_class": "growth_change",
        "evidence_references": [reference],
    }
    document: dict[str, object] = {
        "seo_opportunity_id": str(opportunity.id),
        "seo_decision_snapshot": decision,
    }
    if make_context is not None:
        document["site_change_context"] = make_context(page_id)

    async def resolve(*_args: object) -> dict[str, object]:
        return decision

    async def get_opportunity(*_args: object) -> SEOOpportunity:
        return opportunity

    monkeypatch.setattr("apps.api.app.agents.tools.resolve_decision", resolve)
    tools = AgentToolService()
    monkeypatch.setattr(tools.seo, "get_opportunity", get_opportunity)

    class Session:
        async def get(self, _model: object, _identifier: object) -> object:
            return SimpleNamespace(input_document=document)

    run = SimpleNamespace(
        workflow_run_id=uuid4(),
        organization_id=opportunity.organization_id,
        location_id=None,
        source_references=[reference],
        correlation_id="test",
        final_output=None,
    )
    return tools, Session(), run


def staged(run: Any) -> Any:
    """The proposal a bound run has staged so far."""
    return run.final_output["seo_pending_proposal"]


def proposal(site_changes: object) -> dict[str, Any]:
    return {
        "proposed_action": "Rewrite the title and description for the brunch query.",
        "expected_result_hypothesis": "Higher CTR for brunch searches.",
        "risk": "low",
        "effort": "low",
        "site_changes": site_changes,
    }


@pytest.mark.anyio
async def test_hermes_change_set_uses_repo_current_value(monkeypatch: pytest.MonkeyPatch) -> None:
    tools, session, run = bound_tool_fixtures(monkeypatch, available_context)

    result = await tools._tool_create_seo_recommendation_proposal(
        cast(Any, session),
        cast(Any, run),
        proposal(
            [
                {
                    "field": "seo_title",
                    "proposed_value": "Best Brunch in San Diego | Daily Until 3PM",
                    "rationale": "Lead with the query and the hours.",
                }
            ]
        ),
    )

    assert result["data"] == {"accepted": True}
    change_set = staged(run)["change_set"]
    item = change_set["items"][0]
    # The current value is the one read from the repo, not anything Hermes said.
    assert item["current_value"] == CURRENT_TITLE
    assert item["proposed_value"] == "Best Brunch in San Diego | Daily Until 3PM"
    SiteChangeSet.model_validate(change_set)  # and it is a valid, fingerprintable set


def test_hermes_cannot_assert_a_current_value() -> None:
    opportunity = SimpleNamespace(page_id=uuid4())
    context = available_context(opportunity.page_id)
    with pytest.raises(SiteChangeInvalidError, match="exactly field, proposed_value and rationale"):
        build_change_set(
            [
                {
                    "field": "seo_title",
                    "proposed_value": "New title",
                    "rationale": "r",
                    "current_value": "whatever Hermes wants it to be",
                }
            ],
            opportunity,
            context,
        )


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            {"field": "seo_title", "proposed_value": "T" * 61, "rationale": "r"},
            "exceeds 60 characters",
        ),
        (
            {"field": "meta_description", "proposed_value": "D" * 161, "rationale": "r"},
            "exceeds 160 characters",
        ),
        ({"field": "seo_title", "proposed_value": "", "rationale": "r"}, "at least 1 character"),
        (
            {"field": "seo_title", "proposed_value": CURRENT_TITLE, "rationale": "r"},
            "must differ from current_value",
        ),
        ({"field": "favicon", "proposed_value": "x", "rationale": "r"}, "unknown field"),
        ({"field": "h1", "proposed_value": "x", "rationale": "r"}, "h1 is not mapped"),
    ],
)
@pytest.mark.anyio
async def test_hermes_change_set_rejects_overlong_or_unchanged_value(
    monkeypatch: pytest.MonkeyPatch, entry: dict[str, str], message: str
) -> None:
    tools, session, run = bound_tool_fixtures(monkeypatch, available_context)

    with pytest.raises(SiteChangeInvalidError, match=message) as raised:
        await tools._tool_create_seo_recommendation_proposal(
            cast(Any, session), cast(Any, run), proposal([entry])
        )

    assert raised.value.code == "SITE_CHANGE_INVALID"
    # Nothing was staged, so the run's one allowed proposal is still available:
    # Hermes can correct the value and call again.
    assert run.final_output is None
    retry = await tools._tool_create_seo_recommendation_proposal(
        cast(Any, session),
        cast(Any, run),
        proposal(
            [
                {
                    "field": "seo_title",
                    "proposed_value": "A valid replacement title",
                    "rationale": "r",
                }
            ]
        ),
    )
    assert retry["data"] == {"accepted": True}
    assert staged(run)["change_set"]["items"][0]["field"] == "seo_title"


@pytest.mark.anyio
async def test_unavailable_context_refuses_site_changes_but_not_the_recommendation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tools, session, run = bound_tool_fixtures(
        monkeypatch,
        lambda _page: {
            "status": "unavailable",
            "code": "SITE_MAPPING_REQUIRED",
            "detail": "no map",
        },
    )
    with pytest.raises(SiteChangeInvalidError, match="SITE_MAPPING_REQUIRED"):
        await tools._tool_create_seo_recommendation_proposal(
            cast(Any, session),
            cast(Any, run),
            proposal([{"field": "seo_title", "proposed_value": "New", "rationale": "r"}]),
        )
    assert run.final_output is None

    plain = proposal([])
    del plain["site_changes"]
    await tools._tool_create_seo_recommendation_proposal(cast(Any, session), cast(Any, run), plain)
    assert "change_set" not in staged(run)


def test_duplicate_fields_in_one_proposal_are_refused() -> None:
    opportunity = SimpleNamespace(page_id=uuid4())
    entry = {"field": "seo_title", "proposed_value": "Something else entirely", "rationale": "r"}
    with pytest.raises(SiteChangeInvalidError, match="appears more than once"):
        build_change_set([entry, entry], opportunity, available_context(opportunity.page_id))


# --- recommendations, the page map and approval (database) ---------------------


async def add_blog_target(
    session: AsyncSession, organization_id: UUID, connection_id: UUID
) -> None:
    session.add(
        PublishingTarget(
            organization_id=organization_id,
            connection_id=connection_id,
            key="primary",
            target_type="github_astro",
            repository_id="LilosG/example-site",
            base_branch="main",
            allowed_path_prefix="src/content/blog",
            allowed_site_change_prefixes=["src/content"],
            frontmatter_contract={"page_map": BLOG_PAGE_MAP},
            status="active",
            version=1,
        )
    )
    await session.flush()


async def striking_distance_opportunity(
    session: AsyncSession, organization_id: UUID
) -> SEOOpportunity:
    return cast(
        SEOOpportunity,
        await session.scalar(
            select(SEOOpportunity).where(
                SEOOpportunity.organization_id == organization_id,
                SEOOpportunity.opportunity_type == "gsc_striking_distance",
                SEOOpportunity.active_marker == "active",
            )
        ),
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_recommendation_without_page_map_carries_site_mapping_required(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    async with seo_session_factory.begin() as session:
        organization, _, page, _ = await _seed_attributed_query(session)
        await service.analyze(session, organization.id, location_id=None, correlation_id="nomap")
        opportunity = await striking_distance_opportunity(session, organization.id)
        assert opportunity.page_id == page.id and opportunity.attribution_state == "attributed"
        revision = await session.scalar(
            select(SEORecommendationRevision).where(
                SEORecommendationRevision.opportunity_id == opportunity.id
            )
        )
        assert revision is not None
        # An attributed page, but no publishing target or page map: typed, not silent.
        assert revision.change_set is None
        assert revision.change_set_limitation_code == "SITE_MAPPING_REQUIRED"


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_mapped_page_carries_no_limitation(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    async with seo_session_factory.begin() as session:
        organization, _, _, search_property = await _seed_attributed_query(session)
        await add_blog_target(session, organization.id, search_property.connection_id)
        await service.analyze(session, organization.id, location_id=None, correlation_id="mapped")
        opportunity = await striking_distance_opportunity(session, organization.id)
        revision = await session.scalar(
            select(SEORecommendationRevision).where(
                SEORecommendationRevision.opportunity_id == opportunity.id
            )
        )
        assert revision is not None and revision.change_set_limitation_code is None
        # An unmapped URL on the same target is still refused, for that page only.
        assert (
            await SiteChangeService().mapping_limitation(session, organization.id, uuid4())
            == "SITE_MAPPING_REQUIRED"
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_site_change_context_reads_current_values_from_the_repo(
    seo_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGitHub({POST_PATH: POST})

    async def token(*_args: object) -> str:
        return "token"

    monkeypatch.setattr(handlers, "_github_token_resolver", token)
    monkeypatch.setattr(handlers, "_content_publisher_factory", lambda _token: fake)
    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    async with seo_session_factory.begin() as session:
        organization, _, page, search_property = await _seed_attributed_query(session)
        await add_blog_target(session, organization.id, search_property.connection_id)
        await service.analyze(session, organization.id, location_id=None, correlation_id="ctx")
    # The worker step owns its session and commits it before reading the repo.
    async with seo_session_factory() as session:
        opportunity = await striking_distance_opportunity(session, organization.id)
        context = await SiteChangeService().site_change_context(
            session, organization.id, opportunity
        )

    assert context["status"] == "available"
    assert context["page_id"] == str(page.id)
    assert context["fields"] == {
        "seo_title": CURRENT_TITLE,
        "meta_description": CURRENT_DESCRIPTION,
    }
    assert context["limits"] == {"seo_title": 60, "meta_description": 160}
    # Read from the pinned base commit of the target's branch, not guessed.
    assert any(call.startswith("get_file:base-sha:") for call in fake.calls)


@pytest.mark.integration
@pytest.mark.anyio
async def test_unmapped_or_unreadable_pages_report_a_typed_code(
    seo_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    async with seo_session_factory.begin() as session:
        organization, _, page, _ = await _seed_attributed_query(session)
        await service.analyze(session, organization.id, location_id=None, correlation_id="c")
    async with seo_session_factory() as session:
        opportunity = await striking_distance_opportunity(session, organization.id)
        no_target = await SiteChangeService().site_change_context(
            session, organization.id, opportunity
        )
        direct = await SiteChangeService().read_page_fields(session, organization.id, page)

    assert no_target["status"] == "unavailable" and no_target["code"] == "SITE_MAPPING_REQUIRED"
    assert isinstance(direct, FieldsUnavailable)
    assert not isinstance(direct, PageFields)


@pytest.mark.integration
@pytest.mark.anyio
async def test_change_set_is_bound_to_the_opportunity_page_and_fingerprinted_at_approval(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orchestration = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    seo = SEOService()
    async with seo_session_factory.begin() as session:
        organization, _, page, search_property = await _seed_attributed_query(session)
        approver = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
        session.add(approver)
        await session.flush()
        await add_blog_target(session, organization.id, search_property.connection_id)
        await orchestration.analyze(
            session, organization.id, location_id=None, correlation_id="bind"
        )
        opportunity = await striking_distance_opportunity(session, organization.id)
        reference = f"seo-opportunity:{opportunity.id}"

        def command(target_page: UUID) -> RecommendationCreate:
            change_set = SiteChangeSet(
                items=[
                    SiteChangeItem(
                        page_id=target_page,
                        field=SiteChangeField.SEO_TITLE,
                        current_value=CURRENT_TITLE,
                        proposed_value="Best Brunch in San Diego | Daily Until 3PM",
                        rationale="Lead with the query.",
                    )
                ]
            )
            return RecommendationCreate(
                proposed_action="Rewrite the title.",
                evidence_references=[reference],
                expected_result_hypothesis="Higher CTR.",
                risk="low",
                effort="low",
                change_set=change_set.model_dump(mode="json"),
            )

        # A change set may only edit the page the opportunity is attributed to.
        with pytest.raises(SEOEvidenceInvalidError) as wrong_page:
            await seo.create_recommendation(
                session,
                organization.id,
                opportunity.id,
                command(uuid4()),
                actor_id=None,
                correlation_id="wrong-page",
            )
        assert wrong_page.value.limitation_code == "PAGE_OUT_OF_SCOPE"

        revision = await seo.create_recommendation(
            session,
            organization.id,
            opportunity.id,
            command(page.id),
            actor_id=None,
            correlation_id="ok",
        )
        assert revision.change_set is not None
        assert revision.change_set_limitation_code is None
        assert revision.change_set_fingerprint is None  # recorded at approval, not before
        stored = SiteChangeSet.model_validate(revision.change_set)

        approved = await seo.decide_recommendation(
            session,
            organization.id,
            revision.id,
            RecommendationDecision(approve=True),
            approver.id,
            correlation_id="approve",
        )
        assert approved.status == "approved"
        assert approved.change_set_fingerprint == stored.fingerprint()


@pytest.mark.integration
@pytest.mark.anyio
async def test_worker_stores_the_page_context_on_the_bound_run_once(
    seo_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    from apps.api.app.agents.service import AgentRuntimeService
    from apps.api.app.execution.models import WorkflowRun
    from apps.api.app.execution.service import ExecutionService

    fake = FakeGitHub({POST_PATH: POST})

    async def token(*_args: object) -> str:
        return "token"

    monkeypatch.setattr(handlers, "_github_token_resolver", token)
    monkeypatch.setattr(handlers, "_content_publisher_factory", lambda _token: fake)
    async with seo_session_factory.begin() as session:
        organization, _, _, search_property = await _seed_attributed_query(session)
        await add_blog_target(session, organization.id, search_property.connection_id)
        await SEOOrchestrationService(pagespeed=FakePageSpeedService()).analyze(
            session, organization.id, location_id=None, correlation_id="hook"
        )
        opportunity = await striking_distance_opportunity(session, organization.id)
        run = await ExecutionService().start_named(
            session,
            organization.id,
            "agent.seo",
            f"hook-{uuid4().hex}",
            input_document={"seo_opportunity_id": str(opportunity.id)},
            correlation_id="hook",
            enqueue_job=False,
        )
        organization_id, run_id = organization.id, run.id

    service = AgentRuntimeService()
    document: dict[str, Any] = {"seo_opportunity_id": str(opportunity.id)}
    async with seo_session_factory() as session:
        await service._prepare_site_change_context(session, organization_id, run_id, document)
    reads_after_first = len(fake.calls)
    async with seo_session_factory() as session:
        stored = await session.get(WorkflowRun, run_id)
        assert stored is not None
        context: Any = stored.input_document["site_change_context"]
        assert context["status"] == "available"
        assert context["fields"]["seo_title"] == CURRENT_TITLE
        # A retry sees the stored context in the run's input and reads nothing again.
        await service._prepare_site_change_context(
            session, organization_id, run_id, dict(stored.input_document)
        )
    assert len(fake.calls) == reads_after_first
