"""Single source of truth for SEO crawl page/depth limits.

Every layer that bounds a crawl — the API request contract, the crawl engine
default, and the web operator UI — reads these constants instead of each
declaring its own ceiling. Before this module existed, three different
numbers governed the same crawl (UI 20, API default 50, engine default 250),
so every client's stored crawl was silently truncated far below their real
site size. The web app fetches these values from `GET /seo/crawl-limits`
rather than hardcoding a parallel constant.
"""

from __future__ import annotations

DEFAULT_MAX_PAGES = 300
MAX_MAX_PAGES = 500
MIN_MAX_PAGES = 1

DEFAULT_MAX_DEPTH = 5
MAX_MAX_DEPTH = 10
MIN_MAX_DEPTH = 1


def crawl_limits_payload() -> dict[str, int]:
    """Serialize the shared bounds for the crawl-limits API response."""
    return {
        "default_max_pages": DEFAULT_MAX_PAGES,
        "max_max_pages": MAX_MAX_PAGES,
        "min_max_pages": MIN_MAX_PAGES,
        "default_max_depth": DEFAULT_MAX_DEPTH,
        "max_max_depth": MAX_MAX_DEPTH,
        "min_max_depth": MIN_MAX_DEPTH,
    }
