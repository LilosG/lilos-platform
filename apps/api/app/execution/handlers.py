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
from apps.api.app.products.gbp.adapter import GBPAdapter, GoogleBusinessProfileAdapter

if TYPE_CHECKING:
    from apps.api.app.config import Settings

logger = logging.getLogger(__name__)

# Adapter factory — production creates the real adapter; tests can override
# via ``handlers._adapter_factory = lambda: FakeAdapter()`` to inject a
# deterministic fake without touching the network.
_adapter_factory: Callable[[], GBPAdapter] = GoogleBusinessProfileAdapter


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

    adapter = _adapter_factory()

    try:
        token, _connection = await _token_resolver(session, organization_id)
    except IntegrationNotFoundError:
        publication.status = "failed"
        publication.safe_error_code = "NO_CONNECTED_INTEGRATION"
        return JobOutcome(result="permanent_failure", safe_error="NO_CONNECTED_INTEGRATION")
    except IntegrationReconnectRequiredError:
        publication.status = "reconciliation_required"
        publication.safe_error_code = "TOKEN_REFRESH_FAILED"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
    except Exception:
        publication.status = "reconciliation_required"
        publication.safe_error_code = "TOKEN_REFRESH_FAILED"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")

    from apps.api.app.products.gbp.models import GBPAccount
    from apps.api.app.products.gbp.resource_names import v1_location_name

    acct = await session.get(GBPAccount, gbp_location.account_id)
    if not acct:
        publication.status = "failed"
        publication.safe_error_code = "ACCOUNT_NOT_FOUND"
        return JobOutcome(result="permanent_failure", safe_error="ACCOUNT_NOT_FOUND")

    # Business Information v1 ``locations.patch`` uses the canonical
    # ``locations/{locationId}`` resource name — NOT account-qualified.
    location_name = v1_location_name(gbp_location.external_location_id)
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
    """Publish an approved GBP Local Post via ``accounts.locations.localPosts.create``.

    Resolves the publication -> revision -> GBP location -> GBP account chain
    (never accepts a provider path from the client), validates that only
    supported post fields are present, calls ``create_local_post`` on the
    adapter, then re-reads the post via ``get_local_post`` to verify the
    provider resource exists.  Idempotent: if the publication already has a
    ``provider_post_id`` (from a prior partial attempt), it re-reads that
    resource instead of creating a duplicate.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select

    from apps.api.app.products.gbp.models import GBPAccount, GBPLocation
    from apps.api.app.products.gbp.operations_models import (
        GBPPostPublication,
        GBPPostRevision,
    )
    from apps.api.app.products.gbp.resource_names import v4_localposts_parent

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

    if not gbp_location.write_enabled or gbp_location.mapping_status != "confirmed":
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="WRITE_NOT_ENABLED")

    gbp_account = await session.get(GBPAccount, gbp_location.account_id)
    if gbp_account is None:
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="GBP_ACCOUNT_NOT_FOUND")

    adapter = _adapter_factory()

    try:
        token, _connection = await _token_resolver(session, organization_id)
    except IntegrationNotFoundError:
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="NO_CONNECTED_INTEGRATION")
    except IntegrationReconnectRequiredError:
        publication.status = "reconciliation_required"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")
    except Exception:
        publication.status = "reconciliation_required"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")

    # Legacy My Business v4 ``accounts.locations.localPosts.create`` requires
    # the account-qualified ``accounts/{accountId}/locations/{locationId}``
    # parent — constructed from the same canonical location identity.
    location_name = v4_localposts_parent(
        gbp_account.external_account_id, gbp_location.external_location_id
    )

    if publication.provider_post_id:
        post_name = publication.provider_post_id
        try:
            re_read = await adapter.get_local_post(token, post_name)
        except Exception as exc:
            publication.status = "reconciliation_required"
            logger.warning(
                "GBP post verification re-read failed",
                extra={
                    "event_name": "gbp.publish_post.verification_failed",
                    "publication_id": str(publication.id),
                    "error": str(exc)[:200],
                },
            )
            return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")
        provider_state = str(re_read.get("state", "")).upper()
        if provider_state == "REJECTED":
            publication.status = "failed"
            return JobOutcome(result="permanent_failure", safe_error="POST_REJECTED_BY_PROVIDER")
        if provider_state == "LIVE":
            publication.status = "verified"
            publication.verified_at = datetime.now(UTC)
            return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
        # PROCESSING and any other non-LIVE, non-REJECTED state means the
        # post is still under provider moderation or in a transitional
        # state. Mark reconciliation_required so a later retry re-reads the
        # same provider resource (provider_post_id is already persisted)
        # without creating a duplicate post.
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
        if revision.post_type == "EVENT":
            post_body["event"] = revision.event_or_offer
        elif revision.post_type == "OFFER":
            post_body["offer"] = revision.event_or_offer

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
    except Exception as exc:
        publication.status = "reconciliation_required"
        logger.warning(
            "GBP post verification re-read failed",
            extra={
                "event_name": "gbp.publish_post.verification_failed",
                "publication_id": str(publication.id),
                "error": str(exc)[:200],
            },
        )
        return JobOutcome(result="retryable_failure", safe_error="VERIFICATION_REREAD_FAILED")

    provider_state = str(re_read.get("state", "")).upper()
    if provider_state == "REJECTED":
        publication.status = "failed"
        return JobOutcome(result="permanent_failure", safe_error="POST_REJECTED_BY_PROVIDER")
    if provider_state == "LIVE":
        publication.status = "verified"
        publication.verified_at = datetime.now(UTC)
        return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
    # PROCESSING and any other non-LIVE, non-REJECTED state means the
    # post is still under provider moderation or in a transitional state.
    # provider_post_id is already persisted, so a later retry re-reads the
    # same provider resource without creating a duplicate post.
    publication.status = "reconciliation_required"
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
    except Exception:
        response.status = "reconciliation_required"
        response.safe_error_code = "TOKEN_REFRESH_FAILED"
        return JobOutcome(result="retryable_failure", safe_error="TOKEN_REFRESH_FAILED")

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
# Register all handlers
# ---------------------------------------------------------------------------


def _register_all() -> None:
    register_workflow_handler("gbp.publish_change", _handle_gbp_publish_change)
    register_workflow_handler("gbp.publish_post", _handle_gbp_publish_post)
    register_workflow_handler("seo.crawl_or_analysis", _handle_seo_crawl)
    register_workflow_handler("content.publish", _handle_content_publish)
    register_workflow_handler("reviews.publish_response", _handle_reviews_publish_response)


_register_all()
