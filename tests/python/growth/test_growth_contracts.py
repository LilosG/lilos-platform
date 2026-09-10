import pytest
from pydantic import ValidationError

from apps.api.app.growth.contracts import GrowthActionCreate, GrowthPlanCreate
from apps.api.app.growth.service import (
    GROWTH_EXECUTOR_WORKFLOWS,
    GrowthPlanValidationError,
    GrowthService,
)


def _action(
    key: str,
    *,
    product: str = "seo",
    mode: str = "workflow",
    workflow: str | None = "agent.seo",
    dependencies: list[str] | None = None,
) -> dict[str, object]:
    return {
        "action_key": key,
        "product_key": product,
        "action_type": "analyze_or_optimize",
        "target_reference": "https://example.com/service/",
        "execution_mode": mode,
        "executor_workflow_key": workflow,
        "dependency_keys": dependencies or [],
        "evidence_references": ["seo-opportunity:11111111-1111-4111-8111-111111111111"],
        "expected_result_hypothesis": "Improve qualified organic visibility.",
        "verification_plan": {"metric": "gsc_clicks", "window_days": 28},
        "risk": "low",
        "effort": "medium",
        "approval_required": True,
    }


def _plan(actions: list[dict[str, object]]) -> GrowthPlanCreate:
    return GrowthPlanCreate.model_validate(
        {
            "objective": "Increase qualified local organic demand.",
            "rationale": "Current persisted evidence indicates a prioritized opportunity.",
            "source_references": ["seo-opportunity:11111111-1111-4111-8111-111111111111"],
            "priority_score": 82,
            "confidence": 0.84,
            "actions": actions,
        }
    )


def test_growth_plan_accepts_an_ordered_cross_product_dag() -> None:
    plan = _plan(
        [
            _action("seo.assess"),
            _action(
                "content.execute",
                product="content",
                workflow="agent.content",
                dependencies=["seo.assess"],
            ),
            _action(
                "gbp.support",
                product="gbp",
                workflow="agent.gbp",
                dependencies=["content.execute"],
            ),
        ]
    )

    assert [action.action_key for action in plan.actions] == [
        "seo.assess",
        "content.execute",
        "gbp.support",
    ]


def test_growth_plan_rejects_unknown_dependency() -> None:
    with pytest.raises(ValidationError, match="same plan"):
        _plan([_action("content.execute", dependencies=["missing.action"])])


def test_growth_plan_rejects_dependency_cycle() -> None:
    with pytest.raises(ValidationError, match="acyclic"):
        _plan(
            [
                _action("seo.assess", dependencies=["content.execute"]),
                _action("content.execute", dependencies=["seo.assess"]),
            ]
        )


def test_workflow_mode_requires_executor_and_manual_monitor_forbid_one() -> None:
    with pytest.raises(ValidationError, match="require executor_workflow_key"):
        GrowthActionCreate.model_validate(_action("seo.assess", workflow=None))

    manual = GrowthActionCreate.model_validate(
        _action("manual.verify", product="growth", mode="manual", workflow=None)
    )
    assert manual.executor_workflow_key is None

    with pytest.raises(ValidationError, match="cannot bind an executor"):
        GrowthActionCreate.model_validate(
            _action("manual.invalid", product="growth", mode="manual", workflow="agent.seo")
        )


def test_growth_service_rejects_executor_product_mismatch() -> None:
    plan = _plan([_action("wrong.owner", product="content", workflow="agent.seo")])

    with pytest.raises(GrowthPlanValidationError, match="belongs to seo, not content"):
        GrowthService._validate_executor_bindings(plan)


def test_growth_service_forbids_recursive_planner_execution() -> None:
    plan = _plan([_action("recursive", product="growth", workflow="agent.growth")])

    with pytest.raises(GrowthPlanValidationError, match="recursively"):
        GrowthService._validate_executor_bindings(plan)


@pytest.mark.parametrize(
    ("product", "workflow"),
    [
        ("content", "content.publish"),
        ("gbp", "gbp.publish_change"),
        ("gbp", "gbp.publish_post"),
        ("reviews", "reviews.publish_response"),
    ],
)
def test_growth_service_forbids_direct_product_lifecycle_workflows(
    product: str,
    workflow: str,
) -> None:
    plan = _plan([_action("direct.publish", product=product, workflow=workflow)])

    with pytest.raises(
        GrowthPlanValidationError,
        match="not a growth-delegatable product agent",
    ):
        GrowthService._validate_executor_bindings(plan)


def test_growth_executor_catalog_is_limited_to_governed_product_agents() -> None:
    assert GROWTH_EXECUTOR_WORKFLOWS == {
        "agent.seo": "seo",
        "agent.content": "content",
        "agent.gbp": "gbp",
        "agent.reviews": "reviews",
    }


@pytest.mark.parametrize(
    ("product", "workflow"),
    [
        ("seo", "agent.seo"),
        ("content", "agent.content"),
        ("gbp", "agent.gbp"),
        ("reviews", "agent.reviews"),
    ],
)
def test_growth_service_accepts_only_governed_product_agent_delegation(
    product: str,
    workflow: str,
) -> None:
    plan = _plan([_action("governed.delegate", product=product, workflow=workflow)])

    GrowthService._validate_executor_bindings(plan)
