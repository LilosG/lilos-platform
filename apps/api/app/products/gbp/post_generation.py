"""AI-first GBP post generation grounded in provider and website knowledge."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.knowledge_service import BusinessKnowledgeService
from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.ai.factory import build_ai_gateway
from apps.api.app.ai.gateway import AIGatewayRequest
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.config import Settings
from apps.api.app.integrations.google_drive_media import GoogleDriveMediaService
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.service import resolve_governed_facts
from apps.api.app.products.gbp.models import GBPLocation, GBPProfileSnapshot
from apps.api.app.products.gbp.operations_contracts import PostRevisionCreate
from apps.api.app.products.gbp.operations_models import GBPPostRevision, GBPProviderPost
from apps.api.app.products.gbp.operations_service import GBPOperationsService
from apps.api.app.products.gbp.post_generation_models import GBPPostAsset

TASK_KEY = "gbp.generate_post"
MAXIMUM_LATENCY_MS = 120_000


class GBPPostGenerationService:
    def __init__(self) -> None:
        self.ai_gateway = build_ai_gateway()
        self.knowledge = BusinessKnowledgeService()
        self.operations = GBPOperationsService()
        self.drive = GoogleDriveMediaService()

    async def generate(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        location_id: UUID,
        *,
        workflow_run_id: UUID,
        correlation_id: str,
    ) -> tuple[GBPPostRevision, AIExecution, GBPPostAsset | None]:
        """Create an approval-ready local post with CTA and an optional Drive image."""
        gbp_location = await self._resolve_location(session, organization_id, location_id)
        organization = await session.get(Organization, organization_id)
        if organization is None:
            raise LookupError("organization not found")

        existing_execution = await session.scalar(
            select(AIExecution).where(
                AIExecution.organization_id == organization_id,
                AIExecution.workflow_run_id == workflow_run_id,
            )
        )
        if existing_execution is not None:
            revision_id = (existing_execution.output_document or {}).get("post_revision_id")
            if revision_id:
                revision = await session.get(GBPPostRevision, UUID(str(revision_id)))
                if revision is not None:
                    asset = await session.scalar(
                        select(GBPPostAsset).where(GBPPostAsset.post_revision_id == revision.id)
                    )
                    return revision, existing_execution, asset

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
        if not fact_ids:
            raise ValueError("approved business facts required for GBP AI generation")
        governed_facts = await resolve_governed_facts(
            session,
            organization_id,
            fact_ids,
            location_id=location_id,
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
        knowledge = await self.knowledge.retrieve_for_content(
            session,
            organization_id=organization_id,
            location_id=location_id,
            content_title=f"{topic} Google Business Profile update",
            audience="local prospective customers",
            intent=(
                "highlight a relevant service or useful business update and drive a "
                "qualified website visit"
            ),
            content_type="gbp_post",
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

        target_url = self._select_target_url(profile, knowledge, topic)
        fallback = self._fallback_copy(organization.name, topic, target_url)
        task = await self._task_definition(session)
        request = AIGatewayRequest(
            organization_id=organization_id,
            location_id=location_id,
            task_key=TASK_KEY,
            input_document={
                "audience": "local prospective customers",
                "intent": "create one useful, specific Google Business Profile update",
                "manual_fallback": fallback,
                "content_title": topic,
                "content_type": "gbp_post",
                "governed_facts": governed_facts,
                "knowledge": knowledge,
                "current_gbp_profile": profile,
                "recent_posts_to_avoid_repeating": recent_text[:20],
                "selected_target_url": target_url,
                "instructions": (
                    "Write one concise Google Business Profile update. Pick a specific service or "
                    "customer-useful topic supported by the facts/knowledge. Do not repeat recent "
                    "posts. Do not invent offers, guarantees, pricing, credentials, or service "
                    "areas. Keep the post under 1,200 characters and do not paste the URL into the "
                    "body because LILOs attaches it as the CTA."
                ),
            },
            input_references=tuple(),
            approved_fact_revision_ids=tuple(fact_ids),
            maximum_cost_microunits=task.maximum_cost_microunits,
            maximum_latency_ms=task.maximum_latency_ms,
        )
        output = await self.ai_gateway.execute(request)
        draft = self._clean_draft(str(output.get("draft") or ""), fallback)

        revision = await self.operations.create_post_revision(
            session,
            organization_id,
            gbp_location.id,
            PostRevisionCreate(
                post_type="standard",
                content=draft,
                call_to_action=(
                    {"actionType": "LEARN_MORE", "url": target_url} if target_url else None
                ),
                event_or_offer=None,
            ),
            actor_id=None,
            correlation_id=correlation_id,
        )

        asset: GBPPostAsset | None = None
        selected_image_metadata: dict[str, object] | None = None
        try:
            images = await self.drive.discover_images(settings, organization.name, limit=25)
            if images:
                image = images[0]
                proxy_url = self.drive.public_proxy_url(
                    settings,
                    organization_id=organization_id,
                    image=image,
                )
                if proxy_url:
                    selected_image_metadata = {
                        "file_id": image.file_id,
                        "name": image.name,
                        "mime_type": image.mime_type,
                        "path": image.path,
                        "modified_time": image.modified_time or "",
                    }
                    asset = GBPPostAsset(
                        organization_id=organization_id,
                        post_revision_id=revision.id,
                        source_type="google_drive",
                        source_reference=f"drive:{image.file_id}",
                        provider_fetch_url=proxy_url,
                        metadata_document=selected_image_metadata,
                        status="selected",
                    )
                    session.add(asset)
                    await session.flush()
        except Exception:
            # Image enrichment is additive. A grounded text+CTA draft remains
            # useful and approval-ready even if Drive is temporarily unavailable.
            asset = None

        usage = output.get("usage") if isinstance(output.get("usage"), dict) else {}
        execution_output: dict[str, Any] = dict(output)
        execution_output.update(
            {
                "draft": draft,
                "post_revision_id": str(revision.id),
                "target_url": target_url,
                "selected_image": selected_image_metadata,
            }
        )
        execution = AIExecution(
            organization_id=organization_id,
            location_id=location_id,
            task_definition_id=task.id,
            workflow_run_id=workflow_run_id,
            idempotency_key=f"gbp-post-{workflow_run_id}",
            status="completed",
            provider_key=str(output.get("provider") or "unknown"),
            model_key=str(output.get("model") or "unknown"),
            input_references=[
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
            purpose="Generate grounded, non-repetitive Google Business Profile posts for approval.",
            input_schema={"governed_facts": "array", "knowledge": "object"},
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

    @staticmethod
    def _topic_hint(governed_facts: list[dict[str, object]], profile: dict[str, object]) -> str:
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
        return "business update"

    @staticmethod
    def _select_target_url(
        profile: dict[str, object], knowledge: dict[str, Any], topic: str
    ) -> str | None:
        pages = knowledge.get("website_knowledge")
        topic_terms = {part for part in topic.casefold().replace("-", " ").split() if len(part) > 3}
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
                score = sum(1 for term in topic_terms if term in haystack)
                if url.rstrip("/").count("/") > 2:
                    score += 1
                ranked.append((score, url))
        if ranked:
            ranked.sort(key=lambda item: item[0], reverse=True)
            return ranked[0][1]
        website = profile.get("websiteUri")
        return str(website).strip() if isinstance(website, str) and website.strip() else None

    @staticmethod
    def _fallback_copy(organization_name: str, topic: str, target_url: str | None) -> str:
        del target_url
        return (
            f"Looking for help with {topic}? {organization_name} can help you understand the next "
            "steps and the options that fit your project. Learn more about this "
            "service and what to expect before you schedule."
        )[:1200]

    @staticmethod
    def _clean_draft(draft: str, fallback: str) -> str:
        cleaned = " ".join(draft.strip().split())
        if not cleaned:
            cleaned = fallback
        return cleaned[:1200].rstrip()
