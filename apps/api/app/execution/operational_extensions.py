"""Operational workflow handlers that join product subsystems."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config import Settings
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.execution.handlers import (
    _adapter_factory,
    _handle_seo_crawl,
    _provider_writes_enabled,
    _token_resolver,
    register_workflow_handler,
)
from apps.api.app.integrations.errors import (
    IntegrationNotFoundError,
    IntegrationReconnectRequiredError,
)
from apps.api.app.integrations.google_drive_media import DriveImage, GoogleDriveMediaService
from apps.api.app.integrations.secrets import SecretUnavailableError
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.gbp.operations_models import GBPPostPublication, GBPPostRevision
from apps.api.app.products.gbp.post_generation import GBPPostGenerationService
from apps.api.app.products.gbp.post_generation_models import GBPPostAsset
from apps.api.app.products.gbp.resource_names import v4_localposts_parent
from apps.api.app.products.seo.orchestration import SEOOrchestrationService

logger = logging.getLogger(__name__)


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


async def _handle_gbp_publish_post_with_media(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Publish an approved GBP post and attach its AI-selected Drive image."""
    del correlation_id, workflow_run_id
    publication_id = input_document.get("publication_id")
    if not publication_id:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_PUBLICATION_ID")

    publication = await session.scalar(
        select(GBPPostPublication)
        .where(
            GBPPostPublication.organization_id == organization_id,
            GBPPostPublication.id == UUID(str(publication_id)),
        )
        .with_for_update()
    )
    if publication is None:
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_FOUND")
    if publication.status == "verified":
        return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
    if publication.status not in ("reserved", "dispatched", "reconciliation_required"):
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_RESERVABLE")

    revision = await session.get(GBPPostRevision, publication.post_revision_id)
    if revision is None:
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="POST_REVISION_NOT_FOUND")
    gbp_location = await session.scalar(
        select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.id == revision.gbp_location_id,
        )
    )
    if gbp_location is None:
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")
    if location_id is not None and gbp_location.location_id != location_id:
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_SCOPE_MISMATCH")
    if not gbp_location.write_enabled or gbp_location.mapping_status != "confirmed":
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="WRITE_NOT_ENABLED")
    gbp_account = await session.get(GBPAccount, gbp_location.account_id)
    if gbp_account is None:
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="GBP_ACCOUNT_NOT_FOUND")
    if not _provider_writes_enabled():
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="PROVIDER_WRITES_DISABLED")

    adapter = _adapter_factory()
    try:
        token, _connection = await _token_resolver(session, organization_id)
    except IntegrationNotFoundError:
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="NO_CONNECTED_INTEGRATION")
    except IntegrationReconnectRequiredError:
        publication.status = "reconciliation_required"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
    except SecretUnavailableError:
        publication.status = "reconciliation_required"
        return JobOutcome(result="permanent_failure", safe_error="SECRET_RESOLUTION_FAILED")
    except Exception:
        publication.status = "reconciliation_required"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_RESOLUTION_FAILED")

    location_name = v4_localposts_parent(
        gbp_account.external_account_id, gbp_location.external_location_id
    )
    if publication.provider_post_id:
        try:
            re_read = await adapter.get_local_post(token, publication.provider_post_id)
        except Exception:
            publication.status = "reconciliation_required"
            return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")
        provider_state = str(re_read.get("state", "")).upper()
        if provider_state == "REJECTED":
            publication.status = "failed"
            return JobOutcome(result="permanent_failure", safe_error="POST_REJECTED_BY_PROVIDER")
        if provider_state == "LIVE":
            publication.status = "verified"
            publication.verified_at = datetime.now(UTC)
            return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
        publication.status = "reconciliation_required"
        return JobOutcome(result="retryable_failure", safe_error="POST_NOT_YET_LIVE")

    post_body: dict[str, Any] = {
        "languageCode": "en-US",
        "postType": revision.post_type,
        "text": revision.content,
    }
    if revision.call_to_action:
        post_body["callToAction"] = revision.call_to_action
    if revision.event_or_offer:
        if revision.post_type == "event":
            post_body["event"] = revision.event_or_offer
        elif revision.post_type == "offer":
            post_body["offer"] = revision.event_or_offer

    asset = await session.scalar(
        select(GBPPostAsset).where(
            GBPPostAsset.organization_id == organization_id,
            GBPPostAsset.post_revision_id == revision.id,
            GBPPostAsset.status == "selected",
        )
    )
    if asset is not None and asset.source_type == "google_drive":
        metadata = asset.metadata_document or {}
        file_id = str(metadata.get("file_id") or "")
        if file_id:
            image = DriveImage(
                file_id=file_id,
                name=str(metadata.get("name") or "GBP image"),
                mime_type=str(metadata.get("mime_type") or "image/jpeg"),
                path=str(metadata.get("path") or ""),
                modified_time=str(metadata.get("modified_time") or "") or None,
            )
            fresh_url = GoogleDriveMediaService().public_proxy_url(
                Settings(), organization_id=organization_id, image=image
            )
            if fresh_url:
                asset.provider_fetch_url = fresh_url
                post_body["media"] = [
                    {"mediaFormat": "PHOTO", "sourceUrl": fresh_url}
                ]

    publication.status = "dispatched"
    try:
        created = await adapter.create_local_post(token, location_name, post_body)
    except Exception as exc:
        publication.status = "failed"
        logger.warning(
            "GBP post creation failed",
            extra={
                "event_name": "gbp.publish_post.failed",
                "publication_id": str(publication.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="PROVIDER_WRITE_FAILED")

    provider_post_name = str(created.get("name", ""))
    if not provider_post_name:
        publication.status = "reconciliation_required"
        return JobOutcome(
            result="permanent_failure", safe_error="PROVIDER_RETURNED_NO_RESOURCE_NAME"
        )
    publication.provider_post_id = provider_post_name

    try:
        re_read = await adapter.get_local_post(token, provider_post_name)
    except Exception:
        publication.status = "reconciliation_required"
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")
    provider_state = str(re_read.get("state", "")).upper()
    if provider_state == "REJECTED":
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="POST_REJECTED_BY_PROVIDER")
    if provider_state == "LIVE":
        publication.status = "verified"
        publication.verified_at = datetime.now(UTC)
        return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
    publication.status = "reconciliation_required"
    return JobOutcome(result="retryable_failure", safe_error="POST_NOT_YET_LIVE")


register_workflow_handler("seo.crawl_or_analysis", _handle_seo_crawl_and_analysis)
register_workflow_handler("seo.analyze", _handle_seo_analysis)
register_workflow_handler("gbp.generate_post", _handle_gbp_generate_post)
register_workflow_handler("gbp.publish_post", _handle_gbp_publish_post_with_media)
