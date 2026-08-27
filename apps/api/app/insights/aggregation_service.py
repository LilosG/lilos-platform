"""Insights aggregation service wiring real product-history data.

Computes a cross-product activity summary from REAL rows in the existing
product tables — no simulated charts or fabricated metrics.  Every count is
derived by querying the live tables (workflow runs, GBP snapshots, reviews,
content publications, SEO opportunities/crawl runs, leads) so the Insights
surface reflects genuine operational history.
"""

from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.models import WorkflowRun
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.content.models import ContentItem, ContentPublication
from apps.api.app.products.gbp.models import GBPLocation, GBPProfileSnapshot, GBPPublication
from apps.api.app.products.leads.models import Lead
from apps.api.app.products.reviews.models import Review
from apps.api.app.products.seo.models import SEOCrawlRun, SEOOpportunity, SEOWebsite


@dataclass(frozen=True, slots=True)
class InsightsService:
    """Aggregate real cross-product activity into a reporting read model."""

    analytics: AnalyticsService = field(default_factory=AnalyticsService)

    async def summary(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        location_id: UUID | None = None,
    ) -> dict[str, object]:
        """Return a real activity summary derived from live product tables."""

        def scoped(model: type[Any]) -> ColumnElement[bool]:
            if location_id is None:
                return cast(ColumnElement[bool], model.organization_id == organization_id)
            return and_(
                model.organization_id == organization_id,
                model.location_id == location_id,
            )

        workflow_runs = await self._status_counts(session, WorkflowRun, scoped(WorkflowRun))
        gbp_locations = await self._count(
            session,
            GBPLocation,
            and_(
                GBPLocation.organization_id == organization_id,
                GBPLocation.mapping_status == "confirmed",
                GBPLocation.location_id == location_id if location_id is not None else true(),
            ),
        )
        scoped_gbp_locations = select(GBPLocation.id).where(
            GBPLocation.organization_id == organization_id,
            GBPLocation.mapping_status == "confirmed",
            GBPLocation.location_id == location_id if location_id is not None else true(),
        )
        gbp_snapshots = await self._count(
            session,
            GBPProfileSnapshot,
            and_(
                GBPProfileSnapshot.organization_id == organization_id,
                GBPProfileSnapshot.gbp_location_id.in_(scoped_gbp_locations),
            ),
        )
        gbp_publications = await self._status_counts(
            session, GBPPublication, scoped(GBPPublication)
        )
        reviews = await self._status_counts(session, Review, scoped(Review))
        scoped_content_items = select(ContentItem.id).where(
            ContentItem.organization_id == organization_id,
            or_(ContentItem.location_id == location_id, ContentItem.location_id.is_(None))
            if location_id is not None
            else true(),
        )
        content_publications = await self._status_counts(
            session,
            ContentPublication,
            and_(
                ContentPublication.organization_id == organization_id,
                ContentPublication.content_item_id.in_(scoped_content_items),
            ),
        )
        scoped_websites = select(SEOWebsite.id).where(
            SEOWebsite.organization_id == organization_id,
            or_(SEOWebsite.location_id == location_id, SEOWebsite.location_id.is_(None))
            if location_id is not None
            else true(),
        )
        seo_crawl_runs = await self._status_counts(
            session,
            SEOCrawlRun,
            and_(
                SEOCrawlRun.organization_id == organization_id,
                SEOCrawlRun.website_id.in_(scoped_websites),
            ),
        )
        seo_opportunity_scope = (
            and_(
                SEOOpportunity.organization_id == organization_id,
                or_(
                    SEOOpportunity.location_id == location_id,
                    SEOOpportunity.location_id.is_(None),
                ),
            )
            if location_id is not None
            else SEOOpportunity.organization_id == organization_id
        )
        seo_opportunities = await self._status_counts(
            session, SEOOpportunity, seo_opportunity_scope
        )
        leads = await self._status_counts(session, Lead, scoped(Lead))
        # GA4 metrics supplement the summary only when a property is mapped and
        # synced; when GA4 is disconnected this returns a truthful empty state
        # and never blocks the rest of the Insights surface.
        ga4 = await self.analytics.summary(session, organization_id, location_id=location_id)
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
