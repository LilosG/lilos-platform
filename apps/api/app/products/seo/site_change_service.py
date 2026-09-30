"""Reserve and read the facts a governed site change depends on.

Two jobs, both deterministic:

- `reserve_publication` turns an approved, fingerprinted change set into a
  `content_publications` row of kind ``site_change`` and enqueues the
  ``seo.apply_site_change`` workflow. The publication is the same provider
  state machine Content uses; nothing about branches, pull requests, checks or
  deployment is re-implemented here.
- `read_page_fields` reads a page's CURRENT values out of the client repository
  through the page map, so a change set's ``current_value`` is evidence read from
  the repo and never something a model asserts.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.models import WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.content.models import ContentPublication, PublishingTarget
from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeSet
from apps.api.app.products.seo.decision import SEOEvidenceInvalidError
from apps.api.app.products.seo.errors import SEOSiteMappingRequiredError
from apps.api.app.products.seo.limitation_codes import SEOLimitationCode
from apps.api.app.products.seo.models import SEOPage, SEORecommendationRevision
from apps.api.app.products.seo.site_change_codes import SiteChangeCode
from apps.api.app.products.seo.site_map_resolver import (
    SiteMapLocator,
    page_map_from_contract,
    resolve_current_value,
    resolve_entry,
)

# Publishing waits on repository checks and a production deployment; the generic
# three-attempt job budget is not enough (same budget Content publishing uses).
SITE_CHANGE_JOB_ATTEMPTS = 30

AuditFn = Callable[..., Awaitable[None]]


@dataclass(frozen=True, slots=True)
class PageFields:
    """A page's current, repo-read values for every field its page map declares."""

    url: str
    values: dict[SiteChangeField, str]


@dataclass(frozen=True, slots=True)
class FieldsUnavailable:
    """Why a page's fields could not be read -- always a typed code."""

    code: SiteChangeCode | SEOLimitationCode
    detail: str


@dataclass(slots=True)
class SiteChangeService:
    execution: ExecutionService = field(default_factory=ExecutionService)

    async def active_target(
        self, session: AsyncSession, organization_id: UUID
    ) -> PublishingTarget | None:
        """The organization's one active GitHub target, or None when absent/ambiguous."""
        targets = list(
            await session.scalars(
                select(PublishingTarget).where(
                    PublishingTarget.organization_id == organization_id,
                    PublishingTarget.status == "active",
                )
            )
        )
        return targets[0] if len(targets) == 1 else None

    async def reserve_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision: SEORecommendationRevision,
        workflow_run: WorkflowRun,
        *,
        actor_id: UUID | None,
        correlation_id: str,
        audit: AuditFn,
        location_id: UUID | None,
    ) -> ContentPublication:
        """Create (or return) the publication that applies an approved change set."""
        if revision.change_set is None:
            raise SEOEvidenceInvalidError(SEOLimitationCode.SITE_MAPPING_REQUIRED)
        change_set = SiteChangeSet.model_validate(revision.change_set)
        idempotency_key = f"seo-site-change-{revision.id}"
        existing = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.organization_id == organization_id,
                ContentPublication.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing

        target = await self.active_target(session, organization_id)
        if target is None or not target.allowed_site_change_prefixes:
            raise SEOEvidenceInvalidError(SEOLimitationCode.SITE_CHANGE_TARGET_UNAVAILABLE)
        if not page_map_from_contract(target.frontmatter_contract):
            raise SEOEvidenceInvalidError(SEOLimitationCode.SITE_MAPPING_REQUIRED)
        connection = await session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.id == target.connection_id,
                IntegrationConnection.status == "connected",
            )
        )
        if connection is None:
            raise SEOEvidenceInvalidError(SEOLimitationCode.SITE_CHANGE_TARGET_UNAVAILABLE)

        page_ids = {item.page_id for item in change_set.items}
        urls = {
            row.id: row.normalized_url
            for row in await session.scalars(
                select(SEOPage).where(
                    SEOPage.organization_id == organization_id, SEOPage.id.in_(page_ids)
                )
            )
        }
        if set(urls) != page_ids:
            raise SEOEvidenceInvalidError(SEOLimitationCode.PAGE_OUT_OF_SCOPE)

        publication = ContentPublication(
            organization_id=organization_id,
            publication_kind="site_change",
            content_item_id=None,
            content_revision_id=None,
            seo_recommendation_revision_id=revision.id,
            publishing_target_id=target.id,
            workflow_run_id=workflow_run.id,
            idempotency_key=idempotency_key,
            status="reserved",
            target_path=", ".join(sorted(urls.values()))[:1000],
            change_set_fingerprint=change_set.fingerprint(),
        )
        session.add(publication)
        await session.flush()
        workflow_run.input_document = {
            **(workflow_run.input_document or {}),
            "publication_id": str(publication.id),
        }
        await audit(
            session,
            event="seo.site_change.reserved",
            organization_id=organization_id,
            location_id=location_id,
            actor_id=actor_id,
            resource_type="seo_recommendation_revision",
            resource_id=revision.id,
            correlation_id=correlation_id,
            summary="SEO site change reserved for execution.",
            metadata={
                "publication_id": str(publication.id),
                "change_set_fingerprint": publication.change_set_fingerprint,
                "items": len(change_set.items),
            },
        )
        job = await self.execution.enqueue_consumed_run(session, workflow_run)
        job.max_attempts = SITE_CHANGE_JOB_ATTEMPTS
        return publication

    async def read_page_fields(
        self,
        session: AsyncSession,
        organization_id: UUID,
        page: SEOPage,
        *,
        publisher_factory: Callable[[str], object] | None = None,
    ) -> PageFields | FieldsUnavailable:
        """Read a page's current mapped values from the client repo.

        Returns a typed reason instead of raising when the page has no mapping or
        the repository cannot be read, so a recommendation can carry that code.
        """
        # Imported here: the publish handler module pulls in the execution
        # handlers, which this module must not depend on at import time.
        from apps.api.app.config import Settings
        from apps.api.app.execution import handlers
        from apps.api.app.products.content.adapter import RepositoryPublisher

        target = await self.active_target(session, organization_id)
        if target is None or not target.allowed_site_change_prefixes:
            return FieldsUnavailable(
                SiteChangeCode.SITE_MAPPING_REQUIRED, "No site-change target is configured."
            )
        page_map = page_map_from_contract(target.frontmatter_contract)
        try:
            entry = resolve_entry(
                page_map, page.normalized_url, target.allowed_site_change_prefixes
            )
        except SEOSiteMappingRequiredError as exc:
            return FieldsUnavailable(SiteChangeCode.SITE_MAPPING_REQUIRED, exc.public_message)

        connection = await session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.id == target.connection_id,
                IntegrationConnection.status == "connected",
            )
        )
        if connection is None:
            return FieldsUnavailable(
                SiteChangeCode.GITHUB_CONNECTION_REQUIRED, "GitHub is not connected."
            )
        try:
            token = str(await handlers._github_token_resolver(session, Settings(), connection))
        except Exception:
            return FieldsUnavailable(
                SiteChangeCode.GITHUB_CREDENTIAL_REQUIRED, "GitHub credential is unavailable."
            )
        repository_id, base_branch = target.repository_id, target.base_branch
        # Provider HTTP must not run inside a database transaction.
        await session.commit()

        make = publisher_factory or handlers._content_publisher_factory
        publisher: RepositoryPublisher = make(token)  # type: ignore[assignment]
        try:
            ref = await publisher.get_base_commit(repository_id, base_branch)
            files: dict[str, str] = {}
            for locator in entry.fields.values():
                if locator.file_path not in files:
                    text = await publisher.get_file(repository_id, ref, locator.file_path)
                    if text is not None:
                        files[locator.file_path] = text
        except Exception:
            return FieldsUnavailable(
                SiteChangeCode.SITE_MAPPING_REQUIRED, "The client repository could not be read."
            )

        values: dict[SiteChangeField, str] = {}
        for field_name, locator in entry.fields.items():
            try:
                values[field_name] = _read(files, locator)
            except SEOSiteMappingRequiredError:
                continue  # that one field stays unmapped; the others remain usable
        if not values:
            return FieldsUnavailable(
                SiteChangeCode.SITE_MAPPING_REQUIRED,
                f"No mapped field on {entry.url_path} resolved to exactly one value.",
            )
        return PageFields(url=entry.url_path, values=values)


def _read(files: dict[str, str], locator: SiteMapLocator) -> str:
    return resolve_current_value(files, locator)
