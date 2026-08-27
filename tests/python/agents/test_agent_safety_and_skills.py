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
        "gbp.operator": 3,
        "seo.operator": 1,
        "content.operator": 1,
        "reviews.operator": 1,
        "insights.cross_product": 1,
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
    with pytest.raises(AgentToolDeniedError, match="observed by this bound agent run"):
        AgentToolService._observed_source_references(
            run, ["seo-opportunity:invented"], label="SEO evidence"
        )


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
