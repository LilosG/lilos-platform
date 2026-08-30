"""Bridges a client's configured primary domain to a crawlable SEO website.

The platform stored the same website twice and connected the two halves
nowhere. ``OrganizationDomain`` is what onboarding asks the agency for and what
onboarding calls complete; ``SEOWebsite`` is the only thing the crawler, the
website knowledge base, and every "Learn more" CTA can actually use. Nothing
created the second from the first, so a freshly activated client showed a
completed "Website and primary domain" step, an empty SEO product, and "no site
is connected" on pages that needed the crawl — with no action anywhere that
would have fixed it.

Activation is the correct and only bridge point: activation eligibility already
guarantees a primary domain and a primary location exist, so at that instant the
platform holds everything it needs to provision the website and start its first
crawl without asking the operator for anything twice.

Provisioning runs in the caller's transaction, so a client is either activated
with a website and a queued crawl or not activated at all. A half-provisioned
client is the state this module exists to eliminate; it must not be able to
create one.
"""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.domains.matching import (
    canonical_origin_for_domain,
    origin_matches_domain,
    website_key_for_domain,
)
from apps.api.app.domains.service import OrganizationDomainService
from apps.api.app.locations.repository import LocationRepository
from apps.api.app.products.seo.contracts import CrawlRequest, WebsiteCreate
from apps.api.app.products.seo.models import SEOCrawlRun, SEOWebsite
from apps.api.app.products.seo.service import SEOService

CRAWL_WORKFLOW_KEY = "seo.crawl_or_analysis"


@dataclass(frozen=True, slots=True)
class WebsiteProvisioning:
    """What provisioning did, in terms an operator can be shown.

    ``skipped_reason`` is a stable machine code, not prose: the caller decides
    how to surface it, and no branch of this service returns silently.
    """

    website_id: UUID | None = None
    canonical_origin: str | None = None
    website_created: bool = False
    crawl_run_id: UUID | None = None
    crawl_enqueued: bool = False
    skipped_reason: str | None = None

    @property
    def provisioned(self) -> bool:
        return self.website_id is not None


class OnboardingWebsiteProvisioningService:
    """Provisions the SEO website implied by a client's primary domain."""

    def __init__(self, seo: SEOService | None = None) -> None:
        self.domains = OrganizationDomainService()
        self.locations = LocationRepository()
        self.seo = seo if seo is not None else SEOService()

    async def provision(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
        enqueue_crawl: bool = True,
    ) -> WebsiteProvisioning:
        """Ensure the primary domain has an SEO website, and start its first crawl.

        Idempotent by construction: an existing website matching the primary
        domain is reused, and the crawl carries a website-derived idempotency
        key, so re-activating a client neither duplicates the website nor
        re-crawls it.
        """
        domains = await self.domains.list(session, organization_id)
        primary = next(
            (domain for domain in domains if domain.is_primary and domain.status.value == "active"),
            None,
        )
        if primary is None:
            return WebsiteProvisioning(skipped_reason="NO_PRIMARY_DOMAIN")

        website, created = await self._resolve_website(
            session,
            organization_id,
            primary.domain,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

        if not enqueue_crawl:
            return WebsiteProvisioning(
                website_id=website.id,
                canonical_origin=website.canonical_origin,
                website_created=created,
                skipped_reason="CRAWL_NOT_REQUESTED",
            )

        existing_crawl = await session.scalar(
            select(SEOCrawlRun.id).where(
                SEOCrawlRun.organization_id == organization_id,
                SEOCrawlRun.website_id == website.id,
            )
        )
        if existing_crawl is not None:
            return WebsiteProvisioning(
                website_id=website.id,
                canonical_origin=website.canonical_origin,
                website_created=created,
                skipped_reason="CRAWL_ALREADY_STARTED",
            )

        # start_named(enqueue_job=False) then enqueue_crawl is the supported
        # order: the crawl row has to exist before the job can execute, or the
        # worker fails the run with MISSING_CRAWL_RUN_ID.
        workflow = await self.seo.execution.start_named(
            session,
            organization_id,
            CRAWL_WORKFLOW_KEY,
            f"onboarding-activation-crawl:{website.id}",
            location_id=website.location_id,
            input_document={},
            correlation_id=correlation_id,
            actor_id=actor_id,
            enqueue_job=False,
        )
        crawl_run = await self.seo.enqueue_crawl(
            session,
            organization_id,
            website.id,
            CrawlRequest(
                workflow_run_id=workflow.id,
                idempotency_key=f"onboarding-activation:{website.id}",
            ),
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        return WebsiteProvisioning(
            website_id=website.id,
            canonical_origin=website.canonical_origin,
            website_created=created,
            crawl_run_id=crawl_run.id,
            crawl_enqueued=True,
        )

    async def _resolve_website(
        self,
        session: AsyncSession,
        organization_id: UUID,
        domain: str,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> tuple[SEOWebsite, bool]:
        """Return the website for this domain, creating it when absent."""
        websites = list(
            await session.scalars(
                select(SEOWebsite)
                .where(SEOWebsite.organization_id == organization_id)
                # Oldest first, id as tiebreak: when more than one website
                # matches, the answer must not depend on row order.
                .order_by(SEOWebsite.created_at.asc(), SEOWebsite.id.asc())
            )
        )
        for website in websites:
            if origin_matches_domain(website.canonical_origin, domain):
                return website, False

        primary_location = await self.locations.get_primary(session, organization_id)
        created = await self.seo.create_website(
            session,
            organization_id,
            WebsiteCreate(
                location_id=primary_location.id if primary_location is not None else None,
                key=website_key_for_domain(domain, taken={item.key for item in websites}),
                name=domain,
                canonical_origin=canonical_origin_for_domain(domain),
            ),
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        return created, True
