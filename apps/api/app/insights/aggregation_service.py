"""Insights aggregation service wiring real product-history data.

Computes a cross-product activity summary from REAL rows in the existing
product tables — no simulated charts or fabricated metrics.  Every count is
derived by querying the live tables (workflow runs, GBP snapshots, reviews,
content publications, SEO opportunities/crawl runs, leads) so the Insights
surface reflects genuine operational history.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.models import WorkflowRun
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.content.models import ContentPublication
from apps.api.app.products.gbp.models import GBPLocation, GBPProfileSnapshot, GBPPublication
from apps.api.app.products.leads.models import Lead
from apps.api.app.products.reviews.models import Review
from apps.api.app.products.seo.models import SEOCrawlRun, SEOOpportunity


@dataclass(frozen=True, slots=True)
class InsightsService:
    """Aggregate real cross-product activity into a reporting read model."""

    analytics: AnalyticsService = field(default_factory=AnalyticsService)

    async def summary(self, session: AsyncSession, organization_id: UUID) -> dict[str, object]:
        """Return a real activity summary derived from live product tables."""
        workflow_runs = await self._status_counts(
            session, WorkflowRun, WorkflowRun.organization_id == organization_id
        )
        gbp_locations = await self._count(
            session, GBPLocation, GBPLocation.organization_id == organization_id
        )
        gbp_snapshots = await self._count(
            session, GBPProfileSnapshot, GBPProfileSnapshot.organization_id == organization_id
        )
        gbp_publications = await self._status_counts(
            session, GBPPublication, GBPPublication.organization_id == organization_id
        )
        reviews = await self._status_counts(
            session, Review, Review.organization_id == organization_id
        )
        content_publications = await self._status_counts(
            session, ContentPublication, ContentPublication.organization_id == organization_id
        )
        seo_crawl_runs = await self._status_counts(
            session, SEOCrawlRun, SEOCrawlRun.organization_id == organization_id
        )
        seo_opportunities = await self._status_counts(
            session, SEOOpportunity, SEOOpportunity.organization_id == organization_id
        )
        leads = await self._status_counts(session, Lead, Lead.organization_id == organization_id)
        # GA4 metrics supplement the summary only when a property is mapped and
        # synced; when GA4 is disconnected this returns a truthful empty state
        # and never blocks the rest of the Insights surface.
        ga4 = await self.analytics.summary(session, organization_id)
        return {
            "workflow_runs": workflow_runs,
            "gbp": {
                "locations": gbp_locations,
                "profile_snapshots": gbp_snapshots,
                "publications": gbp_publications,
            },
            "reviews": reviews,
            "content_publications": content_publications,
            "seo": {
                "crawl_runs": seo_crawl_runs,
                "opportunities": seo_opportunities,
            },
            "leads": leads,
            "ga4": ga4,
        }

    async def _count(
        self,
        session: AsyncSession,
        model: type[Any],
        where_clause: ColumnElement[bool],
    ) -> int:
        total = await session.scalar(select(func.count()).select_from(model).where(where_clause))
        return int(total or 0)

    async def _status_counts(
        self,
        session: AsyncSession,
        model: type[Any],
        where_clause: ColumnElement[bool],
    ) -> dict[str, int]:
        rows = (
            await session.execute(
                select(model.status, func.count()).where(where_clause).group_by(model.status)
            )
        ).all()
        return {str(status): int(count) for status, count in rows}
