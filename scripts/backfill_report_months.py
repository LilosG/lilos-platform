"""One-time backfill of whole calendar months of Search Console and GA4 data for client reports.

The recurring syncs keep the last 2 months. Reports over several months, and their comparison,
need more, so this stores up to 16 settled months per mapped property through the same fetch and
store code and the same idempotent upserts the syncs use. Months the provider has not settled are
left to the regular sync. A month that cannot be read stays unsynced (never 0) and is simply
fetched again the next time this runs.

Each property is isolated: a Google problem with one client is logged and skipped. Re-running is
safe and only asks Google for months that are still missing.

Run (Render shell):

    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.backfill_report_months
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.organizations.enums import OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.seo.models import SEOSearchProperty
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from scripts._cli import run_script

assert SEOSearchProperty.metadata is AnalyticsProperty.metadata is Organization.metadata

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SkippedProperty:
    organization_id: UUID
    source: str  # "search_console" | "analytics"
    property_id: UUID
    error_type: str


@dataclass(slots=True)
class BackfillSummary:
    search_console: int = 0
    analytics: int = 0
    skipped: list[SkippedProperty] = field(default_factory=list)


async def backfill_report_months(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    *,
    search_console: SearchConsoleService | None = None,
    analytics: AnalyticsService | None = None,
) -> BackfillSummary:
    """Backfill every mapped Search Console and GA4 property of an active client."""
    search_console = search_console or SearchConsoleService()
    analytics = analytics or AnalyticsService()
    active = (
        Organization.status == OrganizationStatus.ACTIVE,
        Organization.removed_at.is_(None),
    )
    async with session_factory() as session:
        search_properties = list(
            (
                await session.execute(
                    select(SEOSearchProperty.organization_id, SEOSearchProperty.id)
                    .join(Organization, Organization.id == SEOSearchProperty.organization_id)
                    .where(
                        SEOSearchProperty.provider == "google_search_console",
                        SEOSearchProperty.mapping_status == "mapped",
                        *active,
                    )
                    .order_by(SEOSearchProperty.created_at, SEOSearchProperty.id)
                )
            ).all()
        )
        analytics_properties = list(
            (
                await session.execute(
                    select(AnalyticsProperty.organization_id, AnalyticsProperty.id)
                    .join(Organization, Organization.id == AnalyticsProperty.organization_id)
                    .where(AnalyticsProperty.mapping_status == "mapped", *active)
                    .order_by(AnalyticsProperty.created_at, AnalyticsProperty.id)
                )
            ).all()
        )

    summary = BackfillSummary()
    correlation_id = f"backfill-report-months:{uuid4().hex[:12]}"
    for organization_id, property_id in search_properties:
        try:
            await search_console.sync_observations(
                session_factory,
                settings,
                organization_id,
                property_id,
                actor_id=None,
                correlation_id=correlation_id,
                backfill_months=True,
            )
            summary.search_console += 1
        except Exception as exc:
            logger.warning(
                "Search Console backfill skipped",
                extra={"search_property_id": str(property_id), "error_type": type(exc).__name__},
            )
            summary.skipped.append(
                SkippedProperty(organization_id, "search_console", property_id, type(exc).__name__)
            )
    for organization_id, property_id in analytics_properties:
        try:
            await analytics.sync_metrics(
                session_factory,
                settings,
                organization_id,
                property_id,
                actor_id=None,
                correlation_id=correlation_id,
                backfill_months=True,
            )
            summary.analytics += 1
        except Exception as exc:
            logger.warning(
                "GA4 backfill skipped",
                extra={"analytics_property_id": str(property_id), "error_type": type(exc).__name__},
            )
            summary.skipped.append(
                SkippedProperty(organization_id, "analytics", property_id, type(exc).__name__)
            )
    return summary


def format_summary(summary: BackfillSummary) -> list[str]:
    lines = [
        f"Backfill complete: search_console={summary.search_console} "
        f"analytics={summary.analytics} skipped={len(summary.skipped)}"
    ]
    lines.extend(
        f"  SKIPPED {item.source} property={item.property_id} org={item.organization_id} "
        f"error={item.error_type}"
        for item in summary.skipped
    )
    return lines


async def main() -> int:
    settings = Settings()
    runtime = create_database_runtime(settings)
    try:
        summary = await backfill_report_months(runtime.require_session_factory(), settings)
        for line in format_summary(summary):
            print(line)
        return 0
    finally:
        await runtime.dispose()


if __name__ == "__main__":
    raise SystemExit(run_script("backfill_report_months", main))
