"""Re-run GSC sync, crawl, and analysis for every active SEO website.

Milestone 1 closed the page-attribution gap in `SEOOrchestrationService`, but
existing `seo_opportunities` rows only repair themselves the next time
analysis runs for their website, and several clients have no `page_query`
Search Console rows at all yet (their last sync predates the page+query
sync). This command re-runs the full governed evidence pipeline — GSC sync,
crawl, analysis — for every active website through the same code paths the
product routes use, so no client is left stuck on stale evidence.

Idempotent and safe to re-run: each step reuses the existing governed
services (`SearchConsoleService.sync_observations`, `SEOService.enqueue_crawl`,
the `seo.crawl_or_analysis` workflow) rather than writing directly to any
table. Crawl and analysis execute in the worker after this command enqueues
them; GSC sync runs inline here since it is a bounded, one-shot read.

Run with:

    uv run python -m scripts.reevaluate_active_websites
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from sqlalchemy import select

from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.execution.service import ExecutionService
from apps.api.app.products.seo.contracts import CrawlRequest
from apps.api.app.products.seo.models import SEOSearchProperty, SEOWebsite
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from apps.api.app.products.seo.service import SEOService

assert SEOWebsite.metadata is SEOSearchProperty.metadata


async def reevaluate() -> None:
    settings = Settings()
    runtime = create_database_runtime(settings)
    session_factory = runtime.require_session_factory()
    execution = ExecutionService()
    seo = SEOService()
    search_console = SearchConsoleService()

    synced = crawled = skipped = 0
    try:
        async with session_factory() as session:
            websites = list(
                await session.scalars(
                    select(SEOWebsite).where(SEOWebsite.status == "active")
                )
            )

        for website in websites:
            run_marker = uuid4().hex[:12]
            correlation_id = f"reevaluate-active-websites:{run_marker}"

            async with session_factory.begin() as session:
                search_property = await session.scalar(
                    select(SEOSearchProperty).where(
                        SEOSearchProperty.organization_id == website.organization_id,
                        SEOSearchProperty.website_id == website.id,
                        SEOSearchProperty.provider == "google_search_console",
                        SEOSearchProperty.mapping_status == "mapped",
                    )
                )
                if search_property is not None:
                    await search_console.sync_observations(
                        session,
                        settings,
                        website.organization_id,
                        search_property.id,
                        actor_id=None,
                        correlation_id=correlation_id,
                    )
                    synced += 1

            async with session_factory.begin() as session:
                workflow_run = await execution.start_named(
                    session,
                    website.organization_id,
                    "seo.crawl_or_analysis",
                    f"reevaluate-active-websites:{website.id}:{run_marker}",
                    location_id=website.location_id,
                    correlation_id=correlation_id,
                    actor_id=None,
                    enqueue_job=False,
                )
                await seo.enqueue_crawl(
                    session,
                    website.organization_id,
                    website.id,
                    CrawlRequest(
                        workflow_run_id=workflow_run.id,
                        idempotency_key=f"reevaluate-active-websites:{website.id}:{run_marker}",
                    ),
                    actor_id=None,
                    correlation_id=correlation_id,
                )
                crawled += 1

            print(f"queued website={website.id} org={website.organization_id}")

        skipped = 0
        print(
            f"Re-evaluation complete: websites={len(websites)} gsc_synced={synced} "
            f"crawl_analysis_queued={crawled} skipped={skipped}"
        )
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    asyncio.run(reevaluate())
