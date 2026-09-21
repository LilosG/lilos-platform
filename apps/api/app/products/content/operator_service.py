"""Canonical operator workflow projection and governed Content publication start."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config import Settings
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.content.contracts import ApprovalDecision, PublicationCreate
from apps.api.app.products.content.errors import (
    ContentItemNotFoundError,
    ContentPublicationFrontmatterIncompleteError,
    ContentPublicationIdempotencyConflictError,
    ContentPublicationNotAdvanceableError,
    ContentPublicationNotFoundError,
    ContentPublicationRequiresApprovedRevisionError,
    ContentTargetNotConfiguredError,
    ContentTechnicalSiteChangeRequiresSEOError,
)
from apps.api.app.products.content.frontmatter_contract import FrontmatterContract
from apps.api.app.products.content.github_app_service import (
    GitHubAppService,
    installation_id_from_reference,
)
from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentPublication,
    ContentRevision,
    PublishingTarget,
)
from apps.api.app.products.content.service import ContentService, build_publishable_frontmatter
from apps.api.app.site_change_policy import is_technical_site_change

_IMAGE_EXTENSIONS = {".avif", ".gif", ".jpeg", ".jpg", ".png", ".webp"}
_ACTIVE_PUBLICATION_STATES = {
    "reserved",
    "branch_created",
    "pull_request_created",
    "checks_running",
    "merged",
    "deployment_pending",
    "deployed",
}
_ATTENTION_PUBLICATION_STATES = {"checks_failed", "failed", "reconciliation_required"}


@dataclass(frozen=True, slots=True)
class OperatorPublishRequest:
    idempotency_key: str
    publishing_target_id: UUID | None = None
    image: str | None = None
    image_alt: str | None = None


class ContentOperatorService:
    """Present one understandable Content lifecycle while preserving domain authority."""

    def __init__(
        self,
        *,
        content: ContentService | None = None,
        execution: ExecutionService | None = None,
        github: GitHubAppService | None = None,
    ) -> None:
        self.content = content or ContentService()
        self.execution = execution or ExecutionService()
        self.github = github or GitHubAppService()

    async def list_workspace(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, object]], bool]:
        items, has_more = await self.content.list_items(
            session, organization_id, limit=limit, offset=offset
        )
        if not items:
            return [], has_more
        item_ids = [item.id for item in items]
        revisions = list(
            await session.scalars(
                select(ContentRevision)
                .where(
                    ContentRevision.organization_id == organization_id,
                    ContentRevision.content_item_id.in_(item_ids),
                )
                .order_by(ContentRevision.content_item_id, ContentRevision.revision_number.desc())
            )
        )
        publications = list(
            await session.scalars(
                select(ContentPublication)
                .where(
                    ContentPublication.organization_id == organization_id,
                    ContentPublication.content_item_id.in_(item_ids),
                )
                .order_by(ContentPublication.content_item_id, ContentPublication.created_at.desc())
            )
        )
        latest_revision: dict[UUID, ContentRevision] = {}
        latest_publication: dict[UUID, ContentPublication] = {}
        for revision in revisions:
            latest_revision.setdefault(revision.content_item_id, revision)
        for publication in publications:
            latest_publication.setdefault(publication.content_item_id, publication)
        run_ids = [publication.workflow_run_id for publication in latest_publication.values()]
        jobs = list(
            await session.scalars(
                select(Job)
                .where(Job.organization_id == organization_id, Job.workflow_run_id.in_(run_ids))
                .order_by(Job.workflow_run_id, Job.created_at.desc())
            )
        )
        latest_job_status: dict[UUID, str] = {}
        for job in jobs:
            latest_job_status.setdefault(job.workflow_run_id, job.status)
        return [
            self._summary(
                item,
                latest_revision.get(item.id),
                latest_publication.get(item.id),
                latest_job_status.get(latest_publication[item.id].workflow_run_id)
                if item.id in latest_publication
                else None,
            )
            for item in items
        ], has_more

    async def detail(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
    ) -> dict[str, object]:
        item = await self.content.get_item(session, organization_id, item_id)
        briefs = await self.content.list_briefs(session, organization_id, item_id)
        revisions = await self.content.list_revisions(session, organization_id, item_id)
        publications = await self.content.list_publications(session, organization_id, item_id)
        targets = [
            target
            for target in await self.content.list_targets(session, organization_id)
            if target.status == "active"
        ]
        latest_revision = revisions[0] if revisions else None
        latest_publication = publications[0] if publications else None
        job_status = None
        if latest_publication is not None:
            job = await session.scalar(
                select(Job)
                .where(
                    Job.organization_id == organization_id,
                    Job.workflow_run_id == latest_publication.workflow_run_id,
                )
                .order_by(Job.created_at.desc())
                .limit(1)
            )
            job_status = job.status if job else None
        selected_target = self._select_target_for_read(item, targets)
        requirements = self._requirements(selected_target, latest_revision)
        requirements_by_target = {
            str(target.id): self._requirements(target, latest_revision) for target in targets
        }
        return {
            **self._summary(item, latest_revision, latest_publication, job_status),
            "briefs": [self._brief_row(brief) for brief in briefs],
            "revisions": [self._revision_row(revision) for revision in revisions],
            "publications": [self._publication_row(publication) for publication in publications],
            "publishing_targets": [self._target_row(target) for target in targets],
            "publishing_requirements": requirements,
            "publishing_requirements_by_target": requirements_by_target,
        }

    async def decide_revision(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
        revision_id: UUID,
        command: ApprovalDecision,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ContentRevision:
        revision = await self.content.decide(
            session,
            organization_id,
            revision_id,
            command,
            actor_id,
            correlation_id=correlation_id,
            expected_item_id=item_id,
        )
        return revision

    async def publish(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
        command: OperatorPublishRequest,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> ContentPublication:
        item = await session.scalar(
            select(ContentItem)
            .where(
                ContentItem.organization_id == organization_id,
                ContentItem.id == item_id,
            )
            .with_for_update()
        )
        if item is None:
            raise ContentItemNotFoundError
        existing = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.organization_id == organization_id,
                ContentPublication.idempotency_key == command.idempotency_key,
            )
        )
        if existing is not None:
            existing_run = await session.scalar(
                select(WorkflowRun).where(
                    WorkflowRun.organization_id == organization_id,
                    WorkflowRun.id == existing.workflow_run_id,
                )
            )
            if (
                existing.content_item_id != item_id
                or (
                    command.publishing_target_id is not None
                    and existing.publishing_target_id != command.publishing_target_id
                )
                or existing_run is None
                or (existing_run.input_document or {}).get("frontmatter_overrides")
                != self._frontmatter_overrides(command)
            ):
                raise ContentPublicationIdempotencyConflictError
            return existing
        revision = await self._approved_revision(session, organization_id, item)
        if revision is None:
            raise ContentPublicationRequiresApprovedRevisionError
        if self._technical_site_change(item, revision):
            raise ContentTechnicalSiteChangeRequiresSEOError
        targets = [
            target
            for target in await self.content.list_targets(session, organization_id)
            if target.status == "active"
        ]
        target = self._select_target(item, targets, command.publishing_target_id)
        overrides = self._frontmatter_overrides(command)
        contract = FrontmatterContract.from_document(target.frontmatter_contract)
        canonical = self._canonical_for_publish(revision, overrides)
        rendered = contract.render(canonical)
        if contract.missing_required(rendered):
            raise ContentPublicationFrontmatterIncompleteError
        target_path = self._target_path(target, item.slug, contract)
        run_key = f"content-publish-{command.idempotency_key}"[:128]
        run = await self.execution.start_named(
            session,
            organization_id,
            "content.publish",
            run_key,
            location_id=item.location_id,
            input_document={"frontmatter_overrides": overrides},
            correlation_id=correlation_id,
            actor_id=actor_id,
            enqueue_job=False,
        )
        publication = await self.content.reserve_publication(
            session,
            organization_id,
            item_id,
            revision.id,
            PublicationCreate(
                publishing_target_id=target.id,
                workflow_run_id=run.id,
                target_path=target_path,
                idempotency_key=command.idempotency_key,
            ),
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        item.approved_revision_id = revision.id
        item.publishing_target_id = target.id
        item.status = "publishing"
        await session.flush()
        return publication

    async def list_image_assets(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        target_id: UUID,
    ) -> list[dict[str, str]]:
        target = await session.scalar(
            select(PublishingTarget).where(
                PublishingTarget.organization_id == organization_id,
                PublishingTarget.id == target_id,
                PublishingTarget.status == "active",
            )
        )
        if target is None:
            raise ContentTargetNotConfiguredError
        connection = await session.get(IntegrationConnection, target.connection_id)
        if connection is None or connection.organization_id != organization_id:
            raise ContentTargetNotConfiguredError
        installation_id = installation_id_from_reference(connection.external_account_reference)
        if installation_id is None:
            return []
        token = await self.github.create_installation_token(settings, installation_id)
        url = f"https://api.github.com/repos/{target.repository_id}/git/trees/{target.base_branch}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                url,
                params={"recursive": "1"},
                headers={
                    "Authorization": f"Bearer {token.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        response.raise_for_status()
        document = response.json()
        tree = document.get("tree", []) if isinstance(document, dict) else []
        assets: list[dict[str, str]] = []
        for entry in tree:
            if not isinstance(entry, dict) or entry.get("type") != "blob":
                continue
            path = str(entry.get("path") or "")
            suffix = PurePosixPath(path).suffix.lower()
            if not path.startswith("public/") or suffix not in _IMAGE_EXTENSIONS:
                continue
            public_path = "/" + path.removeprefix("public/")
            assets.append({"path": public_path, "name": PurePosixPath(path).name})
            if len(assets) >= 250:
                break
        return assets

    async def recover_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
        publication_id: UUID,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> Job:
        publication = await session.scalar(
            select(ContentPublication)
            .where(
                ContentPublication.organization_id == organization_id,
                ContentPublication.content_item_id == item_id,
                ContentPublication.id == publication_id,
            )
            .with_for_update()
        )
        if publication is None:
            raise ContentPublicationNotFoundError
        if publication.status in {"verified", "failed", "checks_failed", "rolled_back"}:
            raise ContentPublicationNotAdvanceableError
        job = await self.execution.enqueue_recovery_run(
            session,
            organization_id,
            publication.workflow_run_id,
            recovery_reference=f"content-publication:{publication.id}",
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        job.max_attempts = 30
        return job

    async def _approved_revision(
        self, session: AsyncSession, organization_id: UUID, item: ContentItem
    ) -> ContentRevision | None:
        if item.approved_revision_id is not None:
            revision = await session.scalar(
                select(ContentRevision).where(
                    ContentRevision.organization_id == organization_id,
                    ContentRevision.id == item.approved_revision_id,
                    ContentRevision.content_item_id == item.id,
                    ContentRevision.status == "approved",
                )
            )
            if revision is not None:
                return revision
        fallback_revision: ContentRevision | None = await session.scalar(
            select(ContentRevision)
            .where(
                ContentRevision.organization_id == organization_id,
                ContentRevision.content_item_id == item.id,
                ContentRevision.status == "approved",
            )
            .order_by(ContentRevision.revision_number.desc())
            .limit(1)
        )
        return fallback_revision

    @staticmethod
    def _select_target_for_read(
        item: ContentItem, targets: list[PublishingTarget]
    ) -> PublishingTarget | None:
        if item.publishing_target_id is not None:
            matched = next(
                (target for target in targets if target.id == item.publishing_target_id), None
            )
            if matched is not None:
                return matched
        return targets[0] if len(targets) == 1 else None

    @staticmethod
    def _select_target(
        item: ContentItem,
        targets: list[PublishingTarget],
        requested: UUID | None,
    ) -> PublishingTarget:
        if requested is not None:
            matched = next((target for target in targets if target.id == requested), None)
            if matched is None:
                raise ContentTargetNotConfiguredError
            return matched
        if item.publishing_target_id is not None:
            matched = next(
                (target for target in targets if target.id == item.publishing_target_id), None
            )
            if matched is not None:
                return matched
        if len(targets) != 1:
            raise ContentTargetNotConfiguredError
        return targets[0]

    @staticmethod
    def _canonical_for_publish(
        revision: ContentRevision | None,
        overrides: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Complete deterministic canonical metadata for legacy approved revisions.

        Older approved revisions may predate canonical publish metadata. Rebuild
        only the deterministic metadata that current draft generation would have
        produced, using the same generator helper so legacy and current revisions
        follow one contract. Approved body copy is not changed. Target-specific
        fields such as images remain explicit operator inputs.
        """
        canonical = dict(revision.frontmatter or {}) if revision is not None else {}
        title = str(canonical.get("title") or "").strip()
        if revision is not None and title:
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
        if overrides:
            canonical.update(overrides)
        return canonical

    @staticmethod
    def _frontmatter_overrides(command: OperatorPublishRequest) -> dict[str, object]:
        overrides: dict[str, object] = {}
        if command.image and command.image.strip():
            overrides["image"] = command.image.strip()
        if command.image_alt and command.image_alt.strip():
            overrides["image_alt"] = command.image_alt.strip()
        return overrides

    @staticmethod
    def _target_path(target: PublishingTarget, slug: str, contract: FrontmatterContract) -> str:
        extensions = contract.file_extensions or (".mdx",)
        extension = ".mdx" if ".mdx" in extensions else extensions[0]
        prefix = target.allowed_path_prefix.rstrip("/")
        return f"{prefix}/{slug}{extension}"

    @staticmethod
    def _requirements(
        target: PublishingTarget | None,
        revision: ContentRevision | None,
    ) -> dict[str, object]:
        if target is None:
            return {
                "target_selected": False,
                "missing": ["publishing_target"],
                "requires_image": False,
                "requires_image_alt": False,
                "file_extensions": [],
            }
        contract = FrontmatterContract.from_document(target.frontmatter_contract)
        canonical = ContentOperatorService._canonical_for_publish(revision)
        rendered = contract.render(canonical)
        missing = list(contract.missing_required(rendered))
        image_key = contract.target_key("image")
        image_alt_key = contract.target_key("image_alt")
        return {
            "target_selected": True,
            "target_id": str(target.id),
            "missing": missing,
            "requires_image": image_key in missing,
            "requires_image_alt": image_alt_key in missing,
            "file_extensions": list(contract.file_extensions),
        }

    @staticmethod
    def _summary(
        item: ContentItem,
        revision: ContentRevision | None,
        publication: ContentPublication | None,
        job_status: str | None = None,
    ) -> dict[str, object]:
        stage, next_action = ContentOperatorService._operator_state(
            item, revision, publication, job_status
        )
        technical_site_change = ContentOperatorService._technical_site_change(item, revision)
        if technical_site_change:
            next_action = {"key": "seo_implementation", "label": "Continue in SEO"}
        return {
            "id": str(item.id),
            "location_id": str(item.location_id) if item.location_id else None,
            "content_type": item.content_type,
            "title": item.title,
            "slug": item.slug,
            "stage": stage,
            "next_action": next_action,
            "published_at": item.published_at,
            "latest_revision_status": revision.status if revision else None,
            "latest_revision_number": revision.revision_number if revision else None,
            "publication_status": publication.status if publication else None,
            "publication_job_status": job_status,
            "technical_site_change": technical_site_change,
        }

    @staticmethod
    def _technical_site_change(
        item: ContentItem,
        revision: ContentRevision | None,
    ) -> bool:
        return is_technical_site_change(
            item.title,
            item.slug,
            revision.body if revision is not None else None,
        )

    @staticmethod
    def _operator_state(
        item: ContentItem,
        revision: ContentRevision | None,
        publication: ContentPublication | None,
        job_status: str | None = None,
    ) -> tuple[str, dict[str, str]]:
        if publication is not None:
            if publication.status == "verified":
                return "published", {"key": "view", "label": "View publication"}
            if job_status in {"failed", "dead_lettered", "cancelled"}:
                return "needs_attention", {
                    "key": "review_publication",
                    "label": "Review publishing",
                }
            if publication.status == "reconciliation_required" and job_status in {
                "queued",
                "claimed",
                "running",
                "retry_scheduled",
            }:
                return "publishing", {"key": "wait", "label": "Reconciling publication"}
            if publication.status in _ATTENTION_PUBLICATION_STATES:
                return "needs_attention", {
                    "key": "review_publication",
                    "label": "Review publishing",
                }
            if publication.status in _ACTIVE_PUBLICATION_STATES:
                return "publishing", {"key": "wait", "label": "Publishing in progress"}
        if revision is not None:
            if revision.status == "approved":
                return "ready_to_publish", {"key": "publish", "label": "Publish to website"}
            if revision.status == "awaiting_client":
                return "client_review", {"key": "approve_client", "label": "Approve for publishing"}
            if revision.status == "awaiting_editorial":
                return "editorial_review", {
                    "key": "approve_editorial",
                    "label": "Approve editorial review",
                }
            if revision.status in {"rejected", "validation_failed"}:
                return "revision_needed", {"key": "revise", "label": "Revise content"}
            return "drafting", {"key": "review", "label": "Review draft"}
        if item.status in {"brief_ready", "drafting", "draft_ready"}:
            return "draft_needed", {"key": "draft", "label": "Create draft"}
        return "brief_needed", {"key": "brief", "label": "Create brief"}

    @staticmethod
    def _brief_row(item: ContentBrief) -> dict[str, object]:
        return {
            "id": str(item.id),
            "revision_number": item.revision_number,
            "audience": item.audience,
            "intent": item.intent,
            "target_reference": item.target_reference,
            "approved_fact_revision_ids": item.approved_fact_revision_ids,
            "status": item.status,
        }

    @staticmethod
    def _revision_row(item: ContentRevision) -> dict[str, object]:
        return {
            "id": str(item.id),
            "revision_number": item.revision_number,
            "body": item.body,
            "frontmatter": item.frontmatter,
            "created_by_type": item.created_by_type,
            "status": item.status,
            "validation_document": item.validation_document,
            "approved_at": item.approved_at,
        }

    @staticmethod
    def _publication_row(item: ContentPublication) -> dict[str, object]:
        return {
            "id": str(item.id),
            "status": item.status,
            "target_path": item.target_path,
            "external_pull_request_id": item.external_pull_request_id,
            "published_url": item.published_url,
            "build_status": item.build_status,
            "deployment_status": item.deployment_status,
            "verified_at": item.verified_at,
            "safe_error_code": item.safe_error_code,
        }

    @staticmethod
    def _target_row(item: PublishingTarget) -> dict[str, object]:
        contract = FrontmatterContract.from_document(item.frontmatter_contract)
        return {
            "id": str(item.id),
            "key": item.key,
            "repository_id": item.repository_id,
            "base_branch": item.base_branch,
            "allowed_path_prefix": item.allowed_path_prefix,
            "file_extensions": list(contract.file_extensions),
            "status": item.status,
        }
