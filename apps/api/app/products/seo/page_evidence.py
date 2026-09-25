"""Internal read contract for page-level evidence; no scoring or inference."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.insights.models import InsightSource, MetricObservation
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.seo.models import (
    SEOCrawlPageObservation,
    SEOPage,
    SEOSearchObservation,
)


@dataclass(frozen=True, slots=True)
class PageEvidence:
    page: SEOPage
    crawl: tuple[SEOCrawlPageObservation, ...]
    gsc: tuple[SEOSearchObservation, ...]
    ga4: tuple[MetricObservation, ...]
    website_unresolved_gsc: tuple[SEOSearchObservation, ...]
    website_unresolved_ga4: tuple[MetricObservation, ...]
    ga4_availability: tuple[tuple[str, str | None], ...]


async def read_page_evidence(
    session: AsyncSession, organization_id: UUID, website_id: UUID, page_id: UUID
) -> PageEvidence | None:
    """Expose persisted evidence and unresolved rows under a confirmed website."""
    page = await session.scalar(
        select(SEOPage).where(
            SEOPage.organization_id == organization_id,
            SEOPage.website_id == website_id,
            SEOPage.id == page_id,
        )
    )
    if page is None:
        return None
    crawl = tuple(
        await session.scalars(
            select(SEOCrawlPageObservation)
            .where(
                SEOCrawlPageObservation.organization_id == organization_id,
                SEOCrawlPageObservation.website_id == website_id,
                SEOCrawlPageObservation.page_id == page_id,
            )
            .order_by(SEOCrawlPageObservation.observed_at.desc())
        )
    )
    gsc_rows = tuple(
        await session.scalars(
            select(SEOSearchObservation)
            .where(
                SEOSearchObservation.organization_id == organization_id,
                SEOSearchObservation.website_id == website_id,
                SEOSearchObservation.dimensions["page"].astext.is_not(None),
                or_(
                    SEOSearchObservation.page_id == page_id,
                    SEOSearchObservation.page_id.is_(None),
                ),
            )
            .order_by(SEOSearchObservation.date_end.desc())
        )
    )
    ga4_rows = tuple(
        await session.scalars(
            select(MetricObservation)
            .join(
                InsightSource,
                (InsightSource.organization_id == MetricObservation.organization_id)
                & (InsightSource.id == MetricObservation.source_id),
            )
            .where(
                MetricObservation.organization_id == organization_id,
                MetricObservation.website_id == website_id,
                MetricObservation.dimensions["observation_type"].astext == "organic_landing_page",
                InsightSource.provider == "google_analytics",
                or_(MetricObservation.page_id == page_id, MetricObservation.page_id.is_(None)),
            )
            .order_by(MetricObservation.period_end.desc())
        )
    )
    properties = tuple(
        await session.scalars(
            select(AnalyticsProperty).where(
                AnalyticsProperty.organization_id == organization_id,
                AnalyticsProperty.website_id == website_id,
            )
        )
    )
    return PageEvidence(
        page=page,
        crawl=crawl,
        gsc=tuple(row for row in gsc_rows if row.page_id == page_id),
        ga4=tuple(row for row in ga4_rows if row.page_id == page_id),
        website_unresolved_gsc=tuple(row for row in gsc_rows if row.page_id is None),
        website_unresolved_ga4=tuple(row for row in ga4_rows if row.page_id is None),
        ga4_availability=tuple(
            (prop.page_evidence_status or "unavailable", prop.page_evidence_limitation)
            for prop in properties
        ),
    )
