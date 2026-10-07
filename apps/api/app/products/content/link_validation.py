"""Deterministic internal-link rules for generated content.

Pure functions, no I/O: the verified page inventory is passed in. A draft's links
are checked against pages that really exist (crawled pages and existing content),
anchors must be descriptive and distinct, and long-form pieces must link to the
commercial pages the topic needs, not only to other posts. Failures are typed codes
that the bounded repair attempt and the console both consume.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

_LINK = re.compile(r"(?<!!)\[([^\]\n]+)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_WORD = re.compile(r"[a-z0-9]+")

# Same anchor and URL used more than once is stuffing; one URL linked more than this
# many times is over-linking even with varied anchors.
MAX_LINKS_TO_ONE_URL = 2
MIN_ANCHOR_WORDS = 2

GENERIC_ANCHORS = frozenset(
    {
        "click here",
        "here",
        "read more",
        "learn more",
        "more",
        "this page",
        "this link",
        "this post",
        "this article",
        "link",
        "website",
        "our website",
        "visit",
        "visit us",
        "check it out",
        "see more",
        "find out more",
        "go here",
    }
)


class PageKind(StrEnum):
    """What a first-party page is for, derived from its URL path."""

    SERVICE = "service"
    MENU = "menu"
    LOCATION = "location"
    RESERVATION = "reservation"
    CONTACT = "contact"
    CONTENT = "content"
    OTHER = "other"


COMMERCIAL_KINDS = frozenset(
    {PageKind.SERVICE, PageKind.MENU, PageKind.LOCATION, PageKind.RESERVATION, PageKind.CONTACT}
)

_KIND_TOKENS: tuple[tuple[PageKind, frozenset[str]], ...] = (
    (PageKind.RESERVATION, frozenset({"reservations", "reservation", "reserve", "book", "booking"})),
    (PageKind.MENU, frozenset({"menu", "menus", "drinks", "food", "order", "catering"})),
    (PageKind.SERVICE, frozenset({"services", "service", "repair", "install", "installation"})),
    (PageKind.LOCATION, frozenset({"locations", "location", "areas", "service-areas", "visit"})),
    (PageKind.CONTACT, frozenset({"contact", "contact-us", "quote", "estimate"})),
    (PageKind.CONTENT, frozenset({"blog", "blogs", "news", "guides", "guide", "articles", "posts"})),
)


class LinkCode(StrEnum):
    """Typed failures. Values match the existing `article_*` quality-check codes."""

    LINKS_MISSING = "article_internal_links_missing"
    UNVERIFIED = "article_internal_link_unverified"
    ANCHOR_GENERIC = "article_anchor_generic"
    ANCHOR_STUFFING = "article_anchor_stuffing"
    ANCHOR_AMBIGUOUS = "article_anchor_ambiguous"
    COMMERCIAL_MISSING = "article_commercial_link_missing"


@dataclass(frozen=True, slots=True)
class InventoryPage:
    """One first-party URL that exists, with what it is."""

    url: str
    kind: PageKind
    title: str | None = None
    source: str = "crawl"  # "crawl" | "content"


@dataclass(frozen=True, slots=True)
class DraftLink:
    anchor: str
    url: str


def normalize_path(url: str, origin_host: str | None = None) -> str | None:
    """Return a canonical first-party path, or None for an external/non-page link."""
    value = url.strip()
    if not value or value.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        host = parts.netloc.casefold().removeprefix("www.")
        if not origin_host or host != origin_host.casefold().removeprefix("www."):
            return None
    path = parts.path or "/"
    if not path.startswith("/"):
        return None
    path = re.sub(r"/{2,}", "/", path).casefold()
    return path if path == "/" else path.rstrip("/")


def classify_page_kind(path: str) -> PageKind:
    """Deterministic page kind from URL path segments."""
    segments = [segment for segment in path.casefold().split("/") if segment]
    if not segments:
        return PageKind.OTHER
    for kind, tokens in _KIND_TOKENS:
        if any(segment in tokens for segment in segments[:2]):
            return kind
    return PageKind.OTHER


def build_inventory(
    pages: Iterable[Mapping[str, object]],
    *,
    origin_host: str | None = None,
) -> list[InventoryPage]:
    """Build the verified inventory from `{url, title?, source?}` rows, deduplicated."""
    seen: dict[str, InventoryPage] = {}
    for row in pages:
        path = normalize_path(str(row.get("url") or ""), origin_host)
        if path is None or path in seen:
            continue
        title = row.get("title")
        source = str(row.get("source") or "crawl")
        kind = classify_page_kind(path)
        if source == "content" and kind is PageKind.OTHER:
            kind = PageKind.CONTENT
        seen[path] = InventoryPage(
            url=path, kind=kind, title=str(title) if title else None, source=source
        )
    return list(seen.values())


def extract_internal_links(draft: str, *, origin_host: str | None = None) -> list[DraftLink]:
    """Every first-party markdown link in the draft, in order."""
    links: list[DraftLink] = []
    for match in _LINK.finditer(draft):
        path = normalize_path(match.group(2), origin_host)
        if path is not None:
            links.append(DraftLink(anchor=" ".join(match.group(1).split()), url=path))
    return links


def _anchor_key(anchor: str) -> str:
    return " ".join(_WORD.findall(anchor.casefold()))


def validate_links(
    draft: str,
    inventory: Sequence[InventoryPage],
    *,
    minimum_links: int,
    origin_host: str | None = None,
    require_commercial: bool = True,
) -> list[LinkCode]:
    """Typed link failures for one draft. Empty means the links are acceptable."""
    links = extract_internal_links(draft, origin_host=origin_host)
    known = {page.url: page for page in inventory}
    codes: set[LinkCode] = set()

    if any(link.url not in known for link in links):
        codes.add(LinkCode.UNVERIFIED)

    verified_urls = {link.url for link in links if link.url in known}
    if known and len(verified_urls) < min(minimum_links, len(known)):
        codes.add(LinkCode.LINKS_MISSING)

    seen_pair: dict[tuple[str, str], int] = {}
    anchor_targets: dict[str, set[str]] = {}
    per_url: dict[str, int] = {}
    for link in links:
        key = _anchor_key(link.anchor)
        if key in GENERIC_ANCHORS or len(key.split()) < MIN_ANCHOR_WORDS:
            codes.add(LinkCode.ANCHOR_GENERIC)
        seen_pair[(key, link.url)] = seen_pair.get((key, link.url), 0) + 1
        anchor_targets.setdefault(key, set()).add(link.url)
        per_url[link.url] = per_url.get(link.url, 0) + 1
    if any(count > 1 for count in seen_pair.values()) or any(
        count > MAX_LINKS_TO_ONE_URL for count in per_url.values()
    ):
        codes.add(LinkCode.ANCHOR_STUFFING)
    if any(len(targets) > 1 for targets in anchor_targets.values()):
        codes.add(LinkCode.ANCHOR_AMBIGUOUS)

    if require_commercial and any(page.kind in COMMERCIAL_KINDS for page in inventory):
        linked_commercial = any(
            known[link.url].kind in COMMERCIAL_KINDS for link in links if link.url in known
        )
        if not linked_commercial:
            codes.add(LinkCode.COMMERCIAL_MISSING)
    return sorted(codes)


def rank_link_targets(
    inventory: Sequence[InventoryPage], topic: str, *, limit: int = 12
) -> list[InventoryPage]:
    """Inventory pages ordered by topical relevance, commercial pages first on ties."""
    topic_tokens = set(_WORD.findall(topic.casefold()))

    def score(page: InventoryPage) -> tuple[int, int]:
        text = f"{page.url.replace('/', ' ').replace('-', ' ')} {page.title or ''}".casefold()
        overlap = len(topic_tokens & set(_WORD.findall(text)))
        return (overlap, 1 if page.kind in COMMERCIAL_KINDS else 0)

    return sorted(inventory, key=score, reverse=True)[:limit]


@dataclass(frozen=True, slots=True)
class InboundLinkEdit:
    before: str
    after: str
    anchor: str


def build_inbound_link_edit(
    current_value: str, *, target_url: str, phrases: Sequence[str]
) -> InboundLinkEdit | None:
    """Wrap the first natural mention of the new piece's topic in a link.

    `current_value` is text read from the live file, so `before` is exact. The anchor is
    a phrase already present in that text (never invented), at least two words, not
    generic, and not inside an existing link or heading. Returns None when no phrase
    matches, so a page with no natural mention is skipped rather than forced.
    """
    if f"]({target_url}" in current_value:
        return None
    for phrase in sorted({p.strip() for p in phrases if p.strip()}, key=len, reverse=True):
        key = _anchor_key(phrase)
        if len(key.split()) < MIN_ANCHOR_WORDS or key in GENERIC_ANCHORS:
            continue
        pattern = re.compile(rf"(?<![\[\w]){re.escape(phrase)}(?![\w\]])", re.IGNORECASE)
        for match in pattern.finditer(current_value):
            line_start = current_value.rfind("\n", 0, match.start()) + 1
            line = current_value[line_start : match.start()]
            if line.lstrip().startswith("#"):
                continue
            if re.search(r"\]\([^)]*$", line) or re.search(r"\[[^\]]*$", line):
                continue
            anchor = match.group(0)
            after = (
                current_value[: match.start()]
                + f"[{anchor}]({target_url})"
                + current_value[match.end() :]
            )
            return InboundLinkEdit(before=current_value, after=after, anchor=anchor)
    return None
