"""Record a failed provider call as an ``ai_executions`` row.

A provider failure used to leave nothing behind: the exception unwound the workflow
step, the transaction was abandoned, and the operator had only a generic job error.
The row written here names the failure (``safe_error_code`` is the typed code) and
how long the call ran, so a bad run can be read back from the database.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.ai.errors import AIProviderError
from apps.api.app.ai.models import AIExecution

logger = logging.getLogger(__name__)

# The unique idempotency key is reserved for the call that succeeds: a retry reuses it,
# and a failed row holding it would be replayed as if it were that call's result.
_KEY_ROOM = 128 - len(":failed:") - 16


async def record_failed_execution(
    session: AsyncSession,
    *,
    error: AIProviderError,
    organization_id: UUID,
    location_id: UUID | None,
    task_definition_id: UUID,
    workflow_run_id: UUID | None,
    idempotency_key: str,
    input_references: Sequence[object],
    approved_fact_revision_ids: Sequence[object],
) -> None:
    """Add and flush one ``provider_failed`` row. Never raises: the caller re-raises ``error``.

    The caller's transaction must be committed after this (the workflow handlers do) or
    the row is lost with it.
    """
    try:
        async with session.begin_nested():
            session.add(
                AIExecution(
                    organization_id=organization_id,
                    location_id=location_id,
                    task_definition_id=task_definition_id,
                    workflow_run_id=workflow_run_id,
                    idempotency_key=f"{idempotency_key[:_KEY_ROOM]}:failed:{uuid4().hex[:16]}",
                    status="provider_failed",
                    input_references=[str(x) for x in input_references],
                    approved_fact_revision_ids=[str(x) for x in approved_fact_revision_ids],
                    output_tokens=error.output_tokens,
                    latency_ms=error.elapsed_ms,
                    requires_human_review=True,
                    safe_error_code=error.code.value if error.code else None,
                )
            )
    except Exception:
        logger.exception(
            "Could not record the failed AI execution",
            extra={"event_name": "ai.execution.failure_not_recorded"},
        )
