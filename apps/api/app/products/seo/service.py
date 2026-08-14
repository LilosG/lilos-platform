"""Deterministic URL, crawl-safety, score, and missing-data policies plus SEO domain service."""

import ipaddress
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from uuid import UUID

import httpx
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.repository import AuditEventRepository
from apps.api.app.audit.service import AuditEventService
from apps.api.app.execution.models import Job, WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.locations.models import Location
from apps.api.app.notifications.models import NotificationTemplate
from apps.api.app.notifications.service import NotificationService
from apps.api.app.products.seo.contracts import (
    CrawlRequest,
    ImplementationTaskCreate,
    ImplementationTaskVerify,
    OutcomeRecord,
    RecommendationCreate,
    RecommendationDecision,
    SearchPropertyCreate,
    WebsiteCreate,
)
from apps.api.app.products.seo.crawl_engine import (
    LILOS_USER_AGENT,
    CrawlConfig,
    CrawlEngine,
    CrawlReport,
    host_of,
    normalize_crawl_url,
)
from apps.api.app.products.seo.errors import (
    SEOImplementationTaskNotFoundError,
    SEOOpportunityNotFoundError,
    SEOQueryInvalidError,
    SEORecommendationNotDecidableError,
    SEORecommendationNotFoundError,
    SEOSearchPropertyNotConfiguredError,
    SEOWebsiteNotFoundError,
)
from apps.api.app.products.seo.models import (
    SEOCrawlRun,
    SEOImplementationTask,
    SEOOpportunity,
    SEOOutcome,
    SEOPage,
    SEORecommendationRevision,
    SEOSearchProperty,
    SEOWebsite,
)

NOTIFICATION_TEMPLATES = {
    "seo.recommendation.awaiting_approval": ("in_app", "An SEO recommendation needs approval."),
    "seo.opportunity.identified": ("in_app", "A new SEO opportunity was identified."),
}


@dataclass(frozen=True, slots=True)
class NormalizedURL:
    value: str
    reasons: tuple[str, ...]


def normalize_url(value: str) -> NormalizedURL:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("unsupported URL")
    scheme = parsed.scheme.lower()
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    port = parsed.port
    netloc = (
        host
        if port is None or (scheme, port) in {("http", 80), ("https", 443)}
        else f"{host}:{port}"
    )
    path = quote(unquote(parsed.path or "/"), safe="/%:@-._~!$&'()*+,;=")
    reasons = ["fragment_removed"] if parsed.fragment else []
    if parsed.hostname != host:
        reasons.append("host_normalized")
    if netloc != parsed.netloc:
        reasons.append("default_port_or_authority_normalized")
    return NormalizedURL(urlunsplit((scheme, netloc, path, parsed.query, "")), tuple(reasons))


def validate_crawl_target(value: str, allowed_hosts: frozenset[str]) -> NormalizedURL:
    normalized = normalize_url(value)
    host = urlsplit(normalized.value).hostname
    if host not in allowed_hosts:
        raise ValueError("crawl host is outside the confirmed website scope")
    try:
        address = ipaddress.ip_address(host or "")
    except ValueError:
        return normalized
    if not address.is_global:
        raise ValueError("private and special network targets are prohibited")
    return normalized


def opportunity_score(
    *,
    search_potential: int,
    business_value: int,
    relevance: int,
    confidence: int,
    urgency: int,
    effort: int,
) -> tuple[int, dict[str, int]]:
    inputs = {
        "search_potential": search_potential,
        "business_value": business_value,
        "relevance": relevance,
        "confidence": confidence,
        "urgency": urgency,
        "effort": effort,
    }
    if any(value < 0 or value > 100 for value in inputs.values()):
        raise ValueError("score inputs must be between 0 and 100")
    score = round(
        (
            search_potential * 2
            + business_value * 3
            + relevance * 2
            + confidence * 2
            + urgency
            - effort
        )
        / 9
    )
    return max(0, min(100, score)), inputs


def metric_value(value: int | float | None, quality: str) -> dict[str, object]:
    return {"value": value, "state": "missing" if value is None else quality}


class SEOService:
    def __init__(
        self, http_client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient
    ) -> None:
        self.audit = AuditEventService()
        self.audit_repository = AuditEventRepository()
        self.notifications = NotificationService()
        self.execution = ExecutionService()
        self._http_client_factory = http_client_factory

    async def _audit(
        self,
        session: AsyncSession,
        *,
        event: str,
        organization_id: UUID,
        location_id: UUID | None,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID,
        correlation_id: str,
        summary: str,
        metadata: dict[str, object],
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=event,
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                organization_id=organization_id,
                location_id=location_id,
                product_key="seo",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    async def _notify(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        event_type: str,
        idempotency_key: str,
        context: dict[str, object],
        priority: str = "normal",
    ) -> None:
        channel, body = NOTIFICATION_TEMPLATES[event_type]
        template = await session.scalar(
            select(NotificationTemplate).where(
                NotificationTemplate.organization_id == organization_id,
                NotificationTemplate.key == event_type,
                NotificationTemplate.status == "active",
            )
        )
        if template is None:
            template = NotificationTemplate(
                organization_id=organization_id,
                key=event_type,
                version=1,
                channel=channel,
                body_template=body,
                status="active",
            )
            session.add(template)
            await session.flush()
        await self.notifications.create_event(
            session,
            organization_id=organization_id,
            template_id=template.id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            context=context,
            priority=priority,
            location_id=location_id,
        )

    async def create_website(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: WebsiteCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> SEOWebsite:
        website = SEOWebsite(
            organization_id=organization_id,
            location_id=command.location_id,
            key=command.key,
            name=command.name,
            canonical_origin=command.canonical_origin,
            status="pending_verification",
            ownership_status="unverified",
            version=1,
        )
        session.add(website)
        await session.flush()
        await self._audit(
            session,
            event="seo.website.created",
            organization_id=organization_id,
            location_id=command.location_id,
            actor_id=actor_id,
            resource_type="seo_website",
            resource_id=website.id,
            correlation_id=correlation_id,
            summary=f"SEO website created: {website.name}.",
            metadata={"canonical_origin": website.canonical_origin},
        )
        return website

    async def list_websites(self, session: AsyncSession, organization_id: UUID) -> list[SEOWebsite]:
        return list(
            await session.scalars(
                select(SEOWebsite)
                .where(SEOWebsite.organization_id == organization_id)
                .order_by(SEOWebsite.created_at.desc())
            )
        )

    async def get_website(
        self, session: AsyncSession, organization_id: UUID, website_id: UUID
    ) -> SEOWebsite:
        website = await session.scalar(
            select(SEOWebsite).where(
                SEOWebsite.organization_id == organization_id, SEOWebsite.id == website_id
            )
        )
        if not website:
            raise SEOWebsiteNotFoundError
        return website

    async def create_search_property(
        self,
        session: AsyncSession,
        organization_id: UUID,
        website_id: UUID,
        command: SearchPropertyCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> SEOSearchProperty:
        website = await self.get_website(session, organization_id, website_id)
        connection = await session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.id == command.connection_id,
                IntegrationConnection.status == "connected",
            )
        )
        if not connection:
            raise SEOSearchPropertyNotConfiguredError
        prop = SEOSearchProperty(
            organization_id=organization_id,
            website_id=website.id,
            connection_id=connection.id,
            provider="google_search_console",
            external_property_id=command.external_property_id,
            property_type=command.property_type,
            mapping_status="mapped",
            freshness_status="never_synced",
        )
        session.add(prop)
        await session.flush()
        await self._audit(
            session,
            event="seo.search_property.mapped",
            organization_id=organization_id,
            location_id=website.location_id,
            actor_id=actor_id,
            resource_type="seo_website",
            resource_id=website.id,
            correlation_id=correlation_id,
            summary="Search Console property mapped.",
            metadata={"property_type": command.property_type},
        )
        return prop

    async def list_search_properties(
        self, session: AsyncSession, organization_id: UUID, website_id: UUID
    ) -> list[SEOSearchProperty]:
        return list(
            await session.scalars(
                select(SEOSearchProperty).where(
                    SEOSearchProperty.organization_id == organization_id,
                    SEOSearchProperty.website_id == website_id,
                )
            )
        )

    async def enqueue_crawl(
        self,
        session: AsyncSession,
        organization_id: UUID,
        website_id: UUID,
        command: CrawlRequest,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> SEOCrawlRun:
        """HTTP path: create a queued crawl run and enqueue the worker job.
        Returns promptly — the crawl executes in the worker."""
        website = await self.get_website(session, organization_id, website_id)

        existing = await session.scalar(
            select(SEOCrawlRun).where(
                SEOCrawlRun.organization_id == organization_id,
                SEOCrawlRun.idempotency_key == command.idempotency_key,
            )
        )
        if existing:
            return existing

        workflow_run = await session.scalar(
            select(WorkflowRun)
            .where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.id == command.workflow_run_id,
            )
            .with_for_update()
        )
        if not workflow_run:
            raise ValueError("workflow run not found")

        workflow_run.input_document = {
            "website_id": str(website.id),
            "crawl_run_id": "",  # filled after flush
            "workflow_run_id": str(command.workflow_run_id),
            "idempotency_key": command.idempotency_key,
            "max_pages": command.max_pages,
            "max_depth": command.max_depth,
            "crawl_delay_seconds": command.crawl_delay_seconds,
            "request_timeout_seconds": command.request_timeout_seconds,
            "total_timeout_seconds": command.total_timeout_seconds,
            "max_redirects": command.max_redirects,
            "concurrency": command.concurrency,
            "retry_limit": command.retry_limit,
            "seed_paths": list(command.seed_paths),
        }
        await session.flush()

        crawl_run = SEOCrawlRun(
            organization_id=organization_id,
            website_id=website.id,
            workflow_run_id=workflow_run.id,
            idempotency_key=command.idempotency_key,
            status="queued",
            max_pages=command.max_pages,
            max_depth=command.max_depth,
            crawl_delay_seconds=command.crawl_delay_seconds,
            safe_result={},
        )
        session.add(crawl_run)
        await session.flush()

        workflow_run.input_document = {
            **workflow_run.input_document,
            "crawl_run_id": str(crawl_run.id),
        }
        await session.flush()

        session.add(
            Job(
                organization_id=organization_id,
                workflow_run_id=workflow_run.id,
                job_type="workflow.execute",
                status="queued",
                idempotency_key=f"run:{workflow_run.id}",
                payload={"run_id": str(workflow_run.id)},
            )
        )
        await session.flush()

        await self._audit(
            session,
            event="seo.crawl.queued",
            organization_id=organization_id,
            location_id=website.location_id,
            actor_id=actor_id,
            resource_type="seo_website",
            resource_id=website.id,
            correlation_id=correlation_id,
            summary=f"Crawl queued: max={command.max_pages} pages, depth={command.max_depth}.",
            metadata={"crawl_run_id": str(crawl_run.id)},
        )
        return crawl_run

    async def execute_crawl(
        self,
        session: AsyncSession,
        organization_id: UUID,
        crawl_run_id: UUID,
        *,
        correlation_id: str,
    ) -> SEOCrawlRun:
        """Worker path: run the crawl engine to completion, persisting pages incrementally."""
        crawl_run = await session.scalar(
            select(SEOCrawlRun)
            .where(
                SEOCrawlRun.organization_id == organization_id,
                SEOCrawlRun.id == crawl_run_id,
            )
            .with_for_update()
        )
        if not crawl_run:
            raise ValueError("crawl run not found")
        if crawl_run.status not in ("queued", "running"):
            if crawl_run.status in ("success", "partial", "error"):
                return crawl_run
            raise ValueError(f"crawl run not executable: {crawl_run.status}")

        website = await self.get_website(session, organization_id, crawl_run.website_id)
        now = datetime.now(UTC)
        crawl_run.status = "running"
        crawl_run.started_at = now
        await session.flush()

        allowed_host_raw = host_of(normalize_crawl_url(website.canonical_origin))
        if not allowed_host_raw:
            crawl_run.status = "error"
            crawl_run.stop_reason = "Could not determine host from canonical origin"
            await session.flush()
            return crawl_run
        allowed_host = allowed_host_raw.casefold()

        workflow_run = await session.scalar(
            select(WorkflowRun).where(
                WorkflowRun.organization_id == organization_id,
                WorkflowRun.id == crawl_run.workflow_run_id,
            )
        )
        input_doc: dict[str, Any] = workflow_run.input_document if workflow_run else {}

        seeds: list[str] = [website.canonical_origin.rstrip("/") + "/"]
        seed_paths = input_doc.get("seed_paths", ["/"])
        if isinstance(seed_paths, list):
            for sp in seed_paths:
                if isinstance(sp, str):
                    if sp.startswith("http"):
                        seeds.append(sp)
                    else:
                        seeds.append(website.canonical_origin.rstrip("/") + "/" + sp.lstrip("/"))

        seeds = list(dict.fromkeys(seeds))

        config = CrawlConfig(
            base_origin=f"{urlsplit(website.canonical_origin).scheme}://{allowed_host_raw}",
            allowed_host=allowed_host,
            seeds=tuple(seeds),
            max_pages=crawl_run.max_pages,
            max_depth=int(input_doc.get("max_depth", 3)),
            crawl_delay=float(input_doc.get("crawl_delay_seconds", 1.0)),
            request_timeout=float(input_doc.get("request_timeout_seconds", 10.0)),
            total_timeout=float(input_doc.get("total_timeout_seconds", 600.0)),
            max_redirects=int(input_doc.get("max_redirects", 5)),
            concurrency=int(input_doc.get("concurrency", 4)),
            retry_limit=int(input_doc.get("retry_limit", 2)),
            user_agent=LILOS_USER_AGENT,
            query_param_policy="keep",
        )

        async def persist_page(page_data: Any) -> None:
            from apps.api.app.products.seo.crawl_engine import CrawledPage

            cp: CrawledPage = page_data
            existing_page = await session.scalar(
                select(SEOPage).where(
                    SEOPage.website_id == website.id,
                    SEOPage.normalized_url == cp.url,
                )
            )
            if existing_page is None:
                db_page = SEOPage(
                    organization_id=organization_id,
                    website_id=website.id,
                    normalized_url=cp.url,
                    observed_url=cp.observed_url,
                    canonical_url=cp.canonical_url,
                    normalization_reasons=[],
                    http_status=cp.http_status,
                    content_type=cp.content_type,
                    title=cp.title,
                    meta_description=cp.meta_description,
                    h1=cp.h1,
                    robots_directives=list(cp.robots_directives),
                    internal_links=list(cp.internal_links),
                    external_links=list(cp.external_links),
                    word_count=cp.word_count,
                    structured_data_present=cp.structured_data_present,
                    content_hash=cp.content_hash,
                    indexability=cp.indexability,
                    technical_issues=list(cp.technical_issues),
                    crawl_depth=cp.depth,
                    redirect_destination=cp.redirect_destination,
                    quality_status=cp.quality_status,
                    observed_at=datetime.now(UTC),
                )
                session.add(db_page)
                await session.flush()

        report: CrawlReport = CrawlReport(
            terminal_state="error", reason="Engine did not produce a report"
        )
        async with self._http_client_factory() as client:
            engine = CrawlEngine(config, client)
            report = await engine.crawl(on_page=persist_page)

        crawl_run.status = report.terminal_state
        crawl_run.stop_reason = report.reason
        crawl_run.completed_at = datetime.now(UTC)
        crawl_run.safe_result = {
            "pages_crawled": report.pages_fetched,
            "pages_queued": report.pages_queued,
            "max_depth_reached": report.max_depth_reached,
            "robots_available": report.robots_available,
            "robots_disallow_count": len(report.robots_disallowed),
            "robots_disallowed": list(report.robots_disallowed),
            "sitemap_files": list(report.sitemap_file_urls),
            "sitemap_page_count": report.sitemap_page_count,
            "sitemap_page_urls": list(report.sitemap_page_urls),
        }
        await session.flush()

        await self._audit(
            session,
            event=f"seo.crawl.{report.terminal_state}",
            organization_id=organization_id,
            location_id=website.location_id,
            actor_id=None,
            resource_type="seo_website",
            resource_id=website.id,
            correlation_id=correlation_id,
            summary=(
                f"Crawl {report.terminal_state}: {report.pages_fetched} pages fetched, "
                f"{report.sitemap_page_count} sitemap URLs. {report.reason}"
            ),
            metadata={
                "crawl_run_id": str(crawl_run.id),
                "pages_fetched": report.pages_fetched,
            },
        )
        return crawl_run

    async def get_crawl_run(
        self,
        session: AsyncSession,
        organization_id: UUID,
        crawl_run_id: UUID,
    ) -> SEOCrawlRun | None:
        run = await session.scalar(
            select(SEOCrawlRun).where(
                SEOCrawlRun.organization_id == organization_id,
                SEOCrawlRun.id == crawl_run_id,
            )
        )
        return run

    async def list_crawl_runs(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        website_id: UUID | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SEOCrawlRun]:
        stmt: Select[tuple[SEOCrawlRun]] = select(SEOCrawlRun).where(
            SEOCrawlRun.organization_id == organization_id
        )
        if website_id:
            stmt = stmt.where(SEOCrawlRun.website_id == website_id)
        stmt = stmt.order_by(SEOCrawlRun.created_at.desc()).limit(limit).offset(offset)
        return list(await session.scalars(stmt))

    async def list_pages(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        website_id: UUID | None = None,
        crawl_run_id: UUID | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[SEOPage]:
        stmt: Select[tuple[SEOPage]] = select(SEOPage).where(
            SEOPage.organization_id == organization_id
        )
        if website_id:
            stmt = stmt.where(SEOPage.website_id == website_id)
        stmt = stmt.order_by(SEOPage.crawl_depth, SEOPage.observed_at).limit(limit).offset(offset)
        return list(await session.scalars(stmt))

    async def list_opportunities(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        website_id: UUID | None = None,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[SEOOpportunity], bool]:
        if not 1 <= limit <= 100 or offset < 0:
            raise SEOQueryInvalidError
        statement: Select[tuple[SEOOpportunity]] = select(SEOOpportunity).where(
            SEOOpportunity.organization_id == organization_id
        )
        if website_id is not None:
            statement = statement.where(SEOOpportunity.website_id == website_id)
        if status_filter is not None:
            statement = statement.where(SEOOpportunity.status == status_filter)
        statement = statement.order_by(SEOOpportunity.priority_score.desc())
        rows = list(await session.scalars(statement.limit(limit + 1).offset(offset)))
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def get_opportunity(
        self, session: AsyncSession, organization_id: UUID, opportunity_id: UUID
    ) -> SEOOpportunity:
        opportunity = await session.scalar(
            select(SEOOpportunity).where(
                SEOOpportunity.organization_id == organization_id,
                SEOOpportunity.id == opportunity_id,
            )
        )
        if not opportunity:
            raise SEOOpportunityNotFoundError
        return opportunity

    async def create_recommendation(
        self,
        session: AsyncSession,
        organization_id: UUID,
        opportunity_id: UUID,
        command: RecommendationCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> SEORecommendationRevision:
        opportunity = await self.get_opportunity(session, organization_id, opportunity_id)
        last = await session.scalar(
            select(SEORecommendationRevision.revision_number)
            .where(SEORecommendationRevision.opportunity_id == opportunity_id)
            .order_by(SEORecommendationRevision.revision_number.desc())
            .limit(1)
        )
        revision = SEORecommendationRevision(
            organization_id=organization_id,
            opportunity_id=opportunity_id,
            revision_number=(last or 0) + 1,
            proposed_action=command.proposed_action,
            evidence_references=command.evidence_references,
            expected_result_hypothesis=command.expected_result_hypothesis,
            risk=command.risk,
            effort=command.effort,
            status="awaiting_approval",
            created_at=datetime.now(UTC),
        )
        session.add(revision)
        opportunity.status = "recommended"
        await session.flush()
        await self._audit(
            session,
            event="seo.recommendation.created",
            organization_id=organization_id,
            location_id=opportunity.location_id,
            actor_id=actor_id,
            resource_type="seo_opportunity",
            resource_id=opportunity.id,
            correlation_id=correlation_id,
            summary="SEO recommendation created.",
            metadata={"revision_id": str(revision.id), "risk": command.risk},
        )
        await self._notify(
            session,
            organization_id=organization_id,
            location_id=opportunity.location_id,
            event_type="seo.recommendation.awaiting_approval",
            idempotency_key=f"seo.recommendation.awaiting.{revision.id}",
            context={"opportunity_id": str(opportunity.id), "revision_id": str(revision.id)},
        )
        return revision

    async def list_recommendations(
        self, session: AsyncSession, organization_id: UUID, opportunity_id: UUID
    ) -> list[SEORecommendationRevision]:
        return list(
            await session.scalars(
                select(SEORecommendationRevision)
                .where(
                    SEORecommendationRevision.organization_id == organization_id,
                    SEORecommendationRevision.opportunity_id == opportunity_id,
                )
                .order_by(SEORecommendationRevision.revision_number.desc())
            )
        )

    async def decide_recommendation(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        command: RecommendationDecision,
        user_id: UUID,
        *,
        correlation_id: str,
    ) -> SEORecommendationRevision:
        revision = await session.scalar(
            select(SEORecommendationRevision)
            .where(
                SEORecommendationRevision.organization_id == organization_id,
                SEORecommendationRevision.id == revision_id,
            )
            .with_for_update()
        )
        if not revision or revision.status != "awaiting_approval":
            raise SEORecommendationNotDecidableError
        revision.status = "approved" if command.approve else "rejected"
        if command.approve:
            revision.approved_by_user_id = user_id
        opportunity = await session.scalar(
            select(SEOOpportunity).where(SEOOpportunity.id == revision.opportunity_id)
        )
        if opportunity:
            opportunity.status = "approved" if command.approve else "rejected"
        await session.flush()
        await self._audit(
            session,
            event="seo.recommendation.decided",
            organization_id=organization_id,
            location_id=opportunity.location_id if opportunity else None,
            actor_id=user_id,
            resource_type="seo_opportunity",
            resource_id=revision.opportunity_id,
            correlation_id=correlation_id,
            summary=f"SEO recommendation {revision.status}.",
            metadata={"revision_id": str(revision.id), "approve": command.approve},
        )
        return revision

    async def create_implementation_task(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        command: ImplementationTaskCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> SEOImplementationTask:
        revision = await session.scalar(
            select(SEORecommendationRevision).where(
                SEORecommendationRevision.organization_id == organization_id,
                SEORecommendationRevision.id == revision_id,
                SEORecommendationRevision.status == "approved",
            )
        )
        if not revision:
            raise SEORecommendationNotFoundError
        workflow_run = await self.execution.resolve_for_consumption(
            session, organization_id, command.workflow_run_id, "seo.crawl_or_analysis"
        )
        task = SEOImplementationTask(
            organization_id=organization_id,
            recommendation_revision_id=revision.id,
            workflow_run_id=workflow_run.id,
            target_type=command.target_type,
            target_reference=command.target_reference,
            status="pending",
        )
        session.add(task)
        await session.flush()
        await self._audit(
            session,
            event="seo.implementation_task.created",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="seo_opportunity",
            resource_id=revision.opportunity_id,
            correlation_id=correlation_id,
            summary="SEO implementation task created.",
            metadata={"task_id": str(task.id)},
        )
        return task

    async def verify_implementation_task(
        self,
        session: AsyncSession,
        organization_id: UUID,
        task_id: UUID,
        command: ImplementationTaskVerify,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> SEOImplementationTask:
        task = await session.scalar(
            select(SEOImplementationTask)
            .where(
                SEOImplementationTask.organization_id == organization_id,
                SEOImplementationTask.id == task_id,
            )
            .with_for_update()
        )
        if not task:
            raise SEOImplementationTaskNotFoundError
        task.status = "verified"
        task.verification_evidence = command.verification_evidence
        task.verified_at = datetime.now(UTC)
        await session.flush()
        await self._audit(
            session,
            event="seo.implementation_task.verified",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="seo_implementation_task",
            resource_id=task.id,
            correlation_id=correlation_id,
            summary="SEO implementation task verified.",
            metadata={},
        )
        return task

    async def list_implementation_tasks(
        self, session: AsyncSession, organization_id: UUID, revision_id: UUID
    ) -> list[SEOImplementationTask]:
        return list(
            await session.scalars(
                select(SEOImplementationTask).where(
                    SEOImplementationTask.organization_id == organization_id,
                    SEOImplementationTask.recommendation_revision_id == revision_id,
                )
            )
        )

    async def record_outcome(
        self,
        session: AsyncSession,
        organization_id: UUID,
        task_id: UUID,
        command: OutcomeRecord,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> SEOOutcome:
        task = await session.scalar(
            select(SEOImplementationTask).where(
                SEOImplementationTask.organization_id == organization_id,
                SEOImplementationTask.id == task_id,
            )
        )
        if not task:
            raise SEOImplementationTaskNotFoundError
        outcome = SEOOutcome(
            organization_id=organization_id,
            implementation_task_id=task.id,
            baseline_start=datetime.fromisoformat(command.baseline_start),
            baseline_end=datetime.fromisoformat(command.baseline_end),
            measurement_start=datetime.fromisoformat(command.measurement_start),
            measurement_end=datetime.fromisoformat(command.measurement_end),
            classification=command.classification,
            metrics=command.metrics,
            limitations=command.limitations,
        )
        session.add(outcome)
        await session.flush()
        await self._audit(
            session,
            event="seo.outcome.recorded",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="seo_implementation_task",
            resource_id=task.id,
            correlation_id=correlation_id,
            summary=f"SEO outcome recorded: {outcome.classification}.",
            metadata={"outcome_id": str(outcome.id)},
        )
        return outcome

    async def local_landing_page_gaps(
        self, session: AsyncSession, organization_id: UUID, website_id: UUID
    ) -> list[dict[str, object]]:
        website = await self.get_website(session, organization_id, website_id)
        locations = list(
            await session.scalars(
                select(Location).where(Location.organization_id == organization_id)
            )
        )
        pages = list(await session.scalars(select(SEOPage).where(SEOPage.website_id == website.id)))
        page_urls = {page.normalized_url.casefold() for page in pages}
        gaps: list[dict[str, object]] = []
        for location in locations:
            slug = location.slug.casefold()
            if not any(slug in url for url in page_urls):
                gaps.append({"location_id": str(location.id), "location_name": location.name})
        return gaps

    async def summary(self, session: AsyncSession, organization_id: UUID) -> dict[str, object]:
        rows = (
            await session.execute(
                select(SEOOpportunity.status, func.count())
                .where(SEOOpportunity.organization_id == organization_id)
                .group_by(SEOOpportunity.status)
            )
        ).all()
        website_count = await session.scalar(
            select(func.count()).where(SEOWebsite.organization_id == organization_id)
        )
        crawl_run_count = await session.scalar(
            select(func.count()).where(SEOCrawlRun.organization_id == organization_id)
        )
        return {
            "by_status": {status: count for status, count in rows},
            "website_count": int(website_count or 0),
            "crawl_run_count": int(crawl_run_count or 0),
        }

    async def resource_history(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        resource_type: str,
        resource_id: UUID,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        events = await self.audit_repository.list_for_resource(
            session,
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )
        return [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "action": event.action,
                "result": event.result,
                "occurred_at": event.occurred_at,
                "summary": event.summary,
                "actor_type": event.actor_type,
            }
            for event in events
        ]
