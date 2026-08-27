"""Sanctioned LILOs tools exposed to Hermes through the custom plugin."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from time import monotonic
from typing import Any, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.knowledge_service import BusinessKnowledgeService
from apps.api.app.administration.service import AdministrationService
from apps.api.app.agents.models import AgentRun
from apps.api.app.agents.safety import (
    MAX_TOOL_RESULT_BYTES,
    bound_read_result,
    has_secret_key,
    safe_argument_metadata,
)
from apps.api.app.agents.skills import SKILLS
from apps.api.app.ai.models import AIExecution
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.execution.service import ExecutionService
from apps.api.app.insights.aggregation_service import InsightsService
from apps.api.app.products.analytics.service import AnalyticsService
from apps.api.app.products.content.contracts import BriefCreate, ItemCreate, RevisionCreate
from apps.api.app.products.content.models import ContentBrief, ContentOpportunity
from apps.api.app.products.content.service import ContentService
from apps.api.app.products.gbp.models import GBPLocation, GBPProfileSnapshot
from apps.api.app.products.gbp.operations_contracts import ChangeSetPropose
from apps.api.app.products.gbp.operations_models import GBPPostRevision, GBPProviderPost
from apps.api.app.products.gbp.operations_service import GBPOperationsService
from apps.api.app.products.gbp.post_generation import GBPPostGenerationService
from apps.api.app.products.gbp.post_generation_models import GBPPostAsset
from apps.api.app.products.gbp.service import GBPService
from apps.api.app.products.reviews.service import ReviewService
from apps.api.app.products.seo.contracts import CrawlRequest, RecommendationCreate
from apps.api.app.products.seo.search_console_service import SearchConsoleService
from apps.api.app.products.seo.service import SEOService


class AgentToolDeniedError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ToolSpec:
    allowed_arguments: frozenset[str]
    mutating: bool = False


TOOL_SPECS: dict[str, ToolSpec] = {
    "read_client_business_facts": ToolSpec(frozenset()),
    "read_website_knowledge": ToolSpec(frozenset({"query"})),
    "read_gbp_state": ToolSpec(frozenset()),
    "read_gbp_recent_posts": ToolSpec(frozenset({"limit"})),
    "read_gsc_evidence": ToolSpec(frozenset({"days"})),
    "read_ga4_evidence": ToolSpec(frozenset({"days"})),
    "read_reviews_state": ToolSpec(frozenset({"limit"})),
    "read_content_inventory": ToolSpec(frozenset({"limit"})),
    "read_cross_product_summary": ToolSpec(frozenset()),
    "run_site_crawl": ToolSpec(frozenset(), mutating=True),
    "analyze_seo_opportunities": ToolSpec(frozenset({"limit"})),
    "create_seo_recommendation_proposal": ToolSpec(
        frozenset(
            {
                "opportunity_id",
                "proposed_action",
                "evidence_references",
                "expected_result_hypothesis",
                "risk",
                "effort",
            }
        ),
        mutating=True,
    ),
    "create_content_proposal": ToolSpec(
        frozenset({"content_opportunity_id", "content_type", "title", "slug"}), mutating=True
    ),
    "create_content_brief": ToolSpec(
        frozenset(
            {
                "content_item_id",
                "audience",
                "intent",
                "target_reference",
                "approved_fact_revision_ids",
                "required_claims",
                "prohibited_claims",
                "required_local_references",
                "source_evidence_references",
            }
        ),
        mutating=True,
    ),
    "generate_content_draft_proposal": ToolSpec(
        frozenset(
            {
                "content_item_id",
                "content_brief_id",
                "body",
                "frontmatter",
                "approved_fact_revision_ids",
                "source_evidence_references",
            }
        ),
        mutating=True,
    ),
    "generate_gbp_post_proposal": ToolSpec(
        frozenset({"source_evidence_references", "review_id"}),
        mutating=True,
    ),
    "create_gbp_optimization_proposal": ToolSpec(
        frozenset({"capability_key", "field_changes", "evidence_references", "risk"}),
        mutating=True,
    ),
    "draft_review_response_proposal": ToolSpec(
        frozenset({"review_id", "response_text", "approved_fact_revision_ids"}), mutating=True
    ),
    "inspect_workflow": ToolSpec(frozenset()),
    "submit_for_approval": ToolSpec(frozenset({"proposal_reference"}), mutating=True),
}


def _uuid(value: object, name: str) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise AgentToolDeniedError(f"{name} must be a UUID") from exc


# Per-item text budgets. A full page of results must fit MAX_TOOL_RESULT_BYTES
# with room left for keys, references and timestamps, so these are sized against
# the maximum page (50) rather than a typical one. Excerpts only need to support
# triage and repetition-avoidance, not reproduce the source text.
REVIEW_BODY_EXCERPT_CHARACTERS = 500
POST_TEXT_EXCERPT_CHARACTERS = 250


def _excerpt(text: str | None, limit: int = REVIEW_BODY_EXCERPT_CHARACTERS) -> str | None:
    """Collapse whitespace and bound free text destined for a tool result."""
    if text is None:
        return None
    collapsed = " ".join(str(text).split())
    return collapsed[:limit]


def _is_truncated(text: str | None, limit: int = REVIEW_BODY_EXCERPT_CHARACTERS) -> bool:
    """Whether _excerpt dropped content, so the agent knows the text is partial."""
    if text is None:
        return False
    return len(" ".join(str(text).split())) > limit


class AgentToolService:
    def __init__(self) -> None:
        self.audit = AuditEventService()
        self.administration = AdministrationService()
        self.knowledge = BusinessKnowledgeService()
        self.gbp = GBPService()
        self.gbp_operations = GBPOperationsService()
        self.gbp_post_generation = GBPPostGenerationService()
        self.search_console = SearchConsoleService()
        self.analytics = AnalyticsService()
        self.reviews = ReviewService()
        self.content = ContentService()
        self.seo = SEOService()
        self.insights = InsightsService()
        self.execution = ExecutionService()

    async def bound_run(self, session: AsyncSession, hermes_session_id: str) -> AgentRun:
        run = await session.scalar(
            select(AgentRun).where(
                AgentRun.hermes_session_id == hermes_session_id,
                AgentRun.status.in_(("queued", "running", "waiting_approval")),
            )
        )
        if run is None:
            raise AgentToolDeniedError("Hermes session is not bound to an active LILOs run")
        return run

    @staticmethod
    def _validate_arguments(tool_name: str, arguments: dict[str, Any]) -> ToolSpec:
        spec = TOOL_SPECS.get(tool_name)
        if spec is None:
            raise AgentToolDeniedError("tool is not sanctioned")
        extras = set(arguments) - spec.allowed_arguments
        if extras:
            raise AgentToolDeniedError(
                "unsupported tool arguments: " + ", ".join(sorted(str(item) for item in extras))
            )
        safe_argument_metadata(arguments)
        return spec

    @staticmethod
    def _validate_skill_tool(run: AgentRun, tool_name: str) -> None:
        skill = SKILLS.get(run.skill_key)
        if skill is None or tool_name not in skill.required_tools:
            raise AgentToolDeniedError("tool is not sanctioned for the bound agent skill")

    async def invoke(
        self,
        session: AsyncSession,
        run: AgentRun,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, object]:
        started = monotonic()
        outcome = "succeeded"
        result: dict[str, object] = {}
        result_hash: str | None = None
        result_bytes: int | None = None
        spec = TOOL_SPECS.get(tool_name)
        try:
            self._validate_skill_tool(run, tool_name)
            spec = self._validate_arguments(tool_name, arguments)
            handler = getattr(self, f"_tool_{tool_name}")
            result = await handler(session, run, arguments)
            if has_secret_key(result):
                raise AgentToolDeniedError("secret-bearing tool result rejected")
            if not spec.mutating:
                # A read whose payload scales with client data must degrade, not fail.
                # Denying it also loses its source_references, which then blocks any
                # governed proposal that needs to cite that evidence.
                result = bound_read_result(result)
            encoded = json.dumps(result, default=str, separators=(",", ":")).encode()
            result_hash = sha256(encoded).hexdigest()
            result_bytes = len(encoded)
            if len(encoded) > MAX_TOOL_RESULT_BYTES:
                raise AgentToolDeniedError("tool result exceeded bounded result policy")
            sources = result.get("source_references")
            if isinstance(sources, list):
                normalized_sources = [str(item)[:500] for item in sources[:100]]
                run.source_references = list(
                    dict.fromkeys([*run.source_references, *normalized_sources])
                )[:500]
            proposals = result.get("proposal_references")
            if isinstance(proposals, list):
                merged = list(dict.fromkeys([*run.output_references, *proposals]))[:100]
                run.output_references = merged
            await session.flush()
            return result
        except AgentToolDeniedError:
            outcome = "denied"
            raise
        except Exception:
            outcome = "failed"
            raise
        finally:
            latency_ms = round((monotonic() - started) * 1000)
            try:
                metadata = safe_argument_metadata(arguments)
            except ValueError:
                encoded_arguments = json.dumps(
                    arguments, sort_keys=True, separators=(",", ":"), default=str
                ).encode()
                metadata = {
                    "argument_names": [],
                    "argument_hash": sha256(encoded_arguments).hexdigest(),
                    "argument_bytes": len(encoded_arguments),
                }
            source_references = result.get("source_references")
            proposal_references = result.get("proposal_references")
            metadata.update(
                {
                    "agent_run_id": str(run.id),
                    "workflow_run_id": str(run.workflow_run_id),
                    "tool_name": tool_name,
                    "mutating": spec.mutating if spec else False,
                    "latency_ms": latency_ms,
                    "outcome": outcome,
                    "result_hash": result_hash,
                    "result_bytes": result_bytes,
                    "source_references": [str(item)[:200] for item in source_references[:50]]
                    if isinstance(source_references, list)
                    else [],
                    "proposal_references": [str(item)[:200] for item in proposal_references[:20]]
                    if isinstance(proposal_references, list)
                    else [],
                }
            )
            await self.audit.record(
                session,
                AuditEventCreate(
                    event_type="agent.tool.invoked",
                    action="agent.tool.invoke",
                    result=(
                        AuditResult.SUCCEEDED
                        if outcome == "succeeded"
                        else AuditResult.DENIED
                        if outcome == "denied"
                        else AuditResult.FAILED
                    ),
                    actor_type=AuditActorType.SERVICE,
                    actor_display_reference="hermes-agent",
                    organization_id=run.organization_id,
                    location_id=run.location_id,
                    product_key=run.skill_key.split(".")[0],
                    resource_type="agent_run",
                    resource_id=run.id,
                    correlation_id=run.correlation_id,
                    workflow_execution_id=run.workflow_run_id,
                    summary=f"Hermes sanctioned tool {tool_name} {outcome}.",
                    metadata=cast(dict[str, JsonValue], metadata),
                ),
            )

    async def _governed_fact_ids(self, session: AsyncSession, run: AgentRun) -> set[UUID]:
        facts = await self.administration.effective_facts(session, run.organization_id)
        return {
            item.revision_id
            for item in facts
            if item.location_id is None or item.location_id == run.location_id
        }

    @staticmethod
    def _observed_source_references(run: AgentRun, values: object, *, label: str) -> list[str]:
        if not isinstance(values, list):
            raise AgentToolDeniedError(f"{label} must be a list")
        requested = list(dict.fromkeys(str(value)[:500] for value in values))[:100]
        observed = {str(value) for value in run.source_references}
        if not requested or not set(requested) <= observed:
            raise AgentToolDeniedError(
                f"{label} must be non-empty references observed by this bound agent run"
            )
        return requested

    async def _gbp_location(self, session: AsyncSession, run: AgentRun) -> GBPLocation:
        if run.location_id is None:
            raise AgentToolDeniedError("this tool requires a location-scoped agent run")
        matches = [
            item
            for item in await self.gbp.list_locations(
                session, run.organization_id, mapping_status="confirmed"
            )
            if item.location_id == run.location_id
        ]
        if len(matches) != 1:
            raise AgentToolDeniedError("exactly one confirmed GBP mapping is required")
        return matches[0]

    async def _tool_read_client_business_facts(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        del arguments
        facts = await self.administration.effective_facts(session, run.organization_id)
        scoped = [
            item
            for item in facts
            if item.location_id is None or item.location_id == run.location_id
        ]
        return {
            "data": [
                {
                    "fact_key": item.fact_key,
                    "value": item.value,
                    "authority": item.authority.value,
                    "scope": "location" if item.location_id else "organization",
                    "revision": item.revision,
                    "source": item.source,
                }
                for item in scoped[:100]
            ],
            "source_references": [f"business-fact:{item.revision_id}" for item in scoped[:100]],
            "data_quality": "current_approved_facts",
        }

    async def _tool_read_website_knowledge(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        query = str(arguments.get("query") or "current website and business context")[:300]
        result = await self.knowledge.retrieve_for_content(
            session,
            organization_id=run.organization_id,
            location_id=run.location_id,
            content_title=query,
            audience="current and prospective clients",
            intent="evidence gathering",
            content_type="agent_analysis",
            limit=10,
        )
        # Website page documents carry full body text, which for a real client site can
        # exceed the bounded-result policy on its own. Project each page down to what
        # the agent needs to choose a destination, keeping an excerpt not the whole body.
        return {
            "data": {
                "identity": result["identity"],
                "gbp_knowledge": result["gbp_knowledge"],
                "website_knowledge": [
                    self._compact_website_page(page) for page in result["website_knowledge"]
                ],
            },
            "source_references": [
                f"business-knowledge:{item}" for item in result["source_document_ids"]
            ],
        }

    @staticmethod
    def _compact_website_page(page: object) -> dict[str, object]:
        """Reduce a website knowledge document to destination-selection essentials."""
        if not isinstance(page, dict):
            return {}
        compact: dict[str, object] = {}
        for key in ("url", "title", "h1", "page_type", "primary_topic"):
            value = page.get(key)
            if value is not None and str(value).strip():
                compact[key] = str(value)[:300]
        body = str(page.get("body_text") or "").strip()
        if body:
            compact["body_excerpt"] = " ".join(body.split())[:600]
        return compact

    async def _tool_read_gbp_state(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        del arguments
        location = await self._gbp_location(session, run)
        snapshot = await session.scalar(
            select(GBPProfileSnapshot)
            .where(
                GBPProfileSnapshot.organization_id == run.organization_id,
                GBPProfileSnapshot.gbp_location_id == location.id,
            )
            .order_by(GBPProfileSnapshot.observed_at.desc())
            .limit(1)
        )
        return {
            "data": {
                "mapping_status": location.mapping_status,
                "write_enabled": location.write_enabled,
                "last_synced_at": location.last_synced_at.isoformat()
                if location.last_synced_at
                else None,
                "profile": snapshot.normalized_profile if snapshot else None,
                "completeness": snapshot.completeness if snapshot else "missing",
                "observed_at": snapshot.observed_at.isoformat() if snapshot else None,
            },
            "source_references": [f"gbp-profile-snapshot:{snapshot.id}"] if snapshot else [],
        }

    async def _tool_read_gbp_recent_posts(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        location = await self._gbp_location(session, run)
        limit = min(max(int(arguments.get("limit") or 20), 1), 50)
        provider = list(
            await session.scalars(
                select(GBPProviderPost)
                .where(
                    GBPProviderPost.organization_id == run.organization_id,
                    GBPProviderPost.gbp_location_id == location.id,
                    GBPProviderPost.status == "present",
                )
                .order_by(GBPProviderPost.observed_at.desc())
                .limit(limit)
            )
        )
        drafts = (
            await self.gbp_operations.list_post_revision_read_models(
                session, run.organization_id, location.id
            )
        )[:limit]
        return {
            "data": {
                # This read exists so the agent can avoid repeating itself. Post
                # summaries and draft bodies each run to ~1.5k characters, and fifty
                # of both exceeds the bounded-result policy, so they are excerpted:
                # recognising a covered topic does not need the full text.
                "provider_posts": [
                    {
                        "post_type": item.post_type,
                        "summary": _excerpt(item.summary, POST_TEXT_EXCERPT_CHARACTERS),
                        "state": item.state,
                        "observed_at": item.observed_at.isoformat(),
                    }
                    for item in provider
                ],
                "lilos_drafts": [
                    {
                        "reference": f"gbp-post-revision:{item.revision.id}",
                        "post_type": item.revision.post_type,
                        "content": _excerpt(item.revision.content, POST_TEXT_EXCERPT_CHARACTERS),
                        "status": item.revision.status,
                        "created_at": item.revision.created_at.isoformat(),
                    }
                    for item in drafts
                ],
            },
            "source_references": [f"gbp-provider-post:{item.id}" for item in provider]
            + [f"gbp-post-revision:{item.revision.id}" for item in drafts],
        }

    async def _tool_read_gsc_evidence(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        days = int(arguments.get("days") or 28)
        websites = await self.seo.list_websites(session, run.organization_id)
        scoped_websites = [
            item
            for item in websites
            if item.location_id is None or item.location_id == run.location_id
        ]
        if not scoped_websites:
            return {
                "data": {"connected": False, "data_quality": "website_missing"},
                "source_references": [],
            }
        website = next(
            (item for item in scoped_websites if item.location_id == run.location_id),
            scoped_websites[0],
        )
        report = await self.search_console.performance_report(
            session, run.organization_id, website.id, days=days
        )
        properties = report.get("properties")
        refs = (
            [
                f"gsc-property:{item.get('id')}"
                for item in properties
                if isinstance(item, dict) and item.get("id")
            ]
            if isinstance(properties, list)
            else []
        )
        return {"data": report, "source_references": refs}

    async def _tool_read_ga4_evidence(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        days = int(arguments.get("days") or 28)
        report = await self.analytics.performance_report(
            session, run.organization_id, days=days, location_id=run.location_id
        )
        properties = report.get("properties")
        refs = (
            [
                f"ga4-property:{item.get('id')}"
                for item in properties
                if isinstance(item, dict) and item.get("id")
            ]
            if isinstance(properties, list)
            else []
        )
        return {"data": report, "source_references": refs}

    async def _tool_read_reviews_state(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        if run.location_id is None:
            raise AgentToolDeniedError("reviews require a location-scoped agent run")
        limit = min(max(int(arguments.get("limit") or 20), 1), 50)
        rows, has_more = await self.reviews.list_reviews(
            session, run.organization_id, run.location_id, limit=limit
        )
        items: list[dict[str, object]] = []
        refs: list[str] = []
        for review in rows:
            _review, revisions = await self.reviews.get(session, run.organization_id, review.id)
            latest = revisions[0] if revisions else None
            items.append(
                {
                    "reference": f"review:{review.id}",
                    "rating": float(review.rating) if review.rating is not None else None,
                    "status": review.status,
                    "sentiment": review.sentiment,
                    "risk_level": review.risk_level,
                    "topics": review.topics,
                    # Google review bodies run to thousands of characters. Fifty of
                    # them at full length exceeds the bounded-result policy on its
                    # own, which used to deny this read outright and blocked the
                    # Reviews agent the same way full page bodies blocked the GBP
                    # agent. An excerpt is enough to triage and draft a response;
                    # the full text stays reachable through the review reference.
                    "body_excerpt": _excerpt(latest.body if latest else None),
                    "body_truncated": _is_truncated(latest.body if latest else None),
                    "review_created_at": review.review_created_at.isoformat(),
                }
            )
            refs.append(f"review-revision:{latest.id}" if latest else f"review:{review.id}")
        return {
            "data": {
                "summary": await self.reviews.summary(
                    session, run.organization_id, run.location_id
                ),
                "reviews": items,
                "has_more": has_more,
            },
            "source_references": refs,
        }

    async def _tool_read_content_inventory(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        limit = min(max(int(arguments.get("limit") or 30), 1), 50)
        items, _ = await self.content.list_items(session, run.organization_id, limit=limit)
        opportunities, _ = await self.content.list_opportunities(
            session, run.organization_id, limit=limit
        )
        scoped_items = [
            item
            for item in items
            if item.location_id is None or item.location_id == run.location_id
        ]
        scoped_opportunities = [
            item
            for item in opportunities
            if item.location_id is None or item.location_id == run.location_id
        ]
        latest_briefs: dict[UUID, ContentBrief] = {}
        for item in scoped_items:
            briefs = await self.content.list_briefs(session, run.organization_id, item.id)
            if briefs:
                latest_briefs[item.id] = briefs[0]
        return {
            "data": {
                "items": [
                    {
                        "reference": f"content-item:{item.id}",
                        "title": item.title,
                        "content_type": item.content_type,
                        "status": item.status,
                        "location_scoped": item.location_id is not None,
                        "latest_brief": (
                            {
                                "reference": f"content-brief:{latest_briefs[item.id].id}",
                                "status": latest_briefs[item.id].status,
                                "audience": latest_briefs[item.id].audience,
                                "intent": latest_briefs[item.id].intent,
                                "approved_fact_revision_ids": latest_briefs[
                                    item.id
                                ].approved_fact_revision_ids,
                                "source_evidence_references": latest_briefs[
                                    item.id
                                ].source_evidence_references,
                                "prohibited_claims": latest_briefs[item.id].prohibited_claims,
                            }
                            if item.id in latest_briefs
                            else None
                        ),
                    }
                    for item in scoped_items
                ],
                "opportunities": [
                    {
                        "reference": f"content-opportunity:{item.id}",
                        "target_reference": item.target_reference,
                        "opportunity_type": item.opportunity_type,
                        "status": item.status,
                        "priority_score": item.priority_score,
                        "source_reference": item.source_reference,
                    }
                    for item in scoped_opportunities
                ],
            },
            "source_references": list(
                dict.fromkeys(
                    [f"content-item:{item.id}" for item in scoped_items]
                    + [f"content-brief:{item.id}" for item in latest_briefs.values()]
                    + [f"content-opportunity:{item.id}" for item in scoped_opportunities]
                    + [
                        str(reference)[:500]
                        for brief in latest_briefs.values()
                        for reference in brief.source_evidence_references
                    ]
                    + [
                        f"business-fact:{fact_id}"
                        for brief in latest_briefs.values()
                        for fact_id in brief.approved_fact_revision_ids
                    ]
                )
            )[:500],
        }

    async def _tool_read_cross_product_summary(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        del arguments
        return {
            "data": await self.insights.summary(
                session, run.organization_id, location_id=run.location_id
            ),
            "source_references": [f"insights-summary:{run.id}"],
        }

    async def _tool_run_site_crawl(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        del arguments
        # The crawl handler requires input_document["crawl_run_id"]. Starting the
        # workflow with an empty document made every agent-initiated crawl fail
        # permanently with MISSING_CRAWL_RUN_ID. SEOService.enqueue_crawl is the
        # supported path: it creates the crawl run, writes the full input document,
        # and enqueues the job itself, so the workflow must NOT be pre-enqueued.
        websites = await self.seo.list_websites(session, run.organization_id)
        if not websites:
            raise AgentToolDeniedError(
                "a confirmed website must be registered before a crawl can be requested"
            )
        website = websites[0]
        workflow = await self.execution.start_named(
            session,
            run.organization_id,
            "seo.crawl_or_analysis",
            f"agent-crawl-{run.id}",
            location_id=run.location_id,
            input_document={},
            correlation_id=run.correlation_id,
            actor_id=None,
            enqueue_job=False,
        )
        crawl_run = await self.seo.enqueue_crawl(
            session,
            run.organization_id,
            website.id,
            CrawlRequest(
                workflow_run_id=workflow.id,
                idempotency_key=f"agent-crawl-{run.id}",
            ),
            actor_id=None,
            correlation_id=run.correlation_id,
        )
        ref = f"workflow-run:{workflow.id}"
        return {
            "data": {
                "status": crawl_run.status,
                "crawl_run_reference": f"seo-crawl-run:{crawl_run.id}",
                "website_reference": f"seo-website:{website.id}",
            },
            "source_references": [ref, f"seo-crawl-run:{crawl_run.id}"],
            "proposal_references": [ref],
        }

    async def _tool_analyze_seo_opportunities(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        limit = min(max(int(arguments.get("limit") or 30), 1), 50)
        rows, has_more = await self.seo.list_opportunities(
            session, run.organization_id, limit=limit
        )
        scoped = [
            item for item in rows if item.location_id is None or item.location_id == run.location_id
        ]
        return {
            "data": {
                "opportunities": [
                    {
                        "reference": f"seo-opportunity:{item.id}",
                        "opportunity_type": item.opportunity_type,
                        "status": item.status,
                        "priority_score": item.priority_score,
                        "score_explanation": item.score_explanation,
                        "evidence": item.evidence,
                        "source_versions": item.source_versions,
                    }
                    for item in scoped
                ],
                "has_more": has_more,
            },
            "source_references": [f"seo-opportunity:{item.id}" for item in scoped],
        }

    async def _tool_create_seo_recommendation_proposal(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        opportunity_id = _uuid(arguments.get("opportunity_id"), "opportunity_id")
        opportunity = await self.seo.get_opportunity(session, run.organization_id, opportunity_id)
        if opportunity.location_id is not None and opportunity.location_id != run.location_id:
            raise AgentToolDeniedError("SEO opportunity is outside the bound location")
        source_ref = f"seo-opportunity:{opportunity.id}"
        requested_refs = self._observed_source_references(
            run, arguments.get("evidence_references"), label="SEO evidence"
        )
        if source_ref not in requested_refs:
            raise AgentToolDeniedError(
                "SEO recommendation must reference its observed deterministic opportunity"
            )
        revision = await self.seo.create_recommendation(
            session,
            run.organization_id,
            opportunity.id,
            RecommendationCreate(
                proposed_action=str(arguments.get("proposed_action") or "")[:10_000],
                evidence_references=requested_refs,
                expected_result_hypothesis=str(arguments.get("expected_result_hypothesis") or "")[
                    :2_000
                ],
                risk=cast(Any, str(arguments.get("risk") or "medium")),
                effort=cast(Any, str(arguments.get("effort") or "medium")),
            ),
            actor_id=None,
            correlation_id=run.correlation_id,
        )
        ref = f"seo-recommendation:{revision.id}"
        return {
            "data": {"status": revision.status},
            "source_references": [source_ref],
            "proposal_references": [ref],
        }

    async def _tool_create_content_proposal(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        opportunity_id = _uuid(arguments.get("content_opportunity_id"), "content_opportunity_id")
        opportunity = await session.scalar(
            select(ContentOpportunity).where(
                ContentOpportunity.organization_id == run.organization_id,
                ContentOpportunity.id == opportunity_id,
                ContentOpportunity.status == "accepted",
            )
        )
        if opportunity is None or (
            opportunity.location_id is not None and opportunity.location_id != run.location_id
        ):
            raise AgentToolDeniedError("accepted Content opportunity is outside the bound location")
        source_ref = f"content-opportunity:{opportunity_id}"
        if source_ref not in {str(value) for value in run.source_references}:
            raise AgentToolDeniedError(
                "Content opportunity must be observed by this bound agent run"
            )
        item = await self.content.create_item(
            session,
            run.organization_id,
            ItemCreate(
                opportunity_id=opportunity_id,
                location_id=run.location_id,
                content_type=str(arguments.get("content_type") or "page")[:32],
                title=str(arguments.get("title") or "")[:300],
                slug=str(arguments.get("slug") or "")[:200],
            ),
            actor_id=None,
            correlation_id=run.correlation_id,
        )
        ref = f"content-item:{item.id}"
        return {
            "data": {"status": item.status},
            "source_references": [source_ref],
            "proposal_references": [ref],
        }

    async def _tool_create_content_brief(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        item_id = _uuid(arguments.get("content_item_id"), "content_item_id")
        item = await self.content.get_item(session, run.organization_id, item_id)
        if item.location_id is not None and item.location_id != run.location_id:
            raise AgentToolDeniedError("Content item is outside the bound location")
        requested = [
            _uuid(value, "approved_fact_revision_ids")
            for value in arguments.get("approved_fact_revision_ids", [])
        ]
        allowed = await self._governed_fact_ids(session, run)
        if not requested or not set(requested) <= allowed:
            raise AgentToolDeniedError(
                "brief facts must be current approved facts in the bound scope"
            )
        refs = self._observed_source_references(
            run,
            arguments.get("source_evidence_references"),
            label="Content brief evidence",
        )
        brief = await self.content.create_brief(
            session,
            run.organization_id,
            item_id,
            BriefCreate(
                audience=str(arguments.get("audience") or "")[:500],
                intent=str(arguments.get("intent") or "")[:500],
                target_reference=str(arguments.get("target_reference") or "")[:500],
                approved_fact_revision_ids=requested,
                required_claims=[
                    str(value)[:500] for value in arguments.get("required_claims", [])
                ][:100],
                prohibited_claims=[
                    str(value)[:500] for value in arguments.get("prohibited_claims", [])
                ][:100],
                required_local_references=[
                    str(value)[:500] for value in arguments.get("required_local_references", [])
                ][:100],
                source_evidence_references=refs,
                validation_requirements={"agent_run_id": str(run.id), "grounded": True},
            ),
            actor_id=None,
            correlation_id=run.correlation_id,
        )
        ref = f"content-brief:{brief.id}"
        return {
            "data": {"status": brief.status},
            "source_references": refs + [f"business-fact:{item}" for item in requested],
            "proposal_references": [ref],
        }

    async def _tool_generate_content_draft_proposal(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        item_id = _uuid(arguments.get("content_item_id"), "content_item_id")
        brief_id = _uuid(arguments.get("content_brief_id"), "content_brief_id")
        brief = await session.scalar(
            select(ContentBrief).where(
                ContentBrief.organization_id == run.organization_id,
                ContentBrief.content_item_id == item_id,
                ContentBrief.id == brief_id,
                ContentBrief.status == "ready",
            )
        )
        if brief is None:
            raise AgentToolDeniedError("ready Content brief is outside the bound run")
        item = await self.content.get_item(session, run.organization_id, item_id)
        if item.location_id is not None and item.location_id != run.location_id:
            raise AgentToolDeniedError("Content item is outside the bound location")
        requested_facts = [
            _uuid(value, "approved_fact_revision_ids")
            for value in arguments.get("approved_fact_revision_ids", [])
        ]
        brief_facts = {_uuid(value, "brief fact") for value in brief.approved_fact_revision_ids}
        current_facts = await self._governed_fact_ids(session, run)
        if set(requested_facts) != brief_facts or not brief_facts <= current_facts:
            raise AgentToolDeniedError(
                "draft facts must exactly match the ready brief and current approved scope"
            )
        brief_sources = {str(value)[:500] for value in brief.source_evidence_references}
        requested_sources = set(
            self._observed_source_references(
                run,
                arguments.get("source_evidence_references"),
                label="Content draft evidence",
            )
        )
        if not brief_sources or not requested_sources or not requested_sources <= brief_sources:
            raise AgentToolDeniedError(
                "draft sources must be non-empty references from the ready brief"
            )
        frontmatter = arguments.get("frontmatter")
        revision = await self.content.create_revision(
            session,
            run.organization_id,
            item.id,
            RevisionCreate(
                body=str(arguments.get("body") or "")[:200_000],
                frontmatter=frontmatter if isinstance(frontmatter, dict) else {},
                created_by_type="ai",
                approved_fact_revision_ids=requested_facts,
                ai_execution_id=run.ai_execution_id,
                prohibited_claims=[str(value) for value in brief.prohibited_claims],
            ),
            run.organization_id,
            correlation_id=run.correlation_id,
        )
        if run.ai_execution_id is not None:
            execution = await session.get(AIExecution, run.ai_execution_id)
            if execution is not None:
                execution.input_references = list(
                    dict.fromkeys(
                        [
                            *execution.input_references,
                            f"content-brief:{brief.id}",
                            *sorted(requested_sources),
                        ]
                    )
                )[:200]
                execution.approved_fact_revision_ids = [str(value) for value in requested_facts]
        ref = f"content-revision:{revision.id}"
        return {
            "data": {"status": revision.status, "validation": revision.validation_document},
            "source_references": [f"content-brief:{brief.id}"]
            + sorted(requested_sources)
            + [f"business-fact:{value}" for value in requested_facts],
            "proposal_references": [ref],
        }

    async def _tool_generate_gbp_post_proposal(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        """Ask LILOs to generate the post. The agent supplies evidence, not copy.

        There is one GBP post generator: GBPPostGenerationService. It grounds the
        post in a specific customer review (or approved service knowledge when no
        unused review remains), routes drafting through the AI Gateway against a
        versioned task with a cost ceiling, rotates service topics to avoid
        repetition, and binds the required CTA and client-scoped Drive image inside
        one transaction. Previously this tool accepted `content` written by the
        agent's own model, which bypassed all of that and produced posts under
        different rules than the scheduled workflow used.

        The agent still proves it inspected state: source_evidence_references must
        be references this bound run actually observed.
        """
        if run.location_id is None:
            raise AgentToolDeniedError("GBP post proposals require a location-scoped run")
        # Validates that the agent read state before proposing, and records the
        # evidence on the run.
        refs = self._observed_source_references(
            run, arguments.get("source_evidence_references"), label="GBP post evidence"
        )
        review_id = arguments.get("review_id")
        source_review_id = _uuid(review_id, "review_id") if review_id is not None else None

        revision, execution, asset = await self.gbp_post_generation.generate(
            session,
            Settings(),
            run.organization_id,
            run.location_id,
            workflow_run_id=run.workflow_run_id,
            correlation_id=run.correlation_id,
            source_review_id=source_review_id,
        )

        output = execution.output_document or {}
        ref = f"gbp-post-revision:{revision.id}"
        return {
            "data": {
                "status": revision.status,
                "source_type": output.get("source_type"),
                "source_review_reference": (
                    f"review:{output['source_review_id']}"
                    if output.get("source_review_id")
                    else None
                ),
                "service_topic": output.get("source_service_topic"),
                "grounding_sources": output.get("grounding_sources"),
                "target_url": output.get("target_url"),
                "image_reference": asset.source_reference,
            },
            "source_references": refs,
            "proposal_references": [ref],
        }

    async def _tool_create_gbp_optimization_proposal(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        location = await self._gbp_location(session, run)
        refs = self._observed_source_references(
            run, arguments.get("evidence_references"), label="GBP optimization evidence"
        )[:50]
        item = await self.gbp_operations.propose_change_set(
            session,
            run.organization_id,
            location.id,
            ChangeSetPropose(
                capability_key=str(arguments.get("capability_key") or "")[:64],
                field_changes=list(arguments.get("field_changes") or [])[:100],
                evidence={"source_references": refs, "agent_run_id": str(run.id)},
                risk=cast(Any, str(arguments.get("risk") or "low")),
                idempotency_key=f"agent-gbp-optimization-{run.id}",
            ),
            f"agent-gbp-optimization-{run.id}",
            actor_id=None,
            correlation_id=run.correlation_id,
        )
        ref = f"gbp-change-set:{item.id}"
        return {
            "data": {"status": item.status},
            "source_references": refs,
            "proposal_references": [ref],
        }

    async def _tool_draft_review_response_proposal(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        if run.location_id is None:
            raise AgentToolDeniedError("reviews require a location-scoped agent run")
        review_id = _uuid(arguments.get("review_id"), "review_id")
        review, revisions = await self.reviews.get(session, run.organization_id, review_id)
        if review.location_id != run.location_id:
            raise AgentToolDeniedError("review is outside the bound location")
        if review.status == "escalated" or review.risk_level == "high":
            raise AgentToolDeniedError("deterministic review risk guard blocks agent drafting")
        if not revisions:
            raise AgentToolDeniedError("review revision is missing")
        requested = [
            _uuid(value, "approved_fact_revision_ids")
            for value in arguments.get("approved_fact_revision_ids", [])
        ]
        allowed = await self._governed_fact_ids(session, run)
        if not requested or not set(requested) <= allowed:
            raise AgentToolDeniedError("review response facts are outside the approved bound scope")
        required_sources = {f"review-revision:{revisions[0].id}"} | {
            f"business-fact:{item}" for item in requested
        }
        if not required_sources <= {str(value) for value in run.source_references}:
            raise AgentToolDeniedError(
                "review response evidence must be observed by this bound agent run"
            )
        response = await self.reviews.draft(
            session,
            organization_id=run.organization_id,
            location_id=run.location_id,
            review_id=review.id,
            review_revision_id=revisions[0].id,
            text=str(arguments.get("response_text") or "")[:5_000],
            generated_by_type="ai",
            fact_ids=requested,
            actor_id=None,
            correlation_id=run.correlation_id,
            ai_execution_id=run.ai_execution_id,
        )
        ref = f"review-response-revision:{response.id}"
        return {
            "data": {"status": response.status},
            "source_references": [f"review-revision:{revisions[0].id}"]
            + [f"business-fact:{item}" for item in requested],
            "proposal_references": [ref],
        }

    async def _tool_inspect_workflow(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        del arguments
        detail = await self.execution.get_run(session, run.organization_id, run.workflow_run_id)
        return {"data": detail or {}, "source_references": [f"workflow-run:{run.workflow_run_id}"]}

    async def _tool_submit_for_approval(
        self, session: AsyncSession, run: AgentRun, arguments: dict[str, Any]
    ) -> dict[str, object]:
        ref = str(arguments.get("proposal_reference") or "")[:200]
        if ref not in {str(item) for item in run.output_references}:
            raise AgentToolDeniedError("proposal was not created by this bound agent run")
        if ref.startswith("gbp-post-revision:"):
            revision_id = _uuid(ref.removeprefix("gbp-post-revision:"), "GBP post revision")
            revision = await session.scalar(
                select(GBPPostRevision).where(
                    GBPPostRevision.organization_id == run.organization_id,
                    GBPPostRevision.id == revision_id,
                )
            )
            if revision is None:
                raise AgentToolDeniedError("GBP post proposal is outside the bound organization")
            if not revision.call_to_action or not revision.call_to_action.get("url"):
                raise AgentToolDeniedError("GBP post proposal is missing its client-owned CTA")
            if Settings().google_drive_service_account_json:
                asset = await session.scalar(
                    select(GBPPostAsset).where(
                        GBPPostAsset.organization_id == run.organization_id,
                        GBPPostAsset.post_revision_id == revision.id,
                        GBPPostAsset.status == "selected",
                    )
                )
                if asset is None:
                    raise AgentToolDeniedError(
                        "GBP post proposal is missing its client-scoped Drive image"
                    )
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type="agent.proposal.submitted",
                action="agent.proposal.submit",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.WORKFLOW,
                organization_id=run.organization_id,
                location_id=run.location_id,
                product_key=run.skill_key.split(".")[0],
                resource_type="agent_run",
                resource_id=run.id,
                correlation_id=run.correlation_id,
                workflow_execution_id=run.workflow_run_id,
                summary="Agent-created proposal submitted to the canonical LILOs approval queue.",
                metadata={"proposal_reference": ref},
            ),
        )
        return {
            "data": {"status": "awaiting_lilos_approval"},
            "source_references": [ref],
            "proposal_references": [ref],
        }
