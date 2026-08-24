"""Registered workflow step handlers for product workflows.

Each handler receives the database session, organization/location scope,
and the workflow run's input document, performs the actual product work,
and returns a JobOutcome.  Handlers are registered by workflow definition key
and looked up at execution time by the worker runtime.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.integrations.connection_service import GBPConnectionService
from apps.api.app.integrations.errors import (
    IntegrationNotFoundError,
    IntegrationReconnectRequiredError,
)
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.integrations.secrets import SecretUnavailableError
from apps.api.app.products.gbp.adapter import GBPAdapter, GoogleBusinessProfileAdapter

if TYPE_CHECKING:
    from apps.api.app.config import Settings

logger = logging.getLogger(__name__)

# Adapter factory — production creates the real adapter; tests can override
# via ``handlers._adapter_factory = lambda: FakeAdapter()`` to inject a
# deterministic fake without touching the network.
_adapter_factory: Callable[[], GBPAdapter] = GoogleBusinessProfileAdapter


def _provider_writes_enabled() -> bool:
    """Resolve the environment-wide provider write kill switch at execution time."""
    from apps.api.app.config import Settings

    return Settings().provider_writes_enabled


# Content publisher factory — production builds the real GitHub adapter from a
# resolved access token; tests can override to inject a deterministic fake.
def _production_content_publisher_factory(access_token: str) -> Any:
    from apps.api.app.products.content.github_adapter import GitHubRepositoryPublisher

    return GitHubRepositoryPublisher(access_token=access_token)


_content_publisher_factory: Callable[[str], Any] = _production_content_publisher_factory


# GitHub credential resolver — resolves a short-lived installation access token
# for GitHub-App connections (normal production) or falls back to a stored PAT
# (advanced/developer fallback). Tests can override to bypass real GitHub.
async def _production_github_token_resolver(
    session: AsyncSession, settings: Settings, connection: IntegrationConnection
) -> str:
    import json

    from apps.api.app.integrations.secrets import FernetSecretStore, SecretUnavailableError
    from apps.api.app.products.content.github_app_service import (
        GitHubAppService,
        installation_id_from_reference,
    )

    # Normal production: a GitHub App installation. Mint a short-lived token.
    installation_id = installation_id_from_reference(connection.external_account_reference)
    if installation_id is not None:
        app_service = GitHubAppService()
        token = await app_service.create_installation_token(settings, installation_id)
        return token.token
    # Advanced/developer fallback: a stored PAT.
    if not connection.credential_reference:
        raise SecretUnavailableError("no GitHub credential configured")
    store = FernetSecretStore.create(session, settings)
    raw = await store.get(connection.credential_reference)
    return str(json.loads(raw)["access_token"])


_github_token_resolver: Callable[[AsyncSession, Any, IntegrationConnection], Any] = (
    _production_github_token_resolver
)


# Token resolver — production uses the real GBP connection lifecycle; tests
# can override to bypass real OAuth/secret-store interaction.
# Signature: (session, organization_id) -> (access_token, connection)
async def _production_token_resolver(
    session: AsyncSession, organization_id: UUID
) -> tuple[str, IntegrationConnection]:
    from apps.api.app.config import Settings

    connection_svc = GBPConnectionService()
    connection = await connection_svc.get_connection(session, organization_id)
    token = await connection_svc.ensure_fresh_token(session, Settings(), connection)
    return token, connection


_token_resolver: Callable[[AsyncSession, UUID], Any] = _production_token_resolver


class WorkflowStepHandler(Protocol):
    async def __call__(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        input_document: dict[str, Any],
        correlation_id: str,
        workflow_run_id: UUID,
    ) -> JobOutcome: ...


_REGISTRY: dict[str, WorkflowStepHandler] = {}


def register_workflow_handler(key: str, handler: WorkflowStepHandler) -> None:
    """Register exactly one handler for a workflow definition key.

    Import order must never change production behavior. A second registration
    is therefore a startup/configuration error instead of a silent overwrite.
    """
    existing = _REGISTRY.get(key)
    if existing is not None:
        existing_name = getattr(existing, "__name__", type(existing).__name__)
        raise ValueError(
            f"workflow handler already registered for {key}: {existing.__module__}.{existing_name}"
        )
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
    workflow_run_id: UUID,
) -> JobOutcome:
    """Publish and verify one profile change through recoverable phases."""
    from datetime import UTC, datetime

    from sqlalchemy import select

    from apps.api.app.products.gbp.models import (
        GBPAccount,
        GBPLocation,
        GBPProfileChangeRevision,
        GBPPublication,
    )
    from apps.api.app.products.gbp.resource_names import v1_location_name
    from apps.api.app.products.gbp.service import GBPService

    publication_id_raw = input_document.get("publication_id")
    if not publication_id_raw:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_PUBLICATION_ID")
    try:
        publication_id = UUID(str(publication_id_raw))
    except (TypeError, ValueError):
        return JobOutcome(result="permanent_failure", safe_error="INVALID_PUBLICATION_ID")

    publication = await session.scalar(
        select(GBPPublication)
        .where(
            GBPPublication.organization_id == organization_id,
            GBPPublication.id == publication_id,
        )
        .with_for_update()
    )
    if publication is None:
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_FOUND")
    if publication.workflow_run_id != workflow_run_id:
        return JobOutcome(result="permanent_failure", safe_error="WORKFLOW_SCOPE_MISMATCH")
    if publication.status == "verified":
        return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
    if publication.status not in {"reserved", "dispatched", "reconciliation_required"}:
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_RESERVABLE")
    initial_dispatch = publication.status == "reserved"
    if initial_dispatch and not _provider_writes_enabled():
        publication.status = "failed"
        publication.safe_error_code = "PROVIDER_WRITES_DISABLED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="PROVIDER_WRITES_DISABLED")

    revision = await session.scalar(
        select(GBPProfileChangeRevision).where(
            GBPProfileChangeRevision.organization_id == organization_id,
            GBPProfileChangeRevision.id == publication.change_revision_id,
            GBPProfileChangeRevision.location_id == publication.location_id,
        )
    )
    if revision is None:
        publication.status = "failed"
        publication.safe_error_code = "CHANGE_REVISION_NOT_FOUND"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="CHANGE_REVISION_NOT_FOUND")
    if revision.status != "approved":
        publication.status = "failed"
        publication.safe_error_code = "CHANGE_REVISION_NOT_APPROVED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="CHANGE_REVISION_NOT_APPROVED")

    gbp_location = await session.scalar(
        select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.id == revision.gbp_location_id,
            GBPLocation.location_id == publication.location_id,
        )
    )
    if gbp_location is None:
        publication.status = "failed"
        publication.safe_error_code = "GBP_LOCATION_NOT_FOUND"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")
    if location_id is not None and location_id != publication.location_id:
        publication.status = "failed"
        publication.safe_error_code = "GBP_LOCATION_SCOPE_MISMATCH"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_SCOPE_MISMATCH")
    if not gbp_location.write_enabled or gbp_location.mapping_status != "confirmed":
        publication.status = "failed"
        publication.safe_error_code = "WRITE_NOT_ENABLED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="WRITE_NOT_ENABLED")

    account = await session.get(GBPAccount, gbp_location.account_id)
    if account is None or account.organization_id != organization_id:
        publication.status = "failed"
        publication.safe_error_code = "ACCOUNT_NOT_FOUND"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="ACCOUNT_NOT_FOUND")

    update_fields = dict(revision.desired_fields)
    if not update_fields:
        publication.status = "failed"
        publication.safe_error_code = "NO_FIELDS_TO_UPDATE"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="NO_FIELDS_TO_UPDATE")
    location_name = v1_location_name(gbp_location.external_location_id)
    update_mask = [str(field) for field in publication.update_mask]
    idempotency_key = str(publication.idempotency_key)
    gbp_location_id = gbp_location.id

    # Make validation durable and release all locks before OAuth/provider I/O.
    await session.commit()

    try:
        token, _connection = await _token_resolver(session, organization_id)
    except IntegrationNotFoundError:
        publication = await session.get(GBPPublication, publication_id)
        if publication is not None:
            publication.status = "failed"
            publication.safe_error_code = "NO_CONNECTED_INTEGRATION"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="NO_CONNECTED_INTEGRATION")
    except IntegrationReconnectRequiredError:
        publication = await session.get(GBPPublication, publication_id)
        if publication is not None:
            publication.status = "reconciliation_required"
            publication.safe_error_code = "TOKEN_REFRESH_FAILED"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
    except SecretUnavailableError as exc:
        logger.warning(
            "Secret resolution failed in workflow handler",
            extra={
                "event_name": "workflow.secret_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        publication = await session.get(GBPPublication, publication_id)
        if publication is not None:
            publication.status = "reconciliation_required"
            publication.safe_error_code = "SECRET_RESOLUTION_FAILED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="SECRET_RESOLUTION_FAILED")
    except Exception as exc:
        logger.warning(
            "Token resolution failed in workflow handler",
            extra={
                "event_name": "workflow.token_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        publication = await session.get(GBPPublication, publication_id)
        if publication is not None:
            publication.status = "reconciliation_required"
            publication.safe_error_code = "TOKEN_RESOLUTION_FAILED"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_RESOLUTION_FAILED")
    # Token refresh may have written connection state. End that transaction
    # before touching Google.
    await session.commit()
    adapter = _adapter_factory()

    if initial_dispatch:
        publication = await session.scalar(
            select(GBPPublication)
            .where(
                GBPPublication.organization_id == organization_id,
                GBPPublication.id == publication_id,
                GBPPublication.status == "reserved",
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
            await adapter.patch_location(
                token,
                location_name,
                update_fields,
                update_mask,
                idempotency_key,
            )
        except Exception as exc:
            publication = await session.get(GBPPublication, publication_id)
            if publication is not None:
                publication.status = "reconciliation_required"
                publication.safe_error_code = "PROVIDER_WRITE_AMBIGUOUS"
            await session.commit()
            logger.warning(
                "GBP publish result is ambiguous",
                extra={
                    "event_name": "gbp.publish.failed",
                    "publication_id": str(publication_id),
                    "error": str(exc)[:200],
                },
            )
            return JobOutcome(result="ambiguous", safe_error="PROVIDER_WRITE_AMBIGUOUS")

    try:
        raw = await adapter.get_location(token, location_name)
    except Exception as exc:
        publication = await session.get(GBPPublication, publication_id)
        if publication is not None:
            publication.status = "reconciliation_required"
            publication.safe_error_code = "VERIFICATION_REREAD_FAILED"
        await session.commit()
        logger.warning(
            "GBP publish verification re-read failed",
            extra={
                "event_name": "gbp.publish.verification_failed",
                "publication_id": str(publication_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")

    def provider_value(field: str) -> object:
        current: object = raw
        for part in field.split("."):
            if not isinstance(current, dict) or part not in current:
                return None
            current = current[part]
        return current

    verified = all(provider_value(field) == value for field, value in update_fields.items())
    gbp_location = await session.scalar(
        select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.id == gbp_location_id,
        )
    )
    if gbp_location is None:
        await session.rollback()
        return JobOutcome(result="ambiguous", safe_error="GBP_LOCATION_LOST_AFTER_DISPATCH")
    await GBPService().store_snapshot(session, gbp_location, raw, partial=False)
    publication = await session.scalar(
        select(GBPPublication)
        .where(
            GBPPublication.organization_id == organization_id,
            GBPPublication.id == publication_id,
        )
        .with_for_update()
    )
    if publication is None:
        await session.rollback()
        return JobOutcome(result="ambiguous", safe_error="PUBLICATION_LOST_AFTER_DISPATCH")
    if not verified:
        publication.status = "reconciliation_required"
        publication.safe_error_code = "VERIFICATION_CONTENT_MISMATCH"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_CONTENT_MISMATCH")
    publication.status = "verified"
    publication.verified_at = datetime.now(UTC)
    publication.provider_operation_reference = location_name
    publication.safe_error_code = None
    await session.commit()

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
    workflow_run_id: UUID,
) -> JobOutcome:
    """Publish one approved GBP post through committed, recoverable phases.

    The publication reservation, immutable provider payload, and OAuth token
    are validated before dispatch. The durable ``dispatched_at`` boundary is
    committed immediately before Google I/O, provider identity is committed
    before verification, and every later retry re-reads the same provider
    resource. An interrupted dispatch with no provider identity is treated as
    ambiguous and requires reconciliation; it is never blindly repeated.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from apps.api.app.config import Settings
    from apps.api.app.integrations.google_drive_media import DriveImage, GoogleDriveMediaService
    from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
    from apps.api.app.products.gbp.operations_models import (
        GBPPostPublication,
        GBPPostRevision,
    )
    from apps.api.app.products.gbp.post_generation_models import GBPPostAsset
    from apps.api.app.products.gbp.resource_names import v4_localposts_parent

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

    if initial_dispatch and not _provider_writes_enabled():
        publication.status = "failed"
        publication.safe_error_code = "PROVIDER_WRITES_DISABLED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="PROVIDER_WRITES_DISABLED")

    post_type = revision.post_type.upper()
    if post_type not in {"STANDARD", "EVENT", "OFFER"}:
        publication.status = "failed"
        publication.safe_error_code = "POST_TYPE_UNSUPPORTED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="POST_TYPE_UNSUPPORTED")

    post_body: dict[str, Any] = {
        "languageCode": "en-US",
        "postType": post_type,
        "text": revision.content,
    }
    if revision.call_to_action:
        action_type = str(revision.call_to_action.get("actionType", "")).upper()
        if action_type not in {"BOOK", "ORDER", "SHOP", "LEARN_MORE", "SIGN_UP", "CALL", "MENU"}:
            publication.status = "failed"
            publication.safe_error_code = "POST_CTA_UNSUPPORTED"
            await session.commit()
            return JobOutcome(result="permanent_failure", safe_error="POST_CTA_UNSUPPORTED")
        post_body["callToAction"] = {**revision.call_to_action, "actionType": action_type}
    if revision.event_or_offer:
        if post_type == "EVENT":
            post_body["event"] = revision.event_or_offer
        elif post_type == "OFFER":
            post_body["offer"] = revision.event_or_offer

    selected_asset = await session.scalar(
        select(GBPPostAsset).where(
            GBPPostAsset.organization_id == organization_id,
            GBPPostAsset.post_revision_id == revision.id,
            GBPPostAsset.status == "selected",
        )
    )
    if selected_asset is not None and selected_asset.source_type == "google_drive":
        metadata = selected_asset.metadata_document or {}
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
                selected_asset.provider_fetch_url = fresh_url
                post_body["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": fresh_url}]

    location_name = v4_localposts_parent(
        gbp_account.external_account_id, gbp_location.external_location_id
    )
    provider_post_id = publication.provider_post_id

    # Release all validation locks before OAuth/provider work. The runtime also
    # commits its workflow transition before invoking the handler.
    await session.commit()

    try:
        token, _connection = await _token_resolver(session, organization_id)
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
            "Secret resolution failed in workflow handler",
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
            "Token resolution failed in workflow handler",
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

    # Token refresh may have persisted connection/audit state. Commit it before
    # the Local Post provider call so no database transaction spans that I/O.
    await session.commit()
    adapter = _adapter_factory()

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
        provider_state = str(re_read.get("state", "")).upper()
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
        if provider_state == "LIVE":
            publication.status = "verified"
            publication.verified_at = datetime.now(UTC)
            publication.safe_error_code = None
            await session.commit()
            return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
        # PROCESSING and any other non-LIVE, non-REJECTED state means the
        # post is still under provider moderation or in a transitional
        # state. Mark reconciliation_required so a later retry re-reads the
        # same provider resource (provider_post_id is already persisted)
        # without creating a duplicate post.
        publication.status = "reconciliation_required"
        publication.safe_error_code = "POST_NOT_YET_LIVE"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="POST_NOT_YET_LIVE")

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

    provider_state = str(re_read.get("state", "")).upper()
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
    if provider_state == "LIVE":
        publication.status = "verified"
        publication.verified_at = datetime.now(UTC)
        publication.safe_error_code = None
        await session.commit()
        return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
    # PROCESSING and any other non-LIVE, non-REJECTED state means the
    # post is still under provider moderation or in a transitional state.
    # provider_post_id is already persisted, so a later retry re-reads the
    # same provider resource without creating a duplicate post.
    publication.status = "reconciliation_required"
    publication.safe_error_code = "POST_NOT_YET_LIVE"
    await session.commit()
    return JobOutcome(result="retryable_failure", safe_error="POST_NOT_YET_LIVE")


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
    workflow_run_id: UUID,
) -> JobOutcome:
    """Execute a bounded SEO crawl using the existing SEOService crawl engine."""
    from uuid import UUID as _UUID

    from apps.api.app.products.seo.service import SEOService

    crawl_run_id_str = input_document.get("crawl_run_id")
    if not crawl_run_id_str:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_CRAWL_RUN_ID")

    seo_service = SEOService()
    try:
        await seo_service.execute_crawl(
            session,
            organization_id,
            _UUID(str(crawl_run_id_str)),
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.warning(
            "SEO crawl failed",
            extra={
                "event_name": "seo.crawl.failed",
                "crawl_run_id": str(crawl_run_id_str),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="CRAWL_FAILED")

    return JobOutcome(result="succeeded", result_reference=f"crawl_run:{crawl_run_id_str}")


# ---------------------------------------------------------------------------
# Content AI draft revision handler
# ---------------------------------------------------------------------------


async def _handle_content_draft_revision(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Generate an AI-assisted content draft as a durable workflow step.

    Resolves the content item and brief, validates governed business facts,
    calls the AI provider through the shared gateway, persists the
    AIExecution and ContentRevision, and returns the revision for human
    editorial review.

    This handler converts what was previously a synchronous HTTP-bound
    operation into a background workflow so long-running AI generation
    does not cause browser timeouts or false failures.
    """
    from apps.api.app.products.content.service import ContentService

    item_id_raw = input_document.get("item_id")
    brief_id_raw = input_document.get("brief_id")
    idempotency_key_raw = input_document.get("idempotency_key")
    user_id_raw = input_document.get("user_id")

    if not item_id_raw:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_ITEM_ID")
    if not brief_id_raw:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_BRIEF_ID")
    if not idempotency_key_raw:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_IDEMPOTENCY_KEY")

    try:
        item_id = UUID(str(item_id_raw))
        brief_id = UUID(str(brief_id_raw))
        user_id = UUID(str(user_id_raw)) if user_id_raw else None
    except (ValueError, TypeError):
        return JobOutcome(result="permanent_failure", safe_error="INVALID_UUID")

    content_service = ContentService()
    try:
        revision, execution = await content_service.execute_ai_draft_workflow(
            session,
            organization_id=organization_id,
            item_id=item_id,
            brief_id=brief_id,
            idempotency_key=str(idempotency_key_raw),
            workflow_run_id=workflow_run_id,
            user_id=user_id,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.warning(
            "Content AI draft generation failed",
            extra={
                "event_name": "content.draft_revision.failed",
                "organization_id": str(organization_id),
                "item_id": str(item_id),
                "brief_id": str(brief_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(
            result="retryable_failure",
            safe_error="AI_DRAFT_FAILED",
        )

    return JobOutcome(
        result="succeeded",
        result_reference=f"revision:{revision.id}",
    )


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
    workflow_run_id: UUID,
) -> JobOutcome:
    """Publish governed content to a configured GitHub publishing target.

    Resolves the publication -> approved revision -> publishing target ->
    integration connection chain (never accepts a provider path from the
    client), reads the stored GitHub access token through the existing
    credential store, calls the real ``GitHubRepositoryPublisher`` adapter
    (branch -> put file -> pull request), persists the provider references,
    and verifies by re-reading the pull request.  The publication reservation,
    approval, audit, and idempotency controls are preserved upstream by
    ``ContentService.reserve_publication``.

    If the GitHub connection or its credential is not configured, the handler
    fails with a clear external-blocker error code so the operator sees the one
    genuine remaining dependency rather than a fabricated failure.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from apps.api.app.products.content.adapter import RepositoryPublisher
    from apps.api.app.products.content.models import (
        ContentPublication,
        ContentRevision,
        PublishingTarget,
    )

    del location_id
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
    if publication.status not in ("reserved", "branch_created", "pull_request_created"):
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_RESERVABLE")
    if not _provider_writes_enabled():
        publication.status = "failed"
        publication.safe_error_code = "PROVIDER_WRITES_DISABLED"
        return JobOutcome(result="permanent_failure", safe_error="PROVIDER_WRITES_DISABLED")

    target = await session.scalar(
        select(PublishingTarget).where(
            PublishingTarget.organization_id == organization_id,
            PublishingTarget.id == publication.publishing_target_id,
            PublishingTarget.status == "active",
        )
    )
    if target is None:
        publication.status = "failed"
        publication.safe_error_code = "PUBLISHING_TARGET_NOT_CONFIGURED"
        return JobOutcome(result="permanent_failure", safe_error="PUBLISHING_TARGET_NOT_CONFIGURED")

    connection = await session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.id == target.connection_id,
        )
    )
    if connection is None or connection.status != "connected":
        publication.status = "failed"
        publication.safe_error_code = "GITHUB_CONNECTION_REQUIRED"
        return JobOutcome(result="permanent_failure", safe_error="GITHUB_CONNECTION_REQUIRED")

    # A GitHub App installation stores no long-lived credential; a PAT
    # fallback stores one in the secret store. The resolver handles both.
    if not connection.credential_reference and not (
        connection.external_account_reference
        and connection.external_account_reference.startswith("installation:")
    ):
        publication.status = "failed"
        publication.safe_error_code = "GITHUB_CREDENTIAL_REQUIRED"
        return JobOutcome(result="permanent_failure", safe_error="GITHUB_CREDENTIAL_REQUIRED")

    from apps.api.app.config import Settings

    try:
        token = str(await _github_token_resolver(session, Settings(), connection))
    except Exception:
        publication.status = "failed"
        publication.safe_error_code = "GITHUB_CREDENTIAL_REQUIRED"
        return JobOutcome(result="permanent_failure", safe_error="GITHUB_CREDENTIAL_REQUIRED")

    revision = await session.get(ContentRevision, publication.content_revision_id)
    if revision is None:
        publication.status = "failed"
        publication.safe_error_code = "REVISION_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="REVISION_NOT_FOUND")

    publisher: RepositoryPublisher = _content_publisher_factory(token)
    repo = target.repository_id
    branch_name = f"lilos-content-{publication.id}"

    try:
        if not publication.base_commit:
            base_commit = await publisher.get_base_commit(repo, target.base_branch)
            publication.base_commit = base_commit
        base_commit = publication.base_commit
        await publisher.create_branch(repo, target.base_branch, base_commit, branch_name)
        publication.branch_name = branch_name
        publication.status = "branch_created"
        await publisher.put_file(repo, branch_name, publication.target_path, revision.body, None)
        pr_number = await publisher.create_pull_request(
            repo,
            branch_name,
            target.base_branch,
            f"Publish: {publication.target_path}",
            str(publication.idempotency_key),
        )
        publication.external_pull_request_id = pr_number
        publication.external_revision_id = pr_number
        publication.published_url = f"https://github.com/{repo}/pull/{pr_number}"
        publication.status = "pull_request_created"
    except Exception as exc:
        publication.status = "failed"
        publication.safe_error_code = "PROVIDER_WRITE_FAILED"
        logger.warning(
            "Content publish failed",
            extra={
                "event_name": "content.publish.failed",
                "publication_id": str(publication.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="PROVIDER_WRITE_FAILED")

    try:
        pr = await publisher.get_pull_request(repo, pr_number)
        if pr.get("number") is not None:
            publication.status = "verified"
            publication.verified_at = datetime.now(UTC)
            return JobOutcome(
                result="succeeded",
                result_reference=f"publication:{publication.id}",
            )
    except Exception as exc:
        publication.status = "reconciliation_required"
        publication.safe_error_code = "VERIFICATION_REREAD_FAILED"
        logger.warning(
            "Content publish verification re-read failed",
            extra={
                "event_name": "content.publish.verification_failed",
                "publication_id": str(publication.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")

    publication.status = "reconciliation_required"
    return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")


# ---------------------------------------------------------------------------
# Reviews publish-response handler
# ---------------------------------------------------------------------------


async def _handle_reviews_publish_response(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Publish an approved review response to Google via updateReply.

    Resolves the governed review -> provider-resource-mapping -> GBP
    account/location chain (never accepts a provider path from the client),
    refreshes the access token through the existing connection lifecycle,
    calls ``update_review_reply`` on the GBP adapter, then re-reads the
    review and verifies the returned reply matches the approved response
    before marking ``published``.  Ambiguous provider outcomes mark
    ``reconciliation_required``.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from apps.api.app.integrations.models import ProviderResourceMapping
    from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
    from apps.api.app.products.gbp.resource_names import v4_review_name
    from apps.api.app.products.reviews.models import Review, ReviewResponseRevision

    response_id = input_document.get("response_id")
    if not response_id:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_RESPONSE_ID")

    response = await session.scalar(
        select(ReviewResponseRevision)
        .where(
            ReviewResponseRevision.organization_id == organization_id,
            ReviewResponseRevision.id == UUID(str(response_id)),
        )
        .with_for_update()
    )
    if response is None:
        return JobOutcome(result="permanent_failure", safe_error="RESPONSE_NOT_FOUND")

    if response.status == "published":
        return JobOutcome(result="succeeded", result_reference=f"response:{response.id}")
    if response.status != "publishing":
        return JobOutcome(result="permanent_failure", safe_error="RESPONSE_NOT_PUBLISHING")
    if not _provider_writes_enabled():
        response.status = "failed"
        response.safe_error_code = "PROVIDER_WRITES_DISABLED"
        return JobOutcome(result="permanent_failure", safe_error="PROVIDER_WRITES_DISABLED")

    review = await session.scalar(
        select(Review).where(
            Review.organization_id == organization_id,
            Review.id == response.review_id,
        )
    )
    if review is None:
        response.status = "failed"
        response.safe_error_code = "REVIEW_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="REVIEW_NOT_FOUND")

    resource_mapping = await session.scalar(
        select(ProviderResourceMapping).where(
            ProviderResourceMapping.organization_id == organization_id,
            ProviderResourceMapping.id == review.integration_resource_id,
            ProviderResourceMapping.status == "active",
        )
    )
    if resource_mapping is None:
        response.status = "failed"
        response.safe_error_code = "PROVIDER_MAPPING_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="PROVIDER_MAPPING_NOT_FOUND")

    gbp_location = await session.scalar(
        select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.integration_resource_id == resource_mapping.id,
        )
    )
    if gbp_location is None:
        response.status = "failed"
        response.safe_error_code = "GBP_LOCATION_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")

    gbp_account = await session.get(GBPAccount, gbp_location.account_id)
    if gbp_account is None:
        response.status = "failed"
        response.safe_error_code = "GBP_ACCOUNT_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="GBP_ACCOUNT_NOT_FOUND")

    adapter = _adapter_factory()

    try:
        token, _connection = await _token_resolver(session, organization_id)
    except IntegrationNotFoundError:
        response.status = "failed"
        response.safe_error_code = "NO_CONNECTED_INTEGRATION"
        return JobOutcome(result="permanent_failure", safe_error="NO_CONNECTED_INTEGRATION")
    except IntegrationReconnectRequiredError:
        response.status = "reconciliation_required"
        response.safe_error_code = "TOKEN_REFRESH_FAILED"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
    except SecretUnavailableError as exc:
        logger.warning(
            "Secret resolution failed in workflow handler",
            extra={
                "event_name": "workflow.secret_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        response.status = "reconciliation_required"
        response.safe_error_code = "SECRET_RESOLUTION_FAILED"
        return JobOutcome(result="permanent_failure", safe_error="SECRET_RESOLUTION_FAILED")
    except Exception as exc:
        logger.warning(
            "Token resolution failed in workflow handler",
            extra={
                "event_name": "workflow.token_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        response.status = "reconciliation_required"
        response.safe_error_code = "TOKEN_RESOLUTION_FAILED"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_RESOLUTION_FAILED")

    # Legacy My Business v4 ``accounts.locations.reviews`` requires the
    # account-qualified review resource name, constructed from the same
    # canonical location identity.
    review_name = v4_review_name(
        gbp_account.external_account_id,
        gbp_location.external_location_id,
        review.external_review_id,
    )

    approved_comment = response.response_text

    try:
        await adapter.update_review_reply(token, review_name, approved_comment)
    except Exception as exc:
        response.status = "failed"
        response.safe_error_code = "PROVIDER_WRITE_FAILED"
        logger.warning(
            "Review reply publication failed",
            extra={
                "event_name": "reviews.publish.failed",
                "response_id": str(response.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="PROVIDER_WRITE_FAILED")

    try:
        re_read = await adapter.get_review(token, review_name)
    except Exception as exc:
        response.status = "reconciliation_required"
        response.safe_error_code = "VERIFICATION_REREAD_FAILED"
        logger.warning(
            "Review reply verification re-read failed",
            extra={
                "event_name": "reviews.publish.verification_failed",
                "response_id": str(response.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")

    reply = re_read.get("reviewReply") or {}
    provider_comment = str(reply.get("comment", "")).strip()
    if not provider_comment or provider_comment != approved_comment.strip():
        response.status = "reconciliation_required"
        response.safe_error_code = "VERIFICATION_CONTENT_MISMATCH"
        logger.warning(
            "Review reply verification mismatch",
            extra={
                "event_name": "reviews.publish.mismatch",
                "response_id": str(response.id),
            },
        )
        return JobOutcome(result="permanent_failure", safe_error="VERIFICATION_CONTENT_MISMATCH")

    response.status = "published"
    response.external_response_id = review_name
    response.published_at = datetime.now(UTC)

    return JobOutcome(
        result="succeeded",
        result_reference=f"response:{response.id}",
    )


# ---------------------------------------------------------------------------
# GBP upload-media handler
# ---------------------------------------------------------------------------


async def _handle_gbp_upload_media(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Upload an approved GBP media item via the GBP adapter.

    Resolves the media record, reads a fresh access token, calls the
    adapter's create_media, verifies by re-reading, and updates the status.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
    from apps.api.app.products.gbp.operations_models import GBPMedia
    from apps.api.app.products.gbp.resource_names import v4_location_parent

    media_id_raw = input_document.get("media_id")
    if not media_id_raw:
        return JobOutcome(result="permanent_failure", safe_error="MEDIA_ID_MISSING")

    try:
        media_id = UUID(str(media_id_raw))
    except (ValueError, TypeError):
        return JobOutcome(result="permanent_failure", safe_error="MEDIA_ID_INVALID")

    if not _provider_writes_enabled():
        return JobOutcome(result="permanent_failure", safe_error="PROVIDER_WRITES_DISABLED")

    media = await session.scalar(
        select(GBPMedia).where(
            GBPMedia.organization_id == organization_id,
            GBPMedia.id == media_id,
        )
    )
    if not media:
        return JobOutcome(result="permanent_failure", safe_error="MEDIA_NOT_FOUND")

    if media.status != "publishing":
        return JobOutcome(result="permanent_failure", safe_error="MEDIA_NOT_PUBLISHING")

    if media.provider_media_id:
        adapter = _adapter_factory()
        try:
            token, _ = await _token_resolver(session, organization_id)
            re_read = await adapter.get_media(token, media.provider_media_id)
            state = str(re_read.get("state", "")).upper()
            if state == "VERIFIED":
                media.status = "verified"
                media.verified_at = datetime.now(UTC)
                return JobOutcome(
                    result="succeeded",
                    result_reference=f"media:{media.id}",
                )
            return JobOutcome(
                result="retryable_failure",
                safe_error=f"MEDIA_PROVIDER_STATE_{state}",
            )
        except Exception:
            return JobOutcome(
                result="retryable_failure",
                safe_error="MEDIA_VERIFICATION_FAILED",
            )

    location = await session.scalar(
        select(GBPLocation).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.id == media.gbp_location_id,
        )
    )
    if not location:
        media.status = "failed"
        media.safe_error_code = "LOCATION_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="LOCATION_NOT_FOUND")

    if not location.write_enabled or location.mapping_status != "confirmed":
        media.status = "failed"
        media.safe_error_code = "LOCATION_NOT_WRITE_ENABLED"
        return JobOutcome(result="permanent_failure", safe_error="LOCATION_NOT_WRITE_ENABLED")

    account = await session.get(GBPAccount, location.account_id)
    if not account:
        media.status = "failed"
        media.safe_error_code = "ACCOUNT_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="ACCOUNT_NOT_FOUND")

    try:
        token, _ = await _token_resolver(session, organization_id)
    except IntegrationNotFoundError:
        media.status = "failed"
        media.safe_error_code = "INTEGRATION_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="GBP_INTEGRATION_NOT_FOUND")
    except IntegrationReconnectRequiredError:
        media.status = "failed"
        media.safe_error_code = "TOKEN_REFRESH_FAILED"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
    except SecretUnavailableError as exc:
        logger.warning(
            "Secret resolution failed in workflow handler",
            extra={
                "event_name": "workflow.secret_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        media.status = "failed"
        media.safe_error_code = "SECRET_RESOLUTION_FAILED"
        return JobOutcome(result="permanent_failure", safe_error="SECRET_RESOLUTION_FAILED")
    except Exception as exc:
        logger.warning(
            "Token resolution failed in workflow handler",
            extra={
                "event_name": "workflow.token_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        media.status = "failed"
        media.safe_error_code = "TOKEN_RESOLUTION_FAILED"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_RESOLUTION_FAILED")

    adapter = _adapter_factory()
    location_name = v4_location_parent(account.external_account_id, location.external_location_id)

    media_item: dict[str, Any] = {
        "mediaFormat": "PHOTO",
        "locationAssociation": {"category": "ADDITIONAL"},
        "sourceUrl": media.source_reference,
    }
    if media.media_type == "video":
        media_item["mediaFormat"] = "VIDEO"
    elif media.media_type == "cover":
        media_item["locationAssociation"] = {"category": "COVER"}
    elif media.media_type == "logo":
        media_item["locationAssociation"] = {"category": "LOGO"}

    try:
        result = await adapter.create_media(token, location_name, media_item)
    except Exception as exc:
        media.status = "failed"
        media.safe_error_code = "PROVIDER_WRITE_FAILED"
        logger.warning(
            "GBP media upload failed",
            extra={
                "event_name": "gbp.media.upload_failed",
                "media_id": str(media.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="PROVIDER_WRITE_FAILED")

    google_media_name = str(result.get("name", ""))
    if not google_media_name:
        media.status = "failed"
        media.safe_error_code = "PROVIDER_MEDIA_ID_MISSING"
        return JobOutcome(result="retryable_failure", safe_error="PROVIDER_MEDIA_ID_MISSING")

    media.provider_media_id = google_media_name

    try:
        re_read = await adapter.get_media(token, google_media_name)
    except Exception as exc:
        media.status = "reconciliation_required"
        media.safe_error_code = "VERIFICATION_REREAD_FAILED"
        logger.warning(
            "GBP media verification re-read failed",
            extra={
                "event_name": "gbp.media.verification_failed",
                "media_id": str(media.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")

    provider_state = str(re_read.get("state", "")).upper()
    if provider_state == "VERIFIED":
        media.status = "verified"
        media.verified_at = datetime.now(UTC)
        return JobOutcome(
            result="succeeded",
            result_reference=f"media:{media.id}",
        )
    elif provider_state == "REJECTED":
        media.status = "failed"
        media.safe_error_code = "MEDIA_REJECTED_BY_PROVIDER"
        return JobOutcome(result="permanent_failure", safe_error="MEDIA_REJECTED_BY_PROVIDER")

    media.status = "reconciliation_required"
    media.safe_error_code = f"MEDIA_PROVIDER_STATE_{provider_state}"
    safe_error = f"MEDIA_PROVIDER_STATE_{provider_state}"
    return JobOutcome(result="retryable_failure", safe_error=safe_error)


# ---------------------------------------------------------------------------
# Leads send-communication handler
# ---------------------------------------------------------------------------


async def _handle_leads_send_communication(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Dispatch a planned lead communication through the notification system.

    Resolves the communication record, validates it is planned, creates a
    notification event and delivery, and transitions the communication to
    ``queued`` (queued for provider dispatch). The communication is not
    marked ``sent`` until a durable notification delivery job actually
    dispatches it to the provider. If no provider dispatch implementation
    is active, the communication remains ``queued`` — a truthful
    representation of pending delivery.

    IMPORTANT: Setting ``status = "queued"`` rather than ``"sent"`` is a
    deliberate semantic correction. Previously this handler claimed the
    communication was ``sent`` merely because a ``NotificationDelivery``
    row was created. That was incorrect — the delivery had not been
    dispatched to any provider. The platform now truthfully reports the
    communication as ``queued`` until provider dispatch evidence exists.
    See PLATFORM-RELEASE-LEDGER.md § Lead communication status semantics.
    """

    from sqlalchemy import select

    from apps.api.app.notifications.service import NotificationService
    from apps.api.app.products.leads.models import Lead, LeadCommunication

    comm_id_raw = input_document.get("communication_id")
    if not comm_id_raw:
        return JobOutcome(result="permanent_failure", safe_error="COMMUNICATION_ID_MISSING")

    try:
        comm_id = UUID(str(comm_id_raw))
    except (ValueError, TypeError):
        return JobOutcome(result="permanent_failure", safe_error="COMMUNICATION_ID_INVALID")

    communication = await session.scalar(
        select(LeadCommunication).where(
            LeadCommunication.organization_id == organization_id,
            LeadCommunication.id == comm_id,
        )
    )
    if not communication:
        return JobOutcome(result="permanent_failure", safe_error="COMMUNICATION_NOT_FOUND")

    if communication.status == "queued":
        return JobOutcome(
            result="succeeded",
            result_reference=f"communication:{communication.id}",
        )

    if communication.status != "planned":
        return JobOutcome(result="permanent_failure", safe_error="COMMUNICATION_NOT_PLANNED")

    lead = await session.scalar(
        select(Lead).where(
            Lead.organization_id == organization_id,
            Lead.id == communication.lead_id,
        )
    )
    if not lead:
        communication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="LEAD_NOT_FOUND")

    recipient = lead.normalized_email if communication.channel == "email" else lead.normalized_phone
    if not recipient:
        communication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="RECIPIENT_NOT_FOUND")

    notification_svc = NotificationService()

    delivery = None
    try:
        async with session.begin_nested():
            # Ensure the notification template exists (create if missing).
            from apps.api.app.notifications.models import NotificationTemplate

            _TEMPLATE_ID = UUID("00000000-0000-0000-0000-000000000001")
            template = await session.scalar(
                select(NotificationTemplate).where(
                    NotificationTemplate.organization_id == organization_id,
                    NotificationTemplate.id == _TEMPLATE_ID,
                )
            )
            if template is None:
                template = NotificationTemplate(
                    id=_TEMPLATE_ID,
                    organization_id=organization_id,
                    key="leads.communication.send",
                    version=1,
                    channel="email",
                    body_template="A new message has been sent to you.",
                    status="active",
                )
                session.add(template)
                await session.flush()

            event = await notification_svc.create_event(
                session,
                organization_id=organization_id,
                template_id=_TEMPLATE_ID,
                event_type="leads.communication.send",
                idempotency_key=f"lead-comm-{communication.id}",
                context={
                    "lead_id": str(lead.id),
                    "communication_id": str(communication.id),
                    "channel": communication.channel,
                    "message_reference": communication.message_reference,
                },
                location_id=communication.location_id,
            )
            delivery = await notification_svc.add_delivery(
                session,
                event,
                recipient_reference=recipient,
                channel=communication.channel,
            )
    except Exception as exc:
        # The savepoint is already rolled back.  The outer transaction is
        # still clean — the caller's WorkflowRun / Job / audit state is
        # untouched.  We can safely persist the communication failure
        # without poisoning the outer unit-of-work.
        communication.status = "failed"
        await session.flush()
        logger.warning(
            "Lead communication notification failed",
            extra={
                "event_name": "leads.communication.failed",
                "communication_id": str(communication.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(
            result="retryable_failure",
            safe_error="NOTIFICATION_CREATE_FAILED",
        )

    communication.status = "queued"
    communication.notification_delivery_id = delivery.id if delivery else None
    await session.flush()

    return JobOutcome(
        result="succeeded",
        result_reference=f"communication:{communication.id}",
    )


# ---------------------------------------------------------------------------
# Scheduled sync handlers
# ---------------------------------------------------------------------------


async def _handle_gbp_sync(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Scheduled GBP discovery and profile sync.

    Performs a read-only discover-and-sync pass against the Google
    Business Profile provider for the organization. This is a scheduled
    refresh operation — it does not perform writes.

    Resolves a GBP location from ``gbp_location_id`` in the input document
    (product-managed runs) or, for schedule-dispatched runs, from the
    workflow run's platform ``location_id``. The resolved location validates
    that the organization has at least one confirmed GBP location; the
    actual sync operates on the entire organization.
    """
    from uuid import UUID as _UUID

    from sqlalchemy import select

    from apps.api.app.config import Settings
    from apps.api.app.products.gbp.discovery_service import GBPDiscoveryService
    from apps.api.app.products.gbp.models import GBPLocation

    gbp_location_id_raw = input_document.get("gbp_location_id")
    location: GBPLocation | None = None
    if gbp_location_id_raw:
        try:
            gbp_loc_id = _UUID(str(gbp_location_id_raw))
        except (ValueError, TypeError):
            return JobOutcome(result="permanent_failure", safe_error="LOCATION_ID_INVALID")
        location = await session.scalar(
            select(GBPLocation).where(
                GBPLocation.organization_id == organization_id,
                GBPLocation.id == gbp_loc_id,
            )
        )
    elif location_id is not None:
        candidates = (
            await session.scalars(
                select(GBPLocation)
                .where(
                    GBPLocation.organization_id == organization_id,
                    GBPLocation.location_id == location_id,
                )
                .order_by(
                    (GBPLocation.mapping_status == "confirmed").desc(),
                    GBPLocation.created_at.asc(),
                )
            )
        ).all()
        if len(candidates) == 1:
            location = candidates[0]
        elif len(candidates) > 1:
            confirmed = [c for c in candidates if c.mapping_status == "confirmed"]
            if len(confirmed) == 1:
                location = confirmed[0]
            else:
                return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_AMBIGUOUS")
        else:
            return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")
    else:
        return JobOutcome(result="permanent_failure", safe_error="LOCATION_ID_MISSING")

    if not location:
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")

    try:
        token, _ = await _token_resolver(session, organization_id)
    except IntegrationNotFoundError:
        return JobOutcome(result="permanent_failure", safe_error="GBP_INTEGRATION_NOT_FOUND")
    except IntegrationReconnectRequiredError:
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
    except SecretUnavailableError as exc:
        logger.warning(
            "Secret resolution failed in workflow handler",
            extra={
                "event_name": "workflow.secret_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        return JobOutcome(result="permanent_failure", safe_error="SECRET_RESOLUTION_FAILED")
    except Exception as exc:
        logger.warning(
            "Token resolution failed in workflow handler",
            extra={
                "event_name": "workflow.token_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_RESOLUTION_FAILED")

    discovery_svc = GBPDiscoveryService()
    settings = Settings()

    try:
        await discovery_svc.discover_and_sync(
            session,
            settings,
            organization_id,
            actor_id=None,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.warning(
            "Scheduled GBP sync failed",
            extra={
                "event_name": "gbp.sync.failed",
                "organization_id": str(organization_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(
            result="retryable_failure",
            safe_error="GBP_SYNC_FAILED",
        )

    return JobOutcome(
        result="succeeded",
        result_reference=f"gbp-sync:{organization_id}",
    )


async def _handle_reviews_ingest(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Scheduled reviews ingestion for a location.

    Performs a read-only ingest pass against the Google Business
    Profile reviews API for the configured location.

    Resolves the GBP location from ``gbp_location_id`` in the input document
    (product-managed runs) or, for schedule-dispatched runs, from the
    workflow run's platform ``location_id``.
    """
    from uuid import UUID as _UUID

    from sqlalchemy import select

    from apps.api.app.config import Settings
    from apps.api.app.products.gbp.models import GBPLocation
    from apps.api.app.products.reviews.ingestion_service import ReviewIngestionService

    gbp_location_id_raw = input_document.get("gbp_location_id")
    location: GBPLocation | None = None
    if gbp_location_id_raw:
        try:
            gbp_loc_id = _UUID(str(gbp_location_id_raw))
        except (ValueError, TypeError):
            return JobOutcome(result="permanent_failure", safe_error="LOCATION_ID_INVALID")
        location = await session.scalar(
            select(GBPLocation).where(
                GBPLocation.organization_id == organization_id,
                GBPLocation.id == gbp_loc_id,
            )
        )
    elif location_id is not None:
        candidates = (
            await session.scalars(
                select(GBPLocation)
                .where(
                    GBPLocation.organization_id == organization_id,
                    GBPLocation.location_id == location_id,
                )
                .order_by(
                    (GBPLocation.mapping_status == "confirmed").desc(),
                    GBPLocation.created_at.asc(),
                )
            )
        ).all()
        if len(candidates) == 1:
            location = candidates[0]
        elif len(candidates) > 1:
            confirmed = [c for c in candidates if c.mapping_status == "confirmed"]
            if len(confirmed) == 1:
                location = confirmed[0]
            else:
                return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_AMBIGUOUS")
        else:
            return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")
    else:
        return JobOutcome(result="permanent_failure", safe_error="LOCATION_ID_MISSING")

    if not location:
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NOT_FOUND")

    # Resolve the platform location id for the ingest service.
    # ingest_for_location expects a platform location UUID (matching
    # ProviderResourceMapping.platform_resource_id), not a GBPLocation.id.
    platform_location_id = location.location_id
    if platform_location_id is None:
        return JobOutcome(result="permanent_failure", safe_error="GBP_LOCATION_NO_PLATFORM_LINK")

    try:
        _, _ = await _token_resolver(session, organization_id)
    except IntegrationNotFoundError:
        return JobOutcome(result="permanent_failure", safe_error="GBP_INTEGRATION_NOT_FOUND")
    except IntegrationReconnectRequiredError:
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
    except SecretUnavailableError as exc:
        logger.warning(
            "Secret resolution failed in workflow handler",
            extra={
                "event_name": "workflow.secret_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        return JobOutcome(result="permanent_failure", safe_error="SECRET_RESOLUTION_FAILED")
    except Exception as exc:
        logger.warning(
            "Token resolution failed in workflow handler",
            extra={
                "event_name": "workflow.token_resolution_failed",
                "error_type": type(exc).__name__,
                "error_detail": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_RESOLUTION_FAILED")

    try:
        ingestion_svc = ReviewIngestionService()
        await ingestion_svc.ingest_for_location(
            session,
            Settings(),
            organization_id,
            platform_location_id,
            actor_id=None,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        logger.warning(
            "Scheduled reviews ingest failed",
            extra={
                "event_name": "reviews.ingest.failed",
                "organization_id": str(organization_id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(
            result="retryable_failure",
            safe_error="REVIEWS_INGEST_FAILED",
        )

    return JobOutcome(
        result="succeeded",
        result_reference=f"reviews-ingest:{organization_id}",
    )


# ---------------------------------------------------------------------------
# Register all handlers
# ---------------------------------------------------------------------------


def _register_all() -> None:
    register_workflow_handler("gbp.publish_change", _handle_gbp_publish_change)
    register_workflow_handler("gbp.publish_post", _handle_gbp_publish_post)
    register_workflow_handler("gbp.upload_media", _handle_gbp_upload_media)
    register_workflow_handler("content.publish", _handle_content_publish)
    register_workflow_handler("content.draft_revision", _handle_content_draft_revision)
    register_workflow_handler("reviews.publish_response", _handle_reviews_publish_response)
    register_workflow_handler("leads.send_communication", _handle_leads_send_communication)
    register_workflow_handler("gbp.sync", _handle_gbp_sync)
    register_workflow_handler("reviews.ingest", _handle_reviews_ingest)


_register_all()
