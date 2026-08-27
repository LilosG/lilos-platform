"""AI-first GBP post generation grounded in customer reviews and client knowledge."""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, String, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.knowledge_service import BusinessKnowledgeService
from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.ai.factory import build_ai_gateway
from apps.api.app.ai.gateway import AIGatewayRequest
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.config import Settings
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.service import GovernedFact, resolve_governed_facts
from apps.api.app.products.gbp.models import GBPLocation, GBPProfileSnapshot
from apps.api.app.products.gbp.operations_contracts import PostRevisionCreate
from apps.api.app.products.gbp.operations_models import GBPPostRevision, GBPProviderPost
from apps.api.app.products.gbp.operations_service import GBPOperationsService
from apps.api.app.products.gbp.post_generation_models import GBPPostAsset
from apps.api.app.products.gbp.proposal_enrichment import (
    GBPPostProposalEnrichmentService,
    GBPProposalEnrichmentError,
)
from apps.api.app.products.reviews.models import Review, ReviewRevision

TASK_KEY = "gbp.generate_post"
MAXIMUM_LATENCY_MS = 120_000


class GBPPostGenerationService:
    def __init__(self) -> None:
        self.ai_gateway = build_ai_gateway()
        self.knowledge = BusinessKnowledgeService()
        self.operations = GBPOperationsService()
        self.enrichment = GBPPostProposalEnrichmentService()

    async def generate(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        location_id: UUID,
        *,
        workflow_run_id: UUID,
        correlation_id: str,
        source_review_id: UUID | None = None,
    ) -> tuple[GBPPostRevision, AIExecution, GBPPostAsset]:
        """Create an approval-ready review-driven post with a relevant CTA and Drive image."""
        gbp_location = await self._resolve_location(session, organization_id, location_id)
        organization = await session.get(Organization, organization_id)
        if organization is None:
            raise LookupError("organization not found")

        # Match on the key this method writes, not on workflow_run_id alone. A run
        # can carry more than one execution -- an agent run records its own before
        # calling in here -- and matching the wrong one makes this treat a foreign
        # execution as a previous attempt at this post.
        generation_idempotency_key = f"gbp-post-{workflow_run_id}"
        existing_execution = await session.scalar(
            select(AIExecution).where(
                AIExecution.organization_id == organization_id,
                AIExecution.idempotency_key == generation_idempotency_key,
            )
        )
        if existing_execution is not None:
            output_document = existing_execution.output_document or {}
            existing_source_review_id = str(output_document.get("source_review_id") or "").strip()
            if source_review_id is not None and existing_source_review_id != str(source_review_id):
                raise GBPProposalEnrichmentError(
                    "GBP_REVIEW_SOURCE_MISMATCH",
                    "The existing generated post is bound to a different customer review.",
                )
            revision_id = output_document.get("post_revision_id")
            if revision_id:
                revision = await session.get(GBPPostRevision, UUID(str(revision_id)))
                if revision is not None and revision.organization_id == organization_id:
                    existing_asset = await session.scalar(
                        select(GBPPostAsset).where(
                            GBPPostAsset.organization_id == organization_id,
                            GBPPostAsset.post_revision_id == revision.id,
                            GBPPostAsset.status == "selected",
                        )
                    )
                    requirements = revision.publication_requirements or {}
                    metadata = existing_asset.metadata_document if existing_asset else {}
                    existing_source_type = str(requirements.get("source_type") or "")
                    if existing_source_type == "google_review":
                        source_bound = bool(str(requirements.get("source_review_id") or "").strip())
                    elif existing_source_type == "service_knowledge":
                        source_bound = bool(
                            str(requirements.get("source_service_topic") or "").strip()
                        )
                    else:
                        source_bound = False
                    if (
                        requirements.get("version") == 1
                        and requirements.get("cta_required") is True
                        and requirements.get("media_required") is True
                        and source_bound
                        and isinstance(revision.call_to_action, dict)
                        and existing_asset is not None
                        and existing_asset.source_type == "google_drive"
                        and bool(str((metadata or {}).get("file_id") or "").strip())
                    ):
                        return revision, existing_execution, existing_asset
                    raise GBPProposalEnrichmentError(
                        "GBP_POST_DELIVERY_BINDING_MISSING",
                        (
                            "The existing generated post is missing its required source, CTA, "
                            "or image binding."
                        ),
                    )

        # An explicit review_id must resolve or fail closed. Automated runs prefer an
        # unused review and fall back to approved service knowledge when none remains,
        # so post cadence is not capped by a location's review count.
        source_review: Review | None = None
        source_revision: ReviewRevision | None = None
        if source_review_id is not None:
            source_review, source_revision = await self._resolve_source_review(
                session,
                organization_id,
                location_id,
                source_review_id=source_review_id,
            )
        else:
            resolved = await self._resolve_optional_source_review(
                session, organization_id, location_id
            )
            if resolved is not None:
                source_review, source_revision = resolved
        review_text = self._review_text(source_revision) if source_revision is not None else ""
        source_type = "google_review" if source_review is not None else "service_knowledge"

        fact_rows = list(
            await session.scalars(
                select(BusinessFactRevision)
                .where(
                    BusinessFactRevision.organization_id == organization_id,
                    BusinessFactRevision.status.in_(("approved", "active")),
                    or_(
                        BusinessFactRevision.location_id.is_(None),
                        BusinessFactRevision.location_id == location_id,
                    ),
                )
                .order_by(BusinessFactRevision.approved_at.desc().nullslast())
                .limit(100)
            )
        )
        fact_ids = [row.id for row in fact_rows]
        # Approved business facts are the strongest grounding source but not the only
        # one. A newly onboarded client has an authoritative GBP profile and website
        # before anyone curates facts by hand, so absence of facts must not block
        # posting. The grounding requirement is enforced after knowledge retrieval
        # against the union of available client-owned sources.
        governed_facts = (
            await resolve_governed_facts(
                session,
                organization_id,
                fact_ids,
                location_id=location_id,
            )
            if fact_ids
            else []
        )

        snapshot = await session.scalar(
            select(GBPProfileSnapshot)
            .where(
                GBPProfileSnapshot.organization_id == organization_id,
                GBPProfileSnapshot.gbp_location_id == gbp_location.id,
            )
            .order_by(GBPProfileSnapshot.observed_at.desc())
            .limit(1)
        )
        profile = snapshot.normalized_profile if snapshot else {}
        topic = self._topic_hint(governed_facts, profile)
        if source_review is not None:
            knowledge_title = f"Customer review: {review_text[:220]}"
            knowledge_intent = (
                "turn this customer review into a useful Google Business Profile post and link "
                "to the client-owned page most relevant to the experience described"
            )
        else:
            knowledge_title = f"Service update: {topic}"
            knowledge_intent = (
                "write a useful Google Business Profile post about this service using the "
                "client's approved facts, Google Business Profile, and website, and link to "
                "the client-owned page most relevant to it"
            )
        knowledge = await self.knowledge.retrieve_for_content(
            session,
            organization_id=organization_id,
            location_id=location_id,
            content_title=knowledge_title,
            audience="local prospective customers",
            intent=knowledge_intent,
            content_type="gbp_post",
        )
        # Fail closed only when there is genuinely nothing client-owned to ground on.
        # GBP profile and website knowledge are ingested automatically from the
        # client's own profile and site, so a new client is groundable on day one.
        grounding_sources = [
            name
            for name, present in (
                ("business_facts", bool(governed_facts)),
                ("gbp_profile", bool(profile)),
                ("gbp_knowledge", bool(knowledge.get("gbp"))),
                ("website", bool(knowledge.get("website_knowledge"))),
                ("identity", bool(knowledge.get("identity"))),
            )
            if present
        ]
        if not grounding_sources:
            raise ValueError(
                "no approved business facts, GBP profile, or website knowledge available "
                "for GBP AI generation"
            )

        recent_provider = list(
            await session.scalars(
                select(GBPProviderPost)
                .where(
                    GBPProviderPost.organization_id == organization_id,
                    GBPProviderPost.gbp_location_id == gbp_location.id,
                    GBPProviderPost.status == "present",
                )
                .order_by(GBPProviderPost.observed_at.desc())
                .limit(15)
            )
        )
        recent_drafts = list(
            await session.scalars(
                select(GBPPostRevision)
                .where(
                    GBPPostRevision.organization_id == organization_id,
                    GBPPostRevision.gbp_location_id == gbp_location.id,
                )
                .order_by(GBPPostRevision.created_at.desc())
                .limit(10)
            )
        )
        recent_text = [
            str(item.summary).strip()
            for item in recent_provider
            if item.summary and str(item.summary).strip()
        ] + [item.content.strip() for item in recent_drafts if item.content.strip()]

        if source_review is not None:
            relevance_text = f"{review_text} {topic}".strip()
            target_url = self._select_target_url(profile, knowledge, relevance_text)
        else:
            # Without a review the topic is ours to choose. Try candidates in
            # least-recently-used order so consecutive service posts vary, and try
            # every candidate rather than failing because the first has no page.
            relevance_text = topic
            target_url = None
            recent_topics = await self._recent_service_topics(session, organization_id, location_id)
            for candidate in self._rotate_service_topics(
                self._service_topics(governed_facts, profile, knowledge), recent_topics
            ):
                candidate_url = self._select_target_url(profile, knowledge, candidate)
                if candidate_url is not None:
                    topic = candidate
                    relevance_text = candidate
                    target_url = candidate_url
                    break
        if target_url is None:
            raise GBPProposalEnrichmentError(
                "GBP_WEBSITE_TARGET_UNAVAILABLE",
                "No website page with positive relevance to the selected source could be resolved.",
            )
        if source_review is not None and source_revision is not None:
            fallback = self._fallback_copy(organization.name, review_text, target_url)
            content_title = f"Customer review about {topic}"
            intent = "create one Google Business Profile update based on the selected review"
            source_block: dict[str, Any] = {
                "review_id": str(source_review.id),
                "review_revision_id": str(source_revision.id),
                "rating": float(source_revision.rating)
                if source_revision.rating is not None
                else None,
                "title": source_revision.title,
                "body": source_revision.body,
            }
            instructions = (
                "Use the selected customer review as the primary source for the post. "
                "Faithfully paraphrase the experience without inventing details, offers, "
                "guarantees, pricing, credentials, or service areas. Do not identify the "
                "reviewer. Keep the post useful and natural, under 1,200 characters, and do "
                "not paste the URL into the body because LILOs attaches it as the CTA."
            )
            input_references: tuple[UUID, ...] = (source_review.id, source_revision.id)
        else:
            fallback = self._service_fallback_copy(organization.name, topic)
            content_title = f"Service update about {topic}"
            intent = "create one Google Business Profile update about the selected service"
            source_block = {"service_topic": topic}
            instructions = (
                "Write about the selected service using only the client-owned sources "
                "provided: approved business facts, the Google Business Profile, and website "
                "knowledge. Invent nothing: no offers, discounts, "
                "guarantees, pricing, credentials, awards, service areas, or availability that "
                "is not present in the approved facts. Do not imply a customer said anything. "
                "Do not repeat any of the recent posts listed. Keep the post useful and natural, "
                "under 1,200 characters, and do not paste the URL into the body because LILOs "
                "attaches it as the CTA."
            )
            input_references = ()
        task = await self._task_definition(session)
        request = AIGatewayRequest(
            organization_id=organization_id,
            location_id=location_id,
            task_key=TASK_KEY,
            input_document={
                "audience": "local prospective customers",
                "intent": intent,
                "manual_fallback": fallback,
                "content_title": content_title,
                "content_type": "gbp_post",
                "source_type": source_type,
                "source_review" if source_review is not None else "source_service": source_block,
                "governed_facts": governed_facts,
                "knowledge": knowledge,
                "current_gbp_profile": profile,
                "recent_posts_to_avoid_repeating": recent_text[:20],
                "selected_target_url": target_url,
                "instructions": instructions,
            },
            input_references=input_references,
            approved_fact_revision_ids=tuple(fact_ids),
            maximum_cost_microunits=task.maximum_cost_microunits,
            maximum_latency_ms=task.maximum_latency_ms,
        )
        output = await self.ai_gateway.execute(request)
        draft = self._clean_draft(str(output.get("draft") or ""), fallback)

        # Review provenance, draft, destination, selected asset, and the delivery
        # contract are one approval unit. Failed enrichment must not leave a
        # text-only revision behind.
        async with session.begin_nested():
            revision = await self.operations.create_post_revision(
                session,
                organization_id,
                gbp_location.id,
                PostRevisionCreate(
                    post_type="standard",
                    content=draft,
                    call_to_action={"actionType": "LEARN_MORE", "url": target_url},
                    event_or_offer=None,
                ),
                actor_id=None,
                correlation_id=correlation_id,
            )

            enrichment = await self.enrichment.enrich(
                session,
                settings,
                organization_id=organization_id,
                location_id=location_id,
                gbp_location=gbp_location,
                post_revision_id=revision.id,
                content=draft,
                requested_call_to_action=revision.call_to_action,
                relevance_text=f"{relevance_text}\n{draft}",
                source_requirements=(
                    {
                        "source_type": "google_review",
                        "source_review_id": str(source_review.id),
                        "source_review_revision_id": str(source_revision.id),
                    }
                    if source_review is not None and source_revision is not None
                    else {"source_type": "service_knowledge", "source_service_topic": topic}
                ),
            )
            asset = enrichment.asset
            if (
                enrichment.call_to_action is None
                or enrichment.target_url is None
                or asset is None
                or asset.status != "selected"
                or asset.source_type != "google_drive"
                or not str((asset.metadata_document or {}).get("file_id") or "").strip()
            ):
                raise GBPProposalEnrichmentError(
                    "GBP_POST_DELIVERY_BINDING_MISSING",
                    "The generated post could not bind its required CTA and client image.",
                )
            target_url = enrichment.target_url
            selected_image_metadata = dict(asset.metadata_document or {})

        usage = output.get("usage") if isinstance(output.get("usage"), dict) else {}
        execution_output: dict[str, Any] = dict(output)
        execution_output.update(
            {
                "draft": draft,
                "post_revision_id": str(revision.id),
                "source_type": source_type,
                "grounding_sources": grounding_sources,
                "target_url": target_url,
                "selected_image": selected_image_metadata,
                "publication_requirements": dict(revision.publication_requirements or {}),
                "worker_release": os.getenv("LILOS_RELEASE"),
            }
        )
        if source_review is not None and source_revision is not None:
            # source_review_id is the marker that retires a review from future
            # selection. It must be absent (not null) for service-grounded posts.
            execution_output.update(
                {
                    "source_review_id": str(source_review.id),
                    "source_review_revision_id": str(source_revision.id),
                    "source_review_external_id": source_review.external_review_id,
                    "source_review_rating": float(source_revision.rating)
                    if source_revision.rating is not None
                    else None,
                }
            )
        else:
            execution_output["source_service_topic"] = topic
        execution = AIExecution(
            organization_id=organization_id,
            location_id=location_id,
            task_definition_id=task.id,
            workflow_run_id=workflow_run_id,
            idempotency_key=generation_idempotency_key,
            status="completed",
            provider_key=str(output.get("provider") or "unknown"),
            model_key=str(output.get("model") or "unknown"),
            input_references=[
                *(
                    [f"review:{source_review.id}", f"review-revision:{source_revision.id}"]
                    if source_review is not None and source_revision is not None
                    else [f"service-topic:{topic}"]
                ),
                *(str(value) for value in knowledge.get("source_document_ids", [])),
                *(str(item.provider_post_name) for item in recent_provider[:10]),
            ],
            approved_fact_revision_ids=[str(value) for value in fact_ids],
            output_document=execution_output,
            output_hash=hashlib.sha256(draft.encode()).hexdigest(),
            input_tokens=usage.get("input_tokens") if isinstance(usage, dict) else None,
            output_tokens=usage.get("output_tokens") if isinstance(usage, dict) else None,
            estimated_cost_microunits=output.get("cost_microunits"),
            latency_ms=output.get("latency_ms"),
            requires_human_review=True,
            completed_at=datetime.now(UTC),
        )
        session.add(execution)
        await session.flush()
        return revision, execution, asset

    async def _resolve_source_review(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        *,
        source_review_id: UUID | None,
    ) -> tuple[Review, ReviewRevision]:
        current_revision_join = and_(
            ReviewRevision.organization_id == Review.organization_id,
            ReviewRevision.review_id == Review.id,
            ReviewRevision.revision_number == Review.current_revision_number,
        )
        base = (
            select(Review, ReviewRevision)
            .join(ReviewRevision, current_revision_join)
            .where(
                Review.organization_id == organization_id,
                Review.location_id == location_id,
                Review.status != "removed",
            )
        )

        if source_review_id is not None:
            row = (await session.execute(base.where(Review.id == source_review_id))).first()
            if row is None:
                raise GBPProposalEnrichmentError(
                    "GBP_REVIEW_SOURCE_UNAVAILABLE",
                    (
                        "The selected customer review is unavailable in this organization "
                        "and location."
                    ),
                )
            review, revision = row
            if not self._review_text(revision):
                raise GBPProposalEnrichmentError(
                    "GBP_REVIEW_SOURCE_EMPTY",
                    "The selected customer review has no usable text for post generation.",
                )
            return review, revision

        row = (
            await session.execute(
                self._unused_eligible_review_statement(base, organization_id, location_id)
            )
        ).first()
        if row is not None:
            review, revision = row
            if self._review_text(revision):
                return review, revision
        raise GBPProposalEnrichmentError(
            "GBP_REVIEW_SOURCE_UNAVAILABLE",
            (
                "No unused eligible four- or five-star customer review is available for "
                "GBP post generation."
            ),
        )

    async def _resolve_location(
        self, session: AsyncSession, organization_id: UUID, location_id: UUID
    ) -> GBPLocation:
        candidates = list(
            await session.scalars(
                select(GBPLocation)
                .where(
                    GBPLocation.organization_id == organization_id,
                    GBPLocation.location_id == location_id,
                    GBPLocation.mapping_status == "confirmed",
                )
                .order_by(GBPLocation.last_synced_at.desc().nullslast())
            )
        )
        if len(candidates) != 1:
            if not candidates:
                raise LookupError("confirmed GBP location not found")
            raise ValueError("multiple confirmed GBP locations found for platform location")
        return candidates[0]

    async def _task_definition(self, session: AsyncSession) -> AITaskDefinition:
        task = await session.scalar(
            select(AITaskDefinition)
            .where(AITaskDefinition.key == TASK_KEY, AITaskDefinition.status == "active")
            .order_by(AITaskDefinition.version.desc())
            .limit(1)
        )
        if task is not None:
            return task
        task = AITaskDefinition(
            key=TASK_KEY,
            version=1,
            owning_product="gbp",
            purpose="Generate review-grounded Google Business Profile posts for approval.",
            input_schema={
                "source_review": "object",
                "governed_facts": "array",
                "knowledge": "object",
            },
            output_schema={"draft": "string"},
            risk_level="medium",
            maximum_cost_microunits=0,
            maximum_latency_ms=MAXIMUM_LATENCY_MS,
            requires_human_review=True,
            retention_policy_key="gbp.ai_post.default",
            status="active",
        )
        session.add(task)
        await session.flush()
        return task

    async def _resolve_optional_source_review(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
    ) -> tuple[Review, ReviewRevision] | None:
        """Return the newest unused eligible review, or None when none remains.

        Automated runs prefer a review because a real customer experience makes the
        strongest post, but a location's review count must not cap how often it can
        post. Returning None hands the caller the service-knowledge path instead of
        failing the run.
        """
        try:
            return await self._resolve_source_review(
                session, organization_id, location_id, source_review_id=None
            )
        except GBPProposalEnrichmentError as exc:
            if exc.safe_code == "GBP_REVIEW_SOURCE_UNAVAILABLE":
                return None
            raise

    @staticmethod
    def _service_topics(
        governed_facts: list[GovernedFact],
        profile: dict[str, object],
        knowledge: dict[str, Any] | None = None,
    ) -> list[str]:
        """Service topics in authority order, deduplicated.

        Approved facts first, then the GBP profile's own service items, then the
        client's website page titles. All three are client-owned sources, which is
        what makes a newly onboarded client postable before anyone curates facts by
        hand. Ordered candidates rather than a single hint so a location whose
        highest-priority service has no matching page can still post about another.
        """
        topics: list[str] = []

        def add(value: object) -> None:
            text = str(value or "").strip()[:120]
            if text and text.casefold() not in {item.casefold() for item in topics}:
                topics.append(text)

        preferred_keys = ("primary_services", "services", "service", "service_items")
        for key in preferred_keys:
            for fact in governed_facts:
                if key not in str(fact.get("fact_key", "")):
                    continue
                value = fact.get("value")
                if isinstance(value, list):
                    for entry in value:
                        add(entry)
                else:
                    add(value)
        items = profile.get("serviceItems")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    add(item.get("structuredName") or item.get("name"))
                else:
                    add(item)
        # Website page titles: the client's own site, already ingested by the crawler.
        # Homepage-style pages are skipped because they name the business, not a service.
        pages = (knowledge or {}).get("website_knowledge")
        if isinstance(pages, list):
            for raw in pages:
                if not isinstance(raw, dict):
                    continue
                if str(raw.get("url") or "").rstrip("/").count("/") <= 2:
                    continue
                add(raw.get("h1") or raw.get("title"))
        return topics[:12]

    @staticmethod
    async def _recent_service_topics(
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        *,
        window: int = 10,
    ) -> list[str]:
        """Service topics used by the most recent generated posts, newest first.

        A short window, not the full history: repeating a topic eventually is normal
        and must never be an error. Only the recent run of posts should steer away
        from a topic.
        """
        rows = list(
            await session.scalars(
                select(AIExecution.output_document)
                .join(AITaskDefinition, AITaskDefinition.id == AIExecution.task_definition_id)
                .where(
                    AIExecution.organization_id == organization_id,
                    AIExecution.location_id == location_id,
                    AIExecution.status == "completed",
                    AITaskDefinition.key == TASK_KEY,
                )
                .order_by(AIExecution.created_at.desc())
                .limit(window)
            )
        )
        topics: list[str] = []
        for document in rows:
            topic = str((document or {}).get("source_service_topic") or "").strip()
            if topic:
                topics.append(topic)
        return topics

    @staticmethod
    def _rotate_service_topics(candidates: list[str], recent_topics: list[str]) -> list[str]:
        """Order candidates least-recently-used first, keeping every candidate.

        Mirrors the Drive image rule: prefer something unused in the recent window,
        but never drop a candidate, so an exhausted rotation reuses the oldest topic
        instead of failing.
        """
        recent_rank: dict[str, int] = {}
        for position, topic in enumerate(recent_topics):
            recent_rank.setdefault(topic.casefold(), position)
        unused = [c for c in candidates if c.casefold() not in recent_rank]
        used = [c for c in candidates if c.casefold() in recent_rank]
        # recent_topics is newest-first, so a larger rank means longer unused.
        used.sort(key=lambda c: recent_rank[c.casefold()], reverse=True)
        return unused + used

    @staticmethod
    def _service_fallback_copy(organization_name: str, topic: str) -> str:
        """Manual-path copy for a service post. Claims nothing beyond the service name."""
        service = " ".join(str(topic).split())[:120].rstrip(" ,.;:-") or "our services"
        return (
            f"{organization_name} helps local customers with {service}. "
            "Learn more about what the work involves and how to get started."
        )[:1200]

    @staticmethod
    def _unused_eligible_review_statement(
        base: Select[tuple[Review, ReviewRevision]],
        organization_id: UUID,
        location_id: UUID,
    ) -> Select[tuple[Review, ReviewRevision]]:
        """Select the newest 4-5 star review this task has never already used.

        A review counts as used only when a completed execution of THIS task recorded it
        as its source. The exclusion is a correlated NOT EXISTS over the full execution
        history rather than a bounded recency window, because a window can (a) let an
        already-used review age out and be selected again, producing a duplicate post on
        a live profile, and (b) be consumed by unrelated AI tasks at the same location
        (review responses, content drafts, SEO runs), which accelerates (a). Eligibility
        is likewise resolved in SQL rather than by scanning a capped candidate page, so a
        location with many reviews cannot report exhaustion while unused ones remain.
        """
        used_by_prior_generation = (
            select(AIExecution.id)
            .join(AITaskDefinition, AITaskDefinition.id == AIExecution.task_definition_id)
            .where(
                AIExecution.organization_id == organization_id,
                AIExecution.location_id == location_id,
                AIExecution.status == "completed",
                AITaskDefinition.key == TASK_KEY,
                AIExecution.output_document["source_review_id"].astext == Review.id.cast(String),
            )
            .exists()
        )
        # Mirrors _review_text: a revision is usable when its title or body has content.
        has_usable_text = or_(
            func.btrim(func.coalesce(ReviewRevision.title, "")) != "",
            func.btrim(func.coalesce(ReviewRevision.body, "")) != "",
        )
        return (
            base.where(
                Review.rating >= 4,
                has_usable_text,
                ~used_by_prior_generation,
            )
            .order_by(Review.review_created_at.desc())
            .limit(1)
        )

    @staticmethod
    def _review_text(revision: ReviewRevision) -> str:
        return " ".join(
            part.strip() for part in (revision.title or "", revision.body or "") if part.strip()
        )[:5000]

    @staticmethod
    def _topic_hint(governed_facts: list[GovernedFact], profile: dict[str, object]) -> str:
        preferred_keys = ("primary_services", "services", "service", "service_items")
        for key in preferred_keys:
            for fact in governed_facts:
                if key not in str(fact.get("fact_key", "")):
                    continue
                value = fact.get("value")
                if isinstance(value, list) and value:
                    return str(value[0])[:120]
                if isinstance(value, str) and value.strip():
                    return value.strip()[:120]
        items = profile.get("serviceItems")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                return str(first.get("structuredName") or first.get("name") or "service")[:120]
            return str(first)[:120]
        return "customer experience"

    @staticmethod
    def _select_target_url(
        profile: dict[str, object], knowledge: dict[str, Any], relevance_text: str
    ) -> str | None:
        del profile
        pages = knowledge.get("website_knowledge")
        terms = {
            part for part in relevance_text.casefold().replace("-", " ").split() if len(part) > 3
        }
        ranked: list[tuple[int, str]] = []
        if isinstance(pages, list):
            for raw in pages:
                if not isinstance(raw, dict):
                    continue
                url = str(raw.get("url") or "").strip()
                if not url.startswith(("https://", "http://")):
                    continue
                haystack = " ".join(
                    str(raw.get(key) or "") for key in ("url", "title", "h1", "body_text")
                ).casefold()
                overlap = sum(1 for term in terms if term in haystack)
                if overlap <= 0:
                    continue
                score = overlap * 10
                if url.rstrip("/").count("/") > 2:
                    score += 1
                ranked.append((score, url))
        if not ranked:
            return None
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[0][1]

    @staticmethod
    def _fallback_copy(organization_name: str, review_text: str, target_url: str | None) -> str:
        del target_url
        excerpt = " ".join(review_text.split())[:260].rstrip(" ,.;:-")
        return (
            f'A recent customer shared: "{excerpt}." {organization_name} appreciates the feedback '
            "and the opportunity to help. Learn more about the service behind their experience."
        )[:1200]

    @staticmethod
    def _clean_draft(draft: str, fallback: str) -> str:
        cleaned = " ".join(draft.strip().split())
        if not cleaned:
            cleaned = fallback
        return cleaned[:1200].rstrip()
