"""Catalog coverage for directly runnable operational workflows."""

from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES


def test_operational_workflows_are_registered() -> None:
    assert WORKFLOW_TYPES["gbp.sync"][1] == "gbp"
    assert WORKFLOW_TYPES["gbp.generate_post"][1] == "gbp"
    assert WORKFLOW_TYPES["reviews.ingest"][1] == "reviews"
    assert WORKFLOW_TYPES["seo.analyze"][1] == "seo"


def test_organization_removal_is_a_registered_workflow_with_a_handler() -> None:
    import apps.api.app.execution.operational_extensions  # noqa: F401 - registers the handlers
    from apps.api.app.execution.handler_resolver import resolve_workflow_handler
    from apps.api.app.organizations.removal import handle_organization_remove

    assert WORKFLOW_TYPES["organization.remove"][1] == "platform"
    assert resolve_workflow_handler("organization.remove") is handle_organization_remove


def test_every_catalogued_workflow_resolves_to_a_handler() -> None:
    import apps.api.app.execution.operational_extensions  # noqa: F401 - registers the handlers
    from apps.api.app.execution.handler_resolver import resolve_workflow_handler

    unhandled = [key for key in WORKFLOW_TYPES if resolve_workflow_handler(key) is None]
    assert unhandled == []
