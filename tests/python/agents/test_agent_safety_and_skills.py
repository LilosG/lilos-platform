import asyncio
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from apps.api.app.agents.hermes_client import REQUIRED_LILOS_TOOLS, HermesRunsClient
from apps.api.app.agents.models import AgentRun
from apps.api.app.agents.safety import (
    MAX_TOOL_RESULT_BYTES,
    bound_read_result,
    encoded_size,
    redact_text,
    safe_argument_metadata,
    safe_event_document,
)
from apps.api.app.agents.skills import SKILLS, WORKFLOW_SKILLS
from apps.api.app.agents.tools import TOOL_SPECS, AgentToolDeniedError, AgentToolService
from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES
from apps.api.app.routes.hermes_tools import router as hermes_tools_router


def test_event_projection_discards_chain_of_thought_and_redacts_secrets() -> None:
    assert safe_event_document({"event": "reasoning.available", "text": "private steps"}) is None
    assert safe_event_document({"event": "message.delta", "delta": "partial"}) is None
    projected = safe_event_document(
        {
            "event": "run.failed",
            "error": "Authorization: Bearer super-secret-token-12345",
        }
    )
    assert projected is not None
    assert "super-secret" not in str(projected)
    assert "[REDACTED]" in str(projected)


def test_tool_argument_contract_rejects_model_supplied_scope() -> None:
    service = AgentToolService()
    try:
        service._validate_arguments(
            "read_gbp_state",
            {"organization_id": "other-org", "location_id": "other-location"},
        )
    except AgentToolDeniedError as exc:
        assert "unsupported tool arguments" in str(exc)
    else:
        raise AssertionError("model-supplied tenant scope was accepted")


def test_tool_metadata_never_persists_argument_values() -> None:
    metadata = safe_argument_metadata({"review_id": "review-123", "response_text": "hello"})
    assert metadata["argument_names"] == ["response_text", "review_id"]
    assert "review-123" not in str(metadata)
    assert "hello" not in str(metadata)
    assert redact_text("api_key=secret-value") == "[REDACTED]"
    with pytest.raises(ValueError, match="secret-bearing"):
        safe_argument_metadata({"body": "Authorization: Bearer must-not-cross-boundary"})


def test_complete_product_skill_and_sanctioned_tool_plane() -> None:
    assert set(TOOL_SPECS) == REQUIRED_LILOS_TOOLS
    assert set(WORKFLOW_SKILLS) == {
        "agent.gbp",
        "agent.seo",
        "agent.content",
        "agent.reviews",
        "agent.insights",
    }
    expected_versions = {
        # v4: the agent no longer writes post copy; generate_gbp_post_proposal
        # routes through the single governed generator.
        # v5 / v2 across the board: COMMON_POLICY gained the verbatim-citation
        # rule. Every skill embeds it, so every prompt changed, and the AI task
        # definition each run registers is keyed on this version -- leaving it
        # unchanged would record a prompt version that no longer matches the
        # text that ran.
        "gbp.operator": 5,
        "seo.operator": 2,
        "content.operator": 2,
        "reviews.operator": 2,
        "insights.cross_product": 2,
    }
    for skill in SKILLS.values():
        assert skill.version == expected_versions[skill.key]
        assert set(skill.required_tools) <= set(TOOL_SPECS)
        assert "Never" in skill.instructions or "never" in skill.instructions
    assert not any("publish" in name and "proposal" not in name for name in TOOL_SPECS)
    assert not any("google" in name or "github" in name for name in TOOL_SPECS)


def test_private_hermes_tool_route_registers_without_response_model_inference() -> None:
    route = next(
        item
        for item in hermes_tools_router.routes
        if str(getattr(item, "path", "")).endswith("/tools/{tool_name}")
    )
    assert getattr(route, "response_model", object()) is None


def test_bound_skill_limits_tools_and_scheduler_stays_lilos_owned() -> None:
    run = cast(
        AgentRun,
        SimpleNamespace(skill_key="gbp.operator"),
    )
    AgentToolService._validate_skill_tool(run, "generate_gbp_post_proposal")
    with pytest.raises(AgentToolDeniedError, match="bound agent skill"):
        AgentToolService._validate_skill_tool(run, "draft_review_response_proposal")
    assert set(WORKFLOW_SKILLS) <= set(WORKFLOW_TYPES)
    assert not hasattr(HermesRunsClient, "create_job")
    mutating = {name for name, spec in TOOL_SPECS.items() if spec.mutating}
    assert mutating == {
        "run_site_crawl",
        "create_seo_recommendation_proposal",
        "create_content_proposal",
        "create_content_brief",
        "generate_content_draft_proposal",
        "generate_gbp_post_proposal",
        "create_gbp_optimization_proposal",
        "draft_review_response_proposal",
        "submit_for_approval",
    }


def test_proposal_evidence_must_have_been_observed_by_the_bound_run() -> None:
    run = cast(
        AgentRun,
        SimpleNamespace(source_references=["seo-opportunity:observed"]),
    )
    assert AgentToolService._observed_source_references(
        run, ["seo-opportunity:observed"], label="SEO evidence"
    ) == ["seo-opportunity:observed"]
    with pytest.raises(AgentToolDeniedError, match="did not observe"):
        AgentToolService._observed_source_references(
            run, ["seo-opportunity:invented"], label="SEO evidence"
        )


def test_abbreviated_uuid_citation_resolves_to_the_observed_reference() -> None:
    """A real Wheyland run died here.

    The agent read the profile snapshot, then cited it back as
    ``gbp-profile-snapshot:b3cfad5b-...``. Byte-exact matching called that
    unobserved evidence and denied the proposal; the skill forbids retrying a
    mutating tool with different arguments, so the run ended with no post. The
    abbreviation is a presentation habit, not a governance failure.
    """
    snapshot = "gbp-profile-snapshot:b3cfad5b-7d21-4f0e-9c33-5a1f2b8e4d67"
    run = cast(AgentRun, SimpleNamespace(source_references=[snapshot]))

    for cited in (
        f"{snapshot[:30]}...",
        f"{snapshot[:30]}…",
        f"  {snapshot}  ",
        snapshot.upper(),
    ):
        assert AgentToolService._observed_source_references(
            run, [cited], label="GBP post evidence"
        ) == [snapshot], cited


def test_ambiguous_abbreviation_is_still_denied() -> None:
    """Resolution must be unique: two candidates mean the citation is unproven."""
    run = cast(
        AgentRun,
        SimpleNamespace(
            source_references=[
                "gbp-post-revision:11111111-1111-4111-8111-111111111111",
                "gbp-post-revision:11111111-1111-4111-8111-222222222222",
            ]
        ),
    )
    with pytest.raises(AgentToolDeniedError, match="did not observe"):
        AgentToolService._observed_source_references(
            run, ["gbp-post-revision:11111111-1111-4111-8111-"], label="GBP post evidence"
        )


def test_bare_kind_prefix_never_resolves_a_citation() -> None:
    """Otherwise "gbp-post-revision:" would cite whatever the run happened to read."""
    run = cast(
        AgentRun,
        SimpleNamespace(
            source_references=["gbp-post-revision:11111111-1111-4111-8111-111111111111"]
        ),
    )
    for cited in ("gbp-post-revision:", "gbp-post", ":", "..."):
        with pytest.raises(AgentToolDeniedError, match="did not observe"):
            AgentToolService._observed_source_references(run, [cited], label="GBP post evidence")


def test_denial_names_the_unmatched_citation_and_what_is_citable() -> None:
    """A refusal the agent cannot act on ends the run, because retrying is forbidden."""
    run = cast(AgentRun, SimpleNamespace(source_references=["business-fact:abc", "gbp-state:xyz"]))

    with pytest.raises(AgentToolDeniedError) as denied:
        AgentToolService._observed_source_references(
            run, ["business-fact:nope"], label="GBP post evidence"
        )
    message = str(denied.value)
    assert "business-fact:nope" in message
    assert "business-fact:abc" in message
    assert "gbp-state:xyz" in message


def test_empty_citation_list_says_to_read_first_when_nothing_was_observed() -> None:
    run = cast(AgentRun, SimpleNamespace(source_references=[]))
    with pytest.raises(AgentToolDeniedError, match="call the read tools first"):
        AgentToolService._observed_source_references(run, [], label="GBP post evidence")


def test_citable_summary_is_bounded_for_a_run_with_long_evidence() -> None:
    """The denial goes back to a model inside a bounded context; it cannot be unbounded."""
    observed = [f"business-knowledge:{index}" for index in range(120)]
    summary = AgentToolService._citable_summary(observed)
    assert "+100 more" in summary
    assert len(summary) < 1200


def test_review_agent_cannot_bypass_deterministic_restricted_risk() -> None:
    organization_id = uuid4()
    location_id = uuid4()

    class RestrictedReviews:
        async def get(self, *_args: object) -> tuple[SimpleNamespace, list[object]]:
            return (
                SimpleNamespace(
                    id=uuid4(),
                    location_id=location_id,
                    status="escalated",
                    risk_level="high",
                ),
                [],
            )

    async def scenario() -> None:
        service = AgentToolService()
        cast(Any, service).reviews = RestrictedReviews()
        run = cast(
            AgentRun,
            SimpleNamespace(organization_id=organization_id, location_id=location_id),
        )
        with pytest.raises(AgentToolDeniedError, match="risk guard"):
            await service._tool_draft_review_response_proposal(
                cast(Any, None),
                run,
                {
                    "review_id": str(uuid4()),
                    "response_text": "Draft",
                    "approved_fact_revision_ids": [str(uuid4())],
                },
            )

    asyncio.run(scenario())


def test_bound_read_result_returns_small_results_unchanged() -> None:
    result: dict[str, object] = {"data": {"website_knowledge": [{"url": "https://example.com/"}]}}

    assert bound_read_result(result) is result


def test_bound_read_result_degrades_instead_of_denying() -> None:
    """A read whose payload scales with client data must shrink, not fail.

    Regression: read_website_knowledge returned full page bodies, exceeded
    MAX_TOOL_RESULT_BYTES for a real client site, and was denied outright. The denial
    also discarded its source_references, which then blocked generate_gbp_post_proposal
    because the evidence it needed to cite had never been recorded as observed.
    """
    pages = [{"url": f"https://example.com/{i}", "body_excerpt": "x" * 2_000} for i in range(60)]
    result: dict[str, object] = {
        "data": {"website_knowledge": pages, "identity": [{"name": "Wheyland Electric"}]},
        "source_references": [f"business-knowledge:{i}" for i in range(30)],
    }
    assert encoded_size(result) > MAX_TOOL_RESULT_BYTES

    bounded = bound_read_result(result)

    assert encoded_size(bounded) <= MAX_TOOL_RESULT_BYTES
    assert bounded["truncated"] is True
    truncated_fields = bounded["truncated_fields"]
    assert isinstance(truncated_fields, list)
    assert "website_knowledge" in truncated_fields


def test_bound_read_result_never_trims_evidence_references() -> None:
    """source_references are the evidence identity governed proposals validate against."""
    references = [f"business-knowledge:{i}" for i in range(40)]
    result: dict[str, object] = {
        "data": {"website_knowledge": [{"body_excerpt": "y" * 3_000} for _ in range(50)]},
        "source_references": list(references),
    }

    bounded = bound_read_result(result)

    assert bounded["source_references"] == references
    assert encoded_size(bounded) <= MAX_TOOL_RESULT_BYTES


def test_bound_read_result_handles_unstructured_payload() -> None:
    result: dict[str, object] = {
        "data": "z" * (MAX_TOOL_RESULT_BYTES + 10),
        "source_references": ["a:1"],
    }

    bounded = bound_read_result(result)

    assert bounded["data"] == {}
    assert bounded["source_references"] == ["a:1"]
    assert encoded_size(bounded) <= MAX_TOOL_RESULT_BYTES


def test_compact_website_page_drops_full_body() -> None:
    page: dict[str, object] = {
        "url": "https://example.com/panel-upgrades/",
        "h1": "Panel Upgrades",
        "body_text": "word " * 5_000,
        "irrelevant": "drop me",
    }

    compact = AgentToolService._compact_website_page(page)

    assert compact["url"] == "https://example.com/panel-upgrades/"
    assert compact["h1"] == "Panel Upgrades"
    assert "irrelevant" not in compact
    assert "body_text" not in compact
    assert len(str(compact["body_excerpt"])) <= 600


def test_compact_website_page_tolerates_non_dict() -> None:
    assert AgentToolService._compact_website_page("nope") == {}


def test_run_site_crawl_binds_a_crawl_run_to_the_workflow() -> None:
    """Regression: the agent crawl tool started the workflow with an empty document.

    The seo.crawl_or_analysis handler requires input_document["crawl_run_id"], so every
    agent-initiated crawl failed permanently with MISSING_CRAWL_RUN_ID. SEOService
    .enqueue_crawl is the supported path: it creates the crawl run, writes the input
    document, and enqueues the job, so the workflow must not be pre-enqueued.
    """

    async def scenario() -> None:
        organization_id = uuid4()
        location_id = uuid4()
        website_id = uuid4()
        crawl_run_id = uuid4()
        workflow_id = uuid4()
        recorded: dict[str, Any] = {}

        class FakeSEO:
            async def list_websites(self, *_args: object) -> list[object]:
                return [SimpleNamespace(id=website_id)]

            async def enqueue_crawl(
                self,
                _session: object,
                org: object,
                site: object,
                command: Any,
                *,
                actor_id: object,
                correlation_id: object,
            ) -> object:
                recorded["website_id"] = site
                recorded["workflow_run_id"] = command.workflow_run_id
                recorded["idempotency_key"] = command.idempotency_key
                del org, actor_id, correlation_id
                return SimpleNamespace(id=crawl_run_id, status="queued")

        class FakeExecution:
            async def start_named(self, *_args: object, **kwargs: object) -> object:
                recorded["enqueue_job"] = kwargs.get("enqueue_job")
                return SimpleNamespace(id=workflow_id, status="queued")

        service = AgentToolService()
        service.seo = cast(Any, FakeSEO())
        service.execution = cast(Any, FakeExecution())

        result = await service._tool_run_site_crawl(
            cast(Any, None),
            cast(
                Any,
                SimpleNamespace(
                    id=uuid4(),
                    organization_id=organization_id,
                    location_id=location_id,
                    correlation_id="corr",
                ),
            ),
            {},
        )

        # The job must be enqueued by enqueue_crawl, not by start_named.
        assert recorded["enqueue_job"] is False
        assert recorded["workflow_run_id"] == workflow_id
        assert recorded["website_id"] == website_id
        assert len(str(recorded["idempotency_key"])) >= 8
        data = cast(dict[str, object], result["data"])
        assert data["crawl_run_reference"] == f"seo-crawl-run:{crawl_run_id}"
        assert f"seo-crawl-run:{crawl_run_id}" in cast(list[str], result["source_references"])

    asyncio.run(scenario())


def test_run_site_crawl_denies_when_no_website_is_registered() -> None:
    async def scenario() -> None:
        class FakeSEO:
            async def list_websites(self, *_args: object) -> list[object]:
                return []

        service = AgentToolService()
        service.seo = cast(Any, FakeSEO())

        with pytest.raises(AgentToolDeniedError):
            await service._tool_run_site_crawl(
                cast(Any, None),
                cast(
                    Any,
                    SimpleNamespace(
                        id=uuid4(),
                        organization_id=uuid4(),
                        location_id=uuid4(),
                        correlation_id="corr",
                    ),
                ),
                {},
            )

    asyncio.run(scenario())


def test_excerpt_collapses_whitespace_and_bounds_length() -> None:
    """Free text in a tool result is bounded at source, not by the generic trimmer."""
    from apps.api.app.agents.tools import _excerpt, _is_truncated

    assert _excerpt(None) is None
    assert _is_truncated(None) is False
    assert _excerpt("  a\n\n  b  ") == "a b"
    assert _is_truncated("short") is False

    long_body = "word " * 1_000
    excerpt = _excerpt(long_body)
    assert excerpt is not None
    assert len(excerpt) <= 900
    assert _is_truncated(long_body) is True


def test_review_and_post_excerpt_budgets_fit_the_bounded_policy() -> None:
    """Fifty full-length reviews or posts used to exceed MAX_TOOL_RESULT_BYTES.

    Regression guard: the per-item budgets must leave a whole page of results
    inside the cap, so read_reviews_state and read_gbp_recent_posts degrade at
    source rather than being denied or silently halved.
    """
    from apps.api.app.agents.tools import (
        POST_TEXT_EXCERPT_CHARACTERS,
        REVIEW_BODY_EXCERPT_CHARACTERS,
    )

    max_page = 50
    # Text must not consume the whole budget: keys, references, timestamps and the
    # summary object share it. Cap free text at 60% so a full page still fits.
    headroom = MAX_TOOL_RESULT_BYTES * 0.6
    # Reviews carry one excerpt each; posts carry a provider summary and a draft body.
    assert max_page * REVIEW_BODY_EXCERPT_CHARACTERS <= headroom
    assert max_page * 2 * POST_TEXT_EXCERPT_CHARACTERS <= headroom


def test_gbp_post_tool_does_not_accept_agent_written_copy() -> None:
    """There is one GBP post generator, and the agent is not it.

    The tool used to accept `content`, `post_type` and `call_to_action` from the
    model, which bypassed review grounding, service-topic rotation, the governed
    AI task and its cost ceiling -- so the agent produced posts under different
    rules than the scheduled workflow. It now takes evidence only.
    """
    spec = TOOL_SPECS["generate_gbp_post_proposal"]

    assert spec.mutating is True
    assert spec.allowed_arguments == frozenset({"source_evidence_references", "review_id"})
    for rejected in ("content", "post_type", "call_to_action"):
        assert rejected not in spec.allowed_arguments


def test_gbp_post_tool_rejects_content_argument() -> None:
    """Argument validation refuses copy outright rather than ignoring it."""
    with pytest.raises(AgentToolDeniedError):
        AgentToolService._validate_arguments(
            "generate_gbp_post_proposal",
            {"source_evidence_references": ["review:1"], "content": "model written copy"},
        )


def test_skill_instructions_preload_the_tool_surface() -> None:
    """Regression: runs opened with repeated tool_describe calls inside a large context."""
    for skill in SKILLS.values():
        assert "sanctioned tool list is given below in full" in skill.instructions
        assert "Do not probe or" in skill.instructions


def test_gbp_skill_does_not_promise_a_text_only_fallback() -> None:
    """The code raises when Drive media is unavailable; the prompt must agree."""
    instructions = SKILLS["gbp.operator"].instructions

    assert "there is no text-only" in instructions
    assert "when Drive media is configured" not in instructions
    assert "You do not write post copy" in instructions


def test_gbp_post_tool_names_its_failure_causes() -> None:
    """A governed refusal is only useful if it says what to fix.

    The tool previously let any non-enrichment failure escape as the route's
    generic HERMES_TOOL_FAILED / "Sanctioned tool execution failed". A live run
    reported the cause as "not diagnosed" and recommended re-running later, which
    is not actionable. The workflow handler already translated these; the tool now
    does too.
    """
    import inspect

    source = inspect.getsource(AgentToolService._tool_generate_gbp_post_proposal)

    # Each failure mode the generator can raise becomes a named code.
    assert "AIProviderError" in source
    assert "AI_PROVIDER_" in source
    assert "GBP_LOCATION_NOT_FOUND" in source
    assert "GBP_POST_GROUNDING_REQUIRED" in source
    # Translated into a denial, which the route reports with its safe message,
    # rather than falling through to the generic failure handler.
    assert "AgentToolDeniedError" in source


def test_ai_provider_failures_are_reported_as_denials_not_generic_failures() -> None:
    """AIProviderError must not reach the route's generic exception handler."""
    import inspect

    source = inspect.getsource(AgentToolService._tool_generate_gbp_post_proposal)
    provider_block = source[source.index("except AIProviderError") :]

    # The category and safe message both survive into the reported code.
    assert "exc.category" in provider_block
    assert "exc.safe_message" in provider_block


def test_a_refused_tool_names_what_the_run_may_call_instead() -> None:
    """A bare refusal taught the model nothing and it kept probing.

    The runtime advertises every LILOs tool regardless of the bound skill, so a
    GBP run is offered Reviews, SEO and workflow-inspection tools it can never
    call. Production logs show it trying them one after another — each attempt
    an iteration spent on a call that could only be denied.
    """
    run = cast(AgentRun, SimpleNamespace(skill_key="gbp.operator"))

    with pytest.raises(AgentToolDeniedError) as denial:
        AgentToolService._validate_skill_tool(run, "read_reviews_state")

    message = str(denial.value)
    assert "this run may call only:" in message
    # The sanctioned set is named in full, in a stable order.
    for sanctioned in SKILLS["gbp.operator"].required_tools:
        assert sanctioned in message
    # And the refused tool is not presented as if it were allowed.
    assert "read_reviews_state" not in message.split("this run may call only:")[1]


def test_the_named_set_is_exactly_the_skill_contract_not_the_whole_tool_plane() -> None:
    # Disclosing the full tool plane here would hand the model a menu of calls
    # that are refused for this run — the very probing this is meant to stop.
    run = cast(AgentRun, SimpleNamespace(skill_key="gbp.operator"))
    with pytest.raises(AgentToolDeniedError) as denial:
        AgentToolService._validate_skill_tool(run, "inspect_workflow")

    listed = str(denial.value).split("this run may call only:")[1]
    named = {item.strip() for item in listed.split(",")}
    assert named == set(SKILLS["gbp.operator"].required_tools)
    assert named < set(TOOL_SPECS)


def test_an_unknown_skill_is_refused_without_naming_anything() -> None:
    # No skill means no contract to quote; the refusal must not invent one.
    run = cast(AgentRun, SimpleNamespace(skill_key="not.a.skill"))
    with pytest.raises(AgentToolDeniedError) as denial:
        AgentToolService._validate_skill_tool(run, "read_gbp_state")
    assert "may call only" not in str(denial.value)
