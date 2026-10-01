"""Recoverable end-to-end Content publication workflow.

One approved operator action owns the whole provider lifecycle: create/update the
publication branch, open the pull request, wait for repository checks, merge,
wait for deployment evidence, and only then mark the Content item published.
Every phase is persisted before another external mutation so worker retries are
idempotent rather than duplicate-producing.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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


# A repository with no CI and no Vercel preview status yet may simply be slow to
# report; after this long without either, the change is blocked rather than merged.
CHECKS_GRACE_WINDOW = timedelta(minutes=20)

# Builds the exact {repository path: new file text} set a pull request carries, or
# returns a permanent failure. Called once the base commit is pinned.
FileBuilder = Callable[[str], Awaitable["dict[str, str] | JobOutcome"]]
DeploymentFinisher = Callable[[str | None], Awaitable[JobOutcome]]
SubjectStateSetter = Callable[[str], None]


@dataclass(slots=True)
class PublishingContext:
    """Provider access resolved once per worker attempt."""

    target: PublishingTarget
    publisher: RepositoryPublisher
    repository_id: str


@dataclass(slots=True)
class PublicationSubject:
    """What a publication is publishing, as far as the shared phases care.

    Content publications keep their item status in step with the provider
    lifecycle; a site change has no item, so its setter is a no-op. ``finish``
    runs once a production deployment is observed for the merged commit.
    """

    set_state: SubjectStateSetter
    finish: DeploymentFinisher


async def load_publication(
    session: AsyncSession,
    organization_id: UUID,
    raw_publication_id: object,
    *,
    kind: str,
) -> ContentPublication | JobOutcome:
    """Lock the publication this worker attempt owns, or explain why not."""
    if not raw_publication_id:
        return JobOutcome(result="permanent_failure", safe_error="MISSING_PUBLICATION_ID")
    try:
        publication_id = UUID(str(raw_publication_id))
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
    if publication.publication_kind != kind:
        return JobOutcome(result="permanent_failure", safe_error="PUBLICATION_KIND_MISMATCH")
    if publication.status == "verified":
        return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
    if publication.status in {"failed", "checks_failed", "rolled_back"}:
        return JobOutcome(
            result="permanent_failure",
            safe_error=publication.safe_error_code or "PUBLICATION_FAILED",
        )
    return publication


async def load_publishing_context(
    session: AsyncSession,
    organization_id: UUID,
    publication: ContentPublication,
) -> PublishingContext | JobOutcome:
    """Resolve the target, connection and token; fail the publication if any is missing."""
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

    from apps.api.app.staging.write_boundary import ProviderWriteDeniedError, require_github_scope

    settings = Settings()
    try:
        require_github_scope(settings, target.repository_id)
        if (
            settings.environment.value == "staging"
            and target.base_branch != settings.staging_github_base_branch
        ):
            raise ProviderWriteDeniedError("STAGING_GITHUB_BASE_BRANCH_DENIED")
    except ProviderWriteDeniedError as exc:
        await _fail(session, publication, str(exc))
        return JobOutcome(result="permanent_failure", safe_error=str(exc))
    try:
        token = str(await _github_token_resolver(session, Settings(), connection))
    except Exception:
        await _fail(session, publication, "GITHUB_CREDENTIAL_REQUIRED")
        return JobOutcome(result="permanent_failure", safe_error="GITHUB_CREDENTIAL_REQUIRED")

    return PublishingContext(
        target=target,
        publisher=_content_publisher_factory(token),
        repository_id=target.repository_id,
    )


@dataclass(frozen=True, slots=True)
class PullRequestObservation:
    """The provider's pull request state, read without changing anything."""

    state: str  # "open" | "merged" | "closed"
    merge_commit_sha: str | None


class PullRequestUnavailableError(Exception):
    """The pull request could not be read; ``code`` says why, without secrets."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def observe_publication_pull_request(
    session: AsyncSession,
    organization_id: UUID,
    publication: ContentPublication,
) -> PullRequestObservation:
    """Read a publication's pull request state. Unlike `load_publishing_context` this never
    fails the publication, so an operator script can look without side effects.
    """
    if not publication.external_pull_request_id:
        raise PullRequestUnavailableError("PUBLICATION_HAS_NO_PULL_REQUEST")
    target = await session.scalar(
        select(PublishingTarget).where(
            PublishingTarget.organization_id == organization_id,
            PublishingTarget.id == publication.publishing_target_id,
            PublishingTarget.status == "active",
        )
    )
    if target is None:
        raise PullRequestUnavailableError("PUBLISHING_TARGET_NOT_CONFIGURED")
    connection = await session.scalar(
        select(IntegrationConnection).where(
            IntegrationConnection.organization_id == organization_id,
            IntegrationConnection.id == target.connection_id,
            IntegrationConnection.status == "connected",
        )
    )
    if connection is None:
        raise PullRequestUnavailableError("GITHUB_CONNECTION_REQUIRED")
    try:
        token = str(await _github_token_resolver(session, Settings(), connection))
    except Exception as exc:
        raise PullRequestUnavailableError("GITHUB_CREDENTIAL_REQUIRED") from exc
    try:
        pr = await _content_publisher_factory(token).get_pull_request(
            target.repository_id, publication.external_pull_request_id
        )
    except Exception as exc:
        logger.warning("Pull request state lookup failed", exc_info=exc)
        raise PullRequestUnavailableError("PULL_REQUEST_LOOKUP_FAILED") from exc
    if bool(pr.get("merged")):
        return PullRequestObservation("merged", str(pr.get("merge_commit_sha") or "") or None)
    if pr.get("state") == "closed":
        return PullRequestObservation("closed", None)
    return PullRequestObservation("open", None)


async def advance_publication(
    session: AsyncSession,
    publication: ContentPublication,
    context: PublishingContext,
    *,
    build_files: FileBuilder,
    branch_prefix: str,
    pull_request_title: str,
    subject: PublicationSubject,
) -> JobOutcome:
    """Advance one publication through the provider-observed phases."""
    publisher = context.publisher
    repository_id = context.repository_id

    if publication.status == "reconciliation_required":
        reconciliation = await _reconcile_phase(session, publication, publisher, repository_id)
        if reconciliation is not None:
            return reconciliation

    if publication.status in {"reserved", "branch_created"}:
        preparation = await _prepare_pull_request(
            session,
            publication,
            context.target,
            publisher,
            repository_id,
            build_files,
            branch_prefix=branch_prefix,
            pull_request_title=pull_request_title,
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
        return await _verify_merged_deployment(
            session, publication, publisher, repository_id, subject
        )

    publication.status = "reconciliation_required"
    publication.safe_error_code = "PUBLICATION_STATE_UNRECOGNIZED"
    subject.set_state("reconciliation_required")
    await session.commit()
    return JobOutcome(result="retryable_failure", safe_error="PUBLICATION_STATE_UNRECOGNIZED")


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
    loaded = await load_publication(
        session, organization_id, input_document.get("publication_id"), kind="content"
    )
    if isinstance(loaded, JobOutcome):
        return loaded
    publication = loaded

    context = await load_publishing_context(session, organization_id, publication)
    if isinstance(context, JobOutcome):
        return context

    revision = None
    item = None
    if publication.content_revision_id is not None and publication.content_item_id is not None:
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

    overrides = _safe_overrides(input_document.get("frontmatter_overrides"))
    content_revision, content_item = revision, item

    async def build_files(base_commit: str) -> dict[str, str] | JobOutcome:
        del base_commit
        return await _build_content_files(
            session, publication, content_revision, context.target, overrides
        )

    async def finish(deployment_url: str | None) -> JobOutcome:
        return await _mark_published(
            session, publication, content_revision, content_item, deployment_url
        )

    def set_state(state: str) -> None:
        content_item.status = state

    return await advance_publication(
        session,
        publication,
        context,
        build_files=build_files,
        branch_prefix="lilos-content",
        pull_request_title=f"Publish: {publication.target_path}",
        subject=PublicationSubject(set_state=set_state, finish=finish),
    )


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


async def _build_content_files(
    session: AsyncSession,
    publication: ContentPublication,
    revision: ContentRevision,
    target: PublishingTarget,
    overrides: dict[str, object],
) -> dict[str, str] | JobOutcome:
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
        return {publication.target_path: build_content_file(revision.body, rendered)}
    except FrontmatterContractError as exc:
        return await _permanent(session, publication, exc.safe_code, str(exc))
    except ContentFileFormatError as exc:
        return await _permanent(session, publication, exc.safe_code, str(exc))


async def _prepare_pull_request(
    session: AsyncSession,
    publication: ContentPublication,
    target: PublishingTarget,
    publisher: RepositoryPublisher,
    repository_id: str,
    build_files: FileBuilder,
    *,
    branch_prefix: str,
    pull_request_title: str,
) -> JobOutcome | None:
    branch_name = publication.branch_name or f"{branch_prefix}-{publication.id}"
    try:
        if not publication.base_commit:
            publication.base_commit = await publisher.get_base_commit(
                repository_id, target.base_branch
            )
        built = await build_files(publication.base_commit)
        if isinstance(built, JobOutcome):
            return built
        from apps.api.app.staging.write_boundary import require_github_scope

        settings = Settings()
        for path in built:
            require_github_scope(settings, repository_id, path=path, branch=branch_name)
        await publisher.create_branch(
            repository_id,
            target.base_branch,
            publication.base_commit,
            branch_name,
        )
        publication.branch_name = branch_name
        publication.status = "branch_created"
        await session.commit()

        for path, file_contents in built.items():
            await publisher.put_file(repository_id, branch_name, path, file_contents, None)
        pr_number = publication.external_pull_request_id or await publisher.create_pull_request(
            repository_id,
            branch_name,
            target.base_branch,
            pull_request_title,
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
    pr: dict[str, object] = {}
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
    gate = checks.get("gate", "none")
    publication.build_status = f"{gate}:{state}"
    if state == "failed":
        publication.status = "checks_failed"
        publication.safe_error_code = "CONTENT_CHECKS_FAILED"
        await session.commit()
        return JobOutcome(result="permanent_failure", safe_error="CONTENT_CHECKS_FAILED")
    if state == "none":
        # Neither repository CI nor a Vercel preview status exists. Give a slow
        # reporter a grace window; past it the change is blocked, never merged.
        if _checks_grace_elapsed(pr):
            publication.status = "checks_failed"
            publication.safe_error_code = "CHECKS_UNAVAILABLE"
            await session.commit()
            return JobOutcome(result="permanent_failure", safe_error="CHECKS_UNAVAILABLE")
        publication.status = "checks_running"
        publication.safe_error_code = None
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="CONTENT_CHECKS_PENDING")
    if state == "pending":
        publication.status = "checks_running"
        publication.safe_error_code = None
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="CONTENT_CHECKS_PENDING")
    publication.status = "pull_request_created"
    publication.safe_error_code = None
    await session.commit()
    return None


def _checks_grace_elapsed(pr: dict[str, object]) -> bool:
    """True once the pull request is older than the no-checks grace window."""
    raw_created = pr.get("created_at")
    if not isinstance(raw_created, str):
        return False
    try:
        created = datetime.fromisoformat(raw_created.replace("Z", "+00:00"))
    except ValueError:
        return False
    return datetime.now(UTC) - created > CHECKS_GRACE_WINDOW


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
    async def finish(deployment_url: str | None) -> JobOutcome:
        return await _mark_published(session, publication, revision, item, deployment_url)

    def set_state(state: str) -> None:
        item.status = state

    return await _verify_merged_deployment(
        session,
        publication,
        publisher,
        repository_id,
        PublicationSubject(set_state=set_state, finish=finish),
    )


async def _verify_merged_deployment(
    session: AsyncSession,
    publication: ContentPublication,
    publisher: RepositoryPublisher,
    repository_id: str,
    subject: PublicationSubject,
) -> JobOutcome:
    revision_id = publication.external_revision_id
    if not revision_id:
        publication.status = "reconciliation_required"
        publication.safe_error_code = "MERGE_REVISION_MISSING"
        subject.set_state("reconciliation_required")
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="MERGE_REVISION_MISSING")
    try:
        deployment = await publisher.deployment(repository_id, revision_id)
        state = deployment.get("state", "none").lower()
        publication.deployment_status = state
        if state in {"success", "active"}:
            return await subject.finish(deployment.get("url"))
        if state in {"error", "failure", "inactive"}:
            publication.status = "failed"
            publication.safe_error_code = "CONTENT_DEPLOYMENT_FAILED"
            subject.set_state("failed")
            await session.commit()
            return JobOutcome(result="permanent_failure", safe_error="CONTENT_DEPLOYMENT_FAILED")

        # A successful CI check can include a preview build or unrelated tests.
        # Only a production deployment bound to this merged commit proves delivery.
        publication.status = "deployment_pending"
        publication.safe_error_code = None
        subject.set_state("publishing")
        await session.commit()
        return JobOutcome(result="retryable_failure", safe_error="CONTENT_DEPLOYMENT_PENDING")
    except Exception as exc:
        logger.warning("Content deployment verification failed", exc_info=exc)
        publication.status = "reconciliation_required"
        publication.safe_error_code = "DEPLOYMENT_REREAD_FAILED"
        subject.set_state("reconciliation_required")
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
