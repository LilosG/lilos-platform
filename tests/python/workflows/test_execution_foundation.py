from uuid import uuid4

from apps.api.app.execution.contracts import WorkflowSubmit
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.execution.service import ExecutionService


def test_request_hash_is_deterministic_and_excludes_idempotency_key() -> None:
    version = uuid4()
    first = WorkflowSubmit(
        workflow_version_id=version, idempotency_key="request-one", input_document={"b": 2, "a": 1}
    )
    second = WorkflowSubmit(
        workflow_version_id=version, idempotency_key="request-two", input_document={"a": 1, "b": 2}
    )
    assert ExecutionService.request_hash(first) == ExecutionService.request_hash(second)


def test_execution_schema_contains_durable_safety_fields() -> None:
    assert {"idempotency_key", "request_hash", "status", "version"} <= set(
        WorkflowRun.__table__.columns.keys()
    )
    assert {
        "lease_owner",
        "lease_expires_at",
        "attempt_count",
        "max_attempts",
        "cancellation_requested_at",
    } <= set(Job.__table__.columns.keys())
