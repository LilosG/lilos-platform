"""Registered workflow step handlers for product workflows.

Each handler receives the database session, organization/location scope,
and the workflow run's input document, performs the actual product work,
and returns a JobOutcome.  Handlers are registered by workflow definition key
and looked up at execution time by the worker runtime.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.contracts import JobOutcome

logger = logging.getLogger(__name__)


class WorkflowStepHandler(Protocol):
    async def __call__(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        input_document: dict[str, Any],
        correlation_id: str,
    ) -> JobOutcome: ...


_REGISTRY: dict[str, WorkflowStepHandler] = {}


def register_workflow_handler(key: str, handler: WorkflowStepHandler) -> None:
    """Register a step handler for a workflow definition key."""
    _REGISTRY[key] = handler


def get_workflow_handler(key: str) -> WorkflowStepHandler | None:
    return _REGISTRY.get(key)


def registered_workflow_keys() -> Sequence[str]:
    return tuple(_REGISTRY.keys())


# ---------------------------------------------------------------------------
# GBP publish-change handler
# ---------------------------------------------------------------------------


async def _handle_gbp_publish_change(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
) -> JobOutcome:
    """Publish an approved GBP profile change via the GBP adapter.

    Resolves the publication reservation, reads a fresh access token,
    calls the adapter's patch_location, verifies the write by re-reading,
    and updates the publication status.
    """
    from sqlalchemy import select

    from apps.api.app.config import Settings
    from apps.api.app.integrations.connection_service import GBPConnectionService
    from apps.api.app.products.gbp.adapter import GoogleBusinessProfileAdapter
    from apps.api.app.products.gbp.models import GBPLocation, GBPPublication

    publication_id = input_document.get("publication_id")
    if not publication_id:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_PUBLICATION_ID")

    publication = await session.scalar(
        select(GBPPublication).where(
            GBPPublication.organization_id == organization_id,
            GBPPublication.id == UUID(str(publication_id)),
        )
    )
    if publication is None:
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_FOUND")
    if publication.status != "reserved":
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_RESERVABLE")

    gbp_location = await session.scalar(
        select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.id == publication.location_id,
        )
    )
    if gbp_location is None:
        publication.status = "failed"
        publication.safe_error_code = "GBP_LOCATION_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")
    if not gbp_location.write_enabled:
        publication.status = "failed"
        publication.safe_error_code = "WRITE_NOT_ENABLED"
        return JobOutcome(result="permanent_failure", safe_error="WRITE_NOT_ENABLED")

    connection_svc = GBPConnectionService()
    adapter = GoogleBusinessProfileAdapter()

    connection = await connection_svc.get_connection(session, organization_id)
    try:
        token = await connection_svc.ensure_fresh_token(session, Settings(), connection)
    except Exception:
        publication.status = "reconciliation_required"
        publication.safe_error_code = "TOKEN_REFRESH_FAILED"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")

    from apps.api.app.products.gbp.models import GBPAccount

    acct = await session.get(GBPAccount, gbp_location.account_id)
    if not acct:
        publication.status = "failed"
        publication.safe_error_code = "ACCOUNT_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="ACCOUNT_NOT_FOUND")

    location_name = (
        f"accounts/{acct.external_account_id}/locations/{gbp_location.external_location_id}"
    )
    update_fields: dict[str, Any] = {}

    from apps.api.app.products.gbp.models import GBPProfileChangeRevision

    revision = await session.get(GBPProfileChangeRevision, publication.change_revision_id)
    if revision:
        for key, value in revision.desired_fields.items():
            update_fields[key] = value

    if not update_fields:
        publication.status = "failed"
        publication.safe_error_code = "NO_FIELDS_TO_UPDATE"
        return JobOutcome(result="permanent_failure", safe_error="NO_FIELDS_TO_UPDATE")

    publication.status = "dispatched"
    from datetime import UTC, datetime

    publication.dispatched_at = datetime.now(UTC)

    try:
        await adapter.patch_location(
            token,
            location_name,
            update_fields,
            [str(f) for f in publication.update_mask],
            str(publication.idempotency_key),
        )
    except Exception as exc:
        publication.status = "failed"
        publication.safe_error_code = "PROVIDER_WRITE_FAILED"
        logger.warning(
            "GBP publish failed",
            extra={
                "event_name": "gbp.publish.failed",
                "publication_id": str(publication.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="PROVIDER_WRITE_FAILED")

    from apps.api.app.products.gbp.service import GBPService

    gbp_svc = GBPService()
    try:
        raw = await adapter.get_location(token, location_name)
        await gbp_svc.store_snapshot(session, gbp_location, raw, partial=False)
    except Exception as exc:
        publication.status = "reconciliation_required"
        publication.safe_error_code = "VERIFICATION_REREAD_FAILED"
        logger.warning(
            "GBP publish verification re-read failed",
            extra={
                "event_name": "gbp.publish.verification_failed",
                "publication_id": str(publication.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")

    publication.status = "verified"
    publication.verified_at = datetime.now(UTC)
    publication.provider_operation_reference = location_name

    return JobOutcome(
        result="succeeded",
        result_reference=f"publication:{publication.id}",
    )


# ---------------------------------------------------------------------------
# GBP publish-post handler
# ---------------------------------------------------------------------------


async def _handle_gbp_publish_post(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
) -> JobOutcome:
    """Publish an approved GBP post via the GBP Posts API.

    The GBP Posts API requires scopes beyond the currently-configured
    ``business.manage`` and a dedicated adapter method that does not yet
    exist.  Rather than fabricating a ``verified`` publication status, this
    handler fails closed: the publication is marked ``failed`` with a clear
    ``safe_error_code`` so operators see the real blocker.  Once the Posts
    API scope and adapter method are added, this handler should be updated
    to perform the real provider write and verification re-read, mirroring
    ``_handle_gbp_publish_change``.
    """
    from sqlalchemy import select

    from apps.api.app.products.gbp.operations_models import GBPPostPublication

    publication_id = input_document.get("publication_id")
    if not publication_id:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_PUBLICATION_ID")

    publication = await session.scalar(
        select(GBPPostPublication).where(
            GBPPostPublication.organization_id == organization_id,
            GBPPostPublication.id == UUID(str(publication_id)),
        )
    )
    if publication is None:
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_FOUND")

    publication.status = "failed"
    return JobOutcome(result="permanent_failure", safe_error="POSTS_API_SCOPE_NOT_CONFIGURED")


# ---------------------------------------------------------------------------
# SEO crawl handler
# ---------------------------------------------------------------------------


async def _handle_seo_crawl(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
) -> JobOutcome:
    """Execute a bounded SEO crawl using the existing SEOService."""
    from apps.api.app.products.seo.contracts import CrawlRequest
    from apps.api.app.products.seo.service import SEOService

    website_id = input_document.get("website_id")
    if not website_id:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_WEBSITE_ID")

    workflow_run_id_str = input_document.get("workflow_run_id")
    if not workflow_run_id_str:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_WORKFLOW_RUN_ID")

    idempotency_key = input_document.get("idempotency_key", f"crawl-{website_id}")

    command = CrawlRequest(
        workflow_run_id=UUID(str(workflow_run_id_str)),
        idempotency_key=str(idempotency_key),
        max_pages=int(input_document.get("max_pages", 5)),
    )

    seo_service = SEOService()
    try:
        await seo_service.run_crawl(
            session,
            organization_id,
            UUID(str(website_id)),
            UUID(str(workflow_run_id_str)),
            command,
            actor_id=None,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.warning(
            "SEO crawl failed",
            extra={
                "event_name": "seo.crawl.failed",
                "website_id": str(website_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="CRAWL_FAILED")

    return JobOutcome(result="succeeded", result_reference=f"website:{website_id}")


# ---------------------------------------------------------------------------
# Content publish handler
# ---------------------------------------------------------------------------


async def _handle_content_publish(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
) -> JobOutcome:
    """Publish governed content to a configured publishing target.

    Real publication to GitHub/CMS targets requires a configured
    per-organization publishing-target connection and a provider adapter
    that does not yet exist in this codebase.  Rather than fabricating a
    ``verified`` publication status, this handler fails closed: the
    publication is marked ``failed`` with a clear ``safe_error_code`` so
    operators see the real blocker.  Once a publishing connector and
    adapter are added, this handler should perform the real provider write
    and verification, mirroring ``_handle_gbp_publish_change``.
    """
    from sqlalchemy import select

    from apps.api.app.products.content.models import ContentPublication

    publication_id = input_document.get("publication_id")
    if not publication_id:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_PUBLICATION_ID")

    publication = await session.scalar(
        select(ContentPublication).where(
            ContentPublication.organization_id == organization_id,
            ContentPublication.id == UUID(str(publication_id)),
        )
    )
    if publication is None:
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_FOUND")

    publication.status = "failed"
    publication.safe_error_code = "PUBLISHING_TARGET_NOT_CONFIGURED"
    return JobOutcome(result="permanent_failure", safe_error="PUBLISHING_TARGET_NOT_CONFIGURED")


# ---------------------------------------------------------------------------
# Register all handlers
# ---------------------------------------------------------------------------


def _register_all() -> None:
    register_workflow_handler("gbp.publish_change", _handle_gbp_publish_change)
    register_workflow_handler("gbp.publish_post", _handle_gbp_publish_post)
    register_workflow_handler("seo.crawl_or_analysis", _handle_seo_crawl)
    register_workflow_handler("content.publish", _handle_content_publish)


_register_all()
