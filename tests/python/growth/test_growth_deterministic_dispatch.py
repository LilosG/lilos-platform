"""Deterministic Growth actions dispatch their workflow directly, never Hermes."""

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.api.app.growth.action_types import deterministic_workflow_for
from apps.api.app.growth.contracts import GrowthActionCreate, GrowthPlanCreate
from apps.api.app.growth.service import GrowthService


def _action(
    action_key: str = "run-analysis",
    product_key: str = "seo",
    action_type: str = "analyze",
    execution_mode: str = "workflow",
    executor_workflow_key: str | None = None,
    status: str = "approved",
) -> SimpleNamespace:
    action_id = uuid4()
    return SimpleNamespace(
        id=action_id,
        action_key=action_key,
        product_key=product_key,
        action_type=action_type,
        target_reference="https://example.invalid/",
        execution_mode=execution_mode,
        executor_workflow_key=executor_workflow_key,
        dependency_keys=[],
        evidence_references=[],
        expected_result_hypothesis="Evidence improves.",
        verification_plan={},
        status=status,
        workflow_run_id=None,
        completed_at=None,
    )


@pytest.mark.anyio
async def test_dispatch_ready_deterministic_action_skips_hermes_objective() -> None:
    org, initiative_id, actor_id, workflow_id = (uuid4() for _ in range(4))
    action = _action(executor_workflow_key="seo.analyze")
    initiative = SimpleNamespace(
        id=initiative_id, organization_id=org, status="executing", location_id=None
    )
    workflow = SimpleNamespace(id=workflow_id)

    service = GrowthService()
    service.get = AsyncMock(return_value=initiative)  # type: ignore[method-assign]
    service.actions = AsyncMock(return_value=[action])  # type: ignore[method-assign]
    service.execution.start_named = AsyncMock(return_value=workflow)  # type: ignore[method-assign]
    service.audit = AsyncMock()

    class Session:
        flush = AsyncMock()

    dispatched = await service.dispatch_ready(
        cast(Any, Session()),
        org,
        initiative_id,
        actor_id=actor_id,
        correlation_id="dispatch-test",
    )

    assert dispatched == [action]
    assert action.status == "queued"
    assert action.workflow_run_id == workflow_id
    service.execution.start_named.assert_awaited_once()
    call = service.execution.start_named.await_args
    assert call is not None
    assert call.args[2] == "seo.analyze"
    assert "objective" not in call.kwargs["input_document"]
    assert call.kwargs["input_document"] == {"context_reference": f"growth-action:{action.id}"}


@pytest.mark.anyio
async def test_dispatch_ready_reasoning_action_still_uses_hermes_objective() -> None:
    org, initiative_id, actor_id, workflow_id = (uuid4() for _ in range(4))
    action = _action(
        product_key="reviews",
        action_type="respond_to_review",
        executor_workflow_key="agent.reviews",
    )
    initiative = SimpleNamespace(
        id=initiative_id, organization_id=org, status="executing", location_id=None
    )
    workflow = SimpleNamespace(id=workflow_id)

    service = GrowthService()
    service.get = AsyncMock(return_value=initiative)  # type: ignore[method-assign]
    service.actions = AsyncMock(return_value=[action])  # type: ignore[method-assign]
    service.execution.start_named = AsyncMock(return_value=workflow)  # type: ignore[method-assign]
    service.audit = AsyncMock()

    class Session:
        flush = AsyncMock()

    dispatched = await service.dispatch_ready(
        cast(Any, Session()),
        org,
        initiative_id,
        actor_id=actor_id,
        correlation_id="dispatch-test",
    )

    assert dispatched == [action]
    service.execution.start_named.assert_awaited_once()
    call = service.execution.start_named.await_args
    assert call is not None
    assert call.args[2] == "agent.reviews"
    assert "objective" in call.kwargs["input_document"]
    assert action.action_key in call.kwargs["input_document"]["objective"]


def test_deterministic_workflow_for_recognizes_registered_pairs() -> None:
    assert deterministic_workflow_for("seo", "analyze") == "seo.analyze"
    assert deterministic_workflow_for("gbp", "sync") == "gbp.sync"
    assert deterministic_workflow_for("reviews", "ingest") == "reviews.ingest"
    assert deterministic_workflow_for("seo", "draft_recommendation") is None
    assert deterministic_workflow_for("content", "analyze") is None


def test_canonicalize_executor_bindings_routes_deterministic_seo_analysis() -> None:
    command = GrowthPlanCreate(
        objective="Improve site evidence",
        rationale="Stale analysis",
        source_references=["seo-opportunity:test"],
        priority_score=50,
        confidence=0.7,
        actions=[
            GrowthActionCreate(
                action_key="refresh-analysis",
                product_key="seo",
                action_type="analyze",
                target_reference="https://example.invalid/",
                execution_mode="workflow",
                dependency_keys=[],
                evidence_references=["seo-opportunity:test"],
                expected_result_hypothesis="Fresh evidence.",
                verification_plan={},
                risk="low",
                effort="low",
            )
        ],
    )
    canonicalized = GrowthService._canonicalize_executor_bindings(command)
    assert canonicalized.actions[0].executor_workflow_key == "seo.analyze"
    GrowthService._validate_executor_bindings(canonicalized)
