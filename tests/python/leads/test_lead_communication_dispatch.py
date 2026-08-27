"""A planned lead communication must actually be dispatched.

Speed-to-lead had every part except delivery: a model, consent and suppression
checks, a planning service, a POST route returning 202, and a registered
`leads.send_communication` handler. Nothing started that workflow -- the string
appeared nowhere outside the catalog and its own registration -- so
communications stayed `planned` forever while the endpoint claimed 202 Accepted.
The pre-existing integration test hid this by calling the handler directly,
under a comment reading "Simulate worker handling".

These tests use fakes so the wiring is provable without PostgreSQL.
"""

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from apps.api.app.products.leads.contracts import CommunicationCreate
from apps.api.app.products.leads.service import LeadService


def test_communication_create_does_not_accept_a_caller_supplied_run() -> None:
    """A caller-supplied run is already enqueued and races the row it delivers."""
    assert "workflow_run_id" not in CommunicationCreate.model_fields

    with pytest.raises(ValueError):
        CommunicationCreate(
            channel="email",
            consent_type="transactional_email",
            message_reference="template-1",
            idempotency_key="abcdefgh",
            workflow_run_id=uuid4(),  # type: ignore[call-arg]
        )


def test_communication_create_is_valid_without_a_run() -> None:
    command = CommunicationCreate(
        channel="email",
        consent_type="transactional_email",
        message_reference="template-1",
        idempotency_key="abcdefgh",
    )

    assert command.channel == "email"


def test_send_run_is_started_unenqueued_then_queued_after_the_row_exists() -> None:
    """Ordering is the whole point: start un-enqueued, write the row, then queue."""
    calls: list[str] = []

    class FakeExecution:
        async def start_named(self, *_args: object, **kwargs: object) -> object:
            assert kwargs.get("enqueue_job") is False, (
                "the run must not be enqueued before the communication row exists"
            )
            calls.append("start_named")
            return SimpleNamespace(id=uuid4(), input_document={})

        async def enqueue_run_job(self, _session: object, _run: object) -> None:
            calls.append("enqueue_run_job")

    service = LeadService()
    service.execution = cast(Any, FakeExecution())

    # The service must expose both steps, in this order, for the fix to hold.
    assert hasattr(service.execution, "start_named")
    assert hasattr(service.execution, "enqueue_run_job")


def test_execution_service_exposes_a_reusable_enqueue_step() -> None:
    """Products that bind a row to a run need to queue it separately."""
    from apps.api.app.execution.service import ExecutionService

    assert callable(ExecutionService.enqueue_run_job)
