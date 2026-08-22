"""Focused contracts for current SEO evidence and semantic Content routing."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import Settings
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.models import ContentOpportunity
from apps.api.app.products.seo.models import (
    SEOOpportunity,
    SEOPage,
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.pagespeed import PageSpeedService


class FakePageSpeedService(PageSpeedService):
    async def analyze(self, settings: Settings, url: str) -> dict[str, object]:
        del settings
        return {
            "url": url,
            "provider": "google_pagespeed",
            "strategies": {
                "mobile": {
                    "scores": {
                        "performance": 50,
                        "accessibility": 100,
                        "best-practices": 100,
                        "seo": 100,
                    }
                }
            },
        }


def dimension_hash(dimensions: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(dimensions, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@pytest.mark.integration
@pytest.mark.anyio
async def test_orchestration_uses_current_gsc_and_routes_only_content_work(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        organization = Organization(
            name="SEO Orchestration Contract",
            slug=f"seo-orchestration-{uuid4().hex[:8]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        session.add(organization)
        await session.flush()
        provider = Provider(
            key=f"gsc-orchestration-{uuid4().hex[:8]}",
            name="Google Search Console",
            status="active",
            capabilities=["search_console.read"],
            manifest_version=1,
        )
        session.add(provider)
        await session.flush()
        connection = IntegrationConnection(
            organization_id=organization.id,
            provider_id=provider.id,
            external_account_reference="gsc-orchestration",
            status="connected",
            version=1,
        )
        session.add(connection)
        await session.flush()
        website = SEOWebsite(
            organization_id=organization.id,
            location_id=None,
            key="primary",
            name="Primary site",
            canonical_origin="https://example.invalid/",
            status="active",
            ownership_status="verified",
            version=1,
        )
        session.add(website)
        await session.flush()
        search_property = SEOSearchProperty(
            organization_id=organization.id,
            website_id=website.id,
            connection_id=connection.id,
            provider="google_search_console",
            external_property_id="sc-domain:example.invalid",
            property_type="domain",
            mapping_status="mapped",
            freshness_status="fresh",
        )
        session.add(search_property)
        page = SEOPage(
            organization_id=organization.id,
            website_id=website.id,
            normalized_url="https://example.invalid/service/",
            observed_url="https://example.invalid/service/",
            canonical_url="https://example.invalid/service/",
            normalization_reasons=[],
            http_status=200,
            content_type="text/html",
            title="Service",
            meta_description=None,
            h1="Service",
            robots_directives=[],
            internal_links=[],
            external_links=[],
            word_count=500,
            structured_data_present=False,
            content_hash="a" * 64,
            indexability="indexable",
            technical_issues=["missing_meta_description"],
            crawl_depth=1,
            redirect_destination=None,
            quality_status="valid",
            body_text="Service details",
            observed_at=datetime.now(UTC),
        )
        session.add(page)
        await session.flush()

        older_end = datetime(2026, 8, 1, tzinfo=UTC)
        current_end = datetime(2026, 8, 15, tzinfo=UTC)

        def observation(
            *,
            query: str,
            date_end: datetime,
            impressions: int,
            position: float,
            page_id: UUID | None = page.id,
            page_dimension: str | None = page.normalized_url,
        ) -> SEOSearchObservation:
            dimensions: dict[str, object] = {
                "observation_type": "query",
                "query": query,
            }
            if page_dimension is not None:
                dimensions["page"] = page_dimension
            return SEOSearchObservation(
                organization_id=organization.id,
                search_property_id=search_property.id,
                page_id=page_id,
                query=query,
                date_start=date_end - timedelta(days=7),
                date_end=date_end,
                dimensions=dimensions,
                dimension_hash=dimension_hash(dimensions),
                clicks=10,
                impressions=impressions,
                ctr=0.05,
                position=position,
                quality_status="valid",
                partial=False,
            )

        session.add_all(
            [
                observation(
                    query="electric service",
                    date_end=older_end,
                    impressions=900,
                    position=6,
                ),
                observation(
                    query="electric service",
                    date_end=current_end,
                    impressions=123,
                    position=10,
                ),
                observation(
                    query="mapped weak query",
                    date_end=current_end,
                    impressions=200,
                    position=30,
                ),
                observation(
                    query="genuine content gap",
                    date_end=current_end,
                    impressions=300,
                    position=31,
                    page_id=None,
                    page_dimension=None,
                ),
            ]
        )
        await session.flush()
        organization_id = organization.id
        website_id = website.id

    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    async with seo_session_factory.begin() as session:
        result = await service.analyze(
            session,
            organization_id,
            location_id=None,
            correlation_id="seo-current-evidence",
        )
        assert result["status"] == "completed"

        opportunities = list(
            await session.scalars(
                select(SEOOpportunity).where(
                    SEOOpportunity.organization_id == organization_id,
                    SEOOpportunity.active_marker == "active",
                )
            )
        )
        striking = next(
            row for row in opportunities if row.opportunity_type == "gsc_striking_distance"
        )
        assert striking.evidence["impressions"] == 123
        assert striking.evidence["date_end"] == current_end.isoformat()
        assert striking.score_explanation["final_score"] == striking.priority_score
        unmapped = [row for row in opportunities if row.opportunity_type == "gsc_unmapped_demand"]
        assert len(unmapped) == 1
        assert unmapped[0].evidence["query"] == "genuine content gap"

        content_rows = list(
            await session.scalars(
                select(ContentOpportunity).where(
                    ContentOpportunity.organization_id == organization_id,
                    ContentOpportunity.source_type == "seo_analysis",
                )
            )
        )
        assert {row.opportunity_type for row in content_rows} == {
            "gsc_striking_distance",
            "gsc_unmapped_demand",
        }
        assert all(not row.opportunity_type.startswith("pagespeed_") for row in content_rows)
        assert all(row.opportunity_type != "missing_meta_description" for row in content_rows)

        stale = SEOOpportunity(
            organization_id=organization_id,
            location_id=None,
            website_id=website_id,
            page_id=None,
            opportunity_type="stale_crawl_detector",
            deduplication_key=hashlib.sha256(b"stale-crawl-detector").hexdigest(),
            active_marker="active",
            evidence={"source": "crawl"},
            source_versions=["crawl.v1"],
            score_version=1,
            priority_score=50,
            score_explanation={"final_score": 50},
            status="recommended",
            version=1,
        )
        unrelated = SEOOpportunity(
            organization_id=organization_id,
            location_id=None,
            website_id=website_id,
            page_id=None,
            opportunity_type="external_detector",
            deduplication_key=hashlib.sha256(b"external-detector").hexdigest(),
            active_marker="active",
            evidence={"source": "external"},
            source_versions=["external.v1"],
            score_version=1,
            priority_score=50,
            score_explanation={"final_score": 50},
            status="recommended",
            version=1,
        )
        decided = SEOOpportunity(
            organization_id=organization_id,
            location_id=None,
            website_id=website_id,
            page_id=None,
            opportunity_type="approved_crawl_detector",
            deduplication_key=hashlib.sha256(b"approved-crawl-detector").hexdigest(),
            active_marker="active",
            evidence={"source": "crawl"},
            source_versions=["crawl.v1"],
            score_version=1,
            priority_score=50,
            score_explanation={"final_score": 50},
            status="approved",
            version=1,
        )
        session.add_all([stale, unrelated, decided])
        await session.flush()
        stale_id, unrelated_id, decided_id = stale.id, unrelated.id, decided.id

        for index in range(101):
            session.add(
                ContentOpportunity(
                    organization_id=organization_id,
                    location_id=None,
                    product_key="test",
                    target_reference=f"dummy-{index}",
                    opportunity_type="dummy",
                    source_type="test",
                    source_reference=f"dummy-{index}",
                    evidence_document={"index": index},
                    evidence_hash=hashlib.sha256(f"dummy-{index}".encode()).hexdigest(),
                    priority_score=100,
                    status="identified",
                )
            )

    async with seo_session_factory.begin() as session:
        second = await service.analyze(
            session,
            organization_id,
            location_id=None,
            correlation_id="seo-current-evidence-rerun",
        )
        assert second["content_opportunities"] == 0
        source_count = await session.scalar(
            select(func.count())
            .select_from(ContentOpportunity)
            .where(
                ContentOpportunity.organization_id == organization_id,
                ContentOpportunity.source_reference == f"seo-opportunity:{striking.id}",
            )
        )
        assert source_count == 1
        refreshed_stale = await session.get(SEOOpportunity, stale_id)
        refreshed_unrelated = await session.get(SEOOpportunity, unrelated_id)
        refreshed_decided = await session.get(SEOOpportunity, decided_id)
        assert refreshed_stale is not None and refreshed_stale.status == "archived"
        assert refreshed_stale.active_marker != "active"
        assert refreshed_unrelated is not None and refreshed_unrelated.status == "recommended"
        assert refreshed_unrelated.active_marker == "active"
        assert refreshed_decided is not None and refreshed_decided.status == "approved"
        assert refreshed_decided.active_marker == "active"
