"""Canonical provider-write handler for approved Google Business Profile posts."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config import Settings
from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.integrations.errors import (
    IntegrationNotFoundError,
    IntegrationReconnectRequiredError,
)
from apps.api.app.integrations.google_drive_media import DriveImage, GoogleDriveMediaService
from apps.api.app.integrations.secrets import SecretUnavailableError
from apps.api.app.products.gbp.adapter import GBPAdapter
from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
from apps.api.app.products.gbp.operations_models import GBPPostPublication, GBPPostRevision
from apps.api.app.products.gbp.post_generation_models import GBPPostAsset
from apps.api.app.products.gbp.post_publication_contract import (
    GBPPostDeliveryRequirements,
    GBPPostPublicationContractError,
    build_provider_post_body,
    verify_provider_post,
)
from apps.api.app.products.gbp.resource_names import v4_localposts_parent

logger = logging.getLogger(__name__)

AdapterFactory = Callable[[], GBPAdapter]
TokenResolver = Callable[[AsyncSession, UUID], Any]
ProviderWriteGate = Callable[[], bool]


async def handle_gbp_publish_post(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
    adapter_factory: AdapterFactory,
    token_resolver: TokenResolver,
    provider_writes_enabled: ProviderWriteGate,
) -> JobOutcome:
    """Publish one approved post without weakening its governed delivery contract.

    New automated revisions carry a versioned publication contract requiring
    both the selected client-scoped image and the deterministic client-owned
    CTA. The worker fails before dispatch when those requirements cannot be
    satisfied, and a Google ``LIVE`` state is accepted only after the returned
    LocalPost matches the governed contract. Historical revisions without a
    versioned contract retain their legacy LIVE-only verification semantics.
    """
    publication_id_raw = input_document.get("publication_id")
    if not publication_id_raw:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_PUBLICATION_ID")
    try:
        publication_id = UUID(str(publication_id_raw))
    except (TypeError, ValueError):
        return JobOutcome(result="permanent_failure", safe_error="INVALID_PUBLICATION_ID")

    publication = await session.scalar(
        select(GBPPostPublication)
        .where(
            GBPPostPublication.organization_id == organization_id,
            GBPPostPublication.id == publication_id,
        )
        .with_for_update()
    )
    if publication is None:
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_FOUND")
    if publication.workflow_run_id != workflow_run_id:
        return JobOutcome(result="permanent_failure", safe_error="WORKFLOW_SCOPE_MISMATCH")
    if publication.status == "verified":
        return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
    if publication.status not in ("reserved", "dispatched", "reconciliation_required"):
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_RESERVABLE")

    initial_dispatch = publication.status == "reserved" and publication.dispatched_at is None
    if not initial_dispatch and not publication.provider_post_id:
        publication.status = "reconciliation_required"
        publication.safe_error_code = "AMBIGUOUS_PROVIDER_RESULT"
        await session.commit()
        return JobOutcome(result="ambiguous", safe_error="AMBIGUOUS_PROVIDER_RESULT")

    revision = await session.get(GBPPostRevision, publication.post_revision_id)
    if revision is None or revision.organization_id != organization_id:
        publication.status = "failed"
        publication.safe_error_code = "POST_REVISION_NOT_FOUND"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="POST_REVISION_NOT_FOUND")
    if revision.status != "approved":
        publication.status = "failed"
        publication.safe_error_code = "POST_REVISION_NOT_APPROVED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="POST_REVISION_NOT_APPROVED")

    try:
        requirements = GBPPostDeliveryRequirements.from_document(revision.publication_requirements)
    except GBPPostPublicationContractError as exc:
        publication.status = "failed"
        publication.safe_error_code = exc.safe_code
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error=exc.safe_code)

    gbp_location = await session.scalar(
        select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.id == revision.gbp_location_id,
        )
    )
    if gbp_location is None:
        publication.status = "failed"
        publication.safe_error_code = "GBP_LOCATION_NOT_FOUND"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")
    if location_id is not None and gbp_location.location_id != location_id:
        publication.status = "failed"
        publication.safe_error_code = "GBP_LOCATION_SCOPE_MISMATCH"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_SCOPE_MISMATCH")
    if not gbp_location.write_enabled or gbp_location.mapping_status != "confirmed":
        publication.status = "failed"
        publication.safe_error_code = "WRITE_NOT_ENABLED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="WRITE_NOT_ENABLED")

    gbp_account = await session.get(GBPAccount, gbp_location.account_id)
    if gbp_account is None or gbp_account.organization_id != organization_id:
        publication.status = "failed"
        publication.safe_error_code = "GBP_ACCOUNT_NOT_FOUND"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="GBP_ACCOUNT_NOT_FOUND")
    if initial_dispatch and not provider_writes_enabled():
        publication.status = "failed"
        publication.safe_error_code = "PROVIDER_WRITES_DISABLED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="PROVIDER_WRITES_DISABLED")

    selected_asset = await session.scalar(
        select(GBPPostAsset).where(
            GBPPostAsset.organization_id == organization_id,
            GBPPostAsset.post_revision_id == revision.id,
            GBPPostAsset.status == "selected",
        )
    )
    if requirements.media_required and selected_asset is None:
        publication.status = "failed"
        publication.safe_error_code = "POST_MEDIA_REQUIRED_MISSING"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="POST_MEDIA_REQUIRED_MISSING")

    media_url: str | None = None
    if selected_asset is not None:
        if selected_asset.source_type != "google_drive":
            publication.status = "failed"
            publication.safe_error_code = "POST_MEDIA_SOURCE_UNSUPPORTED"
            await session.commit()
            return JobOutcome(
                result="permanent_failure", safe_error="POST_MEDIA_SOURCE_UNSUPPORTED"
            )
        metadata = selected_asset.metadata_document or {}
        file_id = str(metadata.get("file_id") or "").strip()
        if not file_id:
            publication.status = "failed"
            publication.safe_error_code = "POST_MEDIA_FILE_ID_MISSING"
            await session.commit()
            return JobOutcome(result="permanent_failure", safe_error="POST_MEDIA_FILE_ID_MISSING")
        image = DriveImage(
            file_id=file_id,
            name=str(metadata.get("name") or "GBP image"),
            mime_type=str(metadata.get("mime_type") or "image/jpeg"),
            path=str(metadata.get("path") or ""),
            modified_time=str(metadata.get("modified_time") or "") or None,
        )
        media_url = GoogleDriveMediaService().public_proxy_url(
            Settings(), organization_id=organization_id, image=image
        )
        if not media_url:
            publication.status = "reserved"
            publication.safe_error_code = "POST_MEDIA_URL_UNAVAILABLE"
            await session.commit()
            return JobOutcome(result="retryable_failure", safe_error="POST_MEDIA_URL_UNAVAILABLE")
        selected_asset.provider_fetch_url = media_url

    try:
        post_body = build_provider_post_body(
            post_type=revision.post_type,
            content=revision.content,
            call_to_action=revision.call_to_action,
            event_or_offer=revision.event_or_offer,
            requirements=requirements,
            media_url=media_url,
        )
    except GBPPostPublicationContractError as exc:
        publication.status = "failed"
        publication.safe_error_code = exc.safe_code
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error=exc.safe_code)

    location_name = v4_localposts_parent(
        gbp_account.external_account_id, gbp_location.external_location_id
    )
    provider_post_id = publication.provider_post_id

    # No database transaction may span OAuth or provider network I/O.
    await session.commit()

    try:
        token, _connection = await token_resolver(session, organization_id)
    except IntegrationNotFoundError:
        publication = await session.get(GBPPostPublication, publication_id)
        if publication is not None:
            publication.status = "reserved"
            publication.safe_error_code = "NO_CONNECTED_INTEGRATION"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="NO_CONNECTED_INTEGRATION")
    except IntegrationReconnectRequiredError:
        publication = await session.get(GBPPostPublication, publication_id)
        if publication is not None:
            publication.status = "reserved"
            publication.safe_error_code = "TOKEN_REFRESH_FAILED"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
    except SecretUnavailableError as exc:
        logger.warning(
            "Secret resolution failed in GBP post workflow",
            extra={
                "event_name": "workflow.secret_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        publication = await session.get(GBPPostPublication, publication_id)
        if publication is not None:
            publication.status = "reserved"
            publication.safe_error_code = "SECRET_RESOLUTION_FAILED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="SECRET_RESOLUTION_FAILED")
    except Exception as exc:
        logger.warning(
            "Token resolution failed in GBP post workflow",
            extra={
                "event_name": "workflow.token_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        publication = await session.get(GBPPostPublication, publication_id)
        if publication is not None:
            publication.status = "reserved"
            publication.safe_error_code = "TOKEN_RESOLUTION_FAILED"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_RESOLUTION_FAILED")

    await session.commit()
    adapter = adapter_factory()

    if provider_post_id:
        try:
            re_read = await adapter.get_local_post(token, provider_post_id)
        except Exception as exc:
            publication = await session.get(GBPPostPublication, publication_id)
            if publication is not None:
                publication.status = "reconciliation_required"
                publication.safe_error_code = "VERIFICATION_REREAD_FAILED"
            await session.commit()
            logger.warning(
                "GBP post verification re-read failed",
                extra={
                    "event_name": "gbp.publish_post.verification_failed",
                    "publication_id": str(publication_id),
                    "error": str(exc)[:200],
                },
            )
            return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")
        return await _apply_provider_verification(
            session,
            organization_id=organization_id,
            publication_id=publication_id,
            provider_post=re_read,
            revision=revision,
            requirements=requirements,
        )

    publication = await session.scalar(
        select(GBPPostPublication)
        .where(
            GBPPostPublication.organization_id == organization_id,
            GBPPostPublication.id == publication_id,
            GBPPostPublication.status == "reserved",
            GBPPostPublication.dispatched_at.is_(None),
            GBPPostPublication.provider_post_id.is_(None),
        )
        .with_for_update()
    )
    if publication is None:
        await session.rollback()
        return JobOutcome(result="ambiguous", safe_error="PUBLICATION_DISPATCH_CONFLICT")
    publication.status = "dispatched"
    publication.dispatched_at = datetime.now(UTC)
    publication.safe_error_code = None
    await session.commit()

    try:
        created = await adapter.create_local_post(token, location_name, post_body)
    except Exception as exc:
        publication = await session.get(GBPPostPublication, publication_id)
        if publication is not None:
            publication.status = "reconciliation_required"
            publication.safe_error_code = "PROVIDER_WRITE_AMBIGUOUS"
        await session.commit()
        logger.warning(
            "GBP post creation failed",
            extra={
                "event_name": "gbp.publish_post.failed",
                "publication_id": str(publication_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="ambiguous", safe_error="PROVIDER_WRITE_AMBIGUOUS")

    provider_post_name = str(created.get("name", ""))
    if not provider_post_name:
        publication = await session.get(GBPPostPublication, publication_id)
        if publication is not None:
            publication.status = "reconciliation_required"
            publication.safe_error_code = "PROVIDER_RETURNED_NO_RESOURCE_NAME"
        await session.commit()
        return JobOutcome(result="ambiguous", safe_error="PROVIDER_RETURNED_NO_RESOURCE_NAME")

    publication = await session.scalar(
        select(GBPPostPublication)
        .where(
            GBPPostPublication.organization_id == organization_id,
            GBPPostPublication.id == publication_id,
        )
        .with_for_update()
    )
    if publication is None:
        await session.rollback()
        return JobOutcome(result="ambiguous", safe_error="PUBLICATION_LOST_AFTER_DISPATCH")
    if publication.provider_post_id not in (None, provider_post_name):
        publication.status = "reconciliation_required"
        publication.safe_error_code = "PROVIDER_IDENTITY_CONFLICT"
        await session.commit()
        return JobOutcome(result="ambiguous", safe_error="PROVIDER_IDENTITY_CONFLICT")
    publication.provider_post_id = provider_post_name
    publication.safe_error_code = None
    await session.commit()

    try:
        re_read = await adapter.get_local_post(token, provider_post_name)
    except Exception as exc:
        publication = await session.get(GBPPostPublication, publication_id)
        if publication is not None:
            publication.status = "reconciliation_required"
            publication.safe_error_code = "VERIFICATION_REREAD_FAILED"
        await session.commit()
        logger.warning(
            "GBP post verification re-read failed",
            extra={
                "event_name": "gbp.publish_post.verification_failed",
                "publication_id": str(publication_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")

    return await _apply_provider_verification(
        session,
        organization_id=organization_id,
        publication_id=publication_id,
        provider_post=re_read,
        revision=revision,
        requirements=requirements,
    )


async def _apply_provider_verification(
    session: AsyncSession,
    *,
    organization_id: UUID,
    publication_id: UUID,
    provider_post: dict[str, Any],
    revision: GBPPostRevision,
    requirements: GBPPostDeliveryRequirements,
) -> JobOutcome:
    provider_state = str(provider_post.get("state", "")).upper()
    publication = await session.scalar(
        select(GBPPostPublication)
        .where(
            GBPPostPublication.organization_id == organization_id,
            GBPPostPublication.id == publication_id,
        )
        .with_for_update()
    )
    if publication is None:
        await session.rollback()
        return JobOutcome(result="ambiguous", safe_error="PUBLICATION_LOST_AFTER_DISPATCH")

    if provider_state == "REJECTED":
        publication.status = "failed"
        publication.safe_error_code = "POST_REJECTED_BY_PROVIDER"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="POST_REJECTED_BY_PROVIDER")
    if provider_state != "LIVE":
        publication.status = "reconciliation_required"
        publication.safe_error_code = "POST_NOT_YET_LIVE"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="POST_NOT_YET_LIVE")

    mismatch = verify_provider_post(
        provider_post,
        post_type=revision.post_type,
        content=revision.content,
        call_to_action=revision.call_to_action,
        requirements=requirements,
    )
    if mismatch:
        publication.status = "reconciliation_required"
        publication.safe_error_code = mismatch
        await session.commit()
        return JobOutcome(result="ambiguous", safe_error=mismatch)

    publication.status = "verified"
    publication.verified_at = datetime.now(UTC)
    publication.safe_error_code = None
    await session.commit()
    return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
