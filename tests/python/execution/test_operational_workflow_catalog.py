"""Catalog coverage for directly runnable operational workflows."""

from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES


def test_operational_workflows_are_registered() -> None:
    assert WORKFLOW_TYPES["gbp.sync"][1] == "gbp"
    assert WORKFLOW_TYPES["gbp.generate_post"][1] == "gbp"
    assert WORKFLOW_TYPES["reviews.ingest"][1] == "reviews"
    assert WORKFLOW_TYPES["seo.analyze"][1] == "seo"
