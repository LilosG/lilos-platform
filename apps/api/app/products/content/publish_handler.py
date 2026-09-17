"""Recoverable end-to-end Content publication workflow.

One approved operator action owns the whole provider lifecycle: create/update the
publication branch, open the pull request, wait for repository checks, merge,
wait for deployment evidence, and only then mark the Content item published.
Every phase is persisted before another external mutation so worker retries are
idempotent rather than duplicate-producing.
"""

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
    _content_publisher_factory,
    _github_token_resolver,
    _provider_writes_enabled,
)
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.content.adapter import RepositoryPublisher
from apps.api.app.products.content.file_format import ContentFileFormatError, build_content_file
from apps.api.app.products.content.frontmatter_contract import (
    FrontmatterContract,
    FrontmatterContractError,
)
from apps.api.app.products.content.models import (
    ContentItem,
    ContentPublication,
    ContentRevision,
    PublishingTarget,
)
from apps.api.app.products.content.service import build_publishable_frontmatter

logger = logging.getLogger(__name__)


async def handle_content_publish(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Advance one Content publication through provider-observed phases."""
    del location_id, correlation_id, workflow_run_id
    publication_id_raw = input_document.get("publication_id")
    if not publication_id_raw:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_PUBLICATION_ID")
    try:
        publication_id = UUID(str(publication_id_raw))
    except (TypeError, ValueError):
        return JobOutcome(result="permanent_failure", safe_error="INVALID_PUBLICATION_ID")

    publication = await session.scalar(
        select(ContentPublication)
        .where(
            ContentPublication.organization_id == organization_id,
            ContentPublication.id == publication_id,
        )
        .with_for_update()
    )
    if publication is None:
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_NOT_FOUND")
    if publication.status == "verified":
        return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
    if publication.status in {"failed", "checks_failed", "rolled_back"}:
        return JobOutcome(
            result="permanent_failure",
            safe_error=publication.safe_error_code or "PUBLICATION_FAILED",
        )
    if not _provider_writes_enabled():
        await _fail(session, publication, "PROVIDER_WRITES_DISABLED")
        return JobOutcome(result="permanent_failure", safe_error="PROVIDER_WRITES_DISABLED")

    target = await session.scalar(
        select(PublishingTarget).where(
            PublishingTarget.organization_id == organization_id,
            PublishingTarget.id == publication.publishing_target_id,
            PublishingTarget.status == "active",
        )
    )
    if target is None:
        await _fail(session, publication, "PUBLISHING_TARGET_NOT_CONFIGURED")
        return JobOutcome(result="permanent_failure", safe_error="PUBLISHING_TARGET_NOT_CONFIGURED")
    connection = await session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.id == target.connection_id,
            IntegrationConnection.status == "connected",
        )
    )
    if connection is None:
        await _fail(session, publication, "GITHUB_CONNECTION_REQUIRED")
        return JobOutcome(result="permanent_failure", safe_error="GITHUB_CONNECTION_REQUIRED")

    try:
        token = str(await _github_token_resolver(session, Settings(), connection))
    except Exception:
        await _fail(session, publication, "GITHUB_CREDENTIAL_REQUIRED")
        return JobOutcome(result="permanent_failure", safe_error="GITHUB_CREDENTIAL_REQUIRED")

    revision = await session.scalar(
        select(ContentRevision).where(
            ContentRevision.organization_id == organization_id,
            ContentRevision.id == publication.content_revision_id,
            ContentRevision.content_item_id == publication.content_item_id,
        )
    )
    item = await session.scalar(
        select(ContentItem)
        .where(
            ContentItem.organization_id == organization_id,
            ContentItem.id == publication.content_item_id,
        )
        .with_for_update()
    )
    if revision is None or item is None:
        await _fail(session, publication, "REVISION_NOT_FOUND")
        return JobOutcome(result="permanent_failure", safe_error="REVISION_NOT_FOUND")

    publisher: RepositoryPublisher = _content_publisher_factory(token)
    repository_id = target.repository_id
    overrides = _safe_overrides(input_document.get("frontmatter_overrides"))

    if publication.status == "reconciliation_required":
        reconciliation = await _reconcile_phase(session, publication, publisher, repository_id)
        if reconciliation is not None:
            return reconciliation

    if publication.status in {"reserved", "branch_created"}:
        preparation = await _prepare_pull_request(
            session,
            publication,
            revision,
            target,
            publisher,
            repository_id,
            overrides,
        )
        if preparation is not None:
            return preparation

    if publication.status in {"pull_request_created", "checks_running"}:
        checks_result = await _wait_for_pull_request_checks(
            session, publication, publisher, repository_id
        )
        if checks_result is not None:
            return checks_result

    if publication.status in {"pull_request_created", "checks_running"}:
        merge_result = await _merge_pull_request(session, publication, publisher, repository_id)
        if merge_result is not None:
            return merge_result

    if publication.status in {"merged", "deployment_pending", "deployed"}:
        return await _verify_deployment(
            session,
            publication,
            revision,
            item,
            publisher,
            repository_id,
        )

    publication.status = "reconciliation_required"
    publication.safe_error_code = "PUBLICATION_STATE_UNRECOGNIZED"
    item.status = "reconciliation_required"
    await session.commit()
    return JobOutcome(result="retryable_failure", safe_error="PUBLICATION_STATE_UNRECOGNIZED")


async def _reconcile_phase(
    session: AsyncSession,
    publication: ContentPublication,
    publisher: RepositoryPublisher,
    repository_id: str,
) -> JobOutcome | None:
    """Recover persisted phase from provider identity after an ambiguous outcome."""
    try:
        if publication.external_pull_request_id:
            pr = await publisher.get_pull_request(
                repository_id, publication.external_pull_request_id
            )
            head = pr.get("head")
            head_sha = str(head.get("sha") or "") if isinstance(head, dict) else ""
            if not publication.approved_head_sha:
                publication.status = "failed"
                publication.safe_error_code = "CONTENT_PR_HEAD_UNPINNED"
                await session.commit()
                return JobOutcome(result="permanent_failure", safe_error="CONTENT_PR_HEAD_UNPINNED")
            if publication.approved_head_sha and head_sha != publication.approved_head_sha:
                publication.status = "failed"
                publication.safe_error_code = "CONTENT_PR_HEAD_CHANGED"
                await session.commit()
                return JobOutcome(result="permanent_failure", safe_error="CONTENT_PR_HEAD_CHANGED")
            if pr.get("state") == "closed" and not bool(pr.get("merged")):
                publication.status = "failed"
                publication.safe_error_code = "CONTENT_PR_CLOSED"
                await session.commit()
                return JobOutcome(result="permanent_failure", safe_error="CONTENT_PR_CLOSED")
            if bool(pr.get("merged")):
                merge_sha = str(pr.get("merge_commit_sha") or "")
                if not merge_sha:
                    raise RuntimeError("merged pull request has no commit SHA")
                publication.external_revision_id = merge_sha
                publication.status = "merged"
            else:
                publication.status = "pull_request_created"
        else:
            publication.status = "branch_created" if publication.branch_name else "reserved"
        publication.safe_error_code = None
        await session.commit()
        return None
    except Exception as exc:
        logger.warning("Content publication phase reconciliation failed", exc_info=exc)
        publication.safe_error_code = "PUBLICATION_PHASE_REREAD_FAILED"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="PUBLICATION_PHASE_REREAD_FAILED")


def _canonical_frontmatter(
    revision: ContentRevision,
    overrides: dict[str, object],
) -> dict[str, object]:
    """Rebuild deterministic metadata for legacy revisions before worker validation.

    The operator preflight accepts legacy approved revisions by deriving the same
    metadata that modern draft generation stores. The worker must reconstruct
    those values identically or it can accept a publication at the API boundary
    and then reject it as incomplete during execution.
    """
    canonical = dict(revision.frontmatter or {})
    title = str(canonical.get("title") or "").strip()
    if title:
        generated = build_publishable_frontmatter(
            title=title,
            ai_output=None,
            body=revision.body,
            publish_date=revision.created_at.date(),
        )
        for key in ("description", "publish_date", "seo_title"):
            existing = canonical.get(key)
            if existing is None or (isinstance(existing, str) and not existing.strip()):
                canonical[key] = generated[key]
    canonical.update(overrides)
    return canonical


async def _prepare_pull_request(
    session: AsyncSession,
    publication: ContentPublication,
    revision: ContentRevision,
    target: PublishingTarget,
    publisher: RepositoryPublisher,
    repository_id: str,
    overrides: dict[str, object],
) -> JobOutcome | None:
    try:
        contract = FrontmatterContract.from_document(target.frontmatter_contract)
        path_rejection = contract.rejects_path(publication.target_path)
        if path_rejection is not None:
            return await _permanent(
                session,
                publication,
                "CONTENT_TARGET_PATH_UNSUPPORTED",
                path_rejection,
            )
        canonical = _canonical_frontmatter(revision, overrides)
        rendered = contract.render(canonical)
        missing = contract.missing_required(rendered)
        if missing:
            return await _permanent(
                session,
                publication,
                "CONTENT_FRONTMATTER_INCOMPLETE",
                f"missing required publishing fields: {', '.join(missing)}",
            )
        file_contents = build_content_file(revision.body, rendered)
    except FrontmatterContractError as exc:
        return await _permanent(session, publication, exc.safe_code, str(exc))
    except ContentFileFormatError as exc:
        return await _permanent(session, publication, exc.safe_code, str(exc))

    branch_name = publication.branch_name or f"lilos-content-{publication.id}"
    try:
        if not publication.base_commit:
            publication.base_commit = await publisher.get_base_commit(
                repository_id, target.base_branch
            )
        await publisher.create_branch(
            repository_id,
            target.base_branch,
            publication.base_commit,
            branch_name,
        )
        publication.branch_name = branch_name
        publication.status = "branch_created"
        await session.commit()

        await publisher.put_file(
            repository_id,
            branch_name,
            publication.target_path,
            file_contents,
            None,
        )
        pr_number = publication.external_pull_request_id or await publisher.create_pull_request(
            repository_id,
            branch_name,
            target.base_branch,
            f"Publish: {publication.target_path}",
            str(publication.idempotency_key),
        )
        pr = await publisher.get_pull_request(repository_id, pr_number)
        head = pr.get("head") if isinstance(pr, dict) else None
        head_sha = str(head.get("sha") or "") if isinstance(head, dict) else ""
        if not head_sha:
            raise RuntimeError("created pull request has no head commit SHA")
        publication.external_pull_request_id = pr_number
        publication.approved_head_sha = head_sha
        publication.external_revision_id = head_sha
        publication.published_url = f"https://github.com/{repository_id}/pull/{pr_number}"
        publication.status = "pull_request_created"
        publication.safe_error_code = None
        await session.commit()
        return None
    except Exception as exc:
        logger.warning("Content publication preparation failed", exc_info=exc)
        publication.status = "reconciliation_required"
        publication.safe_error_code = "PROVIDER_WRITE_AMBIGUOUS"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="PROVIDER_WRITE_AMBIGUOUS")


async def _wait_for_pull_request_checks(
    session: AsyncSession,
    publication: ContentPublication,
    publisher: RepositoryPublisher,
    repository_id: str,
) -> JobOutcome | None:
    if not publication.external_pull_request_id:
        publication.status = "reconciliation_required"
        publication.safe_error_code = "PULL_REQUEST_REFERENCE_MISSING"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="PULL_REQUEST_REFERENCE_MISSING")
    try:
        pr = await publisher.get_pull_request(repository_id, publication.external_pull_request_id)
        head = pr.get("head") if isinstance(pr, dict) else None
        head_sha = str(head.get("sha") or "") if isinstance(head, dict) else ""
        if publication.approved_head_sha and head_sha != publication.approved_head_sha:
            publication.status = "failed"
            publication.safe_error_code = "CONTENT_PR_HEAD_CHANGED"
            await session.commit()
            return JobOutcome(result="permanent_failure", safe_error="CONTENT_PR_HEAD_CHANGED")
        if head_sha and publication.approved_head_sha is None:
            publication.approved_head_sha = head_sha
        if head_sha:
            publication.external_revision_id = head_sha
        if not publication.external_revision_id:
            raise RuntimeError("pull request head SHA is unavailable")
        checks = await publisher.checks(repository_id, publication.external_revision_id)
    except Exception as exc:
        logger.warning("Content check reconciliation failed", exc_info=exc)
        publication.status = "reconciliation_required"
        publication.safe_error_code = "CHECKS_REREAD_FAILED"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="CHECKS_REREAD_FAILED")

    state = checks.get("state", "pending")
    publication.build_status = state
    if state == "failed":
        publication.status = "checks_failed"
        publication.safe_error_code = "CONTENT_CHECKS_FAILED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="CONTENT_CHECKS_FAILED")
    if state in {"pending", "none"}:
        publication.status = "checks_running"
        publication.safe_error_code = "CONTENT_CHECKS_UNAVAILABLE" if state == "none" else None
        await session.commit()
        return JobOutcome(
            result="retryable_failure",
            safe_error="CONTENT_CHECKS_UNAVAILABLE"
            if state == "none"
            else "CONTENT_CHECKS_PENDING",
        )
    publication.status = "pull_request_created"
    publication.safe_error_code = None
    await session.commit()
    return None


async def _merge_pull_request(
    session: AsyncSession,
    publication: ContentPublication,
    publisher: RepositoryPublisher,
    repository_id: str,
) -> JobOutcome | None:
    if not publication.external_pull_request_id:
        return JobOutcome(result="retryable_failure", safe_error="PULL_REQUEST_REFERENCE_MISSING")
    if not publication.approved_head_sha:
        return JobOutcome(result="retryable_failure", safe_error="PULL_REQUEST_HEAD_MISSING")
    try:
        merge_sha = await publisher.merge_pull_request(
            repository_id, publication.external_pull_request_id, publication.approved_head_sha
        )
        publication.external_revision_id = merge_sha
        publication.status = "merged"
        publication.safe_error_code = None
        await session.commit()
        return None
    except Exception as exc:
        logger.warning("Content pull request merge failed", exc_info=exc)
        publication.status = "reconciliation_required"
        publication.safe_error_code = "PULL_REQUEST_MERGE_FAILED"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="PULL_REQUEST_MERGE_FAILED")


async def _verify_deployment(
    session: AsyncSession,
    publication: ContentPublication,
    revision: ContentRevision,
    item: ContentItem,
    publisher: RepositoryPublisher,
    repository_id: str,
) -> JobOutcome:
    revision_id = publication.external_revision_id
    if not revision_id:
        publication.status = "reconciliation_required"
        publication.safe_error_code = "MERGE_REVISION_MISSING"
        item.status = "reconciliation_required"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="MERGE_REVISION_MISSING")
    try:
        deployment = await publisher.deployment(repository_id, revision_id)
        state = deployment.get("state", "none").lower()
        publication.deployment_status = state
        if state in {"success", "active"}:
            return await _mark_published(
                session, publication, revision, item, deployment.get("url")
            )
        if state in {"error", "failure", "inactive"}:
            publication.status = "failed"
            publication.safe_error_code = "CONTENT_DEPLOYMENT_FAILED"
            item.status = "failed"
            await session.commit()
            return JobOutcome(result="permanent_failure", safe_error="CONTENT_DEPLOYMENT_FAILED")

        # A successful CI check can include a preview build or unrelated tests.
        # Only a production deployment bound to this merged commit proves delivery.
        publication.status = "deployment_pending"
        publication.safe_error_code = None
        item.status = "publishing"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="CONTENT_DEPLOYMENT_PENDING")
    except Exception as exc:
        logger.warning("Content deployment verification failed", exc_info=exc)
        publication.status = "reconciliation_required"
        publication.safe_error_code = "DEPLOYMENT_REREAD_FAILED"
        item.status = "reconciliation_required"
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="DEPLOYMENT_REREAD_FAILED")


async def _mark_published(
    session: AsyncSession,
    publication: ContentPublication,
    revision: ContentRevision,
    item: ContentItem,
    deployment_url: str | None,
) -> JobOutcome:
    now = datetime.now(UTC)
    publication.status = "verified"
    publication.verified_at = now
    publication.safe_error_code = None
    if deployment_url:
        publication.published_url = deployment_url
    revision.status = "published"
    item.status = "published"
    item.approved_revision_id = revision.id
    item.publishing_target_id = publication.publishing_target_id
    item.published_at = now
    await session.commit()
    return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")


def _safe_overrides(raw: object) -> dict[str, object]:
    if not isinstance(raw, dict):
        return {}
    allowed = {"image", "image_alt"}
    result: dict[str, object] = {}
    for key in allowed:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


async def _fail(
    session: AsyncSession,
    publication: ContentPublication,
    code: str,
) -> None:
    publication.status = "failed"
    publication.safe_error_code = code
    await session.commit()


async def _permanent(
    session: AsyncSession,
    publication: ContentPublication,
    code: str,
    message: str,
) -> JobOutcome:
    logger.warning(
        "Content publication rejected",
        extra={"publication_id": str(publication.id), "code": code, "reason": message[:200]},
    )
    publication.status = "failed"
    publication.safe_error_code = code
    await session.commit()
    return JobOutcome(result="permanent_failure", safe_error=code)
