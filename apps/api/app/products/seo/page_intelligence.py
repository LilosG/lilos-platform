"""Deterministic, bounded current-page read model over persisted SEO evidence."""

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.models import BusinessKnowledgeDocument
from apps.api.app.insights.models import InsightSource, MetricDefinition, MetricObservation
from apps.api.app.products.analytics.models import AnalyticsProperty
from apps.api.app.products.seo.crawl_engine import canonicalize_url, normalize_crawl_url
from apps.api.app.products.seo.models import (
    SEOCrawlPageObservation,
    SEOCrawlRun,
    SEOImplementationTask,
    SEOInternalLinkObservation,
    SEOOpportunity,
    SEOOutcome,
    SEOPage,
    SEORecommendationRevision,
    SEOSearchObservation,
    SEOSearchProperty,
    SEOWebsite,
)
from apps.api.app.products.seo.search_console_service import DEFAULT_SYNC_WINDOW_DAYS

VERSION = "page_intelligence.v1"
LIMIT = 50
ORGANIC_KEYS = frozenset(
    {
        "ga4.organicLanding.sessions",
        "ga4.organicLanding.totalUsers",
        "ga4.organicLanding.keyEvents",
    }
)
SCALAR_CHANGES = (
    "http_status",
    "content_type",
    "title",
    "meta_description",
    "h1",
    "canonical_url",
    "word_count",
    "structured_data_present",
    "content_hash",
    "indexability",
    "crawl_depth",
    "redirect_destination",
    "quality_status",
)
LIST_CHANGES = (
    "robots_directives",
    "internal_links",
    "external_links",
    "technical_issues",
)


def _bounded(rows: list[Any]) -> dict[str, object]:
    return {"items": rows[:LIMIT], "has_more": len(rows) > LIMIT, "limit": LIMIT}


def _change_summary(
    latest: SEOCrawlPageObservation | None, previous: SEOCrawlPageObservation | None
) -> dict[str, object]:
    if latest is None:
        return {
            "state": "unavailable",
            "comparable_history_available": False,
            "limitation": "No historical crawl page observation exists.",
        }
    if previous is None:
        return {
            "state": "first_observation",
            "comparable_history_available": False,
            "latest_observed_at": latest.observed_at,
        }
    changes: dict[str, object] = {}
    for field in SCALAR_CHANGES:
        before, after = getattr(previous, field), getattr(latest, field)
        if before != after:
            changes[field] = {"previous": before, "current": after}
    for field in LIST_CHANGES:
        before_values = {str(item) for item in (getattr(previous, field) or [])}
        after_values = {str(item) for item in (getattr(latest, field) or [])}
        if before_values != after_values:
            added, removed = (
                sorted(after_values - before_values),
                sorted(before_values - after_values),
            )
            changes[field] = {
                "previous_count": len(before_values),
                "current_count": len(after_values),
                "added_count": len(added),
                "removed_count": len(removed),
                "added_sample": added[:20],
                "removed_sample": removed[:20],
                "sample_truncated": len(added) > 20 or len(removed) > 20,
            }
    return {
        "state": "changed" if changes else "no_change",
        "comparable_history_available": True,
        "previous_observed_at": previous.observed_at,
        "latest_observed_at": latest.observed_at,
        "changed": bool(changes),
        "fields": changes,
        "limitation": "Stored fields only; body text is not retained in crawl observations.",
    }


def _gsc_row(row: SEOSearchObservation) -> dict[str, object]:
    return {
        "id": row.id,
        "search_property_id": row.search_property_id,
        "query": row.query,
        "raw_page": row.dimensions.get("page"),
        "clicks": row.clicks,
        "impressions": row.impressions,
        "ctr": row.ctr,
        "average_position": row.position,
        "period_start": row.date_start,
        "period_end": row.date_end,
        "quality": row.quality_status,
        "partial": row.partial,
        "mapping_state": row.mapping_state,
        "mapping_basis": row.mapping_basis,
        "resolver_version": row.resolver_version,
        "limitation": row.mapping_limitation,
        "source": "google_search_console",
    }


def _ga4_row(row: MetricObservation, key: str) -> dict[str, object]:
    return {
        "id": row.id,
        "metric_key": key,
        "value": row.value,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "quality": row.quality_state,
        "completeness": row.completeness,
        "source": "google_analytics",
        "source_id": row.source_id,
        "provenance": row.provenance,
        "raw_host": row.dimensions.get("hostName"),
        "raw_landing_page": row.dimensions.get("landingPagePlusQueryString"),
        "mapping_state": row.provenance.get("mapping_state"),
        "mapping_basis": row.provenance.get("mapping_basis"),
        "resolver_version": row.provenance.get("resolver_version"),
        "limitation": row.provenance.get("limitation") or row.provenance.get("mapping_limitation"),
    }


def _link_row(link: SEOInternalLinkObservation) -> dict[str, object]:
    return {
        "id": link.id,
        "source_page_id": link.source_page_id,
        "target_page_id": link.target_page_id,
        "raw_href": link.raw_href,
        "normalized_target_url": link.normalized_target_url,
        "anchor_text": link.anchor_text,
        "nofollow": link.nofollow,
        "occurrence_count": link.occurrence_count,
        "mapping_state": link.mapping_state,
        "mapping_basis": link.mapping_basis,
        "resolver_version": link.resolver_version,
        "limitation": link.mapping_limitation,
        "observed_at": link.observed_at,
    }


def _run_url_list_contains(run: SEOCrawlRun, key: str, url: str) -> bool:
    values = run.safe_result.get(key)
    return isinstance(values, list) and url in values


def _sitemap_evidence(
    latest: SEOCrawlPageObservation | None, run: SEOCrawlRun | None
) -> dict[str, object]:
    limitation = "Sitemap inclusion is evidence, not proof of Google indexation."
    unavailable: dict[str, object] = {
        "availability": "unavailable",
        "crawl_run_id": run.id if run else None,
        "listed": None,
        "listed_not_reached": None,
        "crawled_not_in_sitemap": None,
        "sitemap_non_indexable": None,
        "limitation": "No parsed sitemap URL evidence exists for this exact crawl run. "
        + limitation,
    }
    if (
        latest is None
        or run is None
        or run.safe_result.get("page_evidence_version") != "crawl_page.v1"
    ):
        return unavailable
    values = run.safe_result.get("sitemap_page_urls")
    if not isinstance(values, list) or not values:
        return unavailable
    normalized_url = latest.normalized_url
    listed = False
    for url in values:
        if not isinstance(url, str):
            continue
        try:
            if canonicalize_url(normalize_crawl_url(url)) == normalized_url:
                listed = True
                break
        except ValueError:
            continue
    return {
        "availability": "observed",
        "crawl_run_id": run.id,
        "listed": listed,
        "listed_not_reached": _run_url_list_contains(run, "sitemap_not_reached", normalized_url),
        "crawled_not_in_sitemap": _run_url_list_contains(
            run, "crawled_not_in_sitemap", normalized_url
        ),
        "sitemap_non_indexable": _run_url_list_contains(
            run, "sitemap_non_indexable", normalized_url
        ),
        "limitation": "Membership covers parsed URLs from this run only. " + limitation,
    }


async def read_page_intelligence(
    session: AsyncSession, organization_id: UUID, website_id: UUID, page_id: UUID
) -> dict[str, object] | None:
    """Read a fixed number of bounded, website-scoped evidence sets; no provider access."""
    scoped = await session.execute(
        select(SEOWebsite, SEOPage)
        .join(
            SEOPage,
            (SEOPage.organization_id == SEOWebsite.organization_id)
            & (SEOPage.website_id == SEOWebsite.id),
        )
        .where(
            SEOWebsite.organization_id == organization_id,
            SEOWebsite.id == website_id,
            SEOPage.id == page_id,
        )
    )
    pair = scoped.one_or_none()
    if pair is None:
        return None
    _, page = pair

    history = list(
        await session.scalars(
            select(SEOCrawlPageObservation)
            .where(
                SEOCrawlPageObservation.organization_id == organization_id,
                SEOCrawlPageObservation.website_id == website_id,
                SEOCrawlPageObservation.page_id == page_id,
            )
            .order_by(SEOCrawlPageObservation.observed_at.desc(), SEOCrawlPageObservation.id.desc())
            .limit(2)
        )
    )
    latest = history[0] if history else None
    run = (
        await session.scalar(
            select(SEOCrawlRun).where(
                SEOCrawlRun.organization_id == organization_id,
                SEOCrawlRun.website_id == website_id,
                SEOCrawlRun.id == latest.crawl_run_id,
            )
        )
        if latest
        else None
    )

    # Match SearchConsoleService's deterministic earliest mapped-property selection.
    gsc_property = await session.scalar(
        select(SEOSearchProperty)
        .where(
            SEOSearchProperty.organization_id == organization_id,
            SEOSearchProperty.website_id == website_id,
            SEOSearchProperty.provider == "google_search_console",
            SEOSearchProperty.mapping_status == "mapped",
        )
        .order_by(SEOSearchProperty.created_at, SEOSearchProperty.id)
        .limit(1)
    )
    # The current half-open window comes from that property's authoritative summary.
    gsc_summary = (
        await session.scalar(
            select(SEOSearchObservation)
            .where(
                SEOSearchObservation.organization_id == organization_id,
                SEOSearchObservation.website_id == website_id,
                SEOSearchObservation.search_property_id == gsc_property.id,
                SEOSearchObservation.dimensions["observation_type"].astext == "site_summary",
                SEOSearchObservation.quality_status.in_(("valid", "zero")),
                func.extract(
                    "epoch", SEOSearchObservation.date_end - SEOSearchObservation.date_start
                )
                == DEFAULT_SYNC_WINDOW_DAYS * 86_400,
            )
            .order_by(SEOSearchObservation.date_end.desc())
            .limit(1)
        )
        if gsc_property
        else None
    )
    gsc_window = (gsc_summary.date_start, gsc_summary.date_end) if gsc_summary else None
    mapped_gsc: list[dict[str, object]] = []
    unresolved_gsc: list[dict[str, object]] = []
    query_only_gsc: list[dict[str, object]] = []
    if gsc_window and gsc_property:
        for requested_page_id, destination in (
            (page_id, mapped_gsc),
            (None, unresolved_gsc),
        ):
            rows = await session.scalars(
                select(SEOSearchObservation)
                .where(
                    SEOSearchObservation.organization_id == organization_id,
                    SEOSearchObservation.website_id == website_id,
                    SEOSearchObservation.search_property_id == gsc_property.id,
                    SEOSearchObservation.date_start == gsc_window[0],
                    SEOSearchObservation.date_end == gsc_window[1],
                    SEOSearchObservation.dimensions["page"].astext.is_not(None),
                    SEOSearchObservation.page_id == requested_page_id,
                )
                .order_by(SEOSearchObservation.id)
                .limit(LIMIT + 1)
            )
            destination.extend(_gsc_row(row) for row in rows)
        query_only_rows = await session.scalars(
            select(SEOSearchObservation)
            .where(
                SEOSearchObservation.organization_id == organization_id,
                SEOSearchObservation.website_id == website_id,
                SEOSearchObservation.search_property_id == gsc_property.id,
                SEOSearchObservation.date_start == gsc_window[0],
                SEOSearchObservation.date_end == gsc_window[1],
                SEOSearchObservation.dimensions["observation_type"].astext == "top_query",
                SEOSearchObservation.page_id.is_(None),
            )
            .order_by(SEOSearchObservation.id)
            .limit(LIMIT + 1)
        )
        query_only_gsc.extend(_gsc_row(row) for row in query_only_rows)
    gsc_properties = [gsc_property] if gsc_property else []

    ga4_page: list[dict[str, object]] = []
    ga4_unresolved: list[dict[str, object]] = []
    for requested_page_id, destination in ((page_id, ga4_page), (None, ga4_unresolved)):
        ga4_result_rows = (
            await session.execute(
                select(MetricObservation, MetricDefinition.key)
                .join(
                    MetricDefinition, MetricDefinition.id == MetricObservation.metric_definition_id
                )
                .join(
                    InsightSource,
                    (InsightSource.id == MetricObservation.source_id)
                    & (InsightSource.organization_id == MetricObservation.organization_id),
                )
                .where(
                    MetricObservation.organization_id == organization_id,
                    MetricObservation.website_id == website_id,
                    MetricObservation.page_id == requested_page_id,
                    MetricDefinition.key.in_(ORGANIC_KEYS),
                    MetricObservation.dimensions["observation_type"].astext
                    == "organic_landing_page",
                    InsightSource.provider == "google_analytics",
                )
                .order_by(MetricObservation.period_end.desc(), MetricObservation.id)
                .limit(LIMIT + 1)
            )
        ).all()
        destination.extend(_ga4_row(row, key) for row, key in ga4_result_rows)
    ga4_properties = list(
        await session.scalars(
            select(AnalyticsProperty)
            .where(
                AnalyticsProperty.organization_id == organization_id,
                AnalyticsProperty.website_id == website_id,
            )
            .order_by(AnalyticsProperty.id)
            .limit(LIMIT + 1)
        )
    )
    ga4_evidence_observed = bool(ga4_page or ga4_unresolved) or any(
        item.page_evidence_status in {"observed", "stale"} for item in ga4_properties
    )

    link_run = await session.scalar(
        select(SEOCrawlRun)
        .where(
            SEOCrawlRun.organization_id == organization_id,
            SEOCrawlRun.website_id == website_id,
            SEOCrawlRun.safe_result["internal_link_evidence_version"].astext == "internal_links.v1",
        )
        .order_by(SEOCrawlRun.created_at.desc(), SEOCrawlRun.id.desc())
        .limit(1)
    )
    outbound: list[SEOInternalLinkObservation] = []
    inbound: list[SEOInternalLinkObservation] = []
    outbound_count = inbound_count = unresolved_count = 0
    source_page_observed = False
    source_link_evidence_available = False
    successful_sources: object = None
    if link_run:
        source_page_observed = (
            await session.scalar(
                select(SEOCrawlPageObservation.id)
                .where(
                    SEOCrawlPageObservation.organization_id == organization_id,
                    SEOCrawlPageObservation.website_id == website_id,
                    SEOCrawlPageObservation.crawl_run_id == link_run.id,
                    SEOCrawlPageObservation.page_id == page_id,
                )
                .limit(1)
            )
            is not None
        )
        successful_sources = link_run.safe_result.get(
            "internal_link_evidence_successful_source_urls"
        )
        source_link_evidence_available = (
            source_page_observed
            and isinstance(successful_sources, list)
            and page.normalized_url in successful_sources
        )
        link_filter = (
            SEOInternalLinkObservation.organization_id == organization_id,
            SEOInternalLinkObservation.website_id == website_id,
            SEOInternalLinkObservation.crawl_run_id == link_run.id,
        )
        if source_link_evidence_available:
            outbound = list(
                await session.scalars(
                    select(SEOInternalLinkObservation)
                    .where(*link_filter, SEOInternalLinkObservation.source_page_id == page_id)
                    .order_by(SEOInternalLinkObservation.id)
                    .limit(LIMIT + 1)
                )
            )
        inbound = list(
            await session.scalars(
                select(SEOInternalLinkObservation)
                .where(*link_filter, SEOInternalLinkObservation.target_page_id == page_id)
                .order_by(SEOInternalLinkObservation.id)
                .limit(LIMIT + 1)
            )
        )
        if source_link_evidence_available:
            outbound_count, unresolved_count = (
                await session.execute(
                    select(
                        func.count().filter(SEOInternalLinkObservation.target_page_id.is_not(None)),
                        func.count().filter(SEOInternalLinkObservation.target_page_id.is_(None)),
                    ).where(*link_filter, SEOInternalLinkObservation.source_page_id == page_id)
                )
            ).one()
        inbound_count = (
            await session.scalar(
                select(func.count())
                .select_from(SEOInternalLinkObservation)
                .where(*link_filter, SEOInternalLinkObservation.target_page_id == page_id)
            )
        ) or 0
    link_status = (
        link_run.safe_result.get("internal_link_evidence_status") if link_run else "unavailable"
    )
    if link_run and not source_link_evidence_available and link_status != "unavailable":
        link_status = "partial"
    link_limitation = (
        link_run.safe_result.get("internal_link_evidence_limitation")
        if link_run
        else "No normalized internal-link evidence exists for a crawl run."
    )
    if link_run and not source_page_observed:
        missing_source_limitation = (
            "Selected crawl run did not observe this page as a source; "
            "outbound link evidence is unavailable."
        )
        link_limitation = (
            f"{link_limitation} {missing_source_limitation}"
            if link_limitation
            else missing_source_limitation
        )
    elif link_run and not source_link_evidence_available:
        missing_source_limitation = (
            "Page crawl evidence exists, but outbound link evidence for this source "
            "was not successfully persisted."
            if isinstance(successful_sources, list)
            else "Selected crawl run has no per-source link-evidence success marker; "
            "outbound evidence is unavailable."
        )
        link_limitation = (
            f"{link_limitation} {missing_source_limitation}"
            if link_limitation
            else missing_source_limitation
        )

    knowledge = list(
        await session.scalars(
            select(BusinessKnowledgeDocument)
            .where(
                BusinessKnowledgeDocument.organization_id == organization_id,
                BusinessKnowledgeDocument.source_type == "seo_page",
                BusinessKnowledgeDocument.source_reference == str(page_id),
            )
            .order_by(BusinessKnowledgeDocument.observed_at.desc(), BusinessKnowledgeDocument.id)
            .limit(LIMIT + 1)
        )
    )
    opportunities = list(
        await session.scalars(
            select(SEOOpportunity)
            .where(
                SEOOpportunity.organization_id == organization_id,
                SEOOpportunity.website_id == website_id,
                SEOOpportunity.page_id == page_id,
            )
            .order_by(SEOOpportunity.created_at.desc(), SEOOpportunity.id)
            .limit(LIMIT + 1)
        )
    )
    opportunity_scope = (
        SEOOpportunity.organization_id == organization_id,
        SEOOpportunity.website_id == website_id,
        SEOOpportunity.page_id == page_id,
    )
    revision_to_opportunity = (
        SEORecommendationRevision.organization_id == SEOOpportunity.organization_id
    ) & (SEORecommendationRevision.opportunity_id == SEOOpportunity.id)
    task_to_revision = (
        SEOImplementationTask.organization_id == SEORecommendationRevision.organization_id
    ) & (SEOImplementationTask.recommendation_revision_id == SEORecommendationRevision.id)
    outcome_to_task = (SEOOutcome.organization_id == SEOImplementationTask.organization_id) & (
        SEOOutcome.implementation_task_id == SEOImplementationTask.id
    )
    revisions = list(
        await session.scalars(
            select(SEORecommendationRevision)
            .join(SEOOpportunity, revision_to_opportunity)
            .where(*opportunity_scope)
            .order_by(SEORecommendationRevision.created_at.desc(), SEORecommendationRevision.id)
            .limit(LIMIT + 1)
        )
    )
    tasks = list(
        await session.scalars(
            select(SEOImplementationTask)
            .join(SEORecommendationRevision, task_to_revision)
            .join(SEOOpportunity, revision_to_opportunity)
            .where(*opportunity_scope)
            .order_by(SEOImplementationTask.created_at.desc(), SEOImplementationTask.id)
            .limit(LIMIT + 1)
        )
    )
    outcomes = list(
        await session.scalars(
            select(SEOOutcome)
            .join(SEOImplementationTask, outcome_to_task)
            .join(SEORecommendationRevision, task_to_revision)
            .join(SEOOpportunity, revision_to_opportunity)
            .where(*opportunity_scope)
            .order_by(SEOOutcome.created_at.desc(), SEOOutcome.id)
            .limit(LIMIT + 1)
        )
    )

    current_fields = (
        "http_status",
        "content_type",
        "title",
        "meta_description",
        "h1",
        "robots_directives",
        "word_count",
        "structured_data_present",
        "content_hash",
        "indexability",
        "technical_issues",
        "crawl_depth",
        "redirect_destination",
        "quality_status",
        "observed_at",
    )
    return {
        "version": VERSION,
        "identity": {
            "organization_id": organization_id,
            "website_id": website_id,
            "page_id": page_id,
            "normalized_url": page.normalized_url,
            "observed_url": page.observed_url,
            "canonical_url": page.canonical_url,
        },
        "current_page": {
            name: (
                _bounded(getattr(page, name) or [])
                if name in {"robots_directives", "technical_issues"}
                else getattr(page, name)
            )
            for name in current_fields
        },
        "crawl": {
            "availability": "observed" if latest else "unavailable",
            "source": "crawl",
            "evidence_version": run.safe_result.get("page_evidence_version") if run else None,
            "crawl_run_id": run.id if run else None,
            "run_status": run.status if run else None,
            "completed_at": run.completed_at if run else None,
            "observed_at": latest.observed_at if latest else None,
            "observation": (
                {
                    "id": latest.id,
                    "normalized_url": latest.normalized_url,
                    "http_status": latest.http_status,
                    "canonical_url": latest.canonical_url,
                    "indexability": latest.indexability,
                    "content_hash": latest.content_hash,
                    "quality_status": latest.quality_status,
                }
                if latest
                else None
            ),
            "quality": latest.quality_status if latest else None,
            "robots_available": run.safe_result.get("robots_available") if run else None,
            "sitemap_page_count": run.safe_result.get("sitemap_page_count") if run else None,
            "sitemap": _sitemap_evidence(latest, run),
            "limitation": "Crawl and sitemap evidence do not establish Google indexation.",
        },
        "change": _change_summary(latest, history[1] if len(history) > 1 else None),
        "gsc": {
            "availability": "observed" if gsc_summary else "unavailable",
            "search_property_id": gsc_property.id if gsc_property else None,
            "window_quality": gsc_summary.quality_status if gsc_summary else None,
            "period_start": gsc_window[0] if gsc_window else None,
            "period_end": gsc_window[1] if gsc_window else None,
            "page": _bounded(mapped_gsc),
            "website_unresolved": _bounded(unresolved_gsc),
            "website_query_only": _bounded(query_only_gsc),
            "properties": _bounded(
                [
                    {
                        "id": item.id,
                        "freshness": item.freshness_status,
                        "last_synced_at": item.last_synced_at,
                    }
                    for item in gsc_properties
                ]
            ),
            "limitation": (
                "Average position is provider evidence, not an exact rank; "
                "query-only evidence is website scoped."
            ),
        },
        "ga4_organic_landing": {
            "availability": "observed" if ga4_evidence_observed else "unavailable",
            "page": _bounded(ga4_page),
            "website_unresolved": _bounded(ga4_unresolved),
            "properties": _bounded(
                [
                    {
                        "id": item.id,
                        "status": item.page_evidence_status,
                        "freshness": item.freshness_status,
                        "last_synced_at": item.last_synced_at,
                        "limitation": item.page_evidence_limitation,
                        "checked_at": item.page_evidence_checked_at,
                    }
                    for item in ga4_properties
                ]
            ),
            "key_events_meaning": (
                "GA4-reported key events associated with Organic Search sessions "
                "grouped by landing page."
            ),
            "limitation": "totalUsers is non-additive across landing-page groups.",
        },
        "internal_links": {
            "availability": link_status,
            "evidence_version": "internal_links.v1" if link_run else None,
            "crawl_run_id": link_run.id if link_run else None,
            "run_status": link_run.status if link_run else None,
            "completed_at": link_run.completed_at if link_run else None,
            "stop_reason": link_run.stop_reason if link_run else None,
            "pages_crawled": link_run.safe_result.get("pages_crawled") if link_run else None,
            "pages_queued": link_run.safe_result.get("pages_queued") if link_run else None,
            "pages_skipped": link_run.safe_result.get("pages_skipped") if link_run else None,
            "source_page_observed": source_page_observed,
            "source_link_evidence_available": source_link_evidence_available,
            "mapped_outbound_count": outbound_count if source_link_evidence_available else None,
            "mapped_inbound_count": inbound_count if link_run else None,
            "unresolved_outbound_count": (
                unresolved_count if source_link_evidence_available else None
            ),
            "outbound": _bounded([_link_row(item) for item in outbound]),
            "inbound": _bounded([_link_row(item) for item in inbound]),
            "limitation": link_limitation,
        },
        "content": {
            "availability": "observed" if page.observed_at else "unavailable",
            "title": page.title,
            "meta_description": page.meta_description,
            "h1": page.h1,
            "word_count": page.word_count,
            "structured_data_present": page.structured_data_present,
            "content_hash": page.content_hash,
            "observed_at": page.observed_at,
            "knowledge": _bounded(
                [
                    {
                        "id": item.id,
                        "source_type": item.source_type,
                        "source_reference": item.source_reference,
                        "source_url": item.source_url,
                        "authority": item.authority,
                        "status": item.status,
                        "content_hash": item.content_hash,
                        "observed_at": item.observed_at,
                        "supersedes_id": item.supersedes_id,
                    }
                    for item in knowledge
                ]
            ),
            "business_relationship_availability": "unavailable",
            "limitation": (
                "No deterministic page-to-service or business-priority relationship is persisted."
            ),
        },
        "workflow": {
            "opportunities": _bounded(
                [
                    {"id": item.id, "type": item.opportunity_type, "status": item.status}
                    for item in opportunities
                ]
            ),
            "recommendations": _bounded(
                [
                    {
                        "id": item.id,
                        "opportunity_id": item.opportunity_id,
                        "status": item.status,
                        "revision_number": item.revision_number,
                    }
                    for item in revisions
                ]
            ),
            "tasks": _bounded(
                [
                    {
                        "id": item.id,
                        "recommendation_revision_id": item.recommendation_revision_id,
                        "status": item.status,
                    }
                    for item in tasks
                ]
            ),
            "outcomes": _bounded(
                [
                    {
                        "id": item.id,
                        "implementation_task_id": item.implementation_task_id,
                        "classification": item.classification,
                    }
                    for item in outcomes
                ]
            ),
            "limitation": (
                "Bounded state references only; no scoring or business value is inferred."
            ),
        },
    }
