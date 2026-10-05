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
from apps.api.app.locations.models import Location
from apps.api.app.products.content.models import ContentPublication, PublishingTarget
from apps.api.app.products.seo.change_quality import (
    DESCRIPTION_MAX_LENGTH,
    DESCRIPTION_MIN_LENGTH,
    TITLE_MAX_LENGTH,
    TITLE_MIN_LENGTH,
    TOP_QUERY_LIMIT,
    QualityContext,
    location_phrases,
)
from apps.api.app.products.seo.change_set import (
    MAX_META_DESCRIPTION_LENGTH,
    MAX_SEO_TITLE_LENGTH,
    SiteChangeField,
    SiteChangeSet,
)
from apps.api.app.products.seo.decision import SEOEvidenceInvalidError
from apps.api.app.products.seo.errors import SEOSiteMappingRequiredError
from apps.api.app.products.seo.limitation_codes import SEOLimitationCode
from apps.api.app.products.seo.models import (
    SEOOpportunity,
    SEOPage,
    SEORecommendationRevision,
    SEOSearchObservation,
)
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


def page_mapping_limitation(target: PublishingTarget | None, page_url: str | None) -> str | None:
    """`SITE_MAPPING_REQUIRED` when a page cannot be edited through the target's page map.

    Pure: callers load the page and the active target (one set-based read for many
    pages, or one pair for a single page). None means a site change is possible.
    """
    if page_url is None or target is None or not target.allowed_site_change_prefixes:
        return SiteChangeCode.SITE_MAPPING_REQUIRED.value
    try:
        resolve_entry(
            page_map_from_contract(target.frontmatter_contract),
            page_url,
            target.allowed_site_change_prefixes,
        )
    except SEOSiteMappingRequiredError:
        return SiteChangeCode.SITE_MAPPING_REQUIRED.value
    return None


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

    async def quality_context(
        self, session: AsyncSession, organization_id: UUID, opportunity: SEOOpportunity
    ) -> QualityContext:
        """The facts a proposed title/description is checked against. Database only.

        The target query from the opportunity's evidence, the attributed page's top Search
        Console queries by impressions (newest 28-day window), and the location profile's
        city, region and service-area phrases. A missing source skips only its own checks.
        """
        query = opportunity.evidence.get("query")
        top_queries: list[str] = []
        if opportunity.page_id is not None:
            rows = (
                await session.execute(
                    select(
                        SEOSearchObservation.query,
                        SEOSearchObservation.impressions,
                        SEOSearchObservation.date_start,
                        SEOSearchObservation.date_end,
                    )
                    .where(
                        SEOSearchObservation.organization_id == organization_id,
                        SEOSearchObservation.page_id == opportunity.page_id,
                        SEOSearchObservation.quality_status == "valid",
                        SEOSearchObservation.query.isnot(None),
                        SEOSearchObservation.dimensions["observation_type"].astext == "page_query",
                    )
                    .order_by(SEOSearchObservation.date_end.desc())
                    .limit(5000)
                )
            ).all()
            if rows:
                newest = rows[0].date_end
                same_end = [row for row in rows if row.date_end == newest]
                # Prefer the 28-day window ending on the newest date, else whatever ends there.
                window = [
                    row for row in same_end if (row.date_end - row.date_start).days == 28
                ] or same_end
                ranked = sorted(window, key=lambda row: int(row.impressions or 0), reverse=True)
                for row in ranked:
                    if row.query and row.query not in top_queries:
                        top_queries.append(row.query)
                    if len(top_queries) >= TOP_QUERY_LIMIT:
                        break
        location = await session.scalar(
            select(Location).where(
                Location.organization_id == organization_id,
                *(
                    [Location.id == opportunity.location_id]
                    if opportunity.location_id is not None
                    else [Location.is_primary.is_(True)]
                ),
            )
        )
        terms = (
            location_phrases(location.city, location.region, location.service_area_description)
            if location is not None
            else ()
        )
        return QualityContext(
            target_query=query if isinstance(query, str) and query else None,
            top_queries=tuple(top_queries),
            location_terms=terms,
        )

    async def mapping_limitation(
        self, session: AsyncSession, organization_id: UUID, page_id: UUID
    ) -> str | None:
        """`SITE_MAPPING_REQUIRED` when this page cannot be edited through a page map.

        Database only -- no repository is read -- so it is safe to call while a
        recommendation is being created. None means a site change is possible.
        """
        page = await session.scalar(
            select(SEOPage).where(SEOPage.organization_id == organization_id, SEOPage.id == page_id)
        )
        target = await self.active_target(session, organization_id)
        return page_mapping_limitation(target, page.normalized_url if page else None)

    async def site_change_context(
        self, session: AsyncSession, organization_id: UUID, opportunity: SEOOpportunity
    ) -> dict[str, object]:
        """What Hermes is told about editing this opportunity's page, read from the repo.

        Commits the caller's session before reading the client repository, so call it
        only from a worker step that owns the session. The values are evidence read
        through the page map; Hermes proposes replacements, never the current text.
        """
        if opportunity.page_id is None or opportunity.attribution_state != "attributed":
            return {"status": "not_applicable"}
        quality = await self.quality_context(session, organization_id, opportunity)
        quality_document: dict[str, object] = {
            "target_query": quality.target_query,
            "top_queries": list(quality.top_queries),
            "location_terms": list(quality.location_terms),
            "title_length": [TITLE_MIN_LENGTH, TITLE_MAX_LENGTH],
            "description_length": [DESCRIPTION_MIN_LENGTH, DESCRIPTION_MAX_LENGTH],
        }
        page = await session.scalar(
            select(SEOPage).where(
                SEOPage.organization_id == organization_id, SEOPage.id == opportunity.page_id
            )
        )
        if page is None:
            return {
                "status": "unavailable",
                "code": SiteChangeCode.SITE_MAPPING_REQUIRED.value,
                "quality_context": quality_document,
            }
        page_id, page_url = page.id, page.normalized_url
        result = await self.read_page_fields(session, organization_id, page)
        if isinstance(result, FieldsUnavailable):
            return {
                "status": "unavailable",
                "code": str(result.code),
                "detail": result.detail[:300],
                "quality_context": quality_document,
            }
        return {
            "status": "available",
            "page_id": str(page_id),
            "page_url": page_url,
            "fields": {field_name.value: value for field_name, value in result.values.items()},
            "limits": {
                SiteChangeField.SEO_TITLE.value: MAX_SEO_TITLE_LENGTH,
                SiteChangeField.META_DESCRIPTION.value: MAX_META_DESCRIPTION_LENGTH,
            },
            "quality_context": quality_document,
        }

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
