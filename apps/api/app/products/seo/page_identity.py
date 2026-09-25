"""Shared, versioned resolution of provider URLs to canonical SEO pages."""

from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.seo.crawl_engine import canonicalize_url, normalize_crawl_url
from apps.api.app.products.seo.models import SEOPage

RESOLVER_VERSION = "page_identity.v1"


@dataclass(frozen=True, slots=True)
class PageResolution:
    raw_reference: str | None
    normalized_url: str | None
    state: str
    page_id: UUID | None
    basis: str | None
    limitation: str | None
    resolver_version: str = RESOLVER_VERSION


def _identity(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parts = urlsplit(url)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return None
        return canonicalize_url(normalize_crawl_url(url))
    except ValueError:
        return None


class PageResolver:
    """One scoped inventory snapshot reused across a provider report's rows."""

    def __init__(self, pages: list[SEOPage]) -> None:
        self.exact: dict[str, list[UUID]] = {}
        self.aliases: dict[str, dict[UUID, str]] = {}
        for page in pages:
            self.exact.setdefault(page.normalized_url, []).append(page.id)
            page_host = urlsplit(page.normalized_url).hostname
            for basis, candidate in (
                ("observed_canonical", page.canonical_url),
                ("observed_redirect", page.redirect_destination),
            ):
                alias = _identity(candidate)
                if alias is not None and urlsplit(alias).hostname == page_host:
                    self.aliases.setdefault(alias, {})[page.id] = basis

    @classmethod
    async def load(
        cls, session: AsyncSession, organization_id: UUID, website_id: UUID
    ) -> "PageResolver":
        pages = list(
            await session.scalars(
                select(SEOPage).where(
                    SEOPage.organization_id == organization_id,
                    SEOPage.website_id == website_id,
                )
            )
        )
        return cls(pages)

    def resolve(self, raw_reference: str | None) -> PageResolution:
        """Map exact identity only; retain observed relationships as evidence."""
        normalized = _identity(raw_reference)
        if normalized is None:
            return PageResolution(
                raw_reference,
                None,
                "unknown",
                None,
                None,
                "No valid absolute page URL was provided.",
            )
        exact = self.exact.get(normalized, [])
        if len(exact) == 1:
            return PageResolution(raw_reference, normalized, "mapped", exact[0], "exact", None)
        if len(exact) > 1:
            return PageResolution(
                raw_reference, normalized, "ambiguous", None, None, "Multiple exact pages matched."
            )
        aliases = self.aliases.get(normalized, {})
        if len(aliases) == 1:
            basis = next(iter(aliases.values()))
            return PageResolution(
                raw_reference,
                normalized,
                "unmapped",
                None,
                basis,
                "A source page references this URL, but no exact destination page identity exists.",
            )
        if aliases:
            return PageResolution(
                raw_reference,
                normalized,
                "ambiguous",
                None,
                None,
                "Multiple evidenced page relationships matched.",
            )
        return PageResolution(
            raw_reference,
            normalized,
            "unmapped",
            None,
            None,
            "No page identity match was observed in this website inventory.",
        )


async def resolve_page(
    session: AsyncSession, organization_id: UUID, website_id: UUID, raw_reference: str | None
) -> PageResolution:
    """Resolve one reference for callers without an existing scoped inventory."""
    resolver = await PageResolver.load(session, organization_id, website_id)
    return resolver.resolve(raw_reference)
