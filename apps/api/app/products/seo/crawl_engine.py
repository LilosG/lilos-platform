"""Bounded, same-host, polite SEO crawl engine with link discovery and robots/sitemap support.

The engine is deliberately free of any database or workflow dependency: it is a
pure, deterministic traversal that yields per-page observations through an async
callback.  ``SEOService`` persists those observations incrementally inside the
durable worker, so a crawl that times out or errors retains the pages already
fetched.
"""

import asyncio
import hashlib
import re
import xml.etree.ElementTree as ET
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from time import monotonic
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

LILOS_USER_AGENT = "LILOs-Crawler/1.0 (+https://lilos.io)"

# Documented ingest limits. Content columns (title, meta_description, h1) are
# truncated at MAX_CONTENT_LENGTH with an explicit marker; URL columns are
# widened to text in the schema but capped at MAX_URL_LENGTH so the
# uq_seo_page_normalized_url btree index stays within PostgreSQL's ~2704-byte
# per-entry limit (see migration 20260817_0001).
MAX_URL_LENGTH = 2048
MAX_CONTENT_LENGTH = 2000
CONTENT_TRUNCATION_MARKER = "…[truncated]"

ANCHOR_TAG_PATTERN = re.compile(r"<a\b[^>]*>", re.IGNORECASE)
ANCHOR_HREF_ATTR_PATTERN = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
ANCHOR_NOFOLLOW_PATTERN = re.compile(
    r"""rel\s*=\s*["'][^"']*\bnofollow\b[^"']*["']""", re.IGNORECASE
)
TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
# Tag scanners. Deliberately NOT one regex per attribute pair.
#
# The previous patterns were of the form
#   <meta[^>]+name=["']description["'][^>]+content=["']([^"']*)["']
# which is wrong in three ways that all produced false SEO findings against
# real client sites:
#
#   1. It required `name` to appear before `content`. HTML attribute order is
#      arbitrary, and `<meta content="..." name="description">` is emitted by
#      several generators and minifiers. No match, so the page was reported as
#      missing_meta_description while the tag was plainly there.
#   2. The capture group `[^"']*` stops at the first apostrophe, so
#      content="Carlsbad's best plumber" captured just "Carlsbad" — a silently
#      corrupted value that then fed length checks and AI content generation.
#   3. It required quoted values, so `name=description` never matched.
#
# The robots variant mattered most: a page marked noindex via
# `<meta content="noindex" name="robots">` was read as indexable and ingested.
#
# These scan for the tag, then parse its attributes properly, which is order-
# independent, quote-style independent, and apostrophe-safe.
META_TAG_PATTERN = re.compile(r"<meta\b([^>]*)>", re.IGNORECASE)
LINK_TAG_PATTERN = re.compile(r"<link\b([^>]*)>", re.IGNORECASE)
# Attribute values may be double-quoted, single-quoted, or bare.
_ATTRIBUTE_PATTERN = re.compile(
    r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)      # attribute name
        (?:\s*=\s*
          (?: "([^"]*)"                    # double-quoted value
            | '([^']*)'                    # single-quoted value
            | ([^\s"'=<>`]+)               # bare value
          )
        )?""",
    re.VERBOSE,
)
H1_PATTERN = re.compile(r"<h1[^>]*>", re.IGNORECASE)


def _tag_attributes(attribute_text: str) -> dict[str, str]:
    """Parse a tag's attributes into a lowercased name -> value mapping.

    A valueless attribute maps to the empty string. Later duplicates lose to
    the first, matching how browsers resolve repeated attributes.
    """
    attributes: dict[str, str] = {}
    for match in _ATTRIBUTE_PATTERN.finditer(attribute_text):
        name = match.group(1).lower()
        if name in attributes:
            continue
        double, single, bare = match.group(2), match.group(3), match.group(4)
        value = double if double is not None else single if single is not None else bare
        attributes[name] = value if value is not None else ""
    return attributes


def _meta_content(html: str, meta_name: str) -> str | None:
    """Return the content of ``<meta name="...">``, whatever the attribute order.

    Matching on ``name`` is case-insensitive because HTML attribute values here
    are keywords, not data — ``name="Description"`` is the same tag.
    """
    wanted = meta_name.lower()
    for match in META_TAG_PATTERN.finditer(html):
        attributes = _tag_attributes(match.group(1))
        if attributes.get("name", "").strip().lower() != wanted:
            continue
        content = attributes.get("content")
        if content is not None:
            return content
    return None


def _link_href(html: str, rel: str) -> str | None:
    """Return the href of ``<link rel="...">``, whatever the attribute order.

    ``rel`` is a space-separated token list, so this matches on membership
    rather than string equality — ``rel="canonical alternate"`` still counts.
    """
    wanted = rel.lower()
    for match in LINK_TAG_PATTERN.finditer(html):
        attributes = _tag_attributes(match.group(1))
        if wanted not in attributes.get("rel", "").lower().split():
            continue
        href = attributes.get("href")
        if href is not None:
            return href
    return None


SCRIPT_STYLE_PATTERN = re.compile(
    r"<(?:script|style|noscript|iframe|svg|canvas|template)[^>]*>.*?"
    r"</(?:script|style|noscript|iframe|svg|canvas|template)>",
    re.IGNORECASE | re.DOTALL,
)
STRUCTURED_DATA_PATTERN = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\']', re.IGNORECASE
)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True, slots=True)
class CrawlConfig:
    """Bounds and behaviour for a single crawl. Values come from the confirmed
    website origin and the operator-supplied crawl command."""

    base_origin: str
    allowed_host: str
    seeds: tuple[str, ...]
    max_pages: int = 250
    max_depth: int = 3
    crawl_delay: float = 1.0
    request_timeout: float = 10.0
    total_timeout: float = 600.0
    max_redirects: int = 5
    concurrency: int = 4
    user_agent: str = LILOS_USER_AGENT
    retry_limit: int = 2
    query_param_policy: str = "keep"
    exclusion_patterns: tuple[str, ...] = ()
    max_url_length: int = MAX_URL_LENGTH


@dataclass
class CrawledPage:
    url: str
    observed_url: str
    http_status: int | None = None
    content_type: str | None = None
    title: str | None = None
    meta_description: str | None = None
    h1: str | None = None
    body_text: str | None = None
    canonical_url: str | None = None
    robots_directives: list[str] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    word_count: int | None = None
    structured_data_present: bool = False
    content_hash: str | None = None
    indexability: str = "unknown"
    technical_issues: list[str] = field(default_factory=list)
    quality_status: str = "clean"
    redirect_destination: str | None = None
    depth: int = 0
    error: str | None = None


@dataclass
class CrawlReport:
    terminal_state: str  # success | partial | error
    reason: str
    pages_fetched: int = 0
    pages_queued: int = 0
    pages_skipped: int = 0
    skip_reasons: list[str] = field(default_factory=list)
    max_depth_reached: int = 0
    robots_available: bool = False
    robots_disallowed: list[str] = field(default_factory=list)
    sitemap_file_urls: list[str] = field(default_factory=list)
    sitemap_page_urls: list[str] = field(default_factory=list)
    sitemap_page_count: int = 0
    sitemap_not_reached: list[str] = field(default_factory=list)
    crawled_not_in_sitemap: list[str] = field(default_factory=list)
    sitemap_non_indexable: list[str] = field(default_factory=list)


def _urlparse_absolute(url: str) -> Any:
    return urlparse(url)


def _absolute_url(url: str, base: str) -> str:
    return urljoin(base, url)


def _strip_query(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def normalize_crawl_url(url: str, base: str = "", strip_query: bool = False) -> str:
    absolute = _absolute_url(url, base) if base else url
    parsed = urlparse(absolute)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    netloc = host
    if parsed.port and (scheme, parsed.port) not in {("http", 80), ("https", 443)}:
        netloc = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    query = "" if strip_query else parsed.query
    return urlunparse((scheme, netloc, path, query, "", ""))


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    netloc = host
    if parsed.port and (scheme, parsed.port) not in {("http", 80), ("https", 443)}:
        netloc = f"{host}:{parsed.port}"
    path = parsed.path or "/"
    path = re.sub(r"/{2,}", "/", path)
    while "/./" in path:
        path = path.replace("/./", "/")
    changed = True
    while changed:
        changed = False
        new_path = re.sub(r"/[^/]+/\.\./", "/", path)
        if new_path != path:
            path = new_path
            changed = True
    if path.endswith("/."):
        path = path[:-2]
    return urlunparse((scheme, netloc, path, parsed.query, "", ""))


def host_of(url: str) -> str:
    return urlparse(url).hostname or ""


def same_host(host_a: str, host_b: str) -> bool:
    return host_a.casefold() == host_b.casefold()


def parse_robots_txt(
    text: str, user_agent: str = LILOS_USER_AGENT
) -> tuple[list[str], list[str], list[str]]:
    """Return ``(disallow_rules, allow_rules, sitemap_urls)`` from a robots.txt body."""
    disallow: list[str] = []
    allow: list[str] = []
    sitemaps: list[str] = []
    active_group = False
    agent_matched = False

    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        field, _, value = line.partition(":")
        field = field.strip().lower()
        value = value.strip()

        if field == "user-agent":
            agent_matched = value == "*" or user_agent.lower() in value.lower()
            active_group = agent_matched
        elif field == "sitemap":
            if value:
                sitemaps.append(value)
        elif active_group and field == "disallow":
            if value:
                disallow.append(value)
        elif active_group and field == "allow":
            if value:
                allow.append(value)

    return disallow, allow, sitemaps


def _rule_match_length(rule: str, normalized_path: str) -> int:
    """Return the number of path octets matched by ``rule``, or -1 for no match."""
    if not rule:
        return -1
    pattern = rule
    anchor_end = pattern.endswith("$")
    if anchor_end:
        pattern = pattern[:-1]
    pattern = pattern.lstrip("/")
    if pattern.endswith("*"):
        prefix = pattern[:-1]
        if normalized_path.startswith(prefix):
            return len(prefix)
        return -1
    if normalized_path == pattern:
        return len(pattern)
    if normalized_path.startswith(pattern.rstrip("/") + "/"):
        return len(pattern.rstrip("/"))
    return -1


def is_disallowed(
    path: str, disallow_rules: list[str], allow_rules: list[str] | None = None
) -> bool:
    """Decide whether ``path`` is blocked, honouring RFC 9309 precedence.

    The most specific (longest matching) rule wins; on equal specificity an
    ``Allow`` rule overrides a broader ``Disallow`` rule.
    """
    normalized_path = path.lstrip("/")
    best_rule: str | None = None
    best_length = -1
    for rule in disallow_rules:
        length = _rule_match_length(rule, normalized_path)
        if length >= 0 and length > best_length:
            best_length = length
            best_rule = "disallow"
    if allow_rules:
        for rule in allow_rules:
            length = _rule_match_length(rule, normalized_path)
            if length >= 0 and length >= best_length:
                best_length = length
                best_rule = "allow"
    return best_rule == "disallow"


_SM_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _sitemap_locs(xml_text: str, tag: str) -> list[str]:
    locs: list[str] = []
    try:
        root = ET.fromstring(xml_text)
        for elem in root.iter(f"{{{_SM_NS['sm']}}}{tag}"):
            loc = elem.find(f"{{{_SM_NS['sm']}}}loc")
            if loc is not None and loc.text and loc.text.strip():
                locs.append(loc.text.strip())
    except (ET.ParseError, ValueError):
        pass
    return locs


def parse_sitemap_index(xml_text: str) -> list[str]:
    return _sitemap_locs(xml_text, "sitemap")


def parse_sitemap(xml_text: str) -> list[str]:
    return _sitemap_locs(xml_text, "url")


def extract_links(html: str, base_url: str) -> tuple[list[str], list[str], list[str]]:
    """Return ``(internal, external, nofollow)`` absolute link URLs.

    ``nofollow`` lists URLs whose anchor carries ``rel="nofollow"``. They are
    still inventory but must not be traversed.
    """
    internal: list[str] = []
    external: list[str] = []
    nofollow: list[str] = []
    base_host = host_of(base_url)
    for tag in ANCHOR_TAG_PATTERN.findall(html):
        href_match = ANCHOR_HREF_ATTR_PATTERN.search(tag)
        if not href_match:
            continue
        href = href_match.group(1).strip()
        if not href or href.lower().startswith(
            ("#", "javascript:", "mailto:", "tel:", "data:", "ftp:")
        ):
            continue
        absolute = normalize_crawl_url(href, base_url)
        link_host = host_of(absolute)
        if not link_host:
            continue
        is_nofollow = bool(ANCHOR_NOFOLLOW_PATTERN.search(tag))
        if same_host(link_host, base_host):
            internal.append(absolute)
        else:
            external.append(absolute)
        if is_nofollow:
            nofollow.append(absolute)
    return internal, external, nofollow


def _parse_content_type(response: httpx.Response) -> str | None:
    ct = response.headers.get("content-type", "")
    if ";" in ct:
        ct = ct.split(";", 1)[0]
    return ct.strip().lower() or None


def _truncate_content(value: str | None) -> tuple[str | None, bool]:
    """Bound a content signal to ``MAX_CONTENT_LENGTH`` with an explicit marker.

    Returns ``(value, truncated)``. A value at or under the limit is returned
    unchanged with ``truncated=False``. An over-limit value is cut to make room
    for ``CONTENT_TRUNCATION_MARKER`` so the marker — not silent loss — records
    that truncation occurred.
    """
    if value is None or len(value) <= MAX_CONTENT_LENGTH:
        return value, False
    keep = MAX_CONTENT_LENGTH - len(CONTENT_TRUNCATION_MARKER)
    return value[:keep] + CONTENT_TRUNCATION_MARKER, True


def _extract_body_text(html: str) -> str | None:
    """Extract normalized visible text from an HTML page body.

    Strips ``<script>``, ``<style>``, ``<noscript>`` blocks, then removes
    all remaining HTML tags and collapses whitespace.  Returns ``None``
    when no meaningful text remains.
    """
    import re as _re

    # Remove script, style, noscript blocks
    clean = _re.sub(
        r"<(script|style|noscript)[^>]*>.*?</\1>",
        "",
        html,
        flags=_re.DOTALL | _re.IGNORECASE,
    )
    # Remove HTML comments
    clean = _re.sub(r"<!--.*?-->", "", clean, flags=_re.DOTALL)
    # Remove all remaining tags
    clean = _re.sub(r"<[^>]+>", " ", clean)
    # Decode common entities
    clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    clean = clean.replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " ")
    # Collapse whitespace
    clean = _re.sub(r"\s+", " ", clean).strip()

    return clean if clean else None


def extract_page_signals(
    html: str, http_status: int, base_url: str, robots_directives: list[str]
) -> dict[str, Any]:
    title_match = TITLE_PATTERN.search(html)
    title, title_truncated = _truncate_content(
        title_match.group(1).strip() if title_match else None
    )

    raw_description = _meta_content(html, "description")
    meta_description, meta_description_truncated = _truncate_content(
        raw_description.strip() if raw_description is not None else None
    )

    canonical_href = _link_href(html, "canonical")
    canonical_url = None
    canonical_url_too_long = False
    if canonical_href is not None and canonical_href.strip():
        candidate = normalize_crawl_url(canonical_href.strip(), base_url)
        if len(candidate) <= MAX_URL_LENGTH:
            canonical_url = candidate
        else:
            canonical_url_too_long = True

    h1_matches = H1_PATTERN.findall(html)
    h1_count = len(h1_matches)
    h1_text: str | None = None
    h1_truncated = False
    if h1_matches:
        start = H1_PATTERN.search(html).end()  # type: ignore[union-attr]
        lower = html.lower()
        end_abs = lower.find("</h1>", start)
        end = start if end_abs < 0 else end_abs
        raw_h1 = HTML_TAG_PATTERN.sub("", html[start:end]).strip()
        h1_text, h1_truncated = _truncate_content(raw_h1 or None)

    stripped = SCRIPT_STYLE_PATTERN.sub("", html)
    text_only = HTML_TAG_PATTERN.sub(" ", stripped)
    words = text_only.split()
    word_count = len(words) if words else None

    structured_data_present = bool(STRUCTURED_DATA_PATTERN.search(html))
    content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

    indexability = "not_indexable" if "noindex" in robots_directives else "indexable"

    internal, external, nofollow = extract_links(html, base_url)

    technical_issues: list[str] = []
    if http_status != 200:
        technical_issues.append("non_200_status")
    if not title:
        technical_issues.append("missing_title")
    if not meta_description:
        technical_issues.append("missing_meta_description")
    if h1_count == 0:
        technical_issues.append("missing_h1")
    if h1_count > 1:
        technical_issues.append("multiple_h1")
    if title_truncated:
        technical_issues.append("title_truncated")
    if meta_description_truncated:
        technical_issues.append("meta_description_truncated")
    if h1_truncated:
        technical_issues.append("h1_truncated")
    if canonical_url_too_long:
        technical_issues.append("canonical_url_too_long")

    quality_status = "issues_detected" if technical_issues else "clean"

    return {
        "title": title,
        "meta_description": meta_description,
        "canonical_url": canonical_url,
        "h1": h1_text,
        "internal_links": internal,
        "external_links": external,
        "nofollow_links": nofollow,
        "word_count": word_count,
        "structured_data_present": structured_data_present,
        "content_hash": content_hash,
        "indexability": indexability,
        "technical_issues": technical_issues,
        "quality_status": quality_status,
    }


def compile_exclusions(raw: list[str]) -> list[re.Pattern[str]]:
    compiled: list[re.Pattern[str]] = []
    for pat in raw:
        try:
            compiled.append(re.compile(pat))
        except re.error:
            continue
    return compiled


OnPageCallback = Callable[[CrawledPage], Coroutine[Any, Any, None]]


class CrawlEngine:
    def __init__(self, config: CrawlConfig, http_client: httpx.AsyncClient) -> None:
        self.config = config
        self.client = http_client
        self._exclusions = compile_exclusions(list(config.exclusion_patterns))

    async def _fetch(self, url: str) -> tuple[httpx.Response | None, str, str | None]:
        error: str | None = None
        response: httpx.Response | None = None
        observed_url = url
        for attempt in range(self.config.retry_limit + 1):
            try:
                response = await self.client.get(
                    url,
                    timeout=self.config.request_timeout,
                    follow_redirects=True,
                    headers={"User-Agent": self.config.user_agent},
                )
                observed_url = str(response.url)
                error = None
                break
            except httpx.TimeoutException:
                error = "timeout"
            except httpx.RequestError as exc:
                error = f"request_error:{type(exc).__name__}"
            if attempt < self.config.retry_limit:
                await asyncio.sleep(0.5 * (attempt + 1))
        return response, observed_url, error

    def _is_excluded(self, url: str) -> bool:
        return any(pat.search(url) for pat in self._exclusions)

    async def crawl(self, on_page: OnPageCallback | None = None) -> CrawlReport:
        config = self.config
        started_at = monotonic()
        seen: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        pages_fetched = 0
        pages_queued = 0
        pages_skipped = 0
        skip_reasons: list[str] = []
        max_depth_reached = 0
        timed_out = False
        page_limit_reached = False
        crawled_urls: set[str] = set()
        non_indexable_urls: set[str] = set()

        robots_available = False
        disallow_rules: list[str] = []
        allow_rules: list[str] = []
        sitemap_file_urls: list[str] = []
        sitemap_page_urls: list[str] = []

        robots_url = f"{config.base_origin}/robots.txt"
        try:
            robots_resp = await asyncio.wait_for(
                self.client.get(
                    robots_url,
                    timeout=config.request_timeout,
                    headers={"User-Agent": config.user_agent},
                ),
                timeout=config.request_timeout,
            )
            if 200 <= robots_resp.status_code < 300:
                robots_available = True
                disallow_rules, allow_rules, sitemap_file_urls = parse_robots_txt(
                    robots_resp.text, config.user_agent
                )
        except Exception:
            pass

        sitemap_file_urls = [
            u for u in sitemap_file_urls if same_host(host_of(u), config.allowed_host)
        ]

        pending_sitemap_files: deque[str] = deque(sitemap_file_urls)
        visited_sitemap_files: set[str] = set()
        while pending_sitemap_files:
            sm_file = pending_sitemap_files.popleft()
            if sm_file in visited_sitemap_files:
                continue
            visited_sitemap_files.add(sm_file)
            try:
                sm_resp = await asyncio.wait_for(
                    self.client.get(
                        sm_file,
                        timeout=config.request_timeout,
                        headers={"User-Agent": config.user_agent},
                    ),
                    timeout=config.request_timeout,
                )
                if 200 <= sm_resp.status_code < 300:
                    text = sm_resp.text
                    index_entries = parse_sitemap_index(text)
                    if index_entries:
                        for idx_url in index_entries:
                            if same_host(host_of(idx_url), config.allowed_host):
                                if idx_url not in visited_sitemap_files:
                                    pending_sitemap_files.append(idx_url)
                                if idx_url not in sitemap_file_urls:
                                    sitemap_file_urls.append(idx_url)
                    else:
                        for page_url in parse_sitemap(text):
                            if same_host(host_of(page_url), config.allowed_host):
                                sitemap_page_urls.append(page_url)
            except Exception:
                continue

        def enqueue(url: str, depth: int) -> None:
            nonlocal pages_queued
            if url in seen:
                return
            seen.add(url)
            queue.append((url, depth))
            pages_queued += 1

        for seed in config.seeds:
            normalized = canonicalize_url(normalize_crawl_url(seed, config.base_origin))
            enqueue(normalized, 0)

        for page_url in sitemap_page_urls:
            normalized = canonicalize_url(normalize_crawl_url(page_url))
            enqueue(normalized, 1)

        request_lock = asyncio.Lock()
        last_request_at = 0.0

        async def throttle() -> None:
            nonlocal last_request_at
            async with request_lock:
                now = monotonic()
                wait_s = config.crawl_delay - (now - last_request_at)
                if wait_s > 0:
                    await asyncio.sleep(wait_s)
                last_request_at = monotonic()

        async def process_one(url: str, depth: int) -> None:
            nonlocal pages_fetched, pages_skipped

            if len(url) > config.max_url_length:
                pages_skipped += 1
                skip_reasons.append("url_too_long")
                return
            if self._is_excluded(url):
                return
            if _url_is_disallowed(url, disallow_rules, allow_rules):
                return

            await throttle()

            response, observed_url, error = await self._fetch(url)

            if error or response is None:
                page = CrawledPage(
                    url=url,
                    observed_url=observed_url,
                    http_status=None,
                    content_type=None,
                    depth=depth,
                    indexability="not_indexable",
                    technical_issues=["non_200_status"],
                    quality_status="issues_detected",
                    error=error,
                )
                pages_fetched += 1
                crawled_urls.add(url)
                non_indexable_urls.add(url)
                if on_page:
                    await on_page(page)
                return

            http_status = response.status_code
            content_type = _parse_content_type(response)

            observed_url_too_long = len(observed_url) > config.max_url_length
            if observed_url_too_long:
                observed_url = url

            redirect_dest: str | None = None
            redirect_destination_too_long = False
            if response.history:
                final_url = str(response.url)
                if final_url != url:
                    normalized_final = canonicalize_url(normalize_crawl_url(final_url))
                    if len(normalized_final) > config.max_url_length:
                        redirect_dest = None
                        redirect_destination_too_long = True
                    else:
                        redirect_dest = normalized_final
                        if (
                            same_host(host_of(final_url), config.allowed_host)
                            and final_url not in seen
                        ):
                            enqueue(normalized_final, depth)

            robots_directives: list[str] = []
            robots_content = _meta_content(response.text or "", "robots")
            if robots_content:
                robots_directives = [
                    directive.strip().lower()
                    for directive in robots_content.split(",")
                    if directive.strip()
                ]

            signals: dict[str, Any] = {}
            is_html = bool(content_type and "html" in content_type)
            if is_html and response.text:
                signals = extract_page_signals(
                    response.text, http_status, observed_url, robots_directives
                )

            extra_issues: list[str] = []
            if observed_url_too_long:
                extra_issues.append("observed_url_too_long")
            if redirect_destination_too_long:
                extra_issues.append("redirect_destination_too_long")

            technical_issues = list(signals.get("technical_issues", [])) + extra_issues
            quality_status = signals.get("quality_status", "clean")
            if extra_issues and quality_status == "clean":
                quality_status = "issues_detected"

            page = CrawledPage(
                url=url,
                observed_url=observed_url,
                http_status=http_status,
                content_type=content_type,
                title=signals.get("title"),
                meta_description=signals.get("meta_description"),
                h1=signals.get("h1"),
                body_text=(
                    _extract_body_text(response.text) if is_html and response.text else None
                ),
                canonical_url=signals.get("canonical_url"),
                robots_directives=robots_directives,
                internal_links=signals.get("internal_links", []),
                external_links=signals.get("external_links", []),
                word_count=signals.get("word_count"),
                structured_data_present=signals.get("structured_data_present", False),
                content_hash=signals.get("content_hash"),
                indexability=signals.get(
                    "indexability", "indexable" if http_status == 200 else "not_indexable"
                ),
                technical_issues=technical_issues,
                quality_status=quality_status,
                redirect_destination=redirect_dest,
                depth=depth,
            )

            pages_fetched += 1
            crawled_urls.add(url)
            if page.indexability == "not_indexable":
                non_indexable_urls.add(url)
            if on_page:
                await on_page(page)

            nofollow = "nofollow" in robots_directives
            nofollow_anchor_urls: set[str] = set(signals.get("nofollow_links", []))
            if not nofollow and is_html and depth < config.max_depth:
                for link in signals.get("internal_links", []):
                    if link in nofollow_anchor_urls:
                        continue
                    normalized = canonicalize_url(normalize_crawl_url(link))
                    if normalized not in seen:
                        enqueue(normalized, depth + 1)

        while queue:
            elapsed = monotonic() - started_at
            if elapsed > config.total_timeout:
                timed_out = True
                break
            if pages_fetched >= config.max_pages:
                page_limit_reached = True
                break

            batch: list[tuple[str, int]] = []
            available = config.concurrency
            while queue and len(batch) < available:
                url, depth = queue.popleft()
                max_depth_reached = max(max_depth_reached, depth)
                batch.append((url, depth))

            if not batch:
                continue

            tasks = [asyncio.create_task(process_one(url, depth)) for url, depth in batch]
            await asyncio.gather(*tasks)

        if page_limit_reached:
            terminal_state = "success"
            reason = f"Reached configured max_pages limit ({config.max_pages})"
        elif timed_out:
            terminal_state = "partial"
            reason = (
                f"Total run timeout of {config.total_timeout}s exceeded after "
                f"fetching {pages_fetched} pages"
            )
        else:
            terminal_state = "success"
            reason = "All reachable same-host pages crawled within configured limits"

        canonical_sitemap_urls = {
            canonicalize_url(normalize_crawl_url(u)) for u in sitemap_page_urls
        }
        sitemap_not_reached = sorted(canonical_sitemap_urls - crawled_urls)
        crawled_not_in_sitemap = sorted(crawled_urls - canonical_sitemap_urls)
        sitemap_non_indexable = sorted(u for u in canonical_sitemap_urls if u in non_indexable_urls)

        return CrawlReport(
            terminal_state=terminal_state,
            reason=reason,
            pages_fetched=pages_fetched,
            pages_queued=pages_queued,
            pages_skipped=pages_skipped,
            skip_reasons=skip_reasons,
            max_depth_reached=max_depth_reached,
            robots_available=robots_available,
            robots_disallowed=disallow_rules,
            sitemap_file_urls=sitemap_file_urls,
            sitemap_page_urls=sitemap_page_urls,
            sitemap_page_count=len(sitemap_page_urls),
            sitemap_not_reached=sitemap_not_reached,
            crawled_not_in_sitemap=crawled_not_in_sitemap,
            sitemap_non_indexable=sitemap_non_indexable,
        )


def _url_is_disallowed(url: str, disallow_rules: list[str], allow_rules: list[str]) -> bool:
    path = urlparse(url).path or "/"
    return is_disallowed(path, disallow_rules, allow_rules)
