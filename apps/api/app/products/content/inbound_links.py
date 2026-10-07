"""Proposed inbound links: existing pages that should link to a newly drafted piece.

For a draft, pick up to five existing, crawled pages that are topically close and do not
link to it yet, read each page's mapped `internal_link` text from the client repository
through the governed site-change reader, and build one exact before/after edit per page.
Each proposal becomes a normal SEO recommendation carrying a `SiteChangeSet`, so Mike
approves it through the same single gate and the same executor as every other site edit.
Nothing here writes to a client site.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.content.link_validation import (
    build_inbound_link_edit,
    normalize_origin_host,
    normalize_path,
)
from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeItem, SiteChangeSet
from apps.api.app.products.seo.contracts import RecommendationCreate
from apps.api.app.products.seo.decision import INBOUND_LINK_SOURCE
from apps.api.app.products.seo.models import SEOOpportunity, SEOPage, SEOWebsite
from apps.api.app.products.seo.service import SCORE_VERSION, SEOService
from apps.api.app.products.seo.site_change_service import FieldsUnavailable, SiteChangeService

MAX_INBOUND_PROPOSALS = 5
MAX_CANDIDATES_EVALUATED = 12
_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset({"the", "and", "for", "with", "best", "near", "in", "of", "a", "to", "your"})


class InboundLinkStatus(StrEnum):
    PROPOSED = "proposed"
    UNAVAILABLE = "unavailable"


class InboundLinkCode(StrEnum):
    """Why a candidate page got no proposal. Closed set, never prose."""

    PAGE_MAPPING_REQUIRED = "PAGE_MAPPING_REQUIRED"
    LINK_FIELD_NOT_MAPPED = "LINK_FIELD_NOT_MAPPED"
    NO_NATURAL_ANCHOR = "NO_NATURAL_ANCHOR"
    PROPOSAL_REJECTED = "PROPOSAL_REJECTED"


class InboundLinkProposal(TypedDict, total=False):
    page_id: str
    page_url: str
    field: str
    status: str
    code: str
    anchor: str
    target_url: str
    before: str
    after: str
    recommendation_id: str


@dataclass(frozen=True, slots=True)
class InboundLinkRequest:
    organization_id: UUID
    website_id: UUID
    revision_id: UUID
    content_hash: str
    target_url: str
    topic_phrases: Sequence[str]
    actor_id: UUID | None
    correlation_id: str


def _tokens(value: str) -> set[str]:
    return {t for t in _WORD.findall(value.casefold()) if len(t) > 2 and t not in _STOP}


def _already_links_to(page: SEOPage, target_url: str, origin_host: str | None) -> bool:
    for link in page.internal_links or []:
        raw = link.get("url") if isinstance(link, dict) else link
        if normalize_path(str(raw or ""), origin_host) == target_url:
            return True
    return False


class InboundLinkService:
    def __init__(
        self,
        *,
        seo: SEOService | None = None,
        site_changes: SiteChangeService | None = None,
    ) -> None:
        self.seo = seo or SEOService()
        self.site_changes = site_changes or SiteChangeService()

    async def candidates(
        self,
        session: AsyncSession,
        request: InboundLinkRequest,
        website: SEOWebsite,
    ) -> list[SEOPage]:
        """Existing indexable pages closest to the new piece that do not link to it yet."""
        origin_host = normalize_origin_host(website.canonical_origin)
        topic = _tokens(" ".join(request.topic_phrases))
        pages = list(
            await session.scalars(
                select(SEOPage).where(
                    SEOPage.organization_id == request.organization_id,
                    SEOPage.website_id == website.id,
                    SEOPage.http_status == 200,
                    SEOPage.indexability == "indexable",
                )
            )
        )
        scored: list[tuple[int, str, SEOPage]] = []
        for page in pages:
            path = normalize_path(page.normalized_url, origin_host)
            if path is None or path == request.target_url:
                continue
            if _already_links_to(page, request.target_url, origin_host):
                continue
            text = " ".join(
                part
                for part in (page.title, page.h1, page.meta_description, page.body_text)
                if part
            )
            overlap = len(topic & _tokens(text[:6000] + " " + path.replace("-", " ")))
            if overlap:
                scored.append((overlap, path, page))
        scored.sort(key=lambda row: (-row[0], row[1]))
        return [page for _, _, page in scored[:MAX_CANDIDATES_EVALUATED]]

    async def propose(
        self,
        session: AsyncSession,
        request: InboundLinkRequest,
        *,
        publisher_factory: Callable[[str], object] | None = None,
    ) -> list[InboundLinkProposal]:
        website = await session.scalar(
            select(SEOWebsite).where(
                SEOWebsite.organization_id == request.organization_id,
                SEOWebsite.id == request.website_id,
            )
        )
        if website is None:
            return []
        proposals: list[InboundLinkProposal] = []
        for page in await self.candidates(session, request, website):
            if sum(p["status"] == InboundLinkStatus.PROPOSED for p in proposals) >= (
                MAX_INBOUND_PROPOSALS
            ):
                break
            page_id, page_url = page.id, page.normalized_url
            base: InboundLinkProposal = {
                "page_id": str(page_id),
                "page_url": page_url,
                "field": SiteChangeField.INTERNAL_LINK.value,
                "target_url": request.target_url,
            }
            fields = await self.site_changes.read_page_fields(
                session, request.organization_id, page, publisher_factory=publisher_factory
            )
            if isinstance(fields, FieldsUnavailable):
                proposals.append(
                    {
                        **base,
                        "status": InboundLinkStatus.UNAVAILABLE.value,
                        "code": InboundLinkCode.PAGE_MAPPING_REQUIRED.value,
                    }
                )
                continue
            current = fields.values.get(SiteChangeField.INTERNAL_LINK)
            if current is None:
                proposals.append(
                    {
                        **base,
                        "status": InboundLinkStatus.UNAVAILABLE.value,
                        "code": InboundLinkCode.LINK_FIELD_NOT_MAPPED.value,
                    }
                )
                continue
            edit = build_inbound_link_edit(
                current, target_url=request.target_url, phrases=request.topic_phrases
            )
            if edit is None:
                proposals.append(
                    {
                        **base,
                        "status": InboundLinkStatus.UNAVAILABLE.value,
                        "code": InboundLinkCode.NO_NATURAL_ANCHOR.value,
                    }
                )
                continue
            try:
                change_set = SiteChangeSet(
                    items=[
                        SiteChangeItem(
                            page_id=page_id,
                            field=SiteChangeField.INTERNAL_LINK,
                            current_value=edit.before,
                            proposed_value=edit.after,
                            rationale=(
                                f"Link '{edit.anchor}' to {request.target_url} so the new "
                                "piece is reachable from a closely related page."
                            ),
                        )
                    ]
                )
                recommendation_id = await self._recommend(session, request, page, edit, change_set)
            except ValueError:
                proposals.append(
                    {
                        **base,
                        "status": InboundLinkStatus.UNAVAILABLE.value,
                        "code": InboundLinkCode.PROPOSAL_REJECTED.value,
                    }
                )
                continue
            proposals.append(
                {
                    **base,
                    "status": InboundLinkStatus.PROPOSED.value,
                    "anchor": edit.anchor,
                    "before": edit.before,
                    "after": edit.after,
                    "recommendation_id": str(recommendation_id),
                }
            )
        return proposals

    async def _recommend(
        self,
        session: AsyncSession,
        request: InboundLinkRequest,
        page: SEOPage,
        edit: object,
        change_set: SiteChangeSet,
    ) -> UUID:
        digest = hashlib.sha256(
            f"{INBOUND_LINK_SOURCE}:{request.revision_id}:{page.id}".encode()
        ).hexdigest()
        opportunity = await session.scalar(
            select(SEOOpportunity).where(
                SEOOpportunity.organization_id == request.organization_id,
                SEOOpportunity.deduplication_key == digest,
                SEOOpportunity.active_marker == "active",
            )
        )
        if opportunity is None:
            website = await session.scalar(
                select(SEOWebsite).where(
                    SEOWebsite.organization_id == request.organization_id,
                    SEOWebsite.id == request.website_id,
                )
            )
            assert website is not None
            opportunity = SEOOpportunity(
                organization_id=request.organization_id,
                location_id=website.location_id,
                website_id=website.id,
                page_id=page.id,
                opportunity_type=INBOUND_LINK_SOURCE,
                deduplication_key=digest,
                active_marker="active",
                evidence={
                    "source": INBOUND_LINK_SOURCE,
                    "content_revision_id": str(request.revision_id),
                    "content_hash": request.content_hash,
                    "target_url": request.target_url,
                    "anchor": getattr(edit, "anchor", ""),
                },
                source_versions=["content_inbound_link.v1"],
                score_version=SCORE_VERSION,
                priority_score=50,
                score_explanation={"score_policy_version": "opportunity_score.v2"},
                status="identified",
                version=1,
                attribution_state="attributed",
                candidate_pages=[],
            )
            session.add(opportunity)
            await session.flush()
        revision = await self.seo.create_recommendation(
            session,
            request.organization_id,
            opportunity.id,
            RecommendationCreate(
                proposed_action=(
                    f"Add an internal link to {request.target_url} on {page.normalized_url}."
                ),
                evidence_references=[f"seo-opportunity:{opportunity.id}"],
                expected_result_hypothesis=(
                    "A contextual link from a related page lets crawlers and readers reach "
                    "the new piece."
                ),
                risk="low",
                effort="low",
                change_set=change_set.model_dump(mode="json"),
            ),
            actor_id=request.actor_id,
            correlation_id=request.correlation_id,
        )
        return revision.id
