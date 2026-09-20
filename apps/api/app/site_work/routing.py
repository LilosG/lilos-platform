"""Shared classification for work that changes site code/templates rather than content assets."""

from __future__ import annotations

TECHNICAL_SITE_MARKERS = (
    "technical",
    "missing_h1",
    " h1",
    "title_tag",
    "meta_tag",
    "canonical",
    "structured_data",
    "schema_markup",
    "robots",
    "sitemap",
    "redirect",
    "template",
    "core_web_vitals",
    "pagespeed",
    "page_speed",
    " lcp",
    " cls",
    " inp",
)


def is_technical_site_change(*parts: str | None) -> bool:
    """Return True when the work belongs in governed site/SEO implementation.

    The classifier is deliberately narrow and deterministic. It is used both
    before Growth delegates work and again at Content publication as a
    defense-in-depth boundary for legacy/misrouted items.
    """
    haystack = " ".join(part or "" for part in parts).casefold().replace("-", "_")
    return any(marker in haystack for marker in TECHNICAL_SITE_MARKERS)
