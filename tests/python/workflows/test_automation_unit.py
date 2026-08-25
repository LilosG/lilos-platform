"""Packet 5 — unit-level tests that do not require a PostgreSQL database."""

from datetime import UTC, datetime
from uuid import uuid4

from apps.api.app.execution.contracts import (
    JobOutcome,
    ScheduleCreate,
    ScheduleUpdate,
    WorkflowSubmit,
)
from apps.api.app.execution.service import ExecutionService
from apps.api.app.execution.workflow_catalog import WORKFLOW_TYPES, is_known_workflow_key

# ---------------------------------------------------------------------------
# Contract validation
# ---------------------------------------------------------------------------


def test_schedule_create_contract_requires_workflow_key() -> None:
    """ScheduleCreate now takes workflow_key instead of workflow_version_id."""
    cmd = ScheduleCreate(
        workflow_key="gbp.sync",
        key="test-schedule",
        cron_expression="0 8 * * *",
        timezone="America/Los_Angeles",
        next_run_at=datetime.now(UTC),
    )
    assert cmd.workflow_key == "gbp.sync"
    assert cmd.key == "test-schedule"
    assert cmd.cron_expression == "0 8 * * *"


def test_schedule_update_contract_partial_fields() -> None:
    """ScheduleUpdate allows partial updates — only status is required."""
    # Status-only update (pause)
    cmd = ScheduleUpdate(status="paused")
    assert cmd.status == "paused"
    assert cmd.cron_expression is None
    assert cmd.timezone is None
    assert cmd.next_run_at is None

    # Full update
    cmd2 = ScheduleUpdate(
        status="active",
        cron_expression="0 */4 * * *",
        timezone="UTC",
    )
    assert cmd2.status == "active"
    assert cmd2.cron_expression == "0 */4 * * *"


def test_workflow_submit_idempotency_key_not_in_hash() -> None:
    """request_hash must exclude idempotency_key so same payload with
    different idempotency keys produces the same hash."""
    version = uuid4()
    first = WorkflowSubmit(
        workflow_version_id=version,
        idempotency_key="key-a-001",
        input_document={"action": "sync"},
    )
    second = WorkflowSubmit(
        workflow_version_id=version,
        idempotency_key="key-b-002",
        input_document={"action": "sync"},
    )
    assert ExecutionService.request_hash(first) == ExecutionService.request_hash(second)


def test_job_outcome_queued_semantics() -> None:
    """A succeeded outcome can represent 'queued for delivery' — the result
    field reflects the handler's own success, not provider delivery."""
    outcome = JobOutcome(
        result="succeeded",
        result_reference="communication:queued",
    )
    assert outcome.result == "succeeded"
    assert outcome.result_reference == "communication:queued"


# ---------------------------------------------------------------------------
# Workflow catalog consistency
# ---------------------------------------------------------------------------


def test_canonical_workflow_types_registered() -> None:
    """Verify the fixed registry contains every governed product workflow."""
    assert set(WORKFLOW_TYPES) == {
        "agent.content",
        "agent.gbp",
        "agent.insights",
        "agent.reviews",
        "agent.seo",
        "content.draft_revision",
        "content.publish",
        "gbp.generate_post",
        "gbp.publish_change",
        "gbp.publish_post",
        "gbp.sync",
        "gbp.upload_media",
        "leads.send_communication",
        "reviews.ingest",
        "reviews.publish_response",
        "seo.analyze",
        "seo.crawl_or_analysis",
    }


def test_workflow_keys_follow_naming_convention() -> None:
    """All workflow keys must use dot-notation (product.action)."""
    for key in WORKFLOW_TYPES:
        assert "." in key, f"Workflow key '{key}' must use dot-notation"
        parts = key.split(".")
        assert len(parts) >= 2
        assert all(part.islower() or "_" in part or part.isalnum() for part in parts)


def test_workflow_types_have_product_and_display_name() -> None:
    """Each entry must have a display name and product key."""
    for _key, (display_name, product_key) in WORKFLOW_TYPES.items():
        assert isinstance(display_name, str)
        assert len(display_name) > 0
        assert isinstance(product_key, str)
        assert len(product_key) > 0


def test_is_known_workflow_key_rejects_unknown() -> None:
    """Guard function must reject unknown keys."""
    assert is_known_workflow_key("gbp.sync") is True
    assert is_known_workflow_key("reviews.ingest") is True
    assert is_known_workflow_key("not.a.real.workflow") is False
    assert is_known_workflow_key("") is False


def test_workflow_catalog_coverage() -> None:
    """Every product must have at least one workflow type registered."""
    products = {product_key for _, product_key in WORKFLOW_TYPES.values()}
    assert "gbp" in products
    assert "reviews" in products
    assert "seo" in products
    assert "content" in products
    assert "leads" in products


# ---------------------------------------------------------------------------
# ScheduleCreate contract upgrade path
# ---------------------------------------------------------------------------


def test_schedule_create_old_contract_is_not_importable() -> None:
    """The old ScheduleCreate (with workflow_version_id) has been replaced.
    The new contract uses workflow_key instead."""
    cmd = ScheduleCreate(
        workflow_key="gbp.sync",
        key="migration-test",
        cron_expression="0 12 * * *",
        timezone="UTC",
        next_run_at=datetime.now(UTC),
    )
    # The old workflow_version_id field should not exist
    assert not hasattr(cmd, "workflow_version_id"), (
        "ScheduleCreate should use workflow_key, not workflow_version_id"
    )
    assert hasattr(cmd, "workflow_key")
