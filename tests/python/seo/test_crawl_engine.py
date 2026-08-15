"""Focused crawl-engine acceptance tests for Packet 4A SEO Crawl Engine."""

import asyncio
from collections.abc import Coroutine
from typing import Any

import httpx

from apps.api.app.products.seo.crawl_engine import (
    CrawlConfig,
    CrawledPage,
    CrawlEngine,
    CrawlReport,
    canonicalize_url,
    extract_page_signals,
    is_disallowed,
    normalize_crawl_url,
    parse_robots_txt,
    parse_sitemap,
    parse_sitemap_index,
)


def _repeat(text: str, count: int) -> str:
    return text * count


MULTIPAGE_HTML = (
    "<html><head><title>Page {n}</title>"
    '<meta name="description" content="Description {n}">'
    '<link rel="canonical" href="https://example.test/page{n}">'
    '<meta name="robots" content="index, follow">'
    "</head><body><h1>Heading {n}</h1>"
    '<a href="/page{a}">Link A</a> '
    '<a href="/page{b}">Link B</a> '
    '<a href="https://other.test/external">External</a>'
    '<script type="application/ld+json">{{"@type": "WebPage"}}</script>'
    + _repeat("<p>Some content text that makes up enough words to count. </p>", 5)
    + "</body></html>"
)


def build_site_html(n: int, a: int, b: int) -> str:
    return MULTIPAGE_HTML.format(n=n, a=a, b=b)


GOOD_HTML = build_site_html(0, 1, 2)
BROKEN_HTML = "<html><head></head><body>No title, no meta, no h1.</body></html>"
ROOT_ONLY_HTML = "<html><head><title>Root</title></head><body><p>Hello.</p></body></html>"


class FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses: dict[str, tuple[int, str, dict[str, str]]] | None = None) -> None:
        self.responses = responses or {}
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        key = str(request.url)
        if key in self.responses:
            status, body, headers = self.responses[key]
            return httpx.Response(status, text=body, headers=headers, request=request)
        return httpx.Response(404, text="Not Found", request=request)


def make_client(responses: dict[str, httpx.Response]) -> httpx.AsyncClient:
    raw: dict[str, tuple[int, str, dict[str, str]]] = {}
    for url, resp in responses.items():
        raw[url] = (resp.status_code, resp.text, dict(resp.headers))
    return httpx.AsyncClient(transport=FakeTransport(raw))


def ok_html(body: str, url: str = "") -> httpx.Response:
    target = url or "https://example.test/"
    return httpx.Response(
        200,
        text=body,
        headers={"content-type": "text/html; charset=utf-8"},
        request=httpx.Request("GET", target),
    )


def robots_response(body: str) -> httpx.Response:
    return httpx.Response(
        200, text=body, request=httpx.Request("GET", "https://example.test/robots.txt")
    )


def sitemap_response(body: str, url: str = "") -> httpx.Response:
    target = url or "https://example.test/sitemap.xml"
    return httpx.Response(
        200,
        text=body,
        headers={"content-type": "application/xml"},
        request=httpx.Request("GET", target),
    )


SITEMAP_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
    "<url><loc>https://example.test/page1</loc></url>"
    "<url><loc>https://example.test/page2</loc></url>"
    "<url><loc>https://example.test/page3</loc></url>"
    "</urlset>"
)

ROBOTS_TXT = (
    "User-agent: *\n"
    "Disallow: /admin/\n"
    "Disallow: /private\n"
    "Sitemap: https://example.test/sitemap.xml\n"
)

ROBOTS_DISALLOW_ONLY = "User-agent: *\nDisallow: /admin/\n"


def base_config(**overrides: object) -> CrawlConfig:
    kwargs: dict[str, object] = {
        "base_origin": "https://example.test",
        "allowed_host": "example.test",
        "seeds": ("https://example.test/",),
        "max_pages": 50,
        "max_depth": 3,
        "crawl_delay": 0.0,
        "request_timeout": 5.0,
        "total_timeout": 60.0,
        "concurrency": 2,
    }
    kwargs.update(overrides)
    return CrawlConfig(**kwargs)  # type: ignore[arg-type]


def _run_coro(coro: Coroutine[Any, Any, None]) -> None:
    """Run an async test body to completion."""
    asyncio.run(coro)


# ---------------------------------------------------------------------------
# Engine: standalone
# ---------------------------------------------------------------------------


async def _crawl_with_config(
    config: CrawlConfig, responses: dict[str, httpx.Response]
) -> tuple[list[CrawledPage], CrawlReport]:
    collected: list[CrawledPage] = []

    async def on_page(cp: CrawledPage) -> None:
        collected.append(cp)

    async with make_client(responses) as client:
        engine = CrawlEngine(config, client)
        report = await engine.crawl(on_page=on_page)
    return collected, report


# ---------------------------------------------------------------------------
# SC4A-ROBOTS
# ---------------------------------------------------------------------------


def test_sc4a_crawler_respects_robots_disallow() -> None:
    async def run() -> None:
        responses = {
            "https://example.test/robots.txt": robots_response(ROBOTS_DISALLOW_ONLY),
            "https://example.test/": ok_html(ROOT_ONLY_HTML),
            "https://example.test/admin/": ok_html(ROOT_ONLY_HTML),
        }
        collected, report = await _crawl_with_config(base_config(), responses)
        fetched_urls = {cp.url for cp in collected}
        assert "https://example.test/" in fetched_urls
        assert "https://example.test/admin/" not in fetched_urls
        assert report.robots_available is True

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SC4A-SAMEHOST
# ---------------------------------------------------------------------------


def test_sc4a_no_external_domain_traversal() -> None:
    async def run() -> None:
        responses = {
            "https://example.test/robots.txt": ok_html(""),
            "https://example.test/": ok_html(GOOD_HTML),
        }
        collected, report = await _crawl_with_config(base_config(), responses)
        fetched_urls = {cp.url for cp in collected}
        assert "https://example.test/" in fetched_urls
        assert "https://other.test/external" not in fetched_urls
        root = next(cp for cp in collected if cp.url == "https://example.test/")
        assert any("other.test" in link for link in root.external_links)

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SC4A-LIMITS
# ---------------------------------------------------------------------------


def test_sc4a_max_pages_binds() -> None:
    async def run() -> None:
        chain_html = (
            "<html><head><title>Chain</title></head><body>"
            + "".join(f'<a href="/page{i}">Page {i}</a>' for i in range(50))
            + "</body></html>"
        )
        responses: dict[str, httpx.Response] = {
            "https://example.test/robots.txt": ok_html(""),
            "https://example.test/": ok_html(chain_html),
        }
        for i in range(50):
            responses[f"https://example.test/page{i}"] = ok_html(
                f"<html><head><title>Page {i}</title></head><body></body></html>",
                f"https://example.test/page{i}",
            )

        collected, report = await _crawl_with_config(base_config(max_pages=25), responses)
        assert report.pages_fetched <= 25
        assert report.terminal_state == "success"
        assert "max_pages" in report.reason.lower()

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SC4A-DEPTH
# ---------------------------------------------------------------------------


def test_sc4a_depth_binds_and_recorded() -> None:
    async def run() -> None:
        chain = (
            "<html><head><title>Deep {d}</title></head>"
            '<body><a href="/deep{nd}">Deeper</a></body></html>'
        )
        responses: dict[str, httpx.Response] = {
            "https://example.test/robots.txt": ok_html(""),
            "https://example.test/": ok_html(chain.format(d=0, nd=1), "https://example.test/"),
            "https://example.test/deep1": ok_html(
                chain.format(d=1, nd=2), "https://example.test/deep1"
            ),
            "https://example.test/deep2": ok_html(
                chain.format(d=2, nd=3), "https://example.test/deep2"
            ),
            "https://example.test/deep3": ok_html(
                chain.format(d=3, nd=4), "https://example.test/deep3"
            ),
        }

        collected, report = await _crawl_with_config(base_config(max_depth=2), responses)
        depths = {cp.url: cp.depth for cp in collected}
        assert depths["https://example.test/"] == 0
        assert depths["https://example.test/deep1"] == 1
        assert depths["https://example.test/deep2"] == 2
        assert "https://example.test/deep3" not in depths

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SC4A-FIELDS
# ---------------------------------------------------------------------------


def test_sc4a_all_fields_populated() -> None:
    async def run() -> None:
        responses = {
            "https://example.test/robots.txt": ok_html(""),
            "https://example.test/": ok_html(GOOD_HTML),
        }
        collected, report = await _crawl_with_config(base_config(), responses)
        cp = collected[0]
        assert cp.url == "https://example.test/"
        assert cp.http_status == 200
        assert cp.content_type is not None
        assert cp.title is not None
        assert cp.meta_description is not None
        assert cp.h1 is not None
        assert cp.canonical_url is not None
        assert len(cp.robots_directives) > 0
        assert len(cp.internal_links) > 0
        assert len(cp.external_links) > 0
        assert cp.word_count is not None and cp.word_count > 0
        assert cp.structured_data_present is True
        assert cp.content_hash is not None
        assert cp.indexability == "indexable"

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SC4A-IDEMPOTENT
# ---------------------------------------------------------------------------


def test_sc4a_idempotent_engine_no_duplicate_yields() -> None:
    async def run() -> None:
        responses = {
            "https://example.test/robots.txt": ok_html(""),
            "https://example.test/": ok_html(ROOT_ONLY_HTML),
        }
        collected1, _ = await _crawl_with_config(base_config(), responses)
        collected2, _ = await _crawl_with_config(base_config(), responses)
        assert len(collected1) == len(collected2)
        urls1 = [cp.url for cp in collected1]
        urls2 = [cp.url for cp in collected2]
        assert urls1 == urls2
        assert len(urls1) == len(set(urls1))

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SC4A-SITEMAP
# ---------------------------------------------------------------------------


def test_sc4a_sitemap_discovered_and_parsed() -> None:
    async def run() -> None:
        sitemap_items = "".join(
            f"<url><loc>https://example.test/sm-page-{i}</loc></url>" for i in range(3)
        )
        sm_xml = (
            '<?xml version="1.0"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sitemap_items}</urlset>'
        )
        responses: dict[str, httpx.Response] = {
            "https://example.test/robots.txt": robots_response(
                "User-agent: *\nSitemap: https://example.test/sitemap.xml\n"
            ),
            "https://example.test/sitemap.xml": sitemap_response(sm_xml),
            "https://example.test/": ok_html(ROOT_ONLY_HTML),
        }
        for i in range(3):
            responses[f"https://example.test/sm-page-{i}"] = ok_html(
                ROOT_ONLY_HTML, f"https://example.test/sm-page-{i}"
            )

        collected, report = await _crawl_with_config(base_config(), responses)
        assert report.sitemap_file_urls
        assert report.sitemap_page_count >= 3
        sm_page_urls = [cp.url for cp in collected if "sm-page" in cp.url]
        assert len(sm_page_urls) >= 3

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Unit: parsers
# ---------------------------------------------------------------------------


def test_robots_parser_extracts_disallow_and_sitemap() -> None:
    disallow, allow, sitemaps = parse_robots_txt(ROBOTS_TXT)
    assert "/admin/" in disallow
    assert "/private" in disallow
    assert "https://example.test/sitemap.xml" in sitemaps


def test_disallow_rule_matching() -> None:
    disallow, _, _ = parse_robots_txt(ROBOTS_DISALLOW_ONLY)
    assert is_disallowed("/admin/", disallow)
    assert is_disallowed("/admin/anything", disallow)
    assert not is_disallowed("/public/page", disallow)


def test_sitemap_parser() -> None:
    pages = parse_sitemap(SITEMAP_XML)
    assert len(pages) == 3
    assert "https://example.test/page1" in pages


def test_sitemap_index_parser() -> None:
    idx_xml = (
        '<?xml version="1.0"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<sitemap><loc>https://example.test/sitemap1.xml</loc></sitemap>"
        "<sitemap><loc>https://example.test/sitemap2.xml</loc></sitemap>"
        "</sitemapindex>"
    )
    sitemaps = parse_sitemap_index(idx_xml)
    assert len(sitemaps) == 2
    assert "https://example.test/sitemap1.xml" in sitemaps


def test_url_normalization() -> None:
    result = normalize_crawl_url("https://Example.TEST:443/Path")
    assert result == "https://example.test/Path"


def test_page_signals_extraction() -> None:
    signals = extract_page_signals(GOOD_HTML, 200, "https://example.test/", ["index", "follow"])
    assert signals["title"] is not None
    assert signals["meta_description"] is not None
    assert signals["h1"] is not None
    assert signals["canonical_url"] is not None
    assert len(signals["internal_links"]) > 0
    assert len(signals["external_links"]) > 0
    assert signals["word_count"] is not None and signals["word_count"] > 0
    assert signals["structured_data_present"] is True
    assert signals["content_hash"] is not None
    assert signals["indexability"] == "indexable"


def test_broken_page_indexability() -> None:
    signals = extract_page_signals(BROKEN_HTML, 200, "https://example.test/broken", [])
    assert signals["title"] is None
    assert signals["meta_description"] is None
    assert signals["h1"] is None
    assert signals["indexability"] == "indexable"


def test_canonicalize_url_resolves_dots() -> None:
    result = canonicalize_url("https://example.test/a/b/../c/./d")
    assert result == "https://example.test/a/c/d"


def test_host_same_check() -> None:
    from apps.api.app.products.seo.crawl_engine import same_host

    assert same_host("Example.COM", "example.com")
    assert not same_host("example.com", "other.com")


# ---------------------------------------------------------------------------
# SC4A-R-ALLOW  — Allow overrides broader Disallow by longest match
# ---------------------------------------------------------------------------

ALLOW_ROBOTS = "User-agent: *\nDisallow: /admin/\nAllow: /admin/public\n"


def test_allow_overrides_broader_disallow() -> None:
    disallow, allow, _ = parse_robots_txt(ALLOW_ROBOTS)
    assert "/admin/" in disallow
    assert "/admin/public" in allow
    assert is_disallowed("/admin/anything", disallow, allow)
    assert not is_disallowed("/admin/public", disallow, allow)
    assert not is_disallowed("/admin/public/page", disallow, allow)


# ---------------------------------------------------------------------------
# SC4A-R-NOFOLLOW  — rel="nofollow" anchors recorded but not traversed
# ---------------------------------------------------------------------------

NOFOLLOW_HTML = (
    "<html><head><title>Nofollow</title>"
    '<meta name="description" content="desc">'
    '<meta name="robots" content="index, follow">'
    "</head><body><h1>Heading</h1>"
    '<a href="/followed">Followed</a>'
    '<a href="/nofollow" rel="nofollow">Nofollow</a>'
    "</body></html>"
)


def test_nofollow_anchor_recorded_but_not_traversed() -> None:
    async def run() -> None:
        responses: dict[str, httpx.Response] = {
            "https://example.test/robots.txt": ok_html(""),
            "https://example.test/": ok_html(NOFOLLOW_HTML, "https://example.test/"),
            "https://example.test/followed": ok_html(
                ROOT_ONLY_HTML, "https://example.test/followed"
            ),
            "https://example.test/nofollow": ok_html(
                ROOT_ONLY_HTML, "https://example.test/nofollow"
            ),
        }
        collected, _ = await _crawl_with_config(base_config(), responses)
        fetched_urls = {cp.url for cp in collected}
        root = next(cp for cp in collected if cp.url == "https://example.test/")
        assert "https://example.test/followed" in root.internal_links
        assert "https://example.test/nofollow" in root.internal_links
        assert "https://example.test/followed" in fetched_urls
        assert "https://example.test/nofollow" not in fetched_urls

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SC4A-R-SITEMAP-CMP  — sitemap-vs-crawl comparison
# ---------------------------------------------------------------------------


def test_sitemap_vs_crawl_comparison() -> None:
    async def run() -> None:
        sitemap_items = (
            "<url><loc>https://example.test/page1</loc></url>"
            "<url><loc>https://example.test/page2</loc></url>"
            "<url><loc>https://example.test/page3</loc></url>"
        )
        sm_xml = (
            '<?xml version="1.0"?>'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{sitemap_items}</urlset>'
        )
        responses: dict[str, httpx.Response] = {
            "https://example.test/robots.txt": robots_response(
                "User-agent: *\nSitemap: https://example.test/sitemap.xml\n"
            ),
            "https://example.test/sitemap.xml": sitemap_response(sm_xml),
            "https://example.test/": ok_html(ROOT_ONLY_HTML),
            "https://example.test/page1": ok_html(ROOT_ONLY_HTML, "https://example.test/page1"),
        }
        # page2 → 404 (non-indexable); page3 → never reached (max_pages=3, concurrency=1)
        _, report = await _crawl_with_config(base_config(max_pages=3, concurrency=1), responses)
        assert "https://example.test/page3" in report.sitemap_not_reached
        assert "https://example.test/" in report.crawled_not_in_sitemap
        assert "https://example.test/page2" in report.sitemap_non_indexable

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SC4A-R-LIMITS-250  — max_pages at 250
# ---------------------------------------------------------------------------


def test_sc4a_max_pages_binds_at_250() -> None:
    async def run() -> None:
        chain_html = (
            "<html><head><title>Chain</title></head><body>"
            + "".join(f'<a href="/page{i}">Page {i}</a>' for i in range(300))
            + "</body></html>"
        )
        responses: dict[str, httpx.Response] = {
            "https://example.test/robots.txt": ok_html(""),
            "https://example.test/": ok_html(chain_html),
        }
        for i in range(300):
            responses[f"https://example.test/page{i}"] = ok_html(
                f"<html><head><title>Page {i}</title></head><body></body></html>",
                f"https://example.test/page{i}",
            )

        collected, report = await _crawl_with_config(
            base_config(max_pages=250, concurrency=1), responses
        )
        assert report.pages_fetched <= 250
        assert report.terminal_state == "success"
        assert "max_pages" in report.reason.lower()

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SC4A-R-FIELDS  — redirect, error, quality, technical_issues
# ---------------------------------------------------------------------------


def test_sc4a_redirect_destination_populated() -> None:
    async def run() -> None:
        responses = {
            "https://example.test/robots.txt": ok_html(""),
            "https://example.test/old": httpx.Response(
                301,
                headers={"location": "https://example.test/new"},
                request=httpx.Request("GET", "https://example.test/old"),
            ),
            "https://example.test/new": ok_html(ROOT_ONLY_HTML, "https://example.test/new"),
        }
        collected, _ = await _crawl_with_config(
            base_config(seeds=("https://example.test/old",)), responses
        )
        old_page = next(cp for cp in collected if cp.url.endswith("/old"))
        assert old_page.redirect_destination is not None
        assert old_page.redirect_destination.endswith("/new")

    asyncio.run(run())


def test_sc4a_error_page_fields_populated() -> None:
    async def run() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/broken":
                raise httpx.ConnectError("boom", request=request)
            return httpx.Response(200, text=ROOT_ONLY_HTML, request=request)

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            config = base_config(
                seeds=("https://example.test/", "https://example.test/broken"),
                retry_limit=0,
            )
            engine = CrawlEngine(config, client)
            collected: list[CrawledPage] = []

            async def on_page(cp: CrawledPage) -> None:
                collected.append(cp)

            await engine.crawl(on_page=on_page)

        broken = next(cp for cp in collected if cp.url.endswith("/broken"))
        assert broken.error is not None
        assert broken.quality_status == "issues_detected"
        assert "non_200_status" in broken.technical_issues

    asyncio.run(run())


# ---------------------------------------------------------------------------
# SC4A-R-PARTIAL  — timed-out crawl retains fetched pages, terminates partial
# ---------------------------------------------------------------------------


def test_sc4a_partial_timeout_retains_pages() -> None:
    async def run() -> None:
        root_html = (
            "<html><head><title>Root</title></head><body>"
            + "".join(f'<a href="/page{i}">Page {i}</a>' for i in range(5))
            + "</body></html>"
        )

        async def handler(request: httpx.Request) -> httpx.Response:
            await asyncio.sleep(0.3)
            return httpx.Response(
                200, text=root_html, headers={"content-type": "text/html"}, request=request
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            config = base_config(total_timeout=0.65, request_timeout=5.0, concurrency=1)
            engine = CrawlEngine(config, client)
            collected: list[CrawledPage] = []

            async def on_page(cp: CrawledPage) -> None:
                collected.append(cp)

            report = await engine.crawl(on_page=on_page)

        assert report.terminal_state == "partial"
        assert "timeout" in report.reason.lower()
        assert len(collected) >= 2

    asyncio.run(run())
