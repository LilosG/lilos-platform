"""Re-run GSC sync, crawl, and analysis for every active SEO website.

Milestone 1 closed the page-attribution gap in `SEOOrchestrationService`, but
existing `seo_opportunities` rows only repair themselves the next time
analysis runs for their website, and several clients have no `page_query`
Search Console rows at all yet (their last sync predates the page+query
sync). This command re-runs the full governed evidence pipeline — GSC sync,
crawl, analysis — for every active website through the same code paths the
product routes use, so no client is left stuck on stale evidence.

Each website is isolated. A Search Console failure (a Google connection that
needs reconnecting, a revoked scope, a provider error) is logged and recorded,
the crawl and analysis are still queued for that website, and the run moves on.
The final summary lists every skipped step with its error type. Only websites
whose organization is ACTIVE are included: a suspended, paused or offboarding
organization is not re-evaluated, which is also how a non-client is kept out
(suspend it with `scripts.suspend_organization`).

Idempotent and safe to re-run: each step reuses the existing governed
services (`SearchConsoleService.sync_observations`, `SEOService.enqueue_crawl`,
the `seo.crawl_or_analysis` workflow) rather than writing directly to any
table. Crawl and analysis execute in the worker after this command enqueues
them. The Search Console sync runs here, in short separate transactions, so no
transaction is open while Google is being called.

Run (Render shell):

    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.reevaluate_active_websites
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.execution.service import ExecutionService
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.products.seo.contracts import CrawlRequest
from apps.api.app.products.seo.models import SEOSearchProperty, SEOWebsite
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from apps.api.app.products.seo.service import SEOService
from scripts._cli import run_script

assert SEOWebsite.metadata is SEOSearchProperty.metadata is Organization.metadata

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SkippedStep:
    """One website step that failed and was skipped, never a silent drop."""

    website_id: UUID
    organization_id: UUID
    domain: str
    step: str  # "search_console" | "crawl_analysis"
    error_type: str


@dataclass(slots=True)
class ReevaluationSummary:
    websites: int
    gsc_synced: int
    crawl_analysis_queued: int
    skipped: list[SkippedStep] = field(default_factory=list)


def _domain(canonical_origin: str) -> str:
    return (urlsplit(canonical_origin).hostname or canonical_origin).lower()


async def reevaluate_active_websites(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    execution: ExecutionService | None = None,
    seo: SEOService | None = None,
    search_console: SearchConsoleService | None = None,
) -> ReevaluationSummary:
    """Re-run GSC sync + crawl + analysis for every active website.

    Reuses the same governed services the product routes call — no direct
    table writes — so this is safe to re-run and cannot desync from the
    application's own idempotency and audit guarantees.
    """
    execution = execution or ExecutionService()
    seo = seo or SEOService()
    search_console = search_console or SearchConsoleService()

    async with session_factory() as session:
        websites = list(
            await session.scalars(
                select(SEOWebsite)
                .join(Organization, Organization.id == SEOWebsite.organization_id)
                .where(
                    SEOWebsite.status == "active",
                    Organization.status == OrganizationStatus.ACTIVE,
                )
                .order_by(SEOWebsite.created_at, SEOWebsite.id)
            )
        )

    summary = ReevaluationSummary(websites=len(websites), gsc_synced=0, crawl_analysis_queued=0)
    for website in websites:
        run_marker = uuid4().hex[:12]
        correlation_id = f"reevaluate-active-websites:{run_marker}"
        domain = _domain(website.canonical_origin)

        try:
            async with session_factory() as session:
                search_property_id = await session.scalar(
                    select(SEOSearchProperty.id).where(
                        SEOSearchProperty.organization_id == website.organization_id,
                        SEOSearchProperty.website_id == website.id,
                        SEOSearchProperty.provider == "google_search_console",
                        SEOSearchProperty.mapping_status == "mapped",
                    )
                )
            if search_property_id is not None:
                await search_console.sync_observations(
                    session_factory,
                    settings,
                    website.organization_id,
                    search_property_id,
                    actor_id=None,
                    correlation_id=correlation_id,
                )
                summary.gsc_synced += 1
        except Exception as exc:
            # One client's Google problem must not stop every other client.
            logger.warning(
                "Search Console sync skipped",
                extra={"website_id": str(website.id), "error_type": type(exc).__name__},
            )
            summary.skipped.append(
                SkippedStep(
                    website.id,
                    website.organization_id,
                    domain,
                    "search_console",
                    type(exc).__name__,
                )
            )

        try:
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
            summary.crawl_analysis_queued += 1
            print(f"queued website={website.id} org={website.organization_id} domain={domain}")
        except Exception as exc:
            logger.warning(
                "Crawl and analysis not queued",
                extra={"website_id": str(website.id), "error_type": type(exc).__name__},
            )
            summary.skipped.append(
                SkippedStep(
                    website.id,
                    website.organization_id,
                    domain,
                    "crawl_analysis",
                    type(exc).__name__,
                )
            )

    return summary


def format_summary(summary: ReevaluationSummary) -> list[str]:
    lines = [
        f"Re-evaluation complete: websites={summary.websites} "
        f"gsc_synced={summary.gsc_synced} "
        f"crawl_analysis_queued={summary.crawl_analysis_queued} "
        f"skipped={len(summary.skipped)}"
    ]
    lines.extend(
        f"  SKIPPED {item.step} website={item.website_id} domain={item.domain} "
        f"error={item.error_type}"
        for item in summary.skipped
    )
    return lines


async def main() -> int:
    settings = Settings()
    runtime = create_database_runtime(settings)
    try:
        summary = await reevaluate_active_websites(runtime.require_session_factory(), settings)
        for line in format_summary(summary):
            print(line)
        return 0
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    raise SystemExit(run_script("reevaluate_active_websites", main))
