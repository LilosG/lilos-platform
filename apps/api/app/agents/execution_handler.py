"""Canonical durable-workflow adapter for governed Hermes agent skills."""

from __future__ import annotations

from functools import cache
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.agents.service import AgentRuntimeService
from apps.api.app.agents.skills import WORKFLOW_SKILLS
from apps.api.app.config import Settings
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.handlers import WorkflowStepHandler


@cache
def agent_workflow_handler(workflow_key: str) -> WorkflowStepHandler:
    """Return a stable handler bound to one registered Hermes workflow key.

    Workflow identity stays server-owned: the key comes from the persisted
    WorkflowDefinition resolved by the worker, never from model input.
    """
    if workflow_key not in WORKFLOW_SKILLS:
        raise ValueError(f"unknown Hermes agent workflow: {workflow_key}")

    async def handle(
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        input_document: dict[str, Any],
        correlation_id: str,
        workflow_run_id: UUID,
    ) -> JobOutcome:
        return await AgentRuntimeService().execute_workflow(
            session,
            Settings(),
            organization_id=organization_id,
            location_id=location_id,
            workflow_run_id=workflow_run_id,
            workflow_key=workflow_key,
            input_document=input_document,
            correlation_id=correlation_id,
        )

    handle.__name__ = f"handle_{workflow_key.replace('.', '_')}"
    return handle
