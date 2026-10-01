"""Packet 4: scoped evidence, immutable revisions, and page attribution policy."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from apps.api.app.agents.tools import AgentToolDeniedError, AgentToolService
from apps.api.app.growth.contracts import GrowthActionCreate, GrowthPlanCreate
from apps.api.app.growth.service import GrowthPlanValidationError, GrowthService
from apps.api.app.products.seo.contracts import RecommendationCreate, RecommendationDecision
from apps.api.app.products.seo.decision import (
    SEOActiveChangeError,
    SEOEvidenceInvalidError,
    growth_handoff,
    recommendation_class,
    resolve_decision,
    revision_decision,
)
from apps.api.app.products.seo.models import (
    SEOCrawlPageObservation,
    SEOOpportunity,
    SEORecommendationRevision,
    SEOSearchObservation,
)
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.service import SEOService


def query_opportunity() -> SEOOpportunity:
    return SEOOpportunity(
        id=uuid4(),
        organization_id=uuid4(),
        website_id=uuid4(),
        location_id=uuid4(),
        page_id=None,
        opportunity_type="gsc_query_demand",
        active_marker="active",
        evidence={
            "source": "google_search_console",
            "query": "service near me",
            "page_mapping_state": "unknown",
            "business_importance": {
                "business_importance_state": "unavailable",
                "business_policy_version": "business_importance.v1",
                "limitation": "No attributed landing page.",
            },
        },
        source_versions=["gsc.v1"],
        score_explanation={"score_policy_version": "opportunity_score.v2"},
        version=1,
    )


def bind_observation(opportunity: SEOOpportunity, observation: SEOSearchObservation) -> None:
    opportunity.evidence.update(
        {
            "observation_id": str(observation.id),
            "clicks": observation.clicks,
            "impressions": observation.impressions,
            "ctr": float(observation.ctr) if observation.ctr is not None else None,
            "position": float(observation.position) if observation.position is not None else None,
            "date_start": observation.date_start.isoformat(),
            "date_end": observation.date_end.isoformat(),
        }
    )


class ScalarSession:
    def __init__(self, *values: object) -> None:
        self.values = iter(values)

    async def scalar(self, _query: object) -> Any:
        return next(self.values)


@pytest.mark.anyio
async def test_query_only_decision_resolves_record_without_assigning_page() -> None:
    opportunity = query_opportunity()
    observation = SEOSearchObservation(
        id=uuid4(),
        quality_status="valid",
        dimensions={"query": "service near me"},
        date_end=datetime.now(UTC),
        date_start=datetime.now(UTC),
        mapping_state="unknown",
        clicks=2,
        impressions=100,
        ctr=0.02,
        position=30,
    )
    bind_observation(opportunity, observation)
    session = ScalarSession(
        SimpleNamespace(id=opportunity.website_id, location_id=opportunity.location_id), observation
    )
    decision = await resolve_decision(
        cast(Any, session),
        opportunity.organization_id,
        opportunity,
        [f"seo-opportunity:{opportunity.id}"],
    )
    assert decision["recommendation_class"] == "growth_change"
    assert decision["page_id"] is None
    assert decision["page_mapping_state"] == "unknown"
    assert decision["evidence_references"] == [
        f"seo-opportunity:{opportunity.id}",
        f"seo-search-observation:{observation.id}",
    ]
    passes = cast(dict[str, dict[str, object]], decision["passes"])
    assert passes["competition"]["availability"] == "unavailable"
    assert passes["answer_engines"]["availability"] == "unavailable"
    handoff = growth_handoff(uuid4(), "awaiting_approval", "Hypothesis", "Investigate", decision)
    assert handoff["target_reference"] == f"seo-opportunity:{opportunity.id}"
    assert handoff["approval_state"] == "awaiting_approval"
    observation.clicks = 3
    opportunity.evidence["clicks"] = 3
    updated = await resolve_decision(
        cast(
            Any,
            ScalarSession(
                SimpleNamespace(id=opportunity.website_id, location_id=opportunity.location_id),
                observation,
            ),
        ),
        opportunity.organization_id,
        opportunity,
        [f"seo-opportunity:{opportunity.id}"],
    )
    assert updated["source_evidence_fingerprint"] != decision["source_evidence_fingerprint"]


@pytest.mark.anyio
async def test_decision_fails_closed_for_invalid_or_cross_scope_evidence() -> None:
    opportunity = query_opportunity()
    ref = f"seo-opportunity:{opportunity.id}"
    with pytest.raises(SEOEvidenceInvalidError):
        await resolve_decision(
            cast(Any, ScalarSession()), opportunity.organization_id, opportunity, []
        )
    with pytest.raises(SEOEvidenceInvalidError):
        await resolve_decision(cast(Any, ScalarSession()), uuid4(), opportunity, [ref])
    with pytest.raises(SEOEvidenceInvalidError):
        await resolve_decision(
            cast(Any, ScalarSession(None)), opportunity.organization_id, opportunity, [ref]
        )
    with pytest.raises(SEOEvidenceInvalidError, match="observation ID is unavailable"):
        await resolve_decision(
            cast(Any, ScalarSession(SimpleNamespace(id=opportunity.website_id))),
            opportunity.organization_id,
            opportunity,
            [ref],
        )
    opportunity.evidence = {"source": "google_pagespeed"}
    with pytest.raises(SEOEvidenceInvalidError, match="No persisted scoped source"):
        await resolve_decision(
            cast(Any, ScalarSession(SimpleNamespace(id=opportunity.website_id))),
            opportunity.organization_id,
            opportunity,
            [ref],
        )


@pytest.mark.anyio
async def test_query_only_observation_with_page_dimension_is_rejected() -> None:
    opportunity = query_opportunity()
    observation = SEOSearchObservation(
        id=uuid4(),
        quality_status="valid",
        date_end=datetime.now(UTC),
        date_start=datetime.now(UTC),
        dimensions={"page": "https://example.test/arbitrary"},
        mapping_state="unknown",
        clicks=2,
        impressions=100,
        ctr=0.02,
        position=30,
    )
    bind_observation(opportunity, observation)
    with pytest.raises(SEOEvidenceInvalidError, match="cannot be assigned"):
        await resolve_decision(
            cast(Any, ScalarSession(SimpleNamespace(id=opportunity.website_id), observation)),
            opportunity.organization_id,
            opportunity,
            [f"seo-opportunity:{opportunity.id}"],
        )


def test_classification_is_derived_from_opportunity_type() -> None:
    growth = query_opportunity()
    technical = SEOOpportunity(opportunity_type="missing_title")
    assert recommendation_class(growth) == "growth_change"
    assert recommendation_class(technical) == "technical_regression"


@pytest.mark.anyio
async def test_legacy_crawl_opportunity_requires_current_persisted_issue() -> None:
    opportunity = SEOOpportunity(
        id=uuid4(),
        organization_id=uuid4(),
        website_id=uuid4(),
        location_id=uuid4(),
        page_id=uuid4(),
        opportunity_type="missing_title",
        active_marker="active",
        evidence={"url": "https://example.test/page", "issue": "missing_title"},
        source_versions=["crawl.v1"],
        score_explanation={"score_policy_version": "opportunity_score.v2"},
        version=1,
        priority_score=70,
    )
    observation = SEOCrawlPageObservation(
        id=uuid4(),
        technical_issues=["missing_title"],
        quality_status="issues_detected",
        http_status=200,
        indexability="indexable",
        observed_at=datetime.now(UTC),
    )

    def session() -> ScalarSession:
        return ScalarSession(
            SimpleNamespace(id=opportunity.website_id, location_id=opportunity.location_id),
            SimpleNamespace(id=opportunity.page_id),
            observation,
        )

    ref = f"seo-opportunity:{opportunity.id}"
    decision = await resolve_decision(
        cast(Any, session()), opportunity.organization_id, opportunity, [ref]
    )
    assert decision["evidence_references"] == [ref, f"seo-crawl-observation:{observation.id}"]
    observation.technical_issues = []
    with pytest.raises(SEOEvidenceInvalidError, match="latest crawl"):
        await resolve_decision(
            cast(Any, session()), opportunity.organization_id, opportunity, [ref]
        )


@pytest.mark.parametrize("forbidden", ["business_value", "priority_score", "approve", "site_write"])
def test_hermes_cannot_supply_authoritative_fields(forbidden: str) -> None:
    with pytest.raises(AgentToolDeniedError, match="unsupported tool arguments"):
        AgentToolService._validate_arguments(
            "create_seo_recommendation_proposal", {forbidden: "invented"}
        )


@pytest.mark.anyio
async def test_bound_hermes_reads_only_selected_opportunity_and_uses_current_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opportunity = query_opportunity()
    workflow = SimpleNamespace(input_document={"seo_opportunity_id": str(opportunity.id)})
    run = SimpleNamespace(
        workflow_run_id=uuid4(),
        organization_id=opportunity.organization_id,
        location_id=opportunity.location_id,
    )

    class Session:
        async def get(self, _model: object, _identifier: object) -> object:
            return workflow

    class SEO:
        async def get_opportunity(
            self, _session: object, org: object, identifier: object
        ) -> object:
            assert org == opportunity.organization_id
            assert identifier == opportunity.id
            return opportunity

        async def list_opportunities(self, *_args: object, **_kwargs: object) -> object:
            raise AssertionError("Bound Hermes may not read another opportunity")

    async def decision(*_args: object) -> dict[str, object]:
        return {"page_id": None, "passes": {"competition": {"availability": "unavailable"}}}

    service = AgentToolService()
    service.seo = cast(Any, SEO())
    monkeypatch.setattr("apps.api.app.agents.tools.resolve_decision", decision)
    result = await service._tool_analyze_seo_opportunities(
        cast(Any, Session()), cast(Any, run), {"limit": 50}
    )
    data = cast(dict[str, Any], result["data"])
    assert len(data["opportunities"]) == 1
    assert data["opportunities"][0]["governed_decision"]["page_id"] is None
    assert result["source_references"] == [f"seo-opportunity:{opportunity.id}"]


@pytest.mark.anyio
async def test_bound_hermes_proposal_fails_closed_when_evidence_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opportunity = query_opportunity()
    reference = f"seo-opportunity:{opportunity.id}"
    workflow = SimpleNamespace(
        input_document={
            "seo_opportunity_id": str(opportunity.id),
            "seo_decision_snapshot": {"v": 1},
        }
    )
    run = SimpleNamespace(
        workflow_run_id=uuid4(),
        organization_id=opportunity.organization_id,
        location_id=opportunity.location_id,
        source_references=[reference],
        correlation_id="test",
    )

    class Session:
        async def get(self, _model: object, _identifier: object) -> object:
            return workflow

    class SEO:
        async def get_opportunity(self, *_args: object) -> SEOOpportunity:
            return opportunity

        async def create_recommendation(self, *_args: object, **_kwargs: object) -> object:
            raise AssertionError("Stale reasoning must not create a revision")

    async def decision(*_args: object) -> dict[str, object]:
        return {"v": 2}

    service = AgentToolService()
    service.seo = cast(Any, SEO())
    monkeypatch.setattr("apps.api.app.agents.tools.resolve_decision", decision)
    arguments = {
        "proposed_action": "Investigate unattributed demand",
        "expected_result_hypothesis": "Clarify page attribution",
        "risk": "low",
        "effort": "low",
    }
    with pytest.raises(SEOEvidenceInvalidError, match="changed during Hermes reasoning"):
        await service._tool_create_seo_recommendation_proposal(
            cast(Any, Session()), cast(Any, run), arguments
        )
    with pytest.raises(AgentToolDeniedError, match="only action"):
        await service._tool_create_seo_recommendation_proposal(
            cast(Any, Session()), cast(Any, run), {**arguments, "opportunity_id": str(uuid4())}
        )
    with pytest.raises(AgentToolDeniedError, match="only action"):
        await service._tool_create_seo_recommendation_proposal(
            cast(Any, Session()), cast(Any, run), {**arguments, "evidence_references": [reference]}
        )
    with pytest.raises(AgentToolDeniedError, match="only action"):
        await service._tool_create_seo_recommendation_proposal(
            cast(Any, Session()), cast(Any, run), {"proposed_action": "Incomplete"}
        )


@pytest.mark.anyio
async def test_bound_hermes_stages_proposal_until_successful_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opportunity = query_opportunity()
    reference = f"seo-opportunity:{opportunity.id}"
    decision: dict[str, object] = {
        "contract_version": "seo_decision.v1",
        "organization_id": str(opportunity.organization_id),
        "location_id": str(opportunity.location_id),
        "website_id": str(opportunity.website_id),
        "page_id": None,
        "opportunity_id": str(opportunity.id),
        "page_mapping_state": "unknown",
        "recommendation_class": "growth_change",
        "evidence_references": [reference],
        "target_metric": None,
    }

    async def resolve(*_args: object) -> dict[str, object]:
        return decision

    async def get_opportunity(*_args: object) -> SEOOpportunity:
        return opportunity

    monkeypatch.setattr("apps.api.app.agents.tools.resolve_decision", resolve)
    tools = AgentToolService()
    monkeypatch.setattr(tools.seo, "get_opportunity", get_opportunity)

    class Session:
        async def get(self, _model: object, _identifier: object) -> object:
            return SimpleNamespace(
                input_document={
                    "seo_opportunity_id": str(opportunity.id),
                    "seo_decision_snapshot": decision,
                }
            )

    run = SimpleNamespace(
        workflow_run_id=uuid4(),
        organization_id=opportunity.organization_id,
        location_id=opportunity.location_id,
        source_references=[reference],
        correlation_id="test",
        final_output=None,
    )
    result = await tools._tool_create_seo_recommendation_proposal(
        cast(Any, Session()),
        cast(Any, run),
        {
            "proposed_action": "Investigate demand",
            "expected_result_hypothesis": "Clarify demand attribution",
            "risk": "low",
            "effort": "medium",
        },
    )
    assert result == {"data": {"accepted": True}, "source_references": [reference]}
    assert run.final_output["seo_pending_proposal"]["proposed_action"] == "Investigate demand"


@pytest.mark.anyio
async def test_unsupported_revision_cannot_be_approved() -> None:
    organization_id = uuid4()
    opportunity = SEOOpportunity(
        id=uuid4(),
        organization_id=organization_id,
        active_marker="active",
        status="recommended",
    )
    revision = SEORecommendationRevision(
        id=uuid4(),
        organization_id=organization_id,
        opportunity_id=opportunity.id,
        status="awaiting_approval",
        evidence_references=[],
    )
    with pytest.raises(SEOEvidenceInvalidError, match="snapshot"):
        await SEOService().decide_recommendation(
            cast(Any, ScalarSession(revision, opportunity, revision.id)),
            organization_id,
            revision.id,
            RecommendationDecision(approve=True),
            uuid4(),
            correlation_id="test",
        )
    assert revision.status == "awaiting_approval"


@pytest.mark.anyio
async def test_new_material_text_creates_another_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    opportunity = SEOOpportunity(
        id=uuid4(),
        organization_id=uuid4(),
        page_id=None,
        status="identified",
        opportunity_type="missing_title",
    )
    service = SEOService()

    async def get_opportunity(*_args: object) -> SEOOpportunity:
        return opportunity

    async def decision(*_args: object) -> dict[str, object]:
        return {
            "recommendation_class": "technical_regression",
            "contract_version": "seo_decision.v1",
        }

    async def noop(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(service, "get_opportunity", get_opportunity)
    monkeypatch.setattr("apps.api.app.products.seo.service.resolve_decision", decision)
    monkeypatch.setattr(service, "_audit", noop)
    monkeypatch.setattr(service, "_notify", noop)

    async def forbidden_growth_gate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Technical regression must bypass the growth attribution policy")

    monkeypatch.setattr(service, "_check_active_growth_change", forbidden_growth_gate)

    class Session:
        def __init__(self) -> None:
            self.revisions: list[Any] = []

        async def scalar(self, _query: object) -> int:
            return len(self.revisions)

        async def scalars(self, _query: object) -> list[Any]:
            # The older revisions a new one supersedes (`list_recommendations`).
            return list(self.revisions)

        def add(self, revision: object) -> None:
            self.revisions.append(revision)

        async def flush(self) -> None:
            return None

    session = Session()

    def command(action: str) -> RecommendationCreate:
        return RecommendationCreate(
            proposed_action=action,
            evidence_references=[f"seo-opportunity:{opportunity.id}"],
            expected_result_hypothesis="Restore access",
            risk="low",
            effort="low",
        )

    first = await service.create_recommendation(
        cast(Any, session),
        opportunity.organization_id,
        opportunity.id,
        command("Fix title"),
        actor_id=None,
        correlation_id="test",
    )
    second = await service.create_recommendation(
        cast(Any, session),
        opportunity.organization_id,
        opportunity.id,
        command("Fix canonical"),
        actor_id=None,
        correlation_id="test",
    )
    assert (first.revision_number, first.proposed_action) == (1, "Fix title")
    assert (second.revision_number, second.proposed_action) == (2, "Fix canonical")
    # Only the newest revision is live: the older one was superseded by the newer one.
    assert (first.status, second.status) == ("superseded", "awaiting_approval")
    assert revision_decision(first.evidence_references) == {
        "recommendation_class": "technical_regression",
        "contract_version": "seo_decision.v1",
    }


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("task_state", "expected"),
    [
        (None, "approved_awaiting_implementation"),
        ("pending", "implementing"),
        ("verified", "implemented_measuring"),
    ],
)
async def test_approved_page_growth_change_reports_exact_conflict(
    task_state: str | None, expected: str
) -> None:
    organization_id, website_id, location_id, page_id = (uuid4() for _ in range(4))
    opportunity = SEOOpportunity(
        organization_id=organization_id,
        website_id=website_id,
        location_id=location_id,
        page_id=page_id,
    )
    prior_opportunity = SEOOpportunity(opportunity_type="gsc_low_ctr")
    prior_revision = SimpleNamespace(id=uuid4())

    class Rows:
        def __iter__(self) -> Any:
            return iter([(prior_revision, prior_opportunity)])

    class Session:
        async def scalar(self, _query: object) -> object:
            if not hasattr(self, "page_read"):
                return SimpleNamespace(id=page_id)
            if task_state is not None and not hasattr(self, "task_read"):
                self.task_read = True
                return SimpleNamespace(
                    id=uuid4(),
                    status=task_state,
                    verified_at=datetime.now(UTC) if task_state == "verified" else None,
                )
            return None

        async def execute(self, _query: object) -> Rows:
            self.page_read = True
            return Rows()

    with pytest.raises(SEOActiveChangeError) as error:
        await SEOService()._check_active_growth_change(
            cast(Any, Session()), organization_id, opportunity
        )
    assert error.value.state == expected
    assert error.value.revision_id == prior_revision.id


@pytest.mark.anyio
async def test_attributable_growth_action_also_reserves_page() -> None:
    organization_id, website_id, location_id, page_id = (uuid4() for _ in range(4))
    opportunity = SEOOpportunity(
        organization_id=organization_id,
        website_id=website_id,
        location_id=location_id,
        page_id=page_id,
    )
    action = SimpleNamespace(
        id=uuid4(),
        status="approved",
        evidence_references=[],
        verification_plan={"metric": "gsc_ctr"},
    )

    class EmptyRows:
        def __iter__(self) -> Any:
            return iter(())

    class ActionRows:
        def scalars(self) -> list[object]:
            return [action]

    class Session:
        async def scalar(self, _query: object) -> object:
            return SimpleNamespace(id=page_id)

        async def execute(self, _query: object) -> object:
            if not hasattr(self, "seo_rows_read"):
                self.seo_rows_read = True
                return EmptyRows()
            return ActionRows()

    with pytest.raises(SEOActiveChangeError) as error:
        await SEOService()._check_active_growth_change(
            cast(Any, Session()), organization_id, opportunity
        )
    assert error.value.revision_id == action.id
    assert error.value.state == "approved_awaiting_implementation"


@pytest.mark.anyio
async def test_growth_plan_rejects_a_decision_that_is_not_approved() -> None:
    organization_id, location_id, page_id = uuid4(), uuid4(), uuid4()
    revision = SEORecommendationRevision(
        id=uuid4(),
        organization_id=organization_id,
        # The target and hypothesis are taken from the decision, so a paraphrase is not an
        # error; an unapproved decision still is.
        status="awaiting_approval",
        expected_result_hypothesis="Increase relevant clicks",
        evidence_references=[
            "seo-opportunity:source",
            {"decision_context": {"page_id": str(page_id)}},
        ],
    )
    opportunity = SEOOpportunity(id=uuid4(), page_id=page_id)
    command = GrowthPlanCreate(
        objective="Improve page",
        rationale="Observed demand",
        source_references=[f"seo-recommendation:{revision.id}"],
        priority_score=70,
        confidence=0.7,
        actions=[
            GrowthActionCreate(
                action_key="seo_change",
                product_key="seo",
                action_type="optimize",
                target_reference=f"seo-page:{uuid4()}",
                execution_mode="manual",
                evidence_references=[f"seo-recommendation:{revision.id}"],
                expected_result_hypothesis="Increase relevant clicks",
                risk="low",
                effort="low",
            )
        ],
    )

    class Pair:
        def first(self) -> tuple[SEORecommendationRevision, SEOOpportunity]:
            return revision, opportunity

    class Session:
        async def scalar(self, _query: object) -> None:
            return None

        async def execute(self, _query: object) -> Pair:
            return Pair()

    run = SimpleNamespace(id=uuid4(), organization_id=organization_id, location_id=location_id)
    with pytest.raises(GrowthPlanValidationError, match="does not match"):
        await GrowthService().create_from_agent(cast(Any, Session()), cast(Any, run), command)


@pytest.mark.anyio
async def test_content_handoff_remains_approval_bound() -> None:
    organization_id, opportunity_id = uuid4(), uuid4()
    revision = SEORecommendationRevision(
        id=uuid4(),
        organization_id=organization_id,
        opportunity_id=opportunity_id,
        status="awaiting_approval",
        proposed_action="Improve page copy",
        expected_result_hypothesis="More relevant visits",
    )

    class SEO:
        async def get_opportunity(self, *_args: object) -> SEOOpportunity:
            return SEOOpportunity(id=opportunity_id, opportunity_type="gsc_low_ctr")

    class Content:
        def __init__(self) -> None:
            self.objective: str | None = None

        async def get_opportunity_by_source_reference(self, *_args: object) -> object:
            return SimpleNamespace(id=uuid4(), status="identified")

        async def accept_opportunity_and_dispatch_agent(
            self, *_args: object, objective: str, **_kwargs: object
        ) -> tuple[object, object]:
            self.objective = objective
            return object(), SimpleNamespace(id=uuid4())

    content = Content()
    orchestration = SEOOrchestrationService(seo=cast(Any, SEO()), content=cast(Any, content))
    args = (cast(Any, None), organization_id, revision)
    actor_id = uuid4()
    correlation_id = "test"
    assert (
        await orchestration.handoff_approved_recommendation(
            *args, actor_id=actor_id, correlation_id=correlation_id
        )
        is None
    )
    assert content.objective is None
    revision.status = "approved"
    assert await orchestration.handoff_approved_recommendation(
        *args, actor_id=actor_id, correlation_id=correlation_id
    )
    assert content.objective is not None
    assert "Improve page copy" in content.objective
    assert "More relevant visits" in content.objective
