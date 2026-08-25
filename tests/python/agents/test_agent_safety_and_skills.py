import asyncio
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from apps.api.app.agents.hermes_client import REQUIRED_LILOS_TOOLS, HermesRunsClient
from apps.api.app.agents.models import AgentRun
from apps.api.app.agents.safety import redact_text, safe_argument_metadata, safe_event_document
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
