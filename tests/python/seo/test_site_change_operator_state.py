"""Approved SEO work links to its destination, and says why when it stops."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.execution.models import Job
from apps.api.app.products.content import publish_handler
from apps.api.app.products.content.models import ContentPublication
from apps.api.app.products.seo import site_change_handler
from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeItem, SiteChangeSet
from apps.api.app.products.seo.contracts import RecommendationCreate, RecommendationDecision
from apps.api.app.products.seo.models import SEOImplementationTask
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.service import SEOService
from apps.api.app.products.seo.site_change_state import change_set_items, site_change_state
from apps.api.app.products.seo.verification import LivePage
from apps.api.app.routes import seo as seo_routes

from .test_hermes_change_set import (
    CURRENT_DESCRIPTION,
    CURRENT_TITLE,
    POST,
    POST_PATH,
    add_blog_target,
    striking_distance_opportunity,
)
from .test_orchestration import FakePageSpeedService, _seed_attributed_query
from .test_site_change_executor import FakeGitHub, live_html

NEW_TITLE = "Best Brunch Spots in San Diego | Little Italy Guide"


def revision(*, change_set: bool = True, limitation: str | None = None) -> Any:
    return SimpleNamespace(
        id=uuid4(),
        change_set=(
            {
                "items": [
                    {
                        "page_id": str(uuid4()),
                        "field": "seo_title",
                        "current_value": "old",
                        "proposed_value": "new",
                        "rationale": "r",
                    }
                ]
            }
            if change_set
            else None
        ),
        change_set_limitation_code=limitation,
    )


def publication(**overrides: Any) -> Any:
    base: dict[str, Any] = {
        "status": "pull_request_created",
        "safe_error_code": None,
        "external_pull_request_id": "42",
        "build_status": None,
        "verification_status": None,
        "verification_evidence": None,
    }
    return SimpleNamespace(**{**base, **overrides})


REPO = "LilosG/example-site"


def test_recommendation_without_a_site_change_has_no_state() -> None:
    assert site_change_state(revision(change_set=False), None, None) is None


def test_unmapped_page_shows_the_typed_code_and_no_link() -> None:
    state = site_change_state(
        revision(change_set=False, limitation="SITE_MAPPING_REQUIRED"), None, None
    )
    assert state is not None
    assert state["mapping_state"] == "required"
    assert state["blocked_code"] == "SITE_MAPPING_REQUIRED"
    assert state["pull_request_url"] is None and state["publication_status"] is None


def test_approved_change_not_yet_executed_is_mapped_with_nothing_else_claimed() -> None:
    state = site_change_state(revision(), None, None)
    assert state is not None
    assert state["mapping_state"] == "mapped"
    # Missing evidence is null, never a value that looks like progress.
    assert state["blocked_code"] is None
    assert state["build_state"] is None and state["verification_state"] is None
    assert state["live_checks"] == []


def test_in_flight_change_links_to_the_pull_request_and_reports_the_build_gate() -> None:
    state = site_change_state(
        revision(),
        publication(build_status="vercel_preview:pending", status="checks_running"),
        REPO,
    )
    assert state is not None
    assert state["pull_request_url"] == "https://github.com/LilosG/example-site/pull/42"
    assert (state["build_gate"], state["build_state"]) == ("vercel_preview", "pending")
    assert state["blocked_code"] is None


def test_blocked_builds_carry_their_typed_codes() -> None:
    unavailable = site_change_state(
        revision(),
        publication(
            status="checks_failed",
            safe_error_code="CHECKS_UNAVAILABLE",
            build_status="none:none",
        ),
        REPO,
    )
    assert unavailable is not None
    assert unavailable["blocked_code"] == "CHECKS_UNAVAILABLE"
    assert unavailable["build_state"] == "unavailable"
    assert unavailable["pull_request_url"] is not None  # the PR exists; it was not merged

    failed = site_change_state(
        revision(),
        publication(
            status="checks_failed",
            safe_error_code="CONTENT_CHECKS_FAILED",
            build_status="repository_ci:failed",
        ),
        REPO,
    )
    assert failed is not None
    assert failed["blocked_code"] == "CONTENT_CHECKS_FAILED"
    assert (failed["build_gate"], failed["build_state"]) == ("repository_ci", "failed")


def test_a_retryable_provider_hiccup_is_not_presented_as_a_block() -> None:
    state = site_change_state(
        revision(),
        publication(status="reconciliation_required", safe_error_code="PROVIDER_WRITE_AMBIGUOUS"),
        REPO,
    )
    assert state is not None and state["blocked_code"] is None


def test_verified_and_failed_live_read_back_expose_the_observed_values() -> None:
    checks = [
        {"field": "seo_title", "expected": "new", "observed": "new", "state": "verified"},
        {"field": "meta_description", "expected": "d2", "observed": "d1", "state": "mismatch"},
    ]
    verified = site_change_state(
        revision(),
        publication(
            status="verified",
            build_status="repository_ci:success",
            verification_status="verified",
            verification_evidence={"checks": checks[:1]},
        ),
        REPO,
    )
    assert verified is not None
    assert verified["verification_state"] == "verified"
    assert verified["build_state"] == "passed"

    failed = site_change_state(
        revision(),
        publication(
            status="failed",
            safe_error_code="SITE_CHANGE_VERIFICATION_FAILED",
            verification_status="failed",
            verification_evidence={"checks": checks},
        ),
        REPO,
    )
    assert failed is not None
    assert failed["blocked_code"] == "SITE_CHANGE_VERIFICATION_FAILED"
    assert failed["live_checks"][1] == checks[1]  # type: ignore[index]


def test_change_set_items_are_exposed_for_a_before_after_display() -> None:
    items = change_set_items(revision())
    assert [(i["field"], i["current_value"], i["proposed_value"]) for i in items] == [
        ("seo_title", "old", "new")
    ]
    assert change_set_items(revision(change_set=False)) == []


# --- end to end: approval -> pull request -> link in the operator list ----------


def stub_request() -> Request:
    return cast(
        Request,
        SimpleNamespace(
            state=SimpleNamespace(correlation_id="operator-state"),
            headers={},
            app=SimpleNamespace(state=SimpleNamespace()),
            url=SimpleNamespace(path="/"),
        ),
    )


@pytest.mark.integration
@pytest.mark.anyio
async def test_approved_change_links_to_the_client_pull_request(
    seo_session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGitHub({POST_PATH: POST})

    async def token(*_args: object) -> str:
        return "token"

    async def fetch(url: str, *, cache_buster: str, client: object = None) -> LivePage:
        return LivePage(url=url, http_status=200, html=live_html(NEW_TITLE, CURRENT_DESCRIPTION))

    monkeypatch.setattr(publish_handler, "_provider_writes_enabled", lambda: True)
    monkeypatch.setattr(publish_handler, "_github_token_resolver", token)
    monkeypatch.setattr(publish_handler, "_content_publisher_factory", lambda _t: fake)
    monkeypatch.setattr(site_change_handler, "fetch_live_page", fetch)

    async with seo_session_factory.begin() as session:
        organization, _, page, search_property = await _seed_attributed_query(session)
        approver = UserProfile(auth_user_id=uuid4(), status=UserStatus.ACTIVE, version=1)
        session.add(approver)
        await session.flush()
        await add_blog_target(session, organization.id, search_property.connection_id)
        await SEOOrchestrationService(pagespeed=FakePageSpeedService()).analyze(
            session, organization.id, location_id=None, correlation_id="link"
        )
        opportunity = await striking_distance_opportunity(session, organization.id)
        change_set = SiteChangeSet(
            items=[
                SiteChangeItem(
                    page_id=page.id,
                    field=SiteChangeField.SEO_TITLE,
                    current_value=CURRENT_TITLE,
                    proposed_value=NEW_TITLE,
                    rationale="Lead with the query.",
                )
            ]
        )
        pending = await SEOService().create_recommendation(
            session,
            organization.id,
            opportunity.id,
            RecommendationCreate(
                proposed_action="Rewrite the title.",
                evidence_references=[f"seo-opportunity:{opportunity.id}"],
                expected_result_hypothesis="Higher CTR.",
                risk="low",
                effort="low",
                change_set=change_set.model_dump(mode="json"),
            ),
            actor_id=None,
            correlation_id="link",
        )
        organization_id, opportunity_id, revision_id = organization.id, opportunity.id, pending.id
        approver_id = approver.id

    principal = cast(Any, SimpleNamespace(platform_user_id=approver_id))
    # 1. The human approves the exact change set through the real route.
    async with seo_session_factory.begin() as session:
        approved = await seo_routes.decide_recommendation(
            stub_request(),
            organization_id,
            revision_id,
            RecommendationDecision(approve=True),
            session,
            principal,
            cast(Any, None),
        )
    meta = cast(dict[str, Any], approved["meta"])
    assert meta["workflow_key"] == "seo.apply_site_change"  # not handed to Content
    row = cast(dict[str, Any], approved["data"])
    assert row["site_change"]["mapping_state"] == "mapped"
    assert row["site_change"]["pull_request_url"] is None  # nothing has run yet

    async with seo_session_factory() as session:
        reserved = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.seo_recommendation_revision_id == revision_id
            )
        )
        assert reserved is not None and reserved.publication_kind == "site_change"
        assert reserved.change_set_fingerprint is not None
        assert await session.scalar(select(SEOImplementationTask.id)) is not None
        job = await session.scalar(
            select(Job).where(Job.workflow_run_id == reserved.workflow_run_id)
        )
        assert job is not None  # the approval enqueued execution
        publication_id = reserved.id

    # 2. The worker runs it.
    async with seo_session_factory() as session:
        outcome = await site_change_handler.handle_seo_apply_site_change(
            session,
            organization_id=organization_id,
            location_id=None,
            input_document={"publication_id": str(publication_id)},
            correlation_id="link",
            workflow_run_id=uuid4(),
        )
    assert outcome.result == "succeeded"

    # 3. The operator's list now links to the pull request on the client repo.
    async with seo_session_factory() as session:
        listing = await seo_routes.list_recommendations(
            stub_request(), organization_id, opportunity_id, session, cast(Any, None)
        )
    rows = cast(list[dict[str, Any]], listing["data"])
    linked = next(item for item in rows if item["id"] == str(revision_id))
    state = linked["site_change"]
    assert state["pull_request_url"] == "https://github.com/LilosG/example-site/pull/42"
    assert state["publication_status"] == "verified"
    assert state["verification_state"] == "verified"
    assert state["blocked_code"] is None
    assert linked["change_set"][0]["current_value"] == CURRENT_TITLE
    assert linked["change_set"][0]["proposed_value"] == NEW_TITLE
    # The deterministic recommendation for the same opportunity has no change set and its
    # page is mapped, so it carries no site-change state at all.
    others = [item for item in rows if item["id"] != str(revision_id)]
    assert others and all(item["site_change"] is None for item in others)
