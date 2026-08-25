"""Operational workflow handlers that join product subsystems."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config import Settings
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.handlers import (
    _handle_seo_crawl,
    register_workflow_handler,
)
from apps.api.app.products.gbp.post_generation import GBPPostGenerationService
from apps.api.app.products.seo.orchestration import SEOOrchestrationService

logger = logging.getLogger(__name__)


async def _handle_agent_workflow(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Execute one native Hermes run inside the existing durable worker lease."""
    from sqlalchemy import select

    from apps.api.app.agents.service import AgentRuntimeService
    from apps.api.app.execution.models import WorkflowDefinition, WorkflowRun, WorkflowVersion

    workflow_key = await session.scalar(
        select(WorkflowDefinition.key)
        .join(WorkflowVersion, WorkflowVersion.definition_id == WorkflowDefinition.id)
        .join(WorkflowRun, WorkflowRun.workflow_version_id == WorkflowVersion.id)
        .where(
            WorkflowRun.organization_id == organization_id,
            WorkflowRun.id == workflow_run_id,
        )
    )
    if not workflow_key or not str(workflow_key).startswith("agent."):
        return JobOutcome(result="permanent_failure", safe_error="AGENT_WORKFLOW_BINDING_INVALID")
    return await AgentRuntimeService().execute_workflow(
        session,
        Settings(),
        organization_id=organization_id,
        location_id=location_id,
        workflow_run_id=workflow_run_id,
        workflow_key=str(workflow_key),
        input_document=input_document,
        correlation_id=correlation_id,
    )


async def _handle_seo_analysis(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    del input_document, workflow_run_id
    try:
        result = await SEOOrchestrationService().analyze(
            session,
            organization_id,
            location_id=location_id,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.exception(
            "SEO evidence analysis failed",
            extra={
                "event_name": "seo.analysis.failed",
                "organization_id": str(organization_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="SEO_ANALYSIS_FAILED")

    if result.get("status") == "no_active_website":
        return JobOutcome(result="permanent_failure", safe_error="SEO_ACTIVE_WEBSITE_MISSING")
    return JobOutcome(
        result="succeeded",
        result_reference=(
            "seo-analysis:"
            f"{result.get('website_id', organization_id)}:"
            f"{result.get('seo_opportunities', 0)}"
        ),
    )


async def _handle_seo_crawl_and_analysis(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    crawl = await _handle_seo_crawl(
        session,
        organization_id=organization_id,
        location_id=location_id,
        input_document=input_document,
        correlation_id=correlation_id,
        workflow_run_id=workflow_run_id,
    )
    if crawl.result != "succeeded":
        return crawl
    analysis = await _handle_seo_analysis(
        session,
        organization_id=organization_id,
        location_id=location_id,
        input_document={},
        correlation_id=correlation_id,
        workflow_run_id=workflow_run_id,
    )
    if analysis.result != "succeeded":
        return analysis
    return JobOutcome(
        result="succeeded",
        result_reference=f"{crawl.result_reference}|{analysis.result_reference}",
    )


async def _handle_gbp_generate_post(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    del input_document
    if location_id is None:
        return JobOutcome(result="permanent_failure", safe_error="LOCATION_ID_MISSING")
    try:
        revision, _execution, asset = await GBPPostGenerationService().generate(
            session,
            Settings(),
            organization_id,
            location_id,
            workflow_run_id=workflow_run_id,
            correlation_id=correlation_id,
        )
    except ValueError as exc:
        logger.warning(
            "GBP AI post generation rejected",
            extra={
                "event_name": "gbp.generate_post.rejected",
                "organization_id": str(organization_id),
                "location_id": str(location_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="permanent_failure", safe_error="GBP_POST_GROUNDING_REQUIRED")
    except LookupError as exc:
        logger.warning(
            "GBP AI post generation scope missing",
            extra={
                "event_name": "gbp.generate_post.scope_missing",
                "organization_id": str(organization_id),
                "location_id": str(location_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")
    except Exception as exc:
        logger.exception(
            "GBP AI post generation failed",
            extra={
                "event_name": "gbp.generate_post.failed",
                "organization_id": str(organization_id),
                "location_id": str(location_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="GBP_POST_GENERATION_FAILED")

    suffix = ":image" if asset is not None else ":text"
    return JobOutcome(
        result="succeeded",
        result_reference=f"gbp-post-revision:{revision.id}{suffix}",
    )


register_workflow_handler("seo.crawl_or_analysis", _handle_seo_crawl_and_analysis)
register_workflow_handler("seo.analyze", _handle_seo_analysis)
register_workflow_handler("gbp.generate_post", _handle_gbp_generate_post)
for _agent_workflow_key in (
    "agent.gbp",
    "agent.seo",
    "agent.content",
    "agent.reviews",
    "agent.insights",
):
    register_workflow_handler(_agent_workflow_key, _handle_agent_workflow)
