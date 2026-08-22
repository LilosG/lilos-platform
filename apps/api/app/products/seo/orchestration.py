"""Cross-source SEO analysis and opportunity orchestration.

Converts persisted crawl/Search Console evidence plus fresh PageSpeed data into
SEO opportunities, approval-ready recommendations, and Content opportunities.
The evidence layer is deterministic so every recommendation is traceable.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config import Settings
from apps.api.app.products.content.contracts import OpportunityCreate
from apps.api.app.products.content.service import ContentService
from apps.api.app.products.seo.contracts import RecommendationCreate
from apps.api.app.products.seo.models import (
    SEOOpportunity,
    SEOPage,
    SEORecommendationRevision,
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.products.seo.pagespeed import PageSpeedService
from apps.api.app.products.seo.service import SEOService, opportunity_score

RecommendationEffort = Literal["low", "medium", "high"]
CONTENT_ADDRESSABLE_OPPORTUNITY_TYPES = frozenset(
    {"gsc_striking_distance", "gsc_low_ctr", "gsc_unmapped_demand"}
)


@dataclass(slots=True)
class SEOOrchestrationService:
    pagespeed: PageSpeedService = field(default_factory=PageSpeedService)
    seo: SEOService = field(default_factory=SEOService)
    content: ContentService = field(default_factory=ContentService)

    async def analyze(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        location_id: UUID | None,
        correlation_id: str,
    ) -> dict[str, object]:
        website = await session.scalar(
            select(SEOWebsite)
            .where(
                SEOWebsite.organization_id == organization_id,
                SEOWebsite.status == "active",
                or_(SEOWebsite.location_id == location_id, SEOWebsite.location_id.is_(None)),
            )
            .order_by(SEOWebsite.location_id.desc(), SEOWebsite.created_at.desc())
            .limit(1)
        )
        if website is None:
            return {
                "status": "no_active_website",
                "seo_opportunities": 0,
                "content_opportunities": 0,
                "recommendations_created": 0,
            }

        touched: dict[UUID, SEOOpportunity] = {}
        evaluated_sources: set[str] = set()
        page_rows = list(
            await session.scalars(
                select(SEOPage)
                .where(
                    SEOPage.organization_id == organization_id,
                    SEOPage.website_id == website.id,
                )
                .order_by(SEOPage.observed_at.desc())
                .limit(501)
            )
        )
        crawl_evidence_complete = len(page_rows) <= 500
        pages = page_rows[:500]
        page_lookup = {page.id: page for page in pages}
        page_url_lookup = {page.normalized_url: page for page in pages}

        if pages and crawl_evidence_complete:
            evaluated_sources.add("crawl.v1")

        for page in pages:
            for raw_issue in page.technical_issues or []:
                issue = str(raw_issue).strip()
                if not issue:
                    continue
                score, explanation = opportunity_score(
                    search_potential=45,
                    business_value=60,
                    relevance=85,
                    confidence=95,
                    urgency=55,
                    effort=25,
                )
                opportunity = await self._upsert_opportunity(
                    session,
                    organization_id,
                    website,
                    location_id=website.location_id,
                    page_id=page.id,
                    opportunity_type=issue,
                    target_reference=page.normalized_url,
                    evidence={
                        "source": "crawl",
                        "url": page.normalized_url,
                        "issue": issue,
                        "http_status": page.http_status,
                        "indexability": page.indexability,
                    },
                    source_versions=["crawl.v1"],
                    priority_score=score,
                    score_explanation=explanation,
                )
                touched[opportunity.id] = opportunity

        observations, gsc_evidence_complete = await self._canonical_gsc_observations(
            session, organization_id, website.id
        )
        if observations and gsc_evidence_complete:
            evaluated_sources.add("gsc.v1")
        for observation in observations:
            impressions = int(observation.impressions or 0)
            position = float(observation.position) if observation.position is not None else None
            ctr = float(observation.ctr) if observation.ctr is not None else None
            query = (observation.query or "").strip()
            observed_page: SEOPage | None = (
                page_lookup.get(observation.page_id) if observation.page_id else None
            )
            page_from_dimensions = observation.dimensions.get("page")
            if observed_page is None and page_from_dimensions:
                observed_page = page_url_lookup.get(str(page_from_dimensions))
            target = (
                observed_page.normalized_url
                if observed_page
                else str(page_from_dimensions)
                if page_from_dimensions
                else website.canonical_origin
            )

            if impressions >= 50 and position is not None and 4 <= position <= 20:
                score, explanation = opportunity_score(
                    search_potential=min(100, 55 + impressions // 100),
                    business_value=75,
                    relevance=90,
                    confidence=90,
                    urgency=65,
                    effort=35,
                )
                opportunity = await self._upsert_opportunity(
                    session,
                    organization_id,
                    website,
                    location_id=website.location_id,
                    page_id=observed_page.id if observed_page else None,
                    opportunity_type="gsc_striking_distance",
                    target_reference=f"{target}|{query}",
                    evidence={
                        "source": "google_search_console",
                        "query": query,
                        "url": target,
                        "impressions": impressions,
                        "clicks": observation.clicks,
                        "ctr": ctr,
                        "position": position,
                        "date_start": observation.date_start.isoformat(),
                        "date_end": observation.date_end.isoformat(),
                    },
                    source_versions=["gsc.v1"],
                    priority_score=score,
                    score_explanation=explanation,
                )
                touched[opportunity.id] = opportunity

            if (
                impressions >= 100
                and position is not None
                and position <= 10
                and ctr is not None
                and ctr < 0.02
            ):
                score, explanation = opportunity_score(
                    search_potential=min(100, 60 + impressions // 100),
                    business_value=75,
                    relevance=90,
                    confidence=90,
                    urgency=70,
                    effort=20,
                )
                opportunity = await self._upsert_opportunity(
                    session,
                    organization_id,
                    website,
                    location_id=website.location_id,
                    page_id=observed_page.id if observed_page else None,
                    opportunity_type="gsc_low_ctr",
                    target_reference=f"{target}|{query}",
                    evidence={
                        "source": "google_search_console",
                        "query": query,
                        "url": target,
                        "impressions": impressions,
                        "clicks": observation.clicks,
                        "ctr": ctr,
                        "position": position,
                        "date_start": observation.date_start.isoformat(),
                        "date_end": observation.date_end.isoformat(),
                    },
                    source_versions=["gsc.v1"],
                    priority_score=score,
                    score_explanation=explanation,
                )
                touched[opportunity.id] = opportunity

            # Top-query observations intentionally have no page_id. Only turn
            # them into a new-page/content-gap opportunity when current ranking
            # is weak enough that no existing landing page is performing well.
            if (
                impressions >= 50
                and query
                and observation.page_id is None
                and not page_from_dimensions
                and (position is None or position > 20)
            ):
                score, explanation = opportunity_score(
                    search_potential=min(100, 55 + impressions // 100),
                    business_value=80,
                    relevance=80,
                    confidence=80,
                    urgency=55,
                    effort=55,
                )
                opportunity = await self._upsert_opportunity(
                    session,
                    organization_id,
                    website,
                    location_id=website.location_id,
                    page_id=None,
                    opportunity_type="gsc_unmapped_demand",
                    target_reference=query,
                    evidence={
                        "source": "google_search_console",
                        "query": query,
                        "impressions": impressions,
                        "clicks": observation.clicks,
                        "ctr": ctr,
                        "position": position,
                        "date_start": observation.date_start.isoformat(),
                        "date_end": observation.date_end.isoformat(),
                    },
                    source_versions=["gsc.v1"],
                    priority_score=score,
                    score_explanation=explanation,
                )
                touched[opportunity.id] = opportunity

        pagespeed_result: dict[str, object] | None = None
        try:
            pagespeed_result = await self.pagespeed.analyze(Settings(), website.canonical_origin)
        except Exception as exc:
            pagespeed_result = {"error": type(exc).__name__, "provider": "google_pagespeed"}

        if pagespeed_result and isinstance(pagespeed_result.get("strategies"), dict):
            evaluated_sources.add("pagespeed.v5")
            strategies = pagespeed_result["strategies"]
            assert isinstance(strategies, dict)
            for strategy, raw_summary in strategies.items():
                if not isinstance(raw_summary, dict):
                    continue
                scores = raw_summary.get("scores")
                if not isinstance(scores, dict):
                    continue
                thresholds = {
                    "performance": 90,
                    "accessibility": 90,
                    "best-practices": 90,
                    "seo": 95,
                }
                for category, threshold in thresholds.items():
                    raw_score = scores.get(category)
                    if not isinstance(raw_score, (int, float)) or raw_score >= threshold:
                        continue
                    opportunity_type = f"pagespeed_{category.replace('-', '_')}_{strategy}"
                    score, explanation = opportunity_score(
                        search_potential=55,
                        business_value=70,
                        relevance=85,
                        confidence=95,
                        urgency=75 if category == "performance" else 55,
                        effort=45,
                    )
                    opportunity = await self._upsert_opportunity(
                        session,
                        organization_id,
                        website,
                        location_id=website.location_id,
                        page_id=None,
                        opportunity_type=opportunity_type,
                        target_reference=website.canonical_origin,
                        evidence={
                            "source": "google_pagespeed",
                            "url": website.canonical_origin,
                            "strategy": str(strategy),
                            "category": category,
                            "score": raw_score,
                            "threshold": threshold,
                            "summary": raw_summary,
                        },
                        source_versions=["pagespeed.v5"],
                        priority_score=score,
                        score_explanation=explanation,
                    )
                    touched[opportunity.id] = opportunity

        stale_count = await self._archive_stale_opportunities(
            session,
            organization_id,
            website.id,
            touched_ids=set(touched),
            evaluated_sources=evaluated_sources,
        )

        content_count = 0
        recommendation_count = 0
        for opportunity in touched.values():
            if await self._ensure_recommendation(
                session,
                organization_id,
                opportunity,
                correlation_id=correlation_id,
            ):
                recommendation_count += 1
            if await self._mirror_to_content(
                session,
                organization_id,
                opportunity,
                correlation_id=correlation_id,
            ):
                content_count += 1

        return {
            "status": "completed",
            "website_id": str(website.id),
            "seo_opportunities": len(touched),
            "content_opportunities": content_count,
            "recommendations_created": recommendation_count,
            "opportunities_archived": stale_count,
            "pagespeed": pagespeed_result,
        }

    async def _canonical_gsc_observations(
        self,
        session: AsyncSession,
        organization_id: UUID,
        website_id: UUID,
    ) -> tuple[list[SEOSearchObservation], bool]:
        """Return query evidence from one newest authoritative property/window.

        Search Console persists overlapping 7/28/90-day periods. Opportunity
        detectors must never process all of them as independent current facts.
        The latest end boundary wins; when windows share that boundary, the
        latest start boundary is the deterministic canonical (most current)
        period. Only the oldest confirmed mapping is treated as authoritative,
        matching the reporting read model.
        """
        search_property = await session.scalar(
            select(SEOSearchProperty)
            .where(
                SEOSearchProperty.organization_id == organization_id,
                SEOSearchProperty.website_id == website_id,
                SEOSearchProperty.provider == "google_search_console",
                SEOSearchProperty.mapping_status == "mapped",
            )
            .order_by(SEOSearchProperty.created_at.asc(), SEOSearchProperty.id.asc())
            .limit(1)
        )
        if search_property is None:
            return [], False

        canonical_period = (
            await session.execute(
                select(SEOSearchObservation.date_start, SEOSearchObservation.date_end)
                .where(
                    SEOSearchObservation.organization_id == organization_id,
                    SEOSearchObservation.search_property_id == search_property.id,
                    SEOSearchObservation.quality_status == "valid",
                    SEOSearchObservation.query.isnot(None),
                )
                .order_by(
                    SEOSearchObservation.date_end.desc(),
                    SEOSearchObservation.date_start.desc(),
                )
                .limit(1)
            )
        ).one_or_none()
        if canonical_period is None:
            return [], False
        period_start, period_end = canonical_period
        rows = list(
            await session.scalars(
                select(SEOSearchObservation)
                .where(
                    SEOSearchObservation.organization_id == organization_id,
                    SEOSearchObservation.search_property_id == search_property.id,
                    SEOSearchObservation.quality_status == "valid",
                    SEOSearchObservation.query.isnot(None),
                    SEOSearchObservation.date_start == period_start,
                    SEOSearchObservation.date_end == period_end,
                )
                .order_by(
                    SEOSearchObservation.impressions.desc(),
                    SEOSearchObservation.id.asc(),
                )
                .limit(1501)
            )
        )
        return rows[:1500], len(rows) <= 1500

    async def _upsert_opportunity(
        self,
        session: AsyncSession,
        organization_id: UUID,
        website: SEOWebsite,
        *,
        location_id: UUID | None,
        page_id: UUID | None,
        opportunity_type: str,
        target_reference: str,
        evidence: dict[str, object],
        source_versions: Sequence[object],
        priority_score: int,
        score_explanation: dict[str, object],
    ) -> SEOOpportunity:
        digest = hashlib.sha256(f"{opportunity_type}|{target_reference}".encode()).hexdigest()
        existing = await session.scalar(
            select(SEOOpportunity).where(
                SEOOpportunity.organization_id == organization_id,
                SEOOpportunity.deduplication_key == digest,
                SEOOpportunity.active_marker == "active",
            )
        )
        if existing is not None:
            if not self._incoming_evidence_is_current(existing.evidence, evidence):
                return existing
            existing.evidence = evidence
            existing.priority_score = priority_score
            existing.score_explanation = score_explanation
            existing.source_versions = list(source_versions)
            await session.flush()
            return existing

        opportunity = SEOOpportunity(
            organization_id=organization_id,
            location_id=location_id,
            website_id=website.id,
            page_id=page_id,
            opportunity_type=opportunity_type,
            deduplication_key=digest,
            active_marker="active",
            evidence=evidence,
            source_versions=list(source_versions),
            score_version=1,
            priority_score=priority_score,
            score_explanation=score_explanation,
            status="identified",
            version=1,
        )
        session.add(opportunity)
        await session.flush()
        return opportunity

    @staticmethod
    def _incoming_evidence_is_current(
        existing: dict[str, object], incoming: dict[str, object]
    ) -> bool:
        """Reject an older GSC period before it can replace newer evidence."""

        def period(evidence: dict[str, object]) -> tuple[datetime, datetime] | None:
            if evidence.get("source") != "google_search_console":
                return None
            start = evidence.get("date_start")
            end = evidence.get("date_end")
            if not isinstance(start, str) or not isinstance(end, str):
                return None
            try:
                return datetime.fromisoformat(end), datetime.fromisoformat(start)
            except ValueError:
                return None

        existing_period = period(existing)
        incoming_period = period(incoming)
        if existing_period is None or incoming_period is None:
            return True
        return incoming_period >= existing_period

    async def _archive_stale_opportunities(
        self,
        session: AsyncSession,
        organization_id: UUID,
        website_id: UUID,
        *,
        touched_ids: set[UUID],
        evaluated_sources: set[str],
    ) -> int:
        """Archive only detector-owned, non-decided opportunities evaluated now."""
        if not evaluated_sources:
            return 0
        candidates = list(
            await session.scalars(
                select(SEOOpportunity).where(
                    SEOOpportunity.organization_id == organization_id,
                    SEOOpportunity.website_id == website_id,
                    SEOOpportunity.active_marker == "active",
                    SEOOpportunity.status.in_(("identified", "recommended")),
                )
            )
        )
        archived = 0
        for opportunity in candidates:
            if opportunity.id in touched_ids:
                continue
            source_keys = {str(value) for value in opportunity.source_versions}
            if not source_keys or source_keys.isdisjoint(evaluated_sources):
                continue
            opportunity.status = "archived"
            opportunity.active_marker = opportunity.id.hex[:8]
            content_opportunity = await self.content.get_opportunity_by_source_reference(
                session,
                organization_id,
                f"seo-opportunity:{opportunity.id}",
            )
            if content_opportunity is not None and content_opportunity.status in {
                "identified",
                "validated",
            }:
                content_opportunity.status = "archived"
            archived += 1
        if archived:
            await session.flush()
        return archived

    async def _ensure_recommendation(
        self,
        session: AsyncSession,
        organization_id: UUID,
        opportunity: SEOOpportunity,
        *,
        correlation_id: str,
    ) -> bool:
        existing = await session.scalar(
            select(SEORecommendationRevision.id)
            .where(
                SEORecommendationRevision.organization_id == organization_id,
                SEORecommendationRevision.opportunity_id == opportunity.id,
            )
            .limit(1)
        )
        if existing is not None:
            return False
        action, hypothesis, effort = self._recommendation_text(opportunity)
        await self.seo.create_recommendation(
            session,
            organization_id,
            opportunity.id,
            RecommendationCreate(
                proposed_action=action,
                evidence_references=[f"seo-opportunity:{opportunity.id}"],
                expected_result_hypothesis=hypothesis,
                risk="low",
                effort=effort,
            ),
            actor_id=None,
            correlation_id=correlation_id,
        )
        return True

    async def _mirror_to_content(
        self,
        session: AsyncSession,
        organization_id: UUID,
        opportunity: SEOOpportunity,
        *,
        correlation_id: str,
    ) -> bool:
        if opportunity.opportunity_type not in CONTENT_ADDRESSABLE_OPPORTUNITY_TYPES:
            return False
        source_reference = f"seo-opportunity:{opportunity.id}"
        existing = await self.content.get_opportunity_by_source_reference(
            session, organization_id, source_reference
        )
        if existing is not None:
            return False

        target = str(opportunity.evidence.get("url") or opportunity.evidence.get("query") or "seo")
        await self.content.create_opportunity(
            session,
            organization_id,
            OpportunityCreate(
                location_id=opportunity.location_id,
                product_key="seo",
                target_reference=target[:500],
                opportunity_type=opportunity.opportunity_type[:64],
                source_type="seo_analysis",
                source_reference=source_reference,
                evidence_document={
                    "seo_opportunity_id": str(opportunity.id),
                    "evidence": opportunity.evidence,
                    "score_explanation": opportunity.score_explanation,
                },
                priority_score=opportunity.priority_score,
            ),
            correlation_id=correlation_id,
        )
        return True

    @staticmethod
    def _recommendation_text(
        opportunity: SEOOpportunity,
    ) -> tuple[str, str, RecommendationEffort]:
        evidence = opportunity.evidence
        opportunity_type = opportunity.opportunity_type
        url = str(evidence.get("url") or "the affected page")
        query = str(evidence.get("query") or "the target query")

        if opportunity_type == "gsc_striking_distance":
            return (
                (
                    f"Strengthen {url} for '{query}' using intent-aligned copy, "
                    "relevant internal links, and on-page entity coverage without "
                    "keyword stuffing."
                ),
                (
                    "Improved relevance and internal authority should increase the "
                    "probability of moving a page-four-through-twenty query into "
                    "higher-visibility positions."
                ),
                "medium",
            )

        if opportunity_type == "gsc_low_ctr":
            return (
                (
                    f"Rewrite the title and meta description for {url} around the "
                    f"demonstrated search intent for '{query}', preserving accurate "
                    "claims and page relevance."
                ),
                (
                    "A more compelling and intent-aligned search snippet should improve "
                    "CTR without requiring a ranking change."
                ),
                "low",
            )

        if opportunity_type == "gsc_unmapped_demand":
            return (
                (
                    f"Identify the best existing landing page for '{query}' or create "
                    "a focused service/location page when no suitable page exists; "
                    "connect it through relevant internal links."
                ),
                (
                    "Giving demonstrated search demand a clear canonical landing page "
                    "should improve relevance and conversion path quality."
                ),
                "high",
            )

        if opportunity_type.startswith("pagespeed_"):
            category = opportunity_type.removeprefix("pagespeed_").replace("_", " ")
            return (
                (
                    f"Address the failing {category} PageSpeed/Lighthouse findings for "
                    f"{url}, then rerun mobile and desktop PageSpeed verification "
                    "before closing the recommendation."
                ),
                (
                    "Improving the measured Lighthouse category should reduce technical "
                    "friction and strengthen page experience/SEO quality signals."
                ),
                "medium",
            )

        return (
            (
                f"Resolve the '{opportunity_type}' crawl finding on {url}, preserve "
                "canonical/indexability intent, and verify the fix with a fresh crawl."
            ),
            (
                "Removing the verified technical issue should improve crawlability, "
                "indexability, or page quality without changing unrelated page behavior."
            ),
            "low",
        )
