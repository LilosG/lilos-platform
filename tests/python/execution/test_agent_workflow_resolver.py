from apps.api.app.agents.skills import WORKFLOW_SKILLS
from apps.api.app.execution.handler_resolver import resolve_workflow_handler


def test_every_registered_agent_workflow_has_a_durable_handler() -> None:
    for workflow_key in WORKFLOW_SKILLS:
        handler = resolve_workflow_handler(workflow_key)
        assert handler is not None, workflow_key
        assert handler.__name__ == f"handle_{workflow_key.replace('.', '_')}"


def test_agent_handler_resolution_is_stable() -> None:
    first = resolve_workflow_handler("agent.growth")
    second = resolve_workflow_handler("agent.growth")

    assert first is not None
    assert first is second
