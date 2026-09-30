"""Focused contracts for current SEO evidence and semantic Content routing."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import Settings
from apps.api.app.insights.models import InsightSource, MetricDefinition, MetricObservation
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.content.models import ContentOpportunity
from apps.api.app.products.seo.decision import resolve_decision
from apps.api.app.products.seo.models import (
    SEOOpportunity,
    SEOPage,
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.products.seo.orchestration import SEOOrchestrationService
from apps.api.app.products.seo.pagespeed import PageSpeedService
from apps.api.app.reporting_periods import GA4_SYNC_TAIL_EXCLUSION_DAYS, reporting_window


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


def test_query_demand_recommendation_leaves_page_presence_unknown() -> None:
    opportunity = SEOOpportunity(
        opportunity_type="gsc_query_demand",
        evidence={"query": "electric service", "page_mapping_state": "unknown"},
    )
    action, hypothesis, _ = SEOOrchestrationService._recommendation_text(opportunity)

    assert "page-level Search Console evidence" in action
    assert "current site inventory" in action
    assert "determine whether an appropriate existing landing page exists" in action
    assert "identify it if one does" in action
    assert "only then decide what action is warranted" in action
    assert "identify the appropriate existing landing page" not in action
    assert "no suitable page" not in action
    assert "create" not in action.lower()
    assert "mapping remains unknown" in hypothesis


@pytest.mark.integration
@pytest.mark.anyio
async def test_legacy_unscoped_gsc_cannot_drive_opportunity_and_scoped_refresh_recovers_it(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    async with seo_session_factory.begin() as session:
        organization = Organization(
            name="Scoped GSC evidence",
            slug=f"scoped-gsc-{uuid4().hex[:8]}",
            organization_type=OrganizationType.TEST,
            status=OrganizationStatus.ACTIVE,
            timezone="UTC",
            default_currency="USD",
            version=1,
        )
        provider = Provider(
            key=f"gsc-scoped-{uuid4().hex[:8]}",
            name="Google Search Console",
            status="active",
            capabilities=["search_console.read"],
            manifest_version=1,
        )
        session.add_all([organization, provider])
        await session.flush()
        connection = IntegrationConnection(
            organization_id=organization.id,
            provider_id=provider.id,
            external_account_reference="scoped-gsc",
            status="connected",
            version=1,
        )
        website = SEOWebsite(
            organization_id=organization.id,
            location_id=None,
            key="scoped",
            name="Scoped site",
            canonical_origin="https://scoped.example.invalid",
            status="active",
            ownership_status="verified",
            version=1,
        )
        session.add_all([connection, website])
        await session.flush()
        search_property = SEOSearchProperty(
            organization_id=organization.id,
            website_id=website.id,
            connection_id=connection.id,
            provider="google_search_console",
            external_property_id="sc-domain:scoped.example.invalid",
            property_type="domain",
            mapping_status="mapped",
            freshness_status="fresh",
        )
        session.add(search_property)
        await session.flush()
        now = datetime.now(UTC)
        observations = []
        for source_site, end in (
            (None, now),
            (website.id, now - timedelta(days=7)),
        ):
            dimensions: dict[str, object] = {
                "observation_type": "top_query",
                "query": "brunch nearby",
            }
            observation = SEOSearchObservation(
                organization_id=organization.id,
                search_property_id=search_property.id,
                website_id=source_site,
                page_id=None,
                query="brunch nearby",
                date_start=end - timedelta(days=7),
                date_end=end,
                dimensions=dimensions,
                dimension_hash=dimension_hash(dimensions),
                clicks=0,
                impressions=139,
                ctr=0,
                position=6.6763,
                mapping_state="unknown" if source_site else None,
                quality_status="valid",
                partial=False,
            )
            session.add(observation)
            await session.flush()
            observations.append(observation)
        legacy, scoped = observations
        target = f"{website.canonical_origin}|brunch nearby"
        opportunity = SEOOpportunity(
            organization_id=organization.id,
            location_id=None,
            website_id=website.id,
            page_id=None,
            opportunity_type="gsc_low_ctr",
            deduplication_key=hashlib.sha256(f"gsc_low_ctr|{target}".encode()).hexdigest(),
            active_marker="active",
            evidence={"source": "google_search_console", "observation_id": str(legacy.id)},
            source_versions=["gsc.v1"],
            score_version=2,
            priority_score=89,
            score_explanation={"score_policy_version": "opportunity_score.v2"},
            status="identified",
            version=1,
        )
        session.add(opportunity)
        await session.flush()
        selected, complete = await service._canonical_gsc_observations(
            session, organization.id, website.id
        )
        assert complete is True
        assert selected == []
        analysis = await service.analyze(
            session, organization.id, location_id=None, correlation_id="legacy-evidence-refresh"
        )
        assert analysis["status"] == "completed"
        assert opportunity.status == "archived"
        assert opportunity.active_marker != "active"
        newer_scoped = SEOSearchObservation(
            organization_id=organization.id,
            search_property_id=search_property.id,
            website_id=website.id,
            page_id=None,
            query=scoped.query,
            date_start=now,
            date_end=now + timedelta(days=7),
            dimensions=scoped.dimensions,
            dimension_hash=scoped.dimension_hash,
            clicks=0,
            impressions=139,
            ctr=0,
            position=6.6763,
            mapping_state="unknown",
            quality_status="valid",
            partial=False,
        )
        session.add(newer_scoped)
        await session.flush()
        selected, complete = await service._canonical_gsc_observations(
            session, organization.id, website.id
        )
        assert complete is True
        assert [row.id for row in selected] == [newer_scoped.id]
        evidence: dict[str, object] = {
            "source": "google_search_console",
            "observation_id": str(newer_scoped.id),
            "query": newer_scoped.query,
            "clicks": newer_scoped.clicks,
            "impressions": newer_scoped.impressions,
            "ctr": float(newer_scoped.ctr or 0),
            "position": float(newer_scoped.position or 0),
            "date_start": newer_scoped.date_start.isoformat(),
            "date_end": newer_scoped.date_end.isoformat(),
        }
        refreshed = await service._upsert_opportunity(
            session,
            organization.id,
            website,
            location_id=None,
            page_id=None,
            opportunity_type="gsc_low_ctr",
            target_reference=target,
            evidence=evidence,
            source_versions=["gsc.v1"],
            priority_score=89,
            score_explanation={"score_policy_version": "opportunity_score.v2"},
        )
        assert refreshed.id != opportunity.id
        assert refreshed.evidence["observation_id"] == str(newer_scoped.id)
        decision = await resolve_decision(
            session, organization.id, refreshed, [f"seo-opportunity:{refreshed.id}"]
        )
        assert decision["website_id"] == str(website.id)
        assert decision["page_id"] is None


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
                website_id=website.id,
                page_id=page_id,
                mapping_state="mapped" if page_id else "unmapped",
                mapping_basis="exact_normalized_url" if page_id else None,
                resolver_version="page_identity.v1" if page_id else None,
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

        def page_query_observation(
            *,
            query: str,
            date_end: datetime,
            impressions: int,
            position: float,
        ) -> SEOSearchObservation:
            """A real `page_query` row: the attribution rewrite reads these,
            never the query-dimension aggregate row, to resolve a page."""
            dimensions: dict[str, object] = {
                "observation_type": "page_query",
                "page": page.normalized_url,
                "query": query,
            }
            return SEOSearchObservation(
                organization_id=organization.id,
                search_property_id=search_property.id,
                website_id=website.id,
                page_id=page.id,
                mapping_state="mapped",
                mapping_basis="exact_normalized_url",
                resolver_version="page_identity.v1",
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
                    query="query demand to investigate",
                    date_end=current_end,
                    impressions=300,
                    position=31,
                    page_id=None,
                    page_dimension=None,
                ),
                # Dominant-page evidence for the two current-period mapped
                # queries above. Without a matching `page_query` row, the
                # rewritten orchestration attributes nothing to `page.id` no
                # matter what the query-dimension aggregate row says.
                page_query_observation(
                    query="electric service",
                    date_end=current_end,
                    impressions=123,
                    position=10,
                ),
                page_query_observation(
                    query="mapped weak query",
                    date_end=current_end,
                    impressions=200,
                    position=30,
                ),
            ]
        )
        await session.flush()
        now = datetime.now(UTC)
        analytics_property = AnalyticsProperty(
            organization_id=organization.id,
            connection_id=connection.id,
            website_id=website.id,
            provider="google_analytics",
            external_property_id="properties/123456",
            property_number="123456",
            display_name="Primary GA4",
            mapping_status="mapped",
            last_synced_at=now,
            freshness_status="fresh",
            page_evidence_status="observed",
        )
        source = InsightSource(
            organization_id=organization.id,
            key="properties/123456",
            source_type="analytics_property",
            product_key="insights",
            provider="google_analytics",
            status="active",
            authority_scope="organization",
        )
        definition = await session.scalar(
            select(MetricDefinition).where(
                MetricDefinition.key == "ga4.organicLanding.keyEvents",
                MetricDefinition.version == 1,
            )
        )
        session.add_all([analytics_property, source])
        if definition is None:
            definition = MetricDefinition(
                key="ga4.organicLanding.keyEvents",
                version=1,
                name="GA4 Organic Landing keyEvents",
                description="Organic landing page key events",
                source_product="insights",
                unit="count",
                data_type="integer",
                aggregation_behavior="sum",
                supported_dimensions=[],
                required_filters=[],
                freshness_seconds=86400,
                partial_period_behavior="mark_partial",
                missing_data_behavior="mark_missing",
                status="active",
            )
            session.add(definition)
        await session.flush()
        start, end = reporting_window(now, 28, GA4_SYNC_TAIL_EXCLUSION_DAYS)
        dimensions: dict[str, object] = {
            "observation_type": "organic_landing_page",
            "website_id": str(website.id),
            "hostName": "example.invalid",
            "landingPagePlusQueryString": "/service/",
            "sessionDefaultChannelGroup": "Organic Search",
        }
        key_events = MetricObservation(
            organization_id=organization.id,
            website_id=website.id,
            location_id=None,
            page_id=page.id,
            source_id=source.id,
            metric_definition_id=definition.id,
            period_start=start,
            period_end=end,
            dimensions=dimensions,
            dimension_hash=dimension_hash(dimensions),
            value=Decimal(2),
            quality_state="valid",
            completeness=Decimal("1.0"),
            provenance={
                "provider": "google_analytics",
                "property": "properties/123456",
                "report": "organic_landing_page",
                "availability": "observed",
                "ingested_at": now.isoformat(),
                "window_days": 28,
                "website_id": str(website.id),
                "raw_host_name": "example.invalid",
                "mapping_state": "mapped",
                "mapping_basis": "exact_normalized_url",
                "resolver_version": "page_identity.v1",
            },
        )
        session.add(key_events)
        await session.flush()
        key_events_id = key_events.id
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
        assert striking.attribution_state == "attributed"
        assert striking.page_id == page.id
        assert striking.evidence["attribution_state"] == "attributed"
        assert striking.evidence["url"] == page.normalized_url
        striking_business = cast(dict[str, object], striking.evidence["business_importance"])
        assert striking_business["business_value"] == 40
        assert striking_business["metric_observation_id"] == str(key_events_id)
        assert striking.score_explanation["business_component"] == "supplied"
        query_demand = [row for row in opportunities if row.opportunity_type == "gsc_query_demand"]
        assert len(query_demand) == 1
        assert query_demand[0].evidence["query"] == "query demand to investigate"
        assert query_demand[0].evidence["page_mapping_state"] == "unknown"
        assert query_demand[0].attribution_state == "query_only"
        assert query_demand[0].page_id is None
        query_business = cast(dict[str, object], query_demand[0].evidence["business_importance"])
        assert query_business["business_value"] is None
        assert query_demand[0].score_explanation["business_component"] == "omitted"
        assert "cannot identify" in str(query_demand[0].evidence["evidence_limitation"])
        assert not any(row.opportunity_type == "gsc_unmapped_demand" for row in opportunities)
        action, _, _ = service._recommendation_text(query_demand[0])
        assert "Inspect page-level" in action
        assert "current site inventory" in action
        assert "determine whether an appropriate existing landing page exists" in action
        assert "identify it if one does" in action
        assert "only then decide what action is warranted" in action
        assert "identify the appropriate existing landing page" not in action
        assert "no suitable page" not in action
        assert "create" not in action.lower()

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
        }
        assert all(row.opportunity_type != "gsc_query_demand" for row in content_rows)
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
        obsolete_unmapped = SEOOpportunity(
            organization_id=organization_id,
            location_id=None,
            website_id=website_id,
            page_id=None,
            opportunity_type="gsc_unmapped_demand",
            deduplication_key=hashlib.sha256(b"obsolete-unmapped").hexdigest(),
            active_marker="active",
            evidence={"source": "google_search_console"},
            source_versions=["gsc.v1"],
            score_version=1,
            priority_score=50,
            score_explanation={"final_score": 50},
            status="identified",
            version=1,
        )
        session.add(obsolete_unmapped)
        await session.flush()
        stale_id, unrelated_id, decided_id = stale.id, unrelated.id, decided.id
        obsolete_unmapped_id = obsolete_unmapped.id

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
        observation_to_update = await session.get(MetricObservation, key_events_id)
        assert observation_to_update is not None
        observation_to_update.value = Decimal(25)

    async with seo_session_factory.begin() as session:
        second = await service.analyze(
            session,
            organization_id,
            location_id=None,
            correlation_id="seo-current-evidence-rerun",
        )
        assert second["content_opportunities"] == 0
        rescored = await session.get(SEOOpportunity, striking.id)
        assert rescored is not None
        rescored_business = cast(dict[str, object], rescored.evidence["business_importance"])
        assert rescored_business["business_value"] == 100
        assert rescored.score_version == 2
        assert (
            rescored.priority_score > striking.priority_score
            or rescored.score_explanation["business_value"] == 100
        )
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
        archived_unmapped = await session.get(SEOOpportunity, obsolete_unmapped_id)
        assert archived_unmapped is not None and archived_unmapped.status == "archived"
        assert refreshed_unrelated is not None and refreshed_unrelated.status == "recommended"
        assert refreshed_unrelated.active_marker == "active"
        # Stale archival never touches decided work. This one is an unattributed approval,
        # which can never execute, so the legacy pass withdraws the approval instead: it
        # returns to `identified` and stays live (it is not archived).
        assert refreshed_decided is not None and refreshed_decided.status == "identified"
        assert refreshed_decided.active_marker == "active"


QUERY = "brunch spots san diego"


async def _seed_attributed_query(
    session: AsyncSession,
) -> tuple[Organization, SEOWebsite, SEOPage, SEOSearchProperty]:
    """A site whose one query is dominated by a single crawled page."""
    organization = Organization(
        name="Superseded opportunities",
        slug=f"superseded-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    provider = Provider(
        key=f"gsc-superseded-{uuid4().hex[:8]}",
        name="Google Search Console",
        status="active",
        capabilities=["search_console.read"],
        manifest_version=1,
    )
    session.add_all([organization, provider])
    await session.flush()
    connection = IntegrationConnection(
        organization_id=organization.id,
        provider_id=provider.id,
        external_account_reference="gsc-superseded",
        status="connected",
        version=1,
    )
    website = SEOWebsite(
        organization_id=organization.id,
        location_id=None,
        key="primary",
        name="Primary site",
        canonical_origin="https://superseded.example.invalid",
        status="active",
        ownership_status="verified",
        version=1,
    )
    session.add_all([connection, website])
    await session.flush()
    search_property = SEOSearchProperty(
        organization_id=organization.id,
        website_id=website.id,
        connection_id=connection.id,
        provider="google_search_console",
        external_property_id="sc-domain:superseded.example.invalid",
        property_type="domain",
        mapping_status="mapped",
        freshness_status="fresh",
    )
    page = SEOPage(
        organization_id=organization.id,
        website_id=website.id,
        normalized_url="https://superseded.example.invalid/blog/best-brunch",
        observed_url="https://superseded.example.invalid/blog/best-brunch",
        canonical_url="https://superseded.example.invalid/blog/best-brunch",
        normalization_reasons=[],
        http_status=200,
        content_type="text/html",
        title="Best brunch",
        meta_description="Brunch",
        h1="Best brunch",
        robots_directives=[],
        internal_links=[],
        external_links=[],
        word_count=900,
        structured_data_present=False,
        content_hash="b" * 64,
        indexability="indexable",
        technical_issues=[],
        crawl_depth=1,
        redirect_destination=None,
        quality_status="valid",
        body_text="Brunch",
        observed_at=datetime.now(UTC),
    )
    session.add_all([search_property, page])
    await session.flush()
    end = datetime.now(UTC)
    start = end - timedelta(days=28)
    for observation_type, page_id, mapping_state in (
        ("top_query", None, "unknown"),
        ("page_query", page.id, "mapped"),
    ):
        dimensions: dict[str, object] = {"observation_type": observation_type, "query": QUERY}
        session.add(
            SEOSearchObservation(
                organization_id=organization.id,
                search_property_id=search_property.id,
                website_id=website.id,
                page_id=page_id,
                query=QUERY,
                date_start=start,
                date_end=end,
                dimensions=dimensions,
                dimension_hash=dimension_hash(dimensions),
                clicks=10,
                impressions=400,
                ctr=0.01,
                position=8.2,
                mapping_state=mapping_state,
                quality_status="valid",
                partial=False,
            )
        )
    await session.flush()
    return organization, website, page, search_property


def _legacy_query_only_row(
    organization: Organization, website: SEOWebsite, *, status: str
) -> SEOOpportunity:
    """The pre-attribution row: keyed on `<origin>|<query>`, no page."""
    target = f"{website.canonical_origin}|{QUERY}"
    return SEOOpportunity(
        organization_id=organization.id,
        location_id=None,
        website_id=website.id,
        page_id=None,
        opportunity_type="gsc_striking_distance",
        deduplication_key=hashlib.sha256(f"gsc_striking_distance|{target}".encode()).hexdigest(),
        active_marker="active",
        evidence={"source": "google_search_console", "query": QUERY},
        source_versions=["gsc.v1"],
        score_version=2,
        priority_score=70,
        score_explanation={"score_policy_version": "opportunity_score.v2"},
        status=status,
        version=1,
    )


async def _live_rows(
    session: AsyncSession, organization_id: UUID, opportunity_type: str
) -> list[SEOOpportunity]:
    rows = await session.scalars(
        select(SEOOpportunity).where(
            SEOOpportunity.organization_id == organization_id,
            SEOOpportunity.opportunity_type == opportunity_type,
            SEOOpportunity.active_marker == "active",
        )
    )
    return list(rows)


@pytest.mark.integration
@pytest.mark.anyio
async def test_attributed_opportunity_retires_query_only_row_with_audit(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    async with seo_session_factory.begin() as session:
        organization, website, page, _ = await _seed_attributed_query(session)
        legacy = _legacy_query_only_row(organization, website, status="recommended")
        session.add(legacy)
        await session.flush()

        await service.analyze(session, organization.id, location_id=None, correlation_id="retire-1")

        live = await _live_rows(session, organization.id, "gsc_striking_distance")
        assert [row.page_id for row in live] == [page.id]
        assert live[0].attribution_state == "attributed"
        await session.refresh(legacy)
        assert legacy.status == "archived"
        assert legacy.active_marker != "active"
        assert legacy.version == 2
        events = list(
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.organization_id == organization.id,
                    AuditEvent.event_type == "seo.opportunity.archived",
                    AuditEvent.resource_id == legacy.id,
                )
            )
        )
        assert len(events) == 1
        assert events[0].event_metadata["superseded_by"] == str(live[0].id)
        assert events[0].event_metadata["reason"] in {"superseded", "stale"}


@pytest.mark.integration
@pytest.mark.anyio
async def test_reanalysis_converges_to_one_live_row_per_query_and_type(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    async with seo_session_factory.begin() as session:
        organization, website, _, _ = await _seed_attributed_query(session)
        session.add(_legacy_query_only_row(organization, website, status="identified"))
        await session.flush()

        for run in range(3):
            await service.analyze(
                session, organization.id, location_id=None, correlation_id=f"converge-{run}"
            )
            for opportunity_type in ("gsc_striking_distance", "gsc_low_ctr"):
                live = [
                    row
                    for row in await _live_rows(session, organization.id, opportunity_type)
                    if row.evidence.get("query") == QUERY
                ]
                assert len(live) == 1, (run, opportunity_type)

        archived_events = await session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.event_type == "seo.opportunity.archived",
            )
        )
        assert archived_events == 1  # later runs archive nothing further


@pytest.mark.integration
@pytest.mark.anyio
async def test_plain_retirement_skips_approved_work_but_legacy_pass_supersedes_it(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`_retire_superseded` never archives decided work; the legacy-approval pass does.

    An approved query-only row with nothing in flight can never execute, so once an
    attributed replacement exists it is superseded -- audited as a legacy approval, not
    as an ordinary retirement.
    """
    service = SEOOrchestrationService(pagespeed=FakePageSpeedService())
    async with seo_session_factory.begin() as session:
        organization, website, _, _ = await _seed_attributed_query(session)
        approved = _legacy_query_only_row(organization, website, status="approved")
        session.add(approved)
        await session.flush()
        replacement = await service._upsert_opportunity(
            session,
            organization.id,
            website,
            location_id=None,
            page_id=None,
            opportunity_type="gsc_striking_distance",
            target_reference=QUERY,
            evidence={"source": "google_search_console", "query": QUERY},
            source_versions=["gsc.v1"],
            priority_score=50,
            score_explanation={},
        )
        assert replacement.id != approved.id
        # The ordinary retirement path leaves an approved row exactly as it found it.
        retired = await service._retire_superseded(
            session,
            organization.id,
            website.id,
            await _attributed(session, organization.id, replacement),
            QUERY,
            "keep-1",
        )
        assert retired == 0
        await session.refresh(approved)
        assert approved.status == "approved" and approved.active_marker == "active"

        await service.analyze(session, organization.id, location_id=None, correlation_id="keep-2")

        await session.refresh(approved)
        assert approved.status == "archived"
        events = list(
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.organization_id == organization.id,
                    AuditEvent.event_type == "seo.opportunity.archived",
                    AuditEvent.resource_id == approved.id,
                )
            )
        )
        assert [event.event_metadata["reason"] for event in events] == [
            "legacy_approval_superseded"
        ]


async def _attributed(
    session: AsyncSession, organization_id: UUID, like: SEOOpportunity
) -> SEOOpportunity:
    """Mark `like` attributed to a page so it can act as the superseding opportunity."""
    page_id = await session.scalar(
        select(SEOPage.id).where(SEOPage.organization_id == organization_id)
    )
    like.page_id = page_id
    like.attribution_state = "attributed"
    await session.flush()
    return like
