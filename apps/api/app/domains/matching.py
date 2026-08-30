"""Canonical domain/origin correspondence.

Two tables describe the same website from different angles: an
``OrganizationDomain`` holds a bare hostname the agency configured, and an
``SEOWebsite`` holds a canonical origin the crawler starts from. Deciding
whether one belongs to the other was previously a private helper inside the
administration service, so every other module that needed the same answer had
either no answer or its own. That is why a client could show a green
"Configured · Primary" domain and "no website connected" at the same time.

This module is the single definition, and it is deliberately platform-level:
it depends on neither the domains module nor any product, so both may use it.
"""

import re
from urllib.parse import urlparse

_UNSAFE_KEY_CHARACTERS = re.compile(r"[^a-z0-9]+")

# ``seo_websites.key`` is String(100).
WEBSITE_KEY_MAX_LENGTH = 100


def origin_host(canonical_origin: str) -> str | None:
    """Return the lowercase hostname of a canonical origin, or None if unusable."""
    try:
        host = (urlparse(canonical_origin).hostname or "").lower().strip(".")
    except ValueError:
        return None
    return host or None


def origin_matches_domain(canonical_origin: str, domain: str) -> bool:
    """Return True when a website's canonical origin belongs to the domain.

    A subdomain belongs to its parent domain (``www.example.com`` matches
    ``example.com``), which is what makes an agency-entered bare domain line up
    with a canonical origin that the site itself redirects to.
    """
    host = origin_host(canonical_origin)
    if host is None:
        return False
    domain_clean = domain.lower().strip(".")
    if not domain_clean:
        return False
    return host == domain_clean or host.endswith(f".{domain_clean}")


def canonical_origin_for_domain(domain: str) -> str:
    """Return the origin a crawl should start from for a bare domain.

    HTTPS is assumed rather than probed: the crawler follows redirects, so an
    HTTP-only site still resolves, while defaulting to HTTP would downgrade
    every well-configured site.
    """
    return f"https://{domain.lower().strip('.')}"


def website_key_for_domain(domain: str, *, taken: set[str] | None = None) -> str:
    """Return a stable, unique-per-organization website key for a domain.

    Derived from the domain so the same domain always produces the same key,
    which is what makes provisioning idempotent. ``seo_websites`` has a unique
    constraint on (organization_id, key); when a key is already used by an
    unrelated website, a numeric suffix is appended deterministically rather
    than failing the caller.
    """
    slug = _UNSAFE_KEY_CHARACTERS.sub("-", domain.lower()).strip("-")
    base = (slug or "website")[:WEBSITE_KEY_MAX_LENGTH]
    if not taken or base not in taken:
        return base
    for suffix in range(2, 100):
        tail = f"-{suffix}"
        candidate = f"{base[: WEBSITE_KEY_MAX_LENGTH - len(tail)]}{tail}"
        if candidate not in taken:
            return candidate
    # 98 collisions on one domain slug is not a real state; fail loudly rather
    # than silently reusing a key and tripping the unique constraint.
    raise ValueError(f"unable to derive an unused website key for {domain!r}")
