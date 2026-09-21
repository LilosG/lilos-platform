"""Shared classification policy for editorial content versus technical site work.

Growth planning and legacy Content records must make the same routing decision.
Technical/template/code changes belong to the governed SEO implementation path;
substantive editorial assets remain in Content.
"""

from __future__ import annotations

import re

_STRONG_TECHNICAL_MARKERS = (
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

_TECHNICAL_CONTEXT_MARKERS = (
    "fix",
    "implementation",
    "remediation",
    "site",
    "website",
    "page",
    "template",
    "code",
)


def is_technical_site_change(*parts: str | None) -> bool:
    """Return true only for site-code/template remediation, not editorial copy."""
    haystack = " ".join(part or "" for part in parts).casefold().replace("-", "_")
    haystack = re.sub(r"\s+", " ", haystack)
    if any(marker in haystack for marker in _STRONG_TECHNICAL_MARKERS):
        return True
    return "technical" in haystack and any(
        marker in haystack for marker in _TECHNICAL_CONTEXT_MARKERS
    )
