"""Canonical workflow handler resolution with isolated product handlers."""

from apps.api.app.execution.handlers import WorkflowStepHandler, get_workflow_handler
from apps.api.app.products.reviews.publish_handler import handle_reviews_publish_response

_PRODUCT_HANDLERS: dict[str, WorkflowStepHandler] = {
    "reviews.publish_response": handle_reviews_publish_response,
}


def resolve_workflow_handler(key: str) -> WorkflowStepHandler | None:
    """Return a product-specific handler or the established execution registry entry."""
    return _PRODUCT_HANDLERS.get(key) or get_workflow_handler(key)
