"""Deterministic URL, crawl-safety, score, and missing-data policies plus SEO domain service."""

import hashlib
import ipaddress
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast
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


TITLE_PATTERN = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_DESCRIPTION_PATTERN = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']', re.IGNORECASE
)
CANONICAL_PATTERN = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']*)["\']', re.IGNORECASE
)
H1_PATTERN = re.compile(r"<h1[^>]*>", re.IGNORECASE)


class PageSignals:
    def __init__(self, http_status: int, body: str) -> None:
        self.http_status = http_status
        title_match = TITLE_PATTERN.search(body)
        self.title = title_match.group(1).strip() if title_match else None
        description_match = META_DESCRIPTION_PATTERN.search(body)
        self.meta_description = description_match.group(1).strip() if description_match else None
        canonical_match = CANONICAL_PATTERN.search(body)
        self.canonical_url = canonical_match.group(1).strip() if canonical_match else None
        self.h1_count = len(H1_PATTERN.findall(body))

    def indexability(self) -> str:
        return "indexable" if self.http_status == 200 else "not_indexable"

    def quality_status(self) -> str:
        issues = self.technical_issues()
        return "issues_detected" if issues else "clean"

    def technical_issues(self) -> list[str]:
        issues = []
        if self.http_status != 200:
            issues.append("non_200_status")
        if not self.title:
            issues.append("missing_title")
        if not self.meta_description:
            issues.append("missing_meta_description")
        if self.h1_count == 0:
            issues.append("missing_h1")
        if self.h1_count > 1:
            issues.append("multiple_h1")
        return issues


async def fetch_page(client: httpx.AsyncClient, url: str) -> PageSignals:
    response = await client.get(url, timeout=10.0, follow_redirects=True)
    return PageSignals(response.status_code, response.text)


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

    async def run_crawl(
        self,
        session: AsyncSession,
        organization_id: UUID,
        website_id: UUID,
        workflow_run_id: UUID,
        command: CrawlRequest,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> tuple[SEOCrawlRun, list[SEOOpportunity]]:
        """Run a bounded, same-host, read-only crawl of the confirmed website.

        Requires no external credentials — this fetches the tenant's own
        confirmed public website only, validated by `validate_crawl_target`
        against the website's canonical origin host, with a small page cap
        and a strict timeout.
        """
        existing_run = await session.scalar(
            select(SEOCrawlRun).where(
                SEOCrawlRun.organization_id == organization_id,
                SEOCrawlRun.idempotency_key == command.idempotency_key,
            )
        )
        if existing_run:
            opportunities = list(
                await session.scalars(
                    select(SEOOpportunity).where(
                        SEOOpportunity.organization_id == organization_id,
                        SEOOpportunity.website_id == website_id,
                    )
                )
            )
            return existing_run, opportunities

        workflow_run = await self.execution.resolve_for_consumption(
            session, organization_id, workflow_run_id, "seo.crawl_or_analysis"
        )
        website = await self.get_website(session, organization_id, website_id)
        allowed_host = urlsplit(normalize_url(website.canonical_origin).value).hostname
        allowed_hosts = frozenset({allowed_host} if allowed_host else set())

        targets: list[str] = []
        for seed_path in command.seed_paths[: command.max_pages]:
            if seed_path.startswith("http"):
                candidate = seed_path
            else:
                candidate = website.canonical_origin.rstrip("/") + "/" + seed_path.lstrip("/")
            validate_crawl_target(candidate, allowed_hosts)
            targets.append(normalize_url(candidate).value)

        created_opportunities: list[SEOOpportunity] = []
        async with self._http_client_factory() as client:
            for target_url in targets:
                try:
                    signals = await fetch_page(client, target_url)
                except httpx.HTTPError:
                    signals = PageSignals(0, "")
                digest = hashlib.sha256(target_url.encode()).hexdigest()
                page = await session.scalar(
                    select(SEOPage).where(
                        SEOPage.website_id == website.id, SEOPage.normalized_url == target_url
                    )
                )
                if page is None:
                    page = SEOPage(
                        organization_id=organization_id,
                        website_id=website.id,
                        normalized_url=target_url,
                        observed_url=target_url,
                        canonical_url=signals.canonical_url,
                        normalization_reasons=[],
                        http_status=signals.http_status,
                        indexability=signals.indexability(),
                        quality_status=signals.quality_status(),
                        observed_at=datetime.now(UTC),
                    )
                    session.add(page)
                else:
                    page.http_status = signals.http_status
                    page.indexability = signals.indexability()
                    page.quality_status = signals.quality_status()
                    page.canonical_url = signals.canonical_url
                    page.observed_at = datetime.now(UTC)
                await session.flush()

                for issue in signals.technical_issues():
                    dedup_key = f"{digest}.{issue}"
                    score, explanation = opportunity_score(
                        search_potential=40,
                        business_value=40,
                        relevance=60,
                        confidence=90,
                        urgency=30,
                        effort=10,
                    )
                    existing_opportunity = await session.scalar(
                        select(SEOOpportunity).where(
                            SEOOpportunity.organization_id == organization_id,
                            SEOOpportunity.deduplication_key == dedup_key,
                            SEOOpportunity.active_marker == "active",
                        )
                    )
                    if existing_opportunity:
                        continue
                    opportunity = SEOOpportunity(
                        organization_id=organization_id,
                        location_id=website.location_id,
                        website_id=website.id,
                        page_id=page.id,
                        opportunity_type=issue,
                        deduplication_key=dedup_key,
                        active_marker="active",
                        evidence={"url": target_url, "issue": issue},
                        source_versions=["crawl.v1"],
                        score_version=1,
                        priority_score=score,
                        score_explanation=explanation,
                        status="identified",
                        version=1,
                    )
                    session.add(opportunity)
                    await session.flush()
                    created_opportunities.append(opportunity)

        crawl_run = SEOCrawlRun(
            organization_id=organization_id,
            website_id=website.id,
            workflow_run_id=workflow_run.id,
            idempotency_key=command.idempotency_key,
            status="completed",
            max_pages=command.max_pages,
            safe_result={
                "pages_crawled": len(targets),
                "opportunities_found": len(created_opportunities),
            },
            completed_at=datetime.now(UTC),
        )
        session.add(crawl_run)
        workflow_run.status = "completed"
        workflow_run.completed_at = datetime.now(UTC)
        await session.flush()
        await self._audit(
            session,
            event="seo.crawl.completed",
            organization_id=organization_id,
            location_id=website.location_id,
            actor_id=actor_id,
            resource_type="seo_website",
            resource_id=website.id,
            correlation_id=correlation_id,
            summary=(
                f"Crawl completed: {len(targets)} pages, "
                f"{len(created_opportunities)} opportunities."
            ),
            metadata={"crawl_run_id": str(crawl_run.id)},
        )
        for opportunity in created_opportunities:
            await self._notify(
                session,
                organization_id=organization_id,
                location_id=website.location_id,
                event_type="seo.opportunity.identified",
                idempotency_key=f"seo.opportunity.{opportunity.id}",
                context={
                    "opportunity_id": str(opportunity.id),
                    "type": opportunity.opportunity_type,
                },
            )
        return crawl_run, created_opportunities

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
        return {
            "by_status": {status: count for status, count in rows},
            "website_count": int(website_count or 0),
        }

    async def resource_history(
        self, session: AsyncSession, *, resource_type: str, resource_id: UUID, limit: int = 50
    ) -> list[dict[str, object]]:
        events = await self.audit_repository.list_for_resource(
            session, resource_type=resource_type, resource_id=resource_id, limit=limit
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
