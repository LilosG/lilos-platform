"""Canonical workflow handler resolution with isolated domain adapters."""

from apps.api.app.agents.execution_handler import agent_workflow_handler
from apps.api.app.agents.skills import WORKFLOW_SKILLS
from apps.api.app.execution.handlers import WorkflowStepHandler, get_workflow_handler
from apps.api.app.products.reviews.publish_handler import handle_reviews_publish_response

_PRODUCT_HANDLERS: dict[str, WorkflowStepHandler] = {
    "reviews.publish_response": handle_reviews_publish_response,
}


def resolve_workflow_handler(key: str) -> WorkflowStepHandler | None:
    """Resolve a registered workflow to exactly one authoritative handler family."""
    if key in WORKFLOW_SKILLS:
        return agent_workflow_handler(key)
    return _PRODUCT_HANDLERS.get(key) or get_workflow_handler(key)
