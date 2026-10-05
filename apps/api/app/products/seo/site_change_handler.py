"""`seo.apply_site_change`: apply an approved change set to a client's site.

The provider lifecycle -- branch, pull request, checks, merge, deployment -- is
the Content publication state machine, reused unchanged through
`advance_publication`. This module supplies only what is specific to an SEO site
change: the fingerprint gate, turning the approved items into exact file edits,
and the live-site read-back once production serves the merged commit.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.contracts import JobOutcome
from apps.api.app.products.content.models import ContentPublication
from apps.api.app.products.content.publish_handler import (
    PublicationSubject,
    _permanent,
    advance_publication,
    load_publication,
    load_publishing_context,
)
from apps.api.app.products.seo.change_set import SiteChangeSet
from apps.api.app.products.seo.errors import SEOSiteMappingRequiredError
from apps.api.app.products.seo.models import SEOPage, SEORecommendationRevision
from apps.api.app.products.seo.site_change_codes import SiteChangeCode
from apps.api.app.products.seo.site_change_service import live_change_superseding
from apps.api.app.products.seo.site_map_resolver import (
    SiteMapLocator,
    apply_change,
    page_map_from_contract,
    resolve_entry,
)
from apps.api.app.products.seo.verification import fetch_live_page, verify_live_site_change

logger = logging.getLogger(__name__)


async def handle_seo_apply_site_change(
    session: AsyncSession,
    *,
    organization_id: UUID,
    location_id: UUID | None,
    input_document: dict[str, Any],
    correlation_id: str,
    workflow_run_id: UUID,
) -> JobOutcome:
    """Advance one site-change publication through provider-observed phases."""
    del location_id, correlation_id, workflow_run_id
    loaded = await load_publication(
        session, organization_id, input_document.get("publication_id"), kind="site_change"
    )
    if isinstance(loaded, JobOutcome):
        return loaded
    publication = loaded

    revision = (
        await session.scalar(
            select(SEORecommendationRevision).where(
                SEORecommendationRevision.organization_id == organization_id,
                SEORecommendationRevision.id == publication.seo_recommendation_revision_id,
            )
        )
        if publication.seo_recommendation_revision_id is not None
        else None
    )
    if revision is None or revision.change_set is None:
        return await _permanent(
            session, publication, SiteChangeCode.CHANGE_SET_INVALID, "no approved change set"
        )
    try:
        change_set = SiteChangeSet.model_validate(revision.change_set)
    except ValidationError:
        return await _permanent(
            session, publication, SiteChangeCode.CHANGE_SET_INVALID, "change set does not validate"
        )

    # What a human approved is what executes: the digest recorded at approval, the
    # one reserved with this publication and the one re-derived now must all agree.
    fingerprint = change_set.fingerprint()
    if not (fingerprint == revision.change_set_fingerprint == publication.change_set_fingerprint):
        return await _permanent(
            session,
            publication,
            SiteChangeCode.SITE_CHANGE_FINGERPRINT_MISMATCH,
            "change set differs from the approved fingerprint",
        )

    # A publication reserved before a newer change went live must not roll the page back.
    if publication.status == "reserved" and await live_change_superseding(
        session, organization_id, revision, change_set
    ):
        return await _permanent(
            session,
            publication,
            SiteChangeCode.SUPERSEDED_BY_LIVE_CHANGE,
            "a newer change to the same page field is already live",
        )

    context = await load_publishing_context(session, organization_id, publication)
    if isinstance(context, JobOutcome):
        return context

    pages = {
        page.id: page
        for page in await session.scalars(
            select(SEOPage).where(
                SEOPage.organization_id == organization_id,
                SEOPage.id.in_({item.page_id for item in change_set.items}),
            )
        )
    }

    async def build_files(base_commit: str) -> dict[str, str] | JobOutcome:
        try:
            return await _apply_items(
                context.publisher,
                context.repository_id,
                base_commit,
                context.target.frontmatter_contract,
                list(context.target.allowed_site_change_prefixes),
                change_set,
                pages,
            )
        except SEOSiteMappingRequiredError as exc:
            return await _permanent(
                session, publication, SiteChangeCode.SITE_MAPPING_REQUIRED, exc.public_message
            )

    async def finish(deployment_url: str | None) -> JobOutcome:
        return await _verify_live(session, publication, change_set, pages, deployment_url)

    def no_item_state(state: str) -> None:
        del state  # a site change has no content item whose status tracks the lifecycle

    return await advance_publication(
        session,
        publication,
        context,
        build_files=build_files,
        branch_prefix="lilos-site-change",
        pull_request_title=_pull_request_title(change_set, pages),
        subject=PublicationSubject(set_state=no_item_state, finish=finish),
    )


async def _apply_items(
    publisher: Any,
    repository_id: str,
    base_commit: str,
    contract: object,
    allowed_prefixes: list[str],
    change_set: SiteChangeSet,
    pages: dict[UUID, SEOPage],
) -> dict[str, str]:
    """Resolve every item to its file and field, then apply exactly those edits.

    Returns only the files that changed. Any item that cannot be
    mapped to exactly one value fails the whole change set: the pull request
    carries what was approved or nothing.
    """
    page_map = page_map_from_contract(contract)
    locators: list[tuple[int, SiteMapLocator]] = []
    for index, item in enumerate(change_set.items):
        page = pages.get(item.page_id)
        if page is None:
            raise SEOSiteMappingRequiredError("An approved page is no longer in this website.")
        entry = resolve_entry(page_map, page.normalized_url, allowed_prefixes)
        locator = entry.fields.get(item.field)
        if locator is None:
            raise SEOSiteMappingRequiredError(
                f"{entry.url_path} has no mapping for {item.field.value}."
            )
        locators.append((index, locator))

    files: dict[str, str] = {}
    for _, locator in locators:
        if locator.file_path in files:
            continue
        text = await publisher.get_file(repository_id, base_commit, locator.file_path)
        if text is not None:
            files[locator.file_path] = text

    original = dict(files)
    for index, locator in locators:
        item = change_set.items[index]
        # `apply_change` re-reads the live value and refuses if the repo drifted
        # from the approved `current_value`.
        files = apply_change(files, locator, item.current_value, item.proposed_value)
    return {path: text for path, text in files.items() if original.get(path) != text}


def _pull_request_title(change_set: SiteChangeSet, pages: dict[UUID, SEOPage]) -> str:
    fields = ", ".join(sorted({item.field.value for item in change_set.items}))
    paths = ", ".join(
        sorted(
            {
                pages[item.page_id].normalized_url
                for item in change_set.items
                if item.page_id in pages
            }
        )
    )
    return f"SEO: update {fields} on {paths}"[:200]


async def _verify_live(
    session: AsyncSession,
    publication: ContentPublication,
    change_set: SiteChangeSet,
    pages: dict[UUID, SEOPage],
    deployment_url: str | None,
) -> JobOutcome:
    """Read every changed value back from the live site and record the proof."""
    # No database transaction may be open while the public site is being fetched.
    await session.commit()
    cache_buster = (publication.external_revision_id or "live")[:12]
    live = {
        page_id: await fetch_live_page(page.normalized_url, cache_buster=cache_buster)
        for page_id, page in pages.items()
    }
    proof = verify_live_site_change(change_set, live)
    publication.verification_evidence = proof
    result = proof["result"]
    if result == "verified":
        publication.status = "verified"
        publication.verification_status = "verified"
        publication.verified_at = datetime.now(UTC)
        publication.safe_error_code = None
        if deployment_url:
            publication.published_url = deployment_url
        await session.commit()
        return JobOutcome(result="succeeded", result_reference=f"publication:{publication.id}")
    if result == "failed":
        publication.status = "failed"
        publication.verification_status = "failed"
        publication.safe_error_code = SiteChangeCode.SITE_CHANGE_VERIFICATION_FAILED
        await session.commit()
        return JobOutcome(
            result="permanent_failure", safe_error=SiteChangeCode.SITE_CHANGE_VERIFICATION_FAILED
        )
    # The page could not be read yet (deploy still propagating): try again.
    publication.status = "deployed"
    publication.verification_status = "pending"
    publication.safe_error_code = None
    await session.commit()
    return JobOutcome(result="retryable_failure", safe_error="SITE_CHANGE_VERIFICATION_PENDING")
