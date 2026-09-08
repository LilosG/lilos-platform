"""Regression coverage for max_pages with concurrent crawl batches."""

import asyncio

import httpx

from apps.api.app.products.seo.crawl_engine import CrawlConfig, CrawlEngine


class PageLimitTransport(httpx.AsyncBaseTransport):
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url == "https://example.test/robots.txt":
            return httpx.Response(200, text="User-agent: *\n", request=request)
        if url == "https://example.test/":
            links = "".join(f'<a href="/page{i}">Page {i}</a>' for i in range(40))
            return httpx.Response(
                200,
                text=f"<html><head><title>Root</title></head><body>{links}</body></html>",
                headers={"content-type": "text/html"},
                request=request,
            )
        if url.startswith("https://example.test/page"):
            return httpx.Response(
                200,
                text="<html><head><title>Page</title></head><body>Page</body></html>",
                headers={"content-type": "text/html"},
                request=request,
            )
        return httpx.Response(404, text="Not Found", request=request)


def test_max_pages_is_hard_bound_when_concurrency_exceeds_remaining_budget() -> None:
    async def run() -> None:
        config = CrawlConfig(
            base_origin="https://example.test",
            allowed_host="example.test",
            seeds=("https://example.test/",),
            max_pages=10,
            max_depth=2,
            crawl_delay=0.0,
            request_timeout=5.0,
            total_timeout=60.0,
            concurrency=4,
        )
        collected = []

        async def on_page(page: object) -> None:
            collected.append(page)

        async with httpx.AsyncClient(transport=PageLimitTransport()) as client:
            report = await CrawlEngine(config, client).crawl(on_page=on_page)

        assert report.pages_fetched == 10
        assert len(collected) == 10
        assert report.terminal_state == "success"
        assert "max_pages" in report.reason.lower()

    asyncio.run(run())
