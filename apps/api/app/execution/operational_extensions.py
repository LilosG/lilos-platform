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
from apps.api.app.execution.provider_sync_handlers import (
    handle_analytics_sync,
    handle_gbp_performance_sync,
    handle_search_console_sync,
)
from apps.api.app.organizations.removal import handle_organization_remove
from apps.api.app.products.gbp.post_strategy import StrategicGBPPostGenerationService
from apps.api.app.products.gbp.proposal_enrichment import GBPProposalEnrichmentError
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.site_change_handler import handle_seo_apply_site_change

logger = logging.getLogger(__name__)

# Retrying a malformed or rejected Drive credential just burns the job's attempts
# and delays the operator seeing the real cause, so only transport-class Drive
# failures are retryable. The classified codes come from DriveDiscoveryError.
_RETRYABLE_GBP_ENRICHMENT_ERRORS = frozenset(
    {
        "GBP_WEBSITE_KNOWLEDGE_UNAVAILABLE",
        "GBP_DRIVE_MEDIA_UNAVAILABLE",
        "GBP_DRIVE_MEDIA_PROXY_UNAVAILABLE",
        "GBP_DRIVE_UNREACHABLE",
        "GBP_DRIVE_TEMPORARILY_UNAVAILABLE",
    }
)


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
    del workflow_run_id
    return await _analyze_website(
        session,
        organization_id=organization_id,
        location_id=location_id,
        correlation_id=correlation_id,
        website_id=None,
    )


async def _analyze_website(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    correlation_id: str,
    website_id: UUID | None,
) -> JobOutcome:
    try:
        result = await SEOOrchestrationService().analyze(
            session,
            organization_id,
            location_id=location_id,
            correlation_id=correlation_id,
            website_id=website_id,
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
    """Crawl and analyze either one reserved crawl run or, on a schedule, every active website.

    A schedule carries no crawl run (its input is only the schedule id), so a scheduled run
    creates one crawl run per active website in its scope and handles each like a reserved one.
    """
    if input_document.get("crawl_run_id") or not input_document.get("schedule_id"):
        return await _crawl_then_analyze(
            session,
            organization_id=organization_id,
            location_id=location_id,
            input_document=input_document,
            correlation_id=correlation_id,
            workflow_run_id=workflow_run_id,
        )

    from sqlalchemy import or_, select

    from apps.api.app.products.seo.models import SEOWebsite
    from apps.api.app.products.seo.service import SEOService

    conditions = [SEOWebsite.organization_id == organization_id, SEOWebsite.status == "active"]
    if location_id is not None:
        conditions.append(
            or_(SEOWebsite.location_id == location_id, SEOWebsite.location_id.is_(None))
        )
    websites = list(
        await session.scalars(select(SEOWebsite).where(*conditions).order_by(SEOWebsite.created_at))
    )
    if not websites:
        return JobOutcome(result="permanent_failure", safe_error="SEO_ACTIVE_WEBSITE_MISSING")
    first_failure: JobOutcome | None = None
    references: list[str] = []
    for website in websites:
        crawl_run = await SEOService().ensure_scheduled_crawl_run(
            session, organization_id, website.id, workflow_run_id
        )
        outcome = await _crawl_then_analyze(
            session,
            organization_id=organization_id,
            location_id=location_id,
            input_document={"crawl_run_id": str(crawl_run.id)},
            correlation_id=correlation_id,
            workflow_run_id=workflow_run_id,
        )
        if outcome.result == "succeeded":
            references.append(outcome.result_reference or "")
        elif first_failure is None:
            first_failure = outcome
    if first_failure is not None:
        return first_failure
    return JobOutcome(result="succeeded", result_reference="|".join(references)[:500])


async def _crawl_then_analyze(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Run a crawl, activate a reachable website, then analyze its evidence.

    Onboarding provisions the SEO website from an approved primary organization
    domain, then queues this combined workflow. The website begins as
    ``pending_verification``. A successful crawl proves it is reachable and safe
    to use for SEO analysis, but it does not prove domain ownership; therefore
    this transition changes only the website runtime status and leaves the
    separate ownership fields untouched.

    Previously the crawl handler reported success even when the crawl record
    ended in ``error`` and, when it really did succeed, analysis immediately
    rejected the still-pending website as missing.
    """
    from sqlalchemy import select

    from apps.api.app.products.seo.models import SEOCrawlRun, SEOWebsite

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

    crawl_run_raw = input_document.get("crawl_run_id")
    if not crawl_run_raw:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_CRAWL_RUN_ID")
    try:
        crawl_run_id = UUID(str(crawl_run_raw))
    except (TypeError, ValueError):
        return JobOutcome(result="permanent_failure", safe_error="INVALID_CRAWL_RUN_ID")

    crawl_run = await session.scalar(
        select(SEOCrawlRun).where(
            SEOCrawlRun.organization_id == organization_id,
            SEOCrawlRun.id == crawl_run_id,
        )
    )
    if crawl_run is None:
        return JobOutcome(result="permanent_failure", safe_error="SEO_CRAWL_RUN_NOT_FOUND")
    if crawl_run.status == "error":
        return JobOutcome(result="retryable_failure", safe_error="SEO_CRAWL_FAILED")
    if crawl_run.status not in {"success", "partial"}:
        return JobOutcome(result="retryable_failure", safe_error="SEO_CRAWL_NOT_TERMINAL")

    safe_result = crawl_run.safe_result or {}
    raw_pages_crawled = safe_result.get("pages_crawled")
    pages_crawled = raw_pages_crawled if isinstance(raw_pages_crawled, int) else 0
    if pages_crawled <= 0:
        return JobOutcome(result="retryable_failure", safe_error="SEO_CRAWL_EMPTY")

    website = await session.scalar(
        select(SEOWebsite).where(
            SEOWebsite.organization_id == organization_id,
            SEOWebsite.id == crawl_run.website_id,
        )
    )
    if website is None:
        return JobOutcome(result="permanent_failure", safe_error="SEO_WEBSITE_NOT_FOUND")
    if location_id is not None and website.location_id not in {None, location_id}:
        return JobOutcome(result="permanent_failure", safe_error="SEO_WEBSITE_SCOPE_MISMATCH")
    if website.status == "pending_verification":
        website.status = "active"
        website.version += 1
        await session.flush()
        logger.info(
            "SEO website activated after successful first crawl",
            extra={
                "event_name": "seo.website.activated_by_crawl",
                "organization_id": str(organization_id),
                "website_id": str(website.id),
                "crawl_run_id": str(crawl_run.id),
                "pages_crawled": pages_crawled,
            },
        )
    elif website.status != "active":
        return JobOutcome(result="permanent_failure", safe_error="SEO_WEBSITE_NOT_ACTIVE")

    analysis = await _analyze_website(
        session,
        organization_id=organization_id,
        location_id=location_id,
        correlation_id=correlation_id,
        website_id=website.id,
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
    if location_id is None:
        return JobOutcome(result="permanent_failure", safe_error="LOCATION_ID_MISSING")

    source_review_id: UUID | None = None
    source_review_raw = input_document.get("review_id")
    if source_review_raw is not None:
        try:
            source_review_id = UUID(str(source_review_raw))
        except (TypeError, ValueError):
            return JobOutcome(result="permanent_failure", safe_error="GBP_REVIEW_SOURCE_INVALID")

    try:
        revision, _execution, asset = await StrategicGBPPostGenerationService().generate(
            session,
            Settings(),
            organization_id,
            location_id,
            workflow_run_id=workflow_run_id,
            correlation_id=correlation_id,
            source_review_id=source_review_id,
        )
    except GBPProposalEnrichmentError as exc:
        # The runtime commits returned JobOutcomes. Roll back every mutation made
        # by this handler before translating the enrichment exception into a
        # workflow outcome so no partial review, CTA, or image binding can survive.
        await session.rollback()
        logger.warning(
            "GBP AI post delivery enrichment failed",
            extra={
                "event_name": "gbp.generate_post.delivery_enrichment_failed",
                "organization_id": str(organization_id),
                "location_id": str(location_id),
                "source_review_id": str(source_review_id) if source_review_id else None,
                "safe_error_code": exc.safe_code,
            },
        )
        return JobOutcome(
            result=(
                "retryable_failure"
                if exc.safe_code in _RETRYABLE_GBP_ENRICHMENT_ERRORS
                else "permanent_failure"
            ),
            safe_error=exc.safe_code,
        )
    except ValueError as exc:
        await session.rollback()
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
        await session.rollback()
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
        await session.rollback()
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

    if asset is None:
        await session.rollback()
        return JobOutcome(
            result="permanent_failure",
            safe_error="GBP_POST_DELIVERY_BINDING_MISSING",
        )
    return JobOutcome(
        result="succeeded",
        result_reference=f"gbp-post-revision:{revision.id}:image",
    )


register_workflow_handler("organization.remove", handle_organization_remove)
register_workflow_handler("seo.crawl_or_analysis", _handle_seo_crawl_and_analysis)
register_workflow_handler("seo.analyze", _handle_seo_analysis)
register_workflow_handler("seo.apply_site_change", handle_seo_apply_site_change)
register_workflow_handler("seo.sync_search_console", handle_search_console_sync)
register_workflow_handler("insights.sync_analytics", handle_analytics_sync)
register_workflow_handler("gbp.sync_performance", handle_gbp_performance_sync)
register_workflow_handler("gbp.generate_post", _handle_gbp_generate_post)
for _agent_workflow_key in (
    "agent.gbp",
    "agent.growth",
    "agent.seo",
    "agent.content",
    "agent.reviews",
    "agent.leads",
    "agent.insights",
):
    register_workflow_handler(_agent_workflow_key, _handle_agent_workflow)
