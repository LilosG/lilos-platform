"""The quality gate: the exact Coco Maya brunch regression, every rule, and edit-then-approve."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from apps.api.app.agents.tools import SiteChangeInvalidError, build_change_set
from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.locations.enums import LocationStatus, LocationType
from apps.api.app.locations.models import Location
from apps.api.app.products.content import publish_handler
from apps.api.app.products.content.models import ContentPublication
from apps.api.app.products.seo import site_change_handler
from apps.api.app.products.seo.change_quality import (
    QualityCode,
    QualityContext,
    location_phrases,
    quality_problems,
)
from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeItem, SiteChangeSet
from apps.api.app.products.seo.contracts import (
    RecommendationCreate,
    RecommendationDecision,
    RecommendationRevise,
    SiteChangeEdit,
)
from apps.api.app.products.seo.errors import (
    SEOChangeQualityError,
    SEORecommendationNotDecidableError,
)
from apps.api.app.products.seo.models import SEORecommendationRevision
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.service import SEOService
from apps.api.app.products.seo.site_change_service import SiteChangeService
from apps.api.app.products.seo.verification import LivePage
from apps.api.app.routes import seo as seo_routes

from .test_hermes_change_set import BLOG_PAGE_MAP, add_blog_target, striking_distance_opportunity
from .test_orchestration import FakePageSpeedService, _seed_attributed_query
from .test_site_change_executor import FakeGitHub, live_html

# The production case, verbatim: Coco Maya /blog/best-brunch-san-diego.
CURRENT_TITLE = "Best Daily Brunch in San Diego 2026 | Little Italy & Beyond"
COCO_PROPOSED_TITLE = "Best Brunch Spots in San Diego — Daily Guide by Coco Maya"
COMPLIANT_TITLE = "Best Brunch Spots in San Diego (2026): Little Italy & Beyond"
CURRENT_DESCRIPTION = (
    "San Diego's brunch scene has exploded. Here's where to go in Little Italy and beyond, "
    "and why the patio at Coco Maya is worth the trip in 2026."
)
QUERY = "brunch spots san diego"
CONTEXT = QualityContext(
    target_query=QUERY,
    top_queries=("brunch spots san diego", "best brunch little italy", "little italy brunch"),
    location_terms=("San Diego", "Little Italy"),
)


def codes(problems: list[Any]) -> set[QualityCode]:
    return {problem.code for problem in problems}


def title_problems(proposed: str, context: QualityContext = CONTEXT) -> list[Any]:
    return quality_problems(SiteChangeField.SEO_TITLE, CURRENT_TITLE, proposed, context)


# --- the production regression -------------------------------------------------


def test_the_coco_maya_brunch_title_is_rejected_with_every_specific_reason() -> None:
    problems = title_problems(COCO_PROPOSED_TITLE)

    assert codes(problems) >= {QualityCode.YEAR_REMOVED, QualityCode.LOCATION_REMOVED}
    reasons = " | ".join(str(problem) for problem in problems)
    assert "[YEAR_REMOVED]" in reasons and "2026" in reasons
    assert "[LOCATION_REMOVED]" in reasons and "'Little Italy'" in reasons
    # "San Diego" is still there, so it is not reported.
    assert "'San Diego'" not in reasons


def test_the_compliant_rewrite_passes() -> None:
    assert len(COMPLIANT_TITLE) == 60  # exactly the maximum, which is allowed
    assert title_problems(COMPLIANT_TITLE) == []


# --- each rule on its own -------------------------------------------------------


@pytest.mark.parametrize(
    ("proposed", "expected"),
    [
        ("Brunch San Diego 2026", {QualityCode.TITLE_TOO_SHORT}),
        ("T" * 61, {QualityCode.TITLE_TOO_LONG}),
        (
            "Best Brunch Spots in San Diego &amp; Little Italy 2026",
            {QualityCode.HTML_ENTITY},
        ),
        (
            "Where to Eat Brunch in Little Italy, San Diego (2026)",
            {QualityCode.QUERY_MISSING},
        ),
        (
            "Little Italy Weekend Dining Guide: Brunch Spots San Diego 2026",
            {QualityCode.QUERY_NOT_NEAR_START},
        ),
    ],
)
def test_title_rules(proposed: str, expected: set[QualityCode]) -> None:
    assert expected <= codes(title_problems(proposed))


def test_title_length_bounds_are_inclusive() -> None:
    base = "Brunch Spots San Diego 2026 Little Italy"
    low = base.ljust(30, "x")[:30]
    assert QualityCode.TITLE_TOO_SHORT not in codes(title_problems(low))
    assert QualityCode.TITLE_TOO_SHORT in codes(title_problems(low[:29]))
    sixty = (base + " " + "guide " * 6)[:60]
    assert QualityCode.TITLE_TOO_LONG not in codes(title_problems(sixty))
    assert QualityCode.TITLE_TOO_LONG in codes(title_problems(sixty + "x"))


def test_a_year_is_only_required_when_the_current_value_has_one() -> None:
    no_year_current = "Best Brunch Spots in San Diego | Little Italy & Beyond"
    proposed = "Best Brunch Spots in San Diego: Little Italy & More"
    assert quality_problems(SiteChangeField.SEO_TITLE, no_year_current, proposed, CONTEXT) == []


def test_dropped_top_query_terms_are_named() -> None:
    # No location profile here, so the shared "little italy" tokens come from the queries.
    context = QualityContext(target_query=QUERY, top_queries=CONTEXT.top_queries)
    problems = title_problems("Best Brunch Spots in San Diego (2026): Rooftop Patio Guide", context)
    reason = " ".join(str(p) for p in problems)
    assert QualityCode.TOP_QUERY_TERM_REMOVED in codes(problems)
    assert "'little'" in reason and "'italy'" in reason


def test_year_and_location_are_also_kept_in_the_meta_description() -> None:
    proposed = (
        "Find the best weekend brunch with a rooftop patio, craft cocktails and a full menu "
        "served daily. Reserve your table today."
    )
    problems = quality_problems(
        SiteChangeField.META_DESCRIPTION, CURRENT_DESCRIPTION, proposed, CONTEXT
    )
    assert {QualityCode.YEAR_REMOVED, QualityCode.LOCATION_REMOVED} <= codes(problems)
    # The title-only rules do not apply to the description.
    assert QualityCode.QUERY_MISSING not in codes(problems)


@pytest.mark.parametrize(
    ("length", "expected"),
    [
        (119, {QualityCode.DESCRIPTION_TOO_SHORT}),
        (120, set()),
        (160, set()),
        (161, {QualityCode.DESCRIPTION_TOO_LONG}),
    ],
)
def test_description_length_bounds(length: int, expected: set[QualityCode]) -> None:
    text = ("Brunch spots in San Diego's Little Italy for 2026: " + "x" * 200)[:length]
    got = codes(quality_problems(SiteChangeField.META_DESCRIPTION, "old", text, CONTEXT))
    assert (
        got
        & {
            QualityCode.DESCRIPTION_TOO_SHORT,
            QualityCode.DESCRIPTION_TOO_LONG,
        }
        == expected
    )


def test_other_fields_and_empty_context_pass_through() -> None:
    assert quality_problems(SiteChangeField.H1, "old", "x", CONTEXT) == []
    # No query, queries or locations known: only the always-on checks remain.
    bare = QualityContext()
    assert title_problems("A perfectly ordinary title of fine length", bare) == [
        problem
        for problem in title_problems("A perfectly ordinary title of fine length", bare)
        if problem.code is QualityCode.YEAR_REMOVED
    ]


def test_location_phrases_split_profile_text() -> None:
    assert location_phrases("San Diego", "CA", "Little Italy, Downtown and East Village; ") == (
        "San Diego",
        "Little Italy",
        "Downtown",
        "East Village",
    )
    assert location_phrases(None, "") == ()


# --- as Hermes sees it: one SITE_CHANGE_INVALID listing every problem -----------


def test_hermes_gets_every_problem_in_one_typed_error_it_can_retry_from() -> None:
    opportunity = SimpleNamespace(page_id=uuid4())
    context = {
        "status": "available",
        "page_id": str(opportunity.page_id),
        "fields": {"seo_title": CURRENT_TITLE},
    }
    with pytest.raises(SiteChangeInvalidError) as raised:
        build_change_set(
            [{"field": "seo_title", "proposed_value": COCO_PROPOSED_TITLE, "rationale": "r"}],
            opportunity,
            context,
            CONTEXT,
        )
    message = str(raised.value)
    assert message.startswith("SITE_CHANGE_INVALID: seo_title: [")
    assert "[YEAR_REMOVED]" in message and "[LOCATION_REMOVED]" in message

    # Retrying inside the same run with the compliant title succeeds.
    staged = build_change_set(
        [{"field": "seo_title", "proposed_value": COMPLIANT_TITLE, "rationale": "r"}],
        opportunity,
        context,
        CONTEXT,
    )
    assert staged["items"][0]["proposed_value"] == COMPLIANT_TITLE  # type: ignore[index]


# --- against the database: real context, Coco rejection, edit-then-approve ------


POST = (
    "---\n"
    'title: "Best Brunch Spots in San Diego"\n'
    f'seoTitle: "{CURRENT_TITLE}"\n'
    f'description: "{CURRENT_DESCRIPTION}"\n'
    "---\n\n# Best brunch\n\nBody.\n"
)
POST_PATH = "src/content/blog/best-brunch.mdx"


async def seed(session: AsyncSession) -> tuple[Any, Any, UUID, UUID]:
    """Org with a San Diego / Little Italy location, an attributed brunch page and a target."""
    organization, website, page, search_property = await _seed_attributed_query(session)
    session.add(
        Location(
            organization_id=organization.id,
            name="Coco Maya",
            slug="coco-maya",
            location_type=LocationType.HYBRID,
            status=LocationStatus.ACTIVE,
            timezone="UTC",
            country_code="US",
            address_line_1="1660 India St",
            postal_code="92101",
            city="San Diego",
            region="CA",
            service_area_description="Little Italy, Downtown",
            is_primary=True,
            version=1,
        )
    )
    approver = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
    session.add(approver)
    await session.flush()
    await add_blog_target(session, organization.id, search_property.connection_id)
    await SEOOrchestrationService(pagespeed=FakePageSpeedService()).analyze(
        session, organization.id, location_id=None, correlation_id="quality"
    )
    return organization, page, approver.id, search_property.id


def create_command(opportunity_id: UUID, page_id: UUID, title: str) -> RecommendationCreate:
    change_set = SiteChangeSet(
        items=[
            SiteChangeItem(
                page_id=page_id,
                field=SiteChangeField.SEO_TITLE,
                current_value=CURRENT_TITLE,
                proposed_value=title,
                rationale="Front-load the query; keep the year and Little Italy.",
            )
        ]
    )
    return RecommendationCreate(
        proposed_action="Rewrite the title.",
        evidence_references=[f"seo-opportunity:{opportunity_id}"],
        expected_result_hypothesis="Higher CTR.",
        risk="low",
        effort="low",
        change_set=change_set.model_dump(mode="json"),
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_context_comes_from_the_query_the_page_top_queries_and_the_location_profile(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, _, _, _ = await seed(session)
        opportunity = await striking_distance_opportunity(session, organization.id)
        context = await SiteChangeService().quality_context(session, organization.id, opportunity)
        assert context.target_query == "brunch spots san diego"
        assert context.top_queries == ("brunch spots san diego",)
        # A two-letter region code ("CA") is too short to be a meaningful location term.
        assert context.location_terms == ("San Diego", "Little Italy", "Downtown")


@pytest.mark.integration
@pytest.mark.anyio
async def test_the_production_title_is_rejected_when_a_recommendation_is_created(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, page, _, _ = await seed(session)
        opportunity = await striking_distance_opportunity(session, organization.id)
        seo = SEOService()

        with pytest.raises(SEOChangeQualityError) as raised:
            await seo.create_recommendation(
                session,
                organization.id,
                opportunity.id,
                create_command(opportunity.id, page.id, COCO_PROPOSED_TITLE),
                actor_id=None,
                correlation_id="coco",
            )
        joined = "; ".join(raised.value.problems)
        assert "[YEAR_REMOVED]" in joined and "[LOCATION_REMOVED]" in joined
        assert raised.value.code == "SEO_CHANGE_QUALITY_REJECTED"

        created = await seo.create_recommendation(
            session,
            organization.id,
            opportunity.id,
            create_command(opportunity.id, page.id, COMPLIANT_TITLE),
            actor_id=None,
            correlation_id="ok",
        )
        assert created.change_set is not None


@pytest.mark.integration
@pytest.mark.anyio
async def test_revise_only_edits_values_and_is_gated(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization, page, _, _ = await seed(session)
        opportunity = await striking_distance_opportunity(session, organization.id)
        seo = SEOService()
        pending = await seo.create_recommendation(
            session,
            organization.id,
            opportunity.id,
            create_command(opportunity.id, page.id, COMPLIANT_TITLE),
            actor_id=None,
            correlation_id="p",
        )

        def edit(title: str, field: SiteChangeField = SiteChangeField.SEO_TITLE) -> Any:
            return RecommendationRevise(edits=[SiteChangeEdit(field=field, proposed_value=title)])

        # An edit that drops the year is refused exactly like Hermes' would be.
        with pytest.raises(SEOChangeQualityError, match="YEAR_REMOVED"):
            await seo.revise_site_change(
                session,
                organization.id,
                pending.id,
                edit(COCO_PROPOSED_TITLE),
                actor_id=None,
                correlation_id="bad",
            )
        # An edit cannot add a field the approved change set does not contain.
        with pytest.raises(SEOChangeQualityError, match="not part of this change set"):
            await seo.revise_site_change(
                session,
                organization.id,
                pending.id,
                edit("x" * 130, SiteChangeField.META_DESCRIPTION),
                actor_id=None,
                correlation_id="retarget",
            )
        revised = await seo.revise_site_change(
            session,
            organization.id,
            pending.id,
            edit("Best Brunch Spots in San Diego 2026: Little Italy Guide"),
            actor_id=None,
            correlation_id="good",
        )
        assert revised.revision_number == pending.revision_number + 1
        assert revised.change_set is not None
        item = revised.change_set["items"][0]  # type: ignore[index]
        assert item["proposed_value"] == "Best Brunch Spots in San Diego 2026: Little Italy Guide"
        # Page, field, current value and rationale are carried over, never re-supplied.
        original = SiteChangeSet.model_validate(pending.change_set).items[0]
        assert (item["page_id"], item["current_value"], item["rationale"]) == (
            str(original.page_id),
            original.current_value,
            original.rationale,
        )
        # A revision that is no longer pending cannot be edited.
        revised.status = "rejected"
        await session.flush()
        with pytest.raises(SEORecommendationNotDecidableError):
            await seo.revise_site_change(
                session,
                organization.id,
                revised.id,
                edit(COMPLIANT_TITLE),
                actor_id=None,
                correlation_id="late",
            )


@pytest.mark.integration
@pytest.mark.anyio
async def test_edit_then_approve_opens_a_pull_request_with_the_edited_values(
    seo_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    edited_title = "Best Brunch Spots in San Diego 2026: Little Italy Guide"
    fake = FakeGitHub({POST_PATH: POST})

    async def token(*_args: object) -> str:
        return "token"

    async def fetch(url: str, *, cache_buster: str, client: object = None) -> LivePage:
        return LivePage(url=url, http_status=200, html=live_html(edited_title, CURRENT_DESCRIPTION))

    monkeypatch.setattr(publish_handler, "_provider_writes_enabled", lambda: True)
    monkeypatch.setattr(publish_handler, "_github_token_resolver", token)
    monkeypatch.setattr(publish_handler, "_content_publisher_factory", lambda _t: fake)
    monkeypatch.setattr(site_change_handler, "fetch_live_page", fetch)

    async with seo_session_factory.begin() as session:
        organization, page, approver_id, _ = await seed(session)
        opportunity = await striking_distance_opportunity(session, organization.id)
        seo = SEOService()
        hermes = await seo.create_recommendation(
            session,
            organization.id,
            opportunity.id,
            create_command(opportunity.id, page.id, COMPLIANT_TITLE),
            actor_id=None,
            correlation_id="hermes",
        )
        edited = await seo.revise_site_change(
            session,
            organization.id,
            hermes.id,
            RecommendationRevise(
                edits=[SiteChangeEdit(field=SiteChangeField.SEO_TITLE, proposed_value=edited_title)]
            ),
            actor_id=approver_id,
            correlation_id="edit",
        )
        organization_id, edited_id, hermes_id = organization.id, edited.id, hermes.id

    request = cast(
        Request,
        SimpleNamespace(
            state=SimpleNamespace(correlation_id="quality"),
            headers={},
            app=SimpleNamespace(state=SimpleNamespace()),
            url=SimpleNamespace(path="/"),
        ),
    )
    principal = cast(Any, SimpleNamespace(platform_user_id=approver_id))
    # The human approves the EDITED revision (the newest); that is what executes.
    async with seo_session_factory.begin() as session:
        await seo_routes.decide_recommendation(
            request,
            organization_id,
            edited_id,
            RecommendationDecision(approve=True),
            session,
            principal,
            cast(Any, None),
        )
    async with seo_session_factory() as session:
        publication = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.organization_id == organization_id,
                ContentPublication.publication_kind == "site_change",
            )
        )
        assert publication is not None
        assert publication.seo_recommendation_revision_id == edited_id
        original = await session.get(SEORecommendationRevision, hermes_id)
        assert original is not None and original.status == "awaiting_approval"
        publication_id = publication.id

    async with seo_session_factory() as session:
        outcome = await site_change_handler.handle_seo_apply_site_change(
            session,
            organization_id=organization_id,
            location_id=None,
            input_document={"publication_id": str(publication_id)},
            correlation_id="quality",
            workflow_run_id=uuid4(),
        )
    assert outcome.result == "succeeded"
    written = fake.puts[POST_PATH]
    assert f'seoTitle: "{edited_title}"' in written
    assert COMPLIANT_TITLE not in written  # Hermes' own wording did not ship
    assert f'description: "{CURRENT_DESCRIPTION}"' in written  # nothing else changed
    assert BLOG_PAGE_MAP  # the real page map, not a stub, resolved the file
