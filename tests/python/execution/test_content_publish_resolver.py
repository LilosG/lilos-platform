from apps.api.app.execution.handler_resolver import resolve_workflow_handler
from apps.api.app.products.content.publish_handler import handle_content_publish


def test_content_publish_uses_product_owned_recoverable_handler() -> None:
    assert resolve_workflow_handler("content.publish") is handle_content_publish
