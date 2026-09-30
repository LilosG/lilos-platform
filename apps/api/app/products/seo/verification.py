"""Deterministic implementation truth for an approved SEO decision.

Workflow completion is a prerequisite for review, never proof of a site change.
Only source records already persisted by SEO or Content can verify an outcome.
"""

from __future__ import annotations

import html as html_lib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.execution.models import WorkflowRun
from apps.api.app.products.content.models import (
    ContentItem,
    ContentOpportunity,
    ContentPublication,
)
from apps.api.app.products.seo.change_set import SiteChangeField, SiteChangeSet
from apps.api.app.products.seo.crawl_engine import extract_page_signals
from apps.api.app.products.seo.decision import revision_decision
from apps.api.app.products.seo.models import (
    SEOCrawlPageObservation,
    SEOImplementationTask,
    SEOOpportunity,
    SEORecommendationRevision,
)

VERSION = "seo_implementation_verification.v1"
LIVE_VERSION = "seo_site_change_live_verification.v1"
LIVE_FETCH_TIMEOUT_SECONDS = 20.0
CRAWL_VERIFIABLE_ISSUES = frozenset(
    {
        "missing_title",
        "missing_meta_description",
        "missing_h1",
        "multiple_h1",
        "non_200_status",
        "title_truncated",
        "meta_description_truncated",
        "h1_truncated",
    }
)


def _result(
    task: SEOImplementationTask,
    opportunity: SEOOpportunity,
    *,
    state: str,
    method: str,
    references: list[str],
    observed_at: datetime | None,
    expected: Mapping[str, object],
    actual: Mapping[str, object],
    limitations: list[str],
) -> dict[str, object]:
    return {
        "policy_version": VERSION,
        "result": state,
        "organization_id": str(task.organization_id),
        "website_id": str(opportunity.website_id),
        "location_id": str(opportunity.location_id) if opportunity.location_id else None,
        "page_id": str(opportunity.page_id) if opportunity.page_id else None,
        "recommendation_revision_id": str(task.recommendation_revision_id),
        "implementation_task_id": str(task.id),
        "workflow_run_id": str(task.workflow_run_id),
        "target_reference": task.target_reference,
        "verification_method": method,
        "evidence_references": references,
        "observed_at": observed_at.isoformat() if observed_at else None,
        "expected_change": expected,
        "actual": actual,
        "limitations": limitations,
    }


async def read_implementation_truth(
    session: AsyncSession,
    task: SEOImplementationTask,
    revision: SEORecommendationRevision,
    opportunity: SEOOpportunity,
) -> dict[str, object]:
    """Reconcile one task from exact tenant, site, page, and revision identity."""
    context = revision_decision(revision.evidence_references)
    if (
        revision.status != "approved"
        or revision.organization_id != task.organization_id
        or revision.id != task.recommendation_revision_id
        or opportunity.id != revision.opportunity_id
        or context is None
        or context.get("organization_id") != str(task.organization_id)
        or context.get("website_id") != str(opportunity.website_id)
        or context.get("location_id")
        != (str(opportunity.location_id) if opportunity.location_id else None)
        or context.get("page_id") != (str(opportunity.page_id) if opportunity.page_id else None)
    ):
        return _result(
            task,
            opportunity,
            state="unavailable",
            method="scope_validation",
            references=[],
            observed_at=None,
            expected={},
            actual={},
            limitations=["The approved revision or scoped target cannot be resolved."],
        )
    expected_target = (
        f"seo-page:{opportunity.page_id}"
        if opportunity.page_id
        else f"seo-opportunity:{opportunity.id}"
    )
    if task.target_reference != expected_target:
        return _result(
            task,
            opportunity,
            state="unavailable",
            method="scope_validation",
            references=[],
            observed_at=None,
            expected={"target_reference": expected_target},
            actual={"target_reference": task.target_reference},
            limitations=["Implementation target differs from the approved decision."],
        )
    workflow = await session.scalar(
        select(WorkflowRun).where(
            WorkflowRun.organization_id == task.organization_id,
            WorkflowRun.id == task.workflow_run_id,
            WorkflowRun.location_id == opportunity.location_id,
        )
    )
    if workflow is None:
        return _result(
            task,
            opportunity,
            state="unavailable",
            method="workflow_provenance",
            references=[],
            observed_at=None,
            expected={},
            actual={},
            limitations=["Bound implementation workflow is unavailable."],
        )
    if workflow.status not in {"completed", "partially_completed"}:
        return _result(
            task,
            opportunity,
            state="failed"
            if workflow.status in {"failed", "cancelled", "escalated"}
            else "pending",
            method="workflow_provenance",
            references=[f"workflow-run:{workflow.id}"],
            observed_at=workflow.completed_at,
            expected={"workflow_status": "completed"},
            actual={"workflow_status": workflow.status},
            limitations=["A workflow state cannot prove a client-facing page change."],
        )

    if revision.change_set is not None:
        return await _verify_site_change(session, task, opportunity, revision)
    if context.get("recommendation_class") == "technical_regression":
        return await _verify_technical(session, task, opportunity, context)
    return await _verify_content(session, task, opportunity)


async def _verify_technical(
    session: AsyncSession,
    task: SEOImplementationTask,
    opportunity: SEOOpportunity,
    context: dict[str, object],
) -> dict[str, object]:
    issue = opportunity.opportunity_type
    expected = {"issue_absent": issue}
    if opportunity.page_id is None or issue not in CRAWL_VERIFIABLE_ISSUES:
        return _result(
            task,
            opportunity,
            state="unavailable",
            method="scoped_crawl_comparison",
            references=[],
            observed_at=None,
            expected=expected,
            actual={},
            limitations=["This technical change has no supported deterministic page check."],
        )
    raw_references = context.get("evidence_references")
    references_to_check = raw_references if isinstance(raw_references, list) else []
    baseline_ref = next(
        (str(ref) for ref in references_to_check if str(ref).startswith("seo-crawl-observation:")),
        None,
    )
    if baseline_ref is None:
        return _result(
            task,
            opportunity,
            state="unavailable",
            method="scoped_crawl_comparison",
            references=[],
            observed_at=None,
            expected=expected,
            actual={},
            limitations=["Approved baseline crawl observation is unavailable."],
        )
    try:
        baseline_id = UUID(baseline_ref.split(":", 1)[1])
    except ValueError:
        baseline_id = UUID(int=0)
    baseline = await session.scalar(
        select(SEOCrawlPageObservation).where(
            SEOCrawlPageObservation.id == baseline_id,
            SEOCrawlPageObservation.organization_id == task.organization_id,
            SEOCrawlPageObservation.website_id == opportunity.website_id,
            SEOCrawlPageObservation.page_id == opportunity.page_id,
        )
    )
    if baseline is None or issue not in baseline.technical_issues or baseline.observed_at is None:
        return _result(
            task,
            opportunity,
            state="unavailable",
            method="scoped_crawl_comparison",
            references=[],
            observed_at=None,
            expected=expected,
            actual={},
            limitations=["Approved baseline does not show the claimed technical issue."],
        )
    current = await session.scalar(
        select(SEOCrawlPageObservation)
        .where(
            SEOCrawlPageObservation.organization_id == task.organization_id,
            SEOCrawlPageObservation.website_id == opportunity.website_id,
            SEOCrawlPageObservation.page_id == opportunity.page_id,
        )
        .order_by(SEOCrawlPageObservation.observed_at.desc())
        .limit(1)
    )
    references = [baseline_ref]
    if current is None or current.id == baseline.id or current.observed_at is None:
        return _result(
            task,
            opportunity,
            state="pending",
            method="scoped_crawl_comparison",
            references=references,
            observed_at=None,
            expected=expected,
            actual={},
            limitations=["No newer persisted crawl observation exists for this page."],
        )
    references.append(f"seo-crawl-observation:{current.id}")
    actual = {
        "technical_issues": current.technical_issues,
        "http_status": current.http_status,
        "title": current.title,
        "meta_description": current.meta_description,
        "h1": current.h1,
    }
    if current.observed_at <= max(task.created_at, baseline.observed_at):
        state, limitation = "pending", "The observation predates this implementation task."
    elif current.quality_status not in {"clean", "issues_detected"}:
        state, limitation = "unavailable", "The new crawl observation has invalid quality."
    elif issue in current.technical_issues:
        state, limitation = "failed", "The approved technical issue remains present."
    elif issue == "non_200_status" and current.http_status != 200:
        state, limitation = "failed", "The observed HTTP status remains non-200."
    elif issue == "missing_title" and not current.title:
        state, limitation = "failed", "The current page has no title."
    elif issue == "missing_meta_description" and not current.meta_description:
        state, limitation = "failed", "The current page has no meta description."
    elif issue == "missing_h1" and not current.h1:
        state, limitation = "failed", "The current page has no H1."
    else:
        state, limitation = (
            "verified",
            (
                "Crawl proves the technical issue resolved; it cannot attribute the change "
                "to the workflow or assess qualitative copy claims."
            ),
        )
    return _result(
        task,
        opportunity,
        state=state,
        method="scoped_crawl_comparison",
        references=references,
        observed_at=current.observed_at,
        expected=expected,
        actual=actual,
        limitations=[limitation],
    )


async def _verify_content(
    session: AsyncSession,
    task: SEOImplementationTask,
    opportunity: SEOOpportunity,
) -> dict[str, object]:
    """Retain deployment provenance; do not infer exact public page parity."""
    publication = await session.scalar(
        select(ContentPublication)
        .join(ContentItem, ContentItem.id == ContentPublication.content_item_id)
        .join(ContentOpportunity, ContentOpportunity.id == ContentItem.opportunity_id)
        .where(
            ContentPublication.organization_id == task.organization_id,
            ContentItem.organization_id == task.organization_id,
            ContentOpportunity.organization_id == task.organization_id,
            ContentOpportunity.location_id == opportunity.location_id,
            ContentOpportunity.source_reference == f"seo-opportunity:{opportunity.id}",
            ContentPublication.verified_at >= task.created_at,
        )
        .order_by(ContentPublication.verified_at.desc())
        .limit(1)
    )
    references = [f"content-publication:{publication.id}"] if publication else []
    actual: dict[str, object] = {}
    if publication is not None:
        actual = {
            "publication_status": publication.status,
            "content_revision_id": str(publication.content_revision_id),
            "merged_commit_sha": publication.external_revision_id,
            "published_url": publication.published_url,
        }
    return _result(
        task,
        opportunity,
        state="unavailable",
        method="content_publication_and_page",
        references=references,
        observed_at=publication.verified_at if publication else None,
        expected={"page_id": str(opportunity.page_id) if opportunity.page_id else None},
        actual=actual,
        limitations=[
            "A draft, approval, or agent completion is not deployment evidence."
            if publication is None
            else "Content deployment identity is recorded, but no exact public-page "
            "revision parity evidence links it to this SEO target."
        ],
    )


# --------------------------------------------------------------------------
# Live-site verification of an applied change set
# --------------------------------------------------------------------------

# The page signal each verifiable field is read back from. A field not listed here
# (body sections, schema, links) is applied but reported as not checked -- never as
# verified -- because this read-back cannot prove it.
_LIVE_SIGNAL: dict[SiteChangeField, str] = {
    SiteChangeField.SEO_TITLE: "title",
    SiteChangeField.META_DESCRIPTION: "meta_description",
    SiteChangeField.H1: "h1",
}


@dataclass(frozen=True, slots=True)
class LivePage:
    """One fetched production page: its HTML, or why it could not be read."""

    url: str
    http_status: int | None
    html: str | None
    error: str | None = None


def _normalize_text(value: str | None) -> str:
    return " ".join(html_lib.unescape(value or "").split())


async def fetch_live_page(
    url: str, *, cache_buster: str, client: httpx.AsyncClient | None = None
) -> LivePage:
    """Fetch the public page with no database transaction held by the caller.

    The cache-buster query keeps a CDN that still holds the pre-deploy copy from
    making a correct change look like a failed one.
    """
    separator = "&" if "?" in url else "?"
    target = f"{url}{separator}lilos_verify={cache_buster}"
    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=LIVE_FETCH_TIMEOUT_SECONDS, follow_redirects=True)
    try:
        response = await http.get(target, headers={"Cache-Control": "no-cache"})
        return LivePage(url=url, http_status=response.status_code, html=response.text)
    except httpx.HTTPError as exc:
        return LivePage(url=url, http_status=None, html=None, error=type(exc).__name__)
    finally:
        if owns_client:
            await http.aclose()


def verify_live_site_change(
    change_set: SiteChangeSet,
    pages: Mapping[UUID, LivePage],
    *,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, object]:
    """Confirm every applied value is what production now serves.

    ``unavailable`` means the live page could not be read (retry later); ``failed``
    means it was read and a value differs, with the observed value recorded.
    """
    checks: list[dict[str, object]] = []
    unavailable = False
    failed = False
    for item in change_set.items:
        page = pages.get(item.page_id)
        signal = _LIVE_SIGNAL.get(item.field)
        check: dict[str, object] = {
            "page_id": str(item.page_id),
            "url": page.url if page else None,
            "field": item.field.value,
            "expected": item.proposed_value,
            "observed": None,
        }
        if signal is None:
            check["state"] = "not_checked"
        elif page is None or page.html is None or page.http_status != 200:
            check["state"] = "unavailable"
            check["http_status"] = page.http_status if page else None
            check["error"] = page.error if page else "PAGE_NOT_FETCHED"
            unavailable = True
        else:
            observed = extract_page_signals(page.html, page.http_status, page.url, [])[signal]
            check["observed"] = observed
            if _normalize_text(observed) == _normalize_text(item.proposed_value):
                check["state"] = "verified"
            else:
                check["state"] = "mismatch"
                failed = True
        checks.append(check)

    # A mismatch is decisive even if another page could not be read.
    result = "failed" if failed else "unavailable" if unavailable else "verified"
    return {
        "policy_version": LIVE_VERSION,
        "result": result,
        "observed_at": now().isoformat(),
        "checks": checks,
        "limitations": [
            f"{check['field']} is applied but cannot be read back from the live page."
            for check in checks
            if check["state"] == "not_checked"
        ],
    }


async def _verify_site_change(
    session: AsyncSession,
    task: SEOImplementationTask,
    opportunity: SEOOpportunity,
    revision: SEORecommendationRevision,
) -> dict[str, object]:
    """Report the live-site proof the executor persisted; never re-derive it here."""
    publication = await session.scalar(
        select(ContentPublication)
        .where(
            ContentPublication.organization_id == task.organization_id,
            ContentPublication.publication_kind == "site_change",
            ContentPublication.seo_recommendation_revision_id == revision.id,
        )
        .order_by(ContentPublication.created_at.desc())
        .limit(1)
    )
    expected = {"change_set_fingerprint": revision.change_set_fingerprint}
    if publication is None:
        return _result(
            task,
            opportunity,
            state="pending",
            method="site_change_live_read_back",
            references=[],
            observed_at=None,
            expected=expected,
            actual={},
            limitations=["The site change has not been published yet."],
        )
    references = [f"content-publication:{publication.id}"]
    actual: dict[str, object] = {
        "publication_status": publication.status,
        "pull_request": publication.external_pull_request_id,
        "merged_commit_sha": publication.external_revision_id,
        "build_status": publication.build_status,
        "blocked_code": publication.safe_error_code,
        "live_checks": (publication.verification_evidence or {}).get("checks", []),
    }
    proof = publication.verification_evidence or {}
    observed_raw = proof.get("observed_at")
    observed_at = datetime.fromisoformat(observed_raw) if isinstance(observed_raw, str) else None
    if publication.status == "verified" and proof.get("result") == "verified":
        state, limitation = "verified", "Every changed value was read back from the live page."
    elif publication.status in {"failed", "checks_failed", "rolled_back"}:
        state, limitation = "failed", "The site change stopped before it was verified live."
    else:
        state, limitation = "pending", "The site change is still moving through the pipeline."
    return _result(
        task,
        opportunity,
        state=state,
        method="site_change_live_read_back",
        references=references,
        observed_at=observed_at,
        expected=expected,
        actual=actual,
        limitations=[limitation],
    )
