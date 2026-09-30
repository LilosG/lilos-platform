"""Resolve the evidence and page attribution for one governed SEO decision."""

from __future__ import annotations

import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.errors import ConflictError
from apps.api.app.insights.models import MetricObservation
from apps.api.app.products.seo.limitation_codes import LIMITATION_COPY, SEOLimitationCode
from apps.api.app.products.seo.models import (
    SEOCrawlPageObservation,
    SEOOpportunity,
    SEOPage,
    SEOSearchObservation,
    SEOWebsite,
)

VERSION = "seo_decision.v1"
GROWTH_TYPES = frozenset({"gsc_striking_distance", "gsc_low_ctr", "gsc_query_demand"})


def _fingerprint(value: dict[str, object]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _metric_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except ValueError as exc:
        raise SEOEvidenceInvalidError(SEOLimitationCode.METRIC_VALUE_INVALID) from exc


class SEOEvidenceInvalidError(ConflictError):
    """The proposed decision cannot be resolved to scoped persisted evidence.

    ``limitation_code`` closes the set of reasons this can be raised for
    (`SEOLimitationCode`); the frontend switches on it instead of matching
    ``public_message`` prose.
    """

    code = "SEO_EVIDENCE_INVALID"
    public_message = "The recommendation evidence cannot be resolved in this scope."

    def __init__(self, limitation_code: SEOLimitationCode) -> None:
        self.limitation_code = limitation_code.value
        self.public_message = LIMITATION_COPY[limitation_code]
        super().__init__(self.public_message)


class SEOActiveChangeError(ConflictError):
    code = "SEO_ACTIVE_GROWTH_CHANGE"
    public_message = "This page already has an active material growth change."

    def __init__(self, revision_id: UUID, state: str) -> None:
        self.revision_id = revision_id
        self.state = state
        self.public_message = f"Page has active growth change {revision_id} ({state})."
        super().__init__(f"Page has active growth change {revision_id} ({state})")


def recommendation_class(opportunity: SEOOpportunity) -> str:
    return (
        "growth_change" if opportunity.opportunity_type in GROWTH_TYPES else "technical_regression"
    )


def revision_decision(references: list[object]) -> dict[str, object] | None:
    if references and isinstance(references[-1], dict):
        value = references[-1].get("decision_context")
        return value if isinstance(value, dict) else None
    return None


def growth_handoff(
    revision_id: UUID, status: str, hypothesis: str, action: str, context: dict[str, object]
) -> dict[str, object]:
    return {
        "source_reference": f"seo-recommendation:{revision_id}",
        "opportunity_reference": f"seo-opportunity:{context['opportunity_id']}",
        "target_reference": (
            f"seo-page:{context['page_id']}"
            if context.get("page_id")
            else f"seo-opportunity:{context['opportunity_id']}"
        ),
        "website_id": context["website_id"],
        "location_id": context["location_id"],
        "page_mapping_state": context["page_mapping_state"],
        "evidence_references": context["evidence_references"],
        "target_metric": context["target_metric"],
        "expected_result_hypothesis": hypothesis,
        "proposed_action": action,
        "approval_state": status,
    }


async def resolve_decision(
    session: AsyncSession,
    organization_id: UUID,
    opportunity: SEOOpportunity,
    references: list[str],
) -> dict[str, object]:
    """Only LILOs derives identifiers, facts, and availability; prose is untrusted."""
    source_ref = f"seo-opportunity:{opportunity.id}"
    if references != [source_ref]:
        raise SEOEvidenceInvalidError(SEOLimitationCode.REFERENCE_MISMATCH)
    if opportunity.organization_id != organization_id or opportunity.active_marker != "active":
        raise SEOEvidenceInvalidError(SEOLimitationCode.ORGANIZATION_SCOPE_INVALID)
    if (
        not opportunity.source_versions
        or opportunity.score_explanation.get("score_policy_version") != "opportunity_score.v2"
    ):
        raise SEOEvidenceInvalidError(SEOLimitationCode.SCORE_POLICY_STALE)
    website = await session.scalar(
        select(SEOWebsite).where(
            SEOWebsite.organization_id == organization_id,
            SEOWebsite.id == opportunity.website_id,
            SEOWebsite.location_id == opportunity.location_id,
        )
    )
    if website is None:
        raise SEOEvidenceInvalidError(SEOLimitationCode.WEBSITE_MAPPING_UNAVAILABLE)
    if opportunity.page_id is not None:
        page = await session.scalar(
            select(SEOPage).where(
                SEOPage.organization_id == organization_id,
                SEOPage.website_id == website.id,
                SEOPage.id == opportunity.page_id,
            )
        )
        if page is None:
            raise SEOEvidenceInvalidError(SEOLimitationCode.PAGE_OUT_OF_SCOPE)

    evidence = opportunity.evidence or {}
    source = evidence.get("source")
    if source is None and opportunity.source_versions == ["crawl.v1"] and evidence.get("issue"):
        source = "crawl"
    observation: SEOSearchObservation | SEOCrawlPageObservation | None = None
    if source == "google_search_console":
        record_id = evidence.get("observation_id")
        if not isinstance(record_id, str):
            raise SEOEvidenceInvalidError(SEOLimitationCode.OBSERVATION_ID_MISSING)
        try:
            parsed_id = UUID(record_id)
        except (TypeError, ValueError) as exc:
            raise SEOEvidenceInvalidError(SEOLimitationCode.OBSERVATION_ID_INVALID) from exc
        observation = await session.scalar(
            select(SEOSearchObservation).where(
                SEOSearchObservation.id == parsed_id,
                SEOSearchObservation.organization_id == organization_id,
                SEOSearchObservation.website_id == website.id,
                SEOSearchObservation.page_id == opportunity.page_id,
                SEOSearchObservation.query == evidence.get("query"),
            )
        )
        record_ref = f"seo-search-observation:{record_id}"
    elif source == "crawl" and opportunity.page_id is not None:
        observation = await session.scalar(
            select(SEOCrawlPageObservation)
            .where(
                SEOCrawlPageObservation.organization_id == organization_id,
                SEOCrawlPageObservation.website_id == website.id,
                SEOCrawlPageObservation.page_id == opportunity.page_id,
            )
            .order_by(SEOCrawlPageObservation.observed_at.desc())
            .limit(1)
        )
        record_ref = f"seo-crawl-observation:{observation.id}" if observation else ""
    else:
        raise SEOEvidenceInvalidError(SEOLimitationCode.SOURCE_RECORD_UNSUPPORTED)
    if observation is None:
        raise SEOEvidenceInvalidError(SEOLimitationCode.SOURCE_RECORD_NOT_FOUND)
    if (
        isinstance(observation, SEOCrawlPageObservation)
        and opportunity.opportunity_type not in observation.technical_issues
    ):
        raise SEOEvidenceInvalidError(SEOLimitationCode.CRAWL_ISSUE_STALE)
    allowed_quality = (
        {"issues_detected"}
        if isinstance(observation, SEOCrawlPageObservation)
        else {"valid", "zero"}
    )
    if getattr(observation, "quality_status", None) not in allowed_quality:
        raise SEOEvidenceInvalidError(SEOLimitationCode.SOURCE_QUALITY_INVALID)
    if isinstance(observation, SEOSearchObservation):
        observed_facts: dict[str, object] = {
            "clicks": observation.clicks,
            "impressions": observation.impressions,
            "ctr": str(observation.ctr) if observation.ctr is not None else None,
            "position": str(observation.position) if observation.position is not None else None,
            "date_start": observation.date_start.isoformat(),
            "date_end": observation.date_end.isoformat(),
            "mapping_state": observation.mapping_state,
            "quality_status": observation.quality_status,
        }
        if (
            evidence.get("clicks") != observation.clicks
            or evidence.get("impressions") != observation.impressions
            or evidence.get("date_start") != observed_facts["date_start"]
            or evidence.get("date_end") != observed_facts["date_end"]
            or _metric_float(evidence.get("ctr")) != _metric_float(observation.ctr)
            or _metric_float(evidence.get("position")) != _metric_float(observation.position)
        ):
            raise SEOEvidenceInvalidError(SEOLimitationCode.SEARCH_FACTS_CHANGED)
    else:
        observed_facts = {
            "technical_issues": observation.technical_issues,
            "http_status": observation.http_status,
            "indexability": observation.indexability,
            "quality_status": observation.quality_status,
            "observed_at": observation.observed_at,
        }
        if ("http_status" in evidence and evidence["http_status"] != observation.http_status) or (
            "indexability" in evidence and evidence["indexability"] != observation.indexability
        ):
            raise SEOEvidenceInvalidError(SEOLimitationCode.CRAWL_FACTS_CHANGED)
    if (
        opportunity.opportunity_type == "gsc_query_demand"
        and isinstance(observation, SEOSearchObservation)
        and (
            observation.dimensions.get("page")
            or observation.mapping_state not in {"unknown", "unavailable", None}
            or evidence.get("page_mapping_state") != "unknown"
        )
    ):
        raise SEOEvidenceInvalidError(SEOLimitationCode.QUERY_DEMAND_CANNOT_TARGET_PAGE)

    limitation = evidence.get("evidence_limitation")
    if opportunity.page_id is None:
        limitation = limitation or "No landing page is attributed to this observation."
    business = evidence.get("business_importance")
    business_ref: str | None = None
    business_fingerprint: str | None = None
    if isinstance(business, dict) and business.get("business_importance_state") == "inferred":
        metric_id = business.get("metric_observation_id")
        try:
            parsed_metric_id = UUID(str(metric_id))
        except ValueError as exc:
            raise SEOEvidenceInvalidError(SEOLimitationCode.BUSINESS_EVIDENCE_ID_INVALID) from exc
        metric = await session.scalar(
            select(MetricObservation).where(
                MetricObservation.id == parsed_metric_id,
                MetricObservation.organization_id == organization_id,
                MetricObservation.website_id == website.id,
                MetricObservation.page_id == opportunity.page_id,
            )
        )
        if metric is None or business.get("location_id") != (
            str(opportunity.location_id) if opportunity.location_id else None
        ):
            raise SEOEvidenceInvalidError(SEOLimitationCode.BUSINESS_EVIDENCE_OUT_OF_SCOPE)
        if (
            metric.quality_state != "valid"
            or metric.value is None
            or business.get("value") != int(metric.value)
            or business.get("business_policy_version") != "business_importance.v1"
        ):
            raise SEOEvidenceInvalidError(SEOLimitationCode.BUSINESS_EVIDENCE_MISMATCH)
        business_ref = f"metric-observation:{metric.id}"
        business_fingerprint = _fingerprint(
            {
                "value": metric.value,
                "quality_state": metric.quality_state,
                "period_start": metric.period_start,
                "period_end": metric.period_end,
                "provenance": metric.provenance,
            }
        )
    business_state = (
        business.get("business_importance_state") if isinstance(business, dict) else "unavailable"
    )
    access = {
        "availability": "available" if source == "crawl" else "limited",
        "evidence_references": [record_ref] if source == "crawl" else [],
        "limitation": None
        if source == "crawl"
        else "No page access observation supports this opportunity.",
    }
    conversion = {
        "availability": "limited" if business_state == "inferred" else "unavailable",
        "evidence_references": [business_ref] if business_ref else [],
        "limitation": business.get("limitation")
        if isinstance(business, dict)
        else "No supported conversion evidence.",
    }
    return {
        "contract_version": VERSION,
        "organization_id": str(organization_id),
        "website_id": str(website.id),
        "location_id": str(opportunity.location_id) if opportunity.location_id else None,
        "page_id": str(opportunity.page_id) if opportunity.page_id else None,
        "page_mapping_state": "mapped" if opportunity.page_id else "unknown",
        "opportunity_id": str(opportunity.id),
        "opportunity_version": opportunity.version,
        "recommendation_class": recommendation_class(opportunity),
        "source_versions": opportunity.source_versions,
        "evidence_references": [source_ref, record_ref, *([business_ref] if business_ref else [])],
        "source_evidence_fingerprint": _fingerprint(observed_facts),
        "business_evidence_fingerprint": business_fingerprint,
        "evidence_quality": getattr(observation, "quality_status", None),
        "evidence_freshness": str(
            getattr(observation, "date_end", None) or getattr(observation, "observed_at", None)
        ),
        "evidence_limitation": limitation,
        "business_importance_state": business_state,
        "business_importance_value": (
            business.get("business_value") if isinstance(business, dict) else None
        ),
        "business_importance_version": (
            business.get("business_policy_version") if isinstance(business, dict) else None
        ),
        "opportunity_priority_score": opportunity.priority_score,
        "opportunity_score_policy_version": opportunity.score_explanation.get(
            "score_policy_version"
        ),
        "target_metric": "gsc_ctr" if opportunity.opportunity_type == "gsc_low_ctr" else None,
        "passes": {
            "access": access,
            "competition": {
                "availability": "unavailable",
                "limitation": "No persisted competitive evidence exists.",
            },
            "answer_engines": {
                "availability": "unavailable",
                "limitation": "No persisted answer-engine observation exists.",
            },
            "conversion": conversion,
        },
    }
