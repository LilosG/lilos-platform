"""The workflow run request exposes execution as an explicit choice."""

from apps.api.app.routes.workflows import WorkflowRunStart


def test_workflow_run_start_defaults_to_reservation() -> None:
    command = WorkflowRunStart(idempotency_key="12345678")
    assert command.execute is False


def test_workflow_run_start_can_request_execution() -> None:
    command = WorkflowRunStart(idempotency_key="12345678", execute=True)
    assert command.execute is True
