"""What an opportunity is about, as typed fields, and the short headline of a growth plan.

The console builds every title from these fields. Content opportunities point at their
subject through a reference (`seo-opportunity:<uuid>`, `content-brief:<uuid>`, a page URL or
a bare query); this module resolves that reference once, in batch, to a search query and a
page path so no raw key, UUID or URL ever has to be shown.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.content.models import ContentBrief
from apps.api.app.products.seo.models import SEOOpportunity, SEOPage

GROWTH_HEADLINE_LIMIT = 90
_CLAUSE_END = re.compile(r"(?<=[.;:!?])\s|\s[—–]\s|\s-\s")
_REFERENCE = re.compile(r"^(seo-opportunity|content-brief):([0-9a-fA-F-]{36})(?:\s|$)")


@dataclass(frozen=True, slots=True)
class Subject:
    query: str | None = None
    path: str | None = None


def growth_headline(objective: str, limit: int = GROWTH_HEADLINE_LIMIT) -> str:
    """The plan's first clause, at most ``limit`` characters, cut at a word boundary."""
    text = " ".join(objective.split())
    clause = _CLAUSE_END.split(text, maxsplit=1)[0].rstrip(".;:,!? ")
    if len(clause) <= limit:
        return clause
    cut = clause[: limit - 1].rsplit(" ", 1)[0].rstrip(".;:,!? -—–")
    return f"{cut or clause[: limit - 1]}…"


def url_path(value: str) -> str:
    return urlparse(value).path or "/"


def _literal(reference: str) -> Subject:
    if reference.startswith(("http://", "https://")):
        return Subject(path=url_path(reference))
    if reference.startswith("/"):
        return Subject(path=reference)
    return Subject(query=reference or None)


def evidence_subject(evidence: dict[str, object], page_url: str | None) -> Subject:
    query = evidence.get("query")
    url = evidence.get("url")
    return Subject(
        query=query if isinstance(query, str) and query else None,
        path=url_path(page_url)
        if page_url
        else url_path(url)
        if isinstance(url, str) and url
        else None,
    )


async def content_subjects(
    session: AsyncSession, references: Iterable[tuple[UUID, str]]
) -> dict[tuple[UUID, str], Subject]:
    """Resolve ``(organization_id, target_reference)`` pairs. Unresolvable ones are empty."""
    pairs = set(references)
    resolved: dict[tuple[UUID, str], Subject] = {}
    seo_ids: dict[tuple[UUID, str], UUID] = {}
    brief_ids: dict[tuple[UUID, str], UUID] = {}
    for organization_id, reference in pairs:
        match = _REFERENCE.match(reference)
        if match is None:
            resolved[(organization_id, reference)] = _literal(reference)
            continue
        pending = seo_ids if match.group(1) == "seo-opportunity" else brief_ids
        try:
            pending[(organization_id, reference)] = UUID(match.group(2))
        except ValueError:
            resolved[(organization_id, reference)] = Subject()
    organizations = {organization_id for organization_id, _ in pairs}
    if brief_ids:
        briefs = {
            (organization_id, brief_id): target
            for brief_id, organization_id, target in await session.execute(
                select(
                    ContentBrief.id, ContentBrief.organization_id, ContentBrief.target_reference
                ).where(
                    ContentBrief.organization_id.in_(organizations),
                    ContentBrief.id.in_(set(brief_ids.values())),
                )
            )
        }
        for key, brief_id in brief_ids.items():
            target = briefs.get((key[0], brief_id))
            resolved[key] = _literal(target) if target else Subject()
    if seo_ids:
        rows = {
            (organization_id, opportunity_id): (evidence, page_id)
            for opportunity_id, organization_id, evidence, page_id in await session.execute(
                select(
                    SEOOpportunity.id,
                    SEOOpportunity.organization_id,
                    SEOOpportunity.evidence,
                    SEOOpportunity.page_id,
                ).where(
                    SEOOpportunity.organization_id.in_(organizations),
                    SEOOpportunity.id.in_(set(seo_ids.values())),
                )
            )
        }
        page_urls = {
            (organization_id, page_id): url
            for page_id, organization_id, url in await session.execute(
                select(SEOPage.id, SEOPage.organization_id, SEOPage.normalized_url).where(
                    SEOPage.organization_id.in_(organizations),
                    SEOPage.id.in_({page for _, page in rows.values() if page is not None}),
                )
            )
        }
        for key, opportunity_id in seo_ids.items():
            found = rows.get((key[0], opportunity_id))
            resolved[key] = (
                evidence_subject(found[0] or {}, page_urls.get((key[0], found[1])))
                if found
                else Subject()
            )
    return resolved
