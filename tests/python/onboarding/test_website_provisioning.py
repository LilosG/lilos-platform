"""Activation bridges the configured primary domain to a crawlable website.

The defect these tests pin: ``OrganizationDomain`` and ``SEOWebsite`` described
the same website and nothing connected them, so a client could be fully
onboarded and active while the crawler, the website knowledge base, and every
"Learn more" CTA had no website at all — with no action in the product that
would have fixed it.
"""

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.database.base import utc_now
from apps.api.app.domains.models import OrganizationDomain
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.locations.enums import LocationType
from apps.api.app.locations.models import Location
from apps.api.app.onboarding.website_provisioning import (
    OnboardingWebsiteProvisioningService,
)
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.seo.models import SEOCrawlRun, SEOWebsite


def _run[T](coroutine: Callable[[], Coroutine[Any, Any, T]]) -> T:
    return asyncio.run(coroutine())


async def _seed_client(
    session: AsyncSession,
    *,
    domain: str | None = "fixture-client.com",
    domain_is_primary: bool = True,
    domain_status: str = "active",
    with_primary_location: bool = True,
) -> UUID:
    """Create a client at the state activation reaches it in."""
    organization = Organization(
        name="Provisioning Fixture Org",
        slug=f"provisioning-{uuid4().hex[:12]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ONBOARDING,
        timezone="UTC",
        default_currency="USD",
        version=1,
        onboarding_mode="managed",
    )
    session.add(organization)
    await session.flush()

    if with_primary_location:
        session.add(
            Location(
                organization_id=organization.id,
                name="Primary Site",
                slug=f"loc-{uuid4().hex[:12]}",
                location_type=LocationType.PHYSICAL,
                timezone="UTC",
                address_line_1="1 Fixture Way",
                city="Example",
                region="CA",
                postal_code="00000",
                country_code="US",
                is_primary=True,
                version=1,
            )
        )
    if domain is not None:
        session.add(
            OrganizationDomain(
                organization_id=organization.id,
                domain=domain,
                is_primary=domain_is_primary,
                status=domain_status,
                # The table requires an archival timestamp to accompany the
                # archived status; a fixture that skips it is rejected.
                archived_at=utc_now() if domain_status == "archived" else None,
                version=1,
            )
        )
    await session.flush()
    return organization.id


@pytest.mark.integration
def test_activation_provisions_the_website_and_queues_its_first_crawl(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = OnboardingWebsiteProvisioningService()

    async def exercise() -> None:
        async with onboarding_session_factory.begin() as session:
            organization_id = await _seed_client(session, domain="cocomaya.test")

        async with onboarding_session_factory.begin() as session:
            outcome = await service.provision(
                session,
                organization_id,
                actor_id=None,
                correlation_id="provisioning-test",
            )

            assert outcome.website_created is True
            assert outcome.crawl_enqueued is True
            assert outcome.skipped_reason is None
            assert outcome.canonical_origin == "https://cocomaya.test"

        async with onboarding_session_factory() as session:
            website = await session.scalar(
                select(SEOWebsite).where(SEOWebsite.organization_id == organization_id)
            )
            assert website is not None
            assert website.canonical_origin == "https://cocomaya.test"
            assert website.key == "cocomaya-test"
            assert website.name == "cocomaya.test"

            # Bound to the primary location, so location-scoped product work
            # resolves the site without a second manual mapping step.
            primary_location_id = await session.scalar(
                select(Location.id).where(
                    Location.organization_id == organization_id,
                    Location.is_primary.is_(True),
                )
            )
            assert website.location_id == primary_location_id

            crawl = await session.scalar(
                select(SEOCrawlRun).where(SEOCrawlRun.organization_id == organization_id)
            )
            assert crawl is not None
            assert crawl.website_id == website.id
            assert crawl.status == "queued"

            # The crawl is only real if a worker will pick it up: the workflow
            # run must exist and carry the crawl id the handler reads.
            workflow_run = await session.scalar(
                select(WorkflowRun).where(WorkflowRun.id == crawl.workflow_run_id)
            )
            assert workflow_run is not None
            assert workflow_run.organization_id == organization_id
            assert workflow_run.input_document["crawl_run_id"] == str(crawl.id)

            job = await session.scalar(
                select(Job).where(Job.idempotency_key == f"run:{workflow_run.id}")
            )
            assert job is not None
            assert job.job_type == "workflow.execute"

    _run(exercise)


@pytest.mark.integration
def test_provisioning_twice_neither_duplicates_the_website_nor_recrawls_it(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Activation can be retried; retrying must not cost the client a second crawl."""
    service = OnboardingWebsiteProvisioningService()

    async def exercise() -> None:
        async with onboarding_session_factory.begin() as session:
            organization_id = await _seed_client(session, domain="retry-client.test")

        async with onboarding_session_factory.begin() as session:
            first = await service.provision(
                session, organization_id, actor_id=None, correlation_id="provisioning-first"
            )
        async with onboarding_session_factory.begin() as session:
            second = await service.provision(
                session, organization_id, actor_id=None, correlation_id="provisioning-second"
            )

        assert second.website_id == first.website_id
        assert second.website_created is False
        assert second.crawl_enqueued is False
        assert second.skipped_reason == "CRAWL_ALREADY_STARTED"

        async with onboarding_session_factory() as session:
            websites = await session.scalar(
                select(func.count())
                .select_from(SEOWebsite)
                .where(SEOWebsite.organization_id == organization_id)
            )
            crawls = await session.scalar(
                select(func.count())
                .select_from(SEOCrawlRun)
                .where(SEOCrawlRun.organization_id == organization_id)
            )
            assert websites == 1
            assert crawls == 1

    _run(exercise)


@pytest.mark.integration
def test_an_existing_website_on_a_subdomain_is_reused_not_duplicated(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """A site whose canonical origin is www. is the same site as the bare domain."""
    service = OnboardingWebsiteProvisioningService()

    async def exercise() -> None:
        async with onboarding_session_factory.begin() as session:
            organization_id = await _seed_client(session, domain="existing-client.test")
            session.add(
                SEOWebsite(
                    organization_id=organization_id,
                    location_id=None,
                    key="already-here",
                    name="Existing site",
                    canonical_origin="https://www.existing-client.test",
                    status="active",
                    ownership_status="verified",
                    version=1,
                )
            )

        async with onboarding_session_factory.begin() as session:
            outcome = await service.provision(
                session, organization_id, actor_id=None, correlation_id="provisioning-reuse"
            )
            assert outcome.website_created is False
            assert outcome.crawl_enqueued is True

        async with onboarding_session_factory() as session:
            websites = list(
                await session.scalars(
                    select(SEOWebsite).where(SEOWebsite.organization_id == organization_id)
                )
            )
            assert len(websites) == 1
            assert websites[0].key == "already-here"

    _run(exercise)


@pytest.mark.integration
def test_an_unrelated_website_does_not_satisfy_the_primary_domain(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Having *a* website is not having *this* website."""
    service = OnboardingWebsiteProvisioningService()

    async def exercise() -> None:
        async with onboarding_session_factory.begin() as session:
            organization_id = await _seed_client(session, domain="wanted-client.test")
            session.add(
                SEOWebsite(
                    organization_id=organization_id,
                    location_id=None,
                    key="unrelated",
                    name="Some other site",
                    canonical_origin="https://something-else.test",
                    status="active",
                    ownership_status="verified",
                    version=1,
                )
            )

        async with onboarding_session_factory.begin() as session:
            outcome = await service.provision(
                session, organization_id, actor_id=None, correlation_id="provisioning-unrelated"
            )
            assert outcome.website_created is True

        async with onboarding_session_factory() as session:
            origins = {
                row
                for row in await session.scalars(
                    select(SEOWebsite.canonical_origin).where(
                        SEOWebsite.organization_id == organization_id
                    )
                )
            }
            assert origins == {"https://something-else.test", "https://wanted-client.test"}

    _run(exercise)


@pytest.mark.integration
def test_a_taken_website_key_does_not_break_provisioning(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """The derived key collides with an unrelated row; the unique constraint holds."""
    service = OnboardingWebsiteProvisioningService()

    async def exercise() -> None:
        async with onboarding_session_factory.begin() as session:
            organization_id = await _seed_client(session, domain="collide-client.test")
            session.add(
                SEOWebsite(
                    organization_id=organization_id,
                    location_id=None,
                    key="collide-client-test",
                    name="Squatting on the derived key",
                    canonical_origin="https://unrelated-origin.test",
                    status="active",
                    ownership_status="verified",
                    version=1,
                )
            )

        async with onboarding_session_factory.begin() as session:
            outcome = await service.provision(
                session, organization_id, actor_id=None, correlation_id="provisioning-collide"
            )
            assert outcome.website_created is True

        async with onboarding_session_factory() as session:
            provisioned = await session.scalar(
                select(SEOWebsite).where(
                    SEOWebsite.organization_id == organization_id,
                    SEOWebsite.canonical_origin == "https://collide-client.test",
                )
            )
            assert provisioned is not None
            assert provisioned.key == "collide-client-test-2"

    _run(exercise)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"domain": None}, "NO_PRIMARY_DOMAIN"),
        ({"domain_is_primary": False}, "NO_PRIMARY_DOMAIN"),
        ({"domain_status": "archived", "domain_is_primary": False}, "NO_PRIMARY_DOMAIN"),
    ],
)
def test_without_an_active_primary_domain_provisioning_reports_why_and_writes_nothing(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
    kwargs: dict[str, object],
    reason: str,
) -> None:
    """No guessing: absent a primary domain there is no website to provision."""
    service = OnboardingWebsiteProvisioningService()

    async def exercise() -> None:
        async with onboarding_session_factory.begin() as session:
            organization_id = await _seed_client(session, **kwargs)  # type: ignore[arg-type]

        async with onboarding_session_factory.begin() as session:
            outcome = await service.provision(
                session, organization_id, actor_id=None, correlation_id="provisioning-none"
            )
            assert outcome.skipped_reason == reason
            assert outcome.provisioned is False
            assert outcome.crawl_enqueued is False

        async with onboarding_session_factory() as session:
            websites = await session.scalar(
                select(func.count())
                .select_from(SEOWebsite)
                .where(SEOWebsite.organization_id == organization_id)
            )
            assert websites == 0

    _run(exercise)


@pytest.mark.integration
def test_a_client_without_a_primary_location_still_gets_its_website(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Activation guarantees a primary location, but provisioning must not
    depend on a guarantee made elsewhere: an unbound website beats none."""
    service = OnboardingWebsiteProvisioningService()

    async def exercise() -> None:
        async with onboarding_session_factory.begin() as session:
            organization_id = await _seed_client(
                session, domain="no-location.test", with_primary_location=False
            )

        async with onboarding_session_factory.begin() as session:
            outcome = await service.provision(
                session, organization_id, actor_id=None, correlation_id="provisioning-no-location"
            )
            assert outcome.website_created is True

        async with onboarding_session_factory() as session:
            website = await session.scalar(
                select(SEOWebsite).where(SEOWebsite.organization_id == organization_id)
            )
            assert website is not None
            assert website.location_id is None

    _run(exercise)


@pytest.mark.integration
def test_crawl_can_be_deferred_without_losing_the_website(
    onboarding_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = OnboardingWebsiteProvisioningService()

    async def exercise() -> None:
        async with onboarding_session_factory.begin() as session:
            organization_id = await _seed_client(session, domain="deferred.test")

        async with onboarding_session_factory.begin() as session:
            outcome = await service.provision(
                session,
                organization_id,
                actor_id=None,
                correlation_id="provisioning-deferred",
                enqueue_crawl=False,
            )
            assert outcome.provisioned is True
            assert outcome.crawl_enqueued is False
            assert outcome.skipped_reason == "CRAWL_NOT_REQUESTED"

        async with onboarding_session_factory() as session:
            crawls = await session.scalar(
                select(func.count())
                .select_from(SEOCrawlRun)
                .where(SEOCrawlRun.organization_id == organization_id)
            )
            assert crawls == 0

    _run(exercise)
