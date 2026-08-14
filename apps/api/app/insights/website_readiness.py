"""Derived tenant-scoped website readiness read model.

Presents a unified view of website-related state without exposing
contradictory internal lifecycle semantics to clients. Combines
OrganizationDomain, SEOWebsite, Search Console mapping, Analytics
mapping, and crawl state into a single coherent read model.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.domains.models import OrganizationDomain
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.seo.models import SEOCrawlRun, SEOSearchProperty, SEOWebsite


def _iso(ts: datetime | None) -> str | None:
    return ts.isoformat() if ts else None


@dataclass(frozen=True, slots=True)
class WebsiteReadiness:
    """Derived website readiness facts for a tenant."""

    canonical_domain_configured: bool
    primary_domain: str | None
    domains: list[dict[str, object]]
    seo_websites: list[dict[str, object]]
    search_console_mapped: bool
    search_console_connected: bool
    search_console_last_sync: str | None
    search_console_freshness: str
    analytics_mapped: bool
    analytics_connected: bool
    analytics_last_sync: str | None
    analytics_freshness: str
    last_crawl_at: str | None
    crawl_ready: bool


@dataclass(frozen=True, slots=True, init=False)
class WebsiteReadinessService:
    """Derive website readiness from authoritative records only."""

    async def readiness(self, session: AsyncSession, organization_id: UUID) -> dict[str, object]:
        """Return tenant-scoped website readiness facts.

        Uses actual authoritative records — OrganizationDomain for
        domain configuration, SEOWebsite for SEO website state,
        SEOSearchProperty for Search Console mapping, AnalyticsProperty
        for GA4 mapping, and SEOCrawlRun for crawl history.
        """
        # OrganizationDomains
        domains = list(
            await session.scalars(
                select(OrganizationDomain).where(
                    OrganizationDomain.organization_id == organization_id,
                )
            )
        )
        canonical_configured = any(d.status == "active" for d in domains)
        primary = next((d.domain for d in domains if d.is_primary and d.status == "active"), None)
        domain_data = [
            {
                "id": str(d.id),
                "domain": d.domain,
                "is_primary": d.is_primary,
                "status": d.status,
            }
            for d in domains
        ]

        # SEO Websites
        websites = list(
            await session.scalars(
                select(SEOWebsite)
                .where(
                    SEOWebsite.organization_id == organization_id,
                )
                .order_by(SEOWebsite.created_at.desc())
            )
        )
        website_data = [
            {
                "id": str(w.id),
                "key": w.key,
                "name": w.name,
                "canonical_origin": w.canonical_origin,
                "status": w.status,
                "ownership_status": w.ownership_status,
                "verified_at": _iso(w.verified_at),
            }
            for w in websites
        ]

        # Search Console — check if any website has a mapped Search Console property
        search_console_mapped = False
        sc_last_sync: datetime | None = None
        sc_freshness = "not_mapped"
        for w in websites:
            sc_props = list(
                await session.scalars(
                    select(SEOSearchProperty).where(
                        SEOSearchProperty.organization_id == organization_id,
                        SEOSearchProperty.website_id == w.id,
                        SEOSearchProperty.provider == "google_search_console",
                        SEOSearchProperty.mapping_status == "mapped",
                    )
                )
            )
            if sc_props:
                search_console_mapped = True
                # Get most recent sync
                for sp in sc_props:
                    if sp.last_synced_at and (
                        sc_last_sync is None or sp.last_synced_at > sc_last_sync
                    ):
                        sc_last_sync = sp.last_synced_at
                    if sp.freshness_status == "fresh":
                        sc_freshness = "fresh"
                    elif sp.freshness_status != "never_synced" and sc_freshness == "not_mapped":
                        sc_freshness = sp.freshness_status

        if search_console_mapped and sc_freshness == "not_mapped":
            sc_freshness = "never_synced"

        # Analytics — check if any GA4 property is mapped
        analytics_mapped = False
        analytics_last_sync: datetime | None = None
        analytics_freshness = "not_mapped"
        ga4_props = list(
            await session.scalars(
                select(AnalyticsProperty).where(
                    AnalyticsProperty.organization_id == organization_id,
                    AnalyticsProperty.provider == "google_analytics",
                    AnalyticsProperty.mapping_status == "mapped",
                )
            )
        )
        if ga4_props:
            analytics_mapped = True
            for ap in ga4_props:
                if ap.last_synced_at and (
                    analytics_last_sync is None or ap.last_synced_at > analytics_last_sync
                ):
                    analytics_last_sync = ap.last_synced_at
                if ap.freshness_status == "fresh":
                    analytics_freshness = "fresh"
                elif ap.freshness_status != "never_synced" and analytics_freshness == "not_mapped":
                    analytics_freshness = ap.freshness_status

        if analytics_mapped and analytics_freshness == "not_mapped":
            analytics_freshness = "never_synced"

        # Last successful crawl
        last_crawl_at: datetime | None = None
        crawl_ready = False
        for w in websites:
            latest_completed = await session.scalar(
                select(SEOCrawlRun)
                .where(
                    SEOCrawlRun.organization_id == organization_id,
                    SEOCrawlRun.website_id == w.id,
                    SEOCrawlRun.status == "completed",
                )
                .order_by(SEOCrawlRun.completed_at.desc())
            )
            if latest_completed is not None:
                crawl_ready = True
                completed_at = latest_completed.completed_at
                if completed_at and (last_crawl_at is None or completed_at > last_crawl_at):
                    last_crawl_at = completed_at

        if not websites:
            crawl_ready = False

        return {
            "canonical_domain_configured": canonical_configured,
            "primary_domain": primary,
            "domains": domain_data,
            "seo_websites": website_data,
            "search_console_mapped": search_console_mapped,
            "search_console_connected": search_console_mapped,
            "search_console_last_sync": _iso(sc_last_sync),
            "search_console_freshness": sc_freshness,
            "analytics_mapped": analytics_mapped,
            "analytics_connected": analytics_mapped,
            "analytics_last_sync": _iso(analytics_last_sync),
            "analytics_freshness": analytics_freshness,
            "last_crawl_at": _iso(last_crawl_at),
            "crawl_ready": crawl_ready,
        }
