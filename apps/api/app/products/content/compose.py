"""Write content from one plain prompt.

`content.compose` is the single pipeline every piece of new content goes through, whether
an operator typed a sentence or accepted an opportunity. The route only reserves a
placeholder item and starts a durable run. The worker then:

1. gathers the client's scope (approved facts, crawled pages, existing content, location),
2. asks Hermes, through the AI gateway, to resolve what the prompt left unsaid,
3. checks that plan deterministically and records the prompt's own claims as
   operator-verified facts attributed to the submitting user,
4. fills in the item and brief through `ContentService`, and
5. drafts through the same `execute_ai_draft_workflow` every other draft uses, so the
   quality floors, link validation and bounded repair apply unchanged.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.knowledge_service import BusinessKnowledgeService
from apps.api.app.ai.gateway import AIGateway, AIGatewayRequest
from apps.api.app.ai.models import AITaskDefinition
from apps.api.app.execution.models import WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.locations.models import Location
from apps.api.app.products.content.contracts import BriefCreate, ComposeCreate
from apps.api.app.products.content.enums import (
    ComposeContentType,
    ComposeFailureCode,
    ContentTargetKind,
)
from apps.api.app.products.content.errors import (
    ContentComposeWebsiteNotFoundError,
    ContentItemNotFoundError,
)
from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentOpportunity,
    ContentRevision,
)
from apps.api.app.products.content.service import (
    ContentService,
    approved_governed_facts,
    record_operator_claim,
)
from apps.api.app.products.seo.models import SEOOpportunity, SEOWebsite

PLAN_TASK_KEY = "content.compose_plan"
_SLUG = re.compile(r"[^a-z0-9]+")
_SLUG_VALID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# Listicles, roundups and guides are articles; the rest are pages.
_PAGE_TYPES = frozenset(
    {
        ComposeContentType.LANDING_PAGE,
        ComposeContentType.SERVICE_PAGE,
        ComposeContentType.LOCATION_PAGE,
    }
)


class ComposeFailure(Exception):
    """A compose run that must stop, with the typed code the console reads."""

    def __init__(self, code: ComposeFailureCode) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class ComposePlan:
    content_type: ComposeContentType
    title: str
    slug: str
    target_kind: ContentTargetKind
    target_reference: str
    audience: str
    intent: str
    primary_topic: str
    keywords: list[str]
    local_references: list[str]
    link_targets: list[str]
    prompt_claims: list[str]


def slugify(value: str) -> str:
    return _SLUG.sub("-", value.casefold()).strip("-")[:120].strip("-")


def provisional_title(prompt: str) -> str:
    words = prompt.split()
    title = " ".join(words[:14])
    return title[:300] if title else "New content"


def opportunity_prompt(opportunity: ContentOpportunity, objective: str | None = None) -> str:
    """The prompt an opportunity composes from, built only from its recorded evidence."""
    facts = [
        f"{key.replace('_', ' ')}: {value}"
        for key, value in sorted((opportunity.evidence_document or {}).items())
        if isinstance(value, (str, int, float)) and not isinstance(value, bool) and str(value)
    ][:12]
    lines = [
        f"Write content for the {opportunity.opportunity_type.replace('_', ' ')} opportunity "
        f"targeting {opportunity.target_reference}.",
        *([f"Evidence: {'; '.join(facts)}."] if facts else []),
        *([objective.strip()] if objective and objective.strip() else []),
    ]
    return " ".join(lines)[:2000]


async def resolve_opportunity_website(
    session: AsyncSession, opportunity: ContentOpportunity
) -> SEOWebsite:
    """The website an opportunity belongs to: its own SEO opportunity's, else the only one."""
    reference = opportunity.source_reference or ""
    if reference.startswith("seo-opportunity:"):
        try:
            seo_id = UUID(reference.split(":", 1)[1])
        except ValueError:
            seo_id = None
        if seo_id is not None:
            seo = await session.scalar(
                select(SEOOpportunity).where(
                    SEOOpportunity.organization_id == opportunity.organization_id,
                    SEOOpportunity.id == seo_id,
                )
            )
            if seo is not None:
                website = await session.scalar(
                    select(SEOWebsite).where(
                        SEOWebsite.organization_id == opportunity.organization_id,
                        SEOWebsite.id == seo.website_id,
                    )
                )
                if website is not None:
                    return website
    websites = list(
        await session.scalars(
            select(SEOWebsite).where(
                SEOWebsite.organization_id == opportunity.organization_id,
                SEOWebsite.status == "active",
            )
        )
    )
    if len(websites) == 1:
        return websites[0]
    raise ContentComposeWebsiteNotFoundError


def compose_item_id(organization_id: UUID, idempotency_key: str) -> UUID:
    """The placeholder item for one compose request. Same key, same item: retries are safe."""
    return uuid5(NAMESPACE_URL, f"lilos:content-compose:{organization_id}:{idempotency_key}")


def build_plan(
    raw: object,
    *,
    forced_type: ComposeContentType | None,
    existing_slugs: set[str],
    inventory_urls: set[str],
) -> ComposePlan:
    """Validate Hermes's plan. Anything off is a typed failure, never a guess."""
    if not isinstance(raw, dict):
        raise ComposeFailure(ComposeFailureCode.PLAN_INVALID)
    try:
        content_type = forced_type or ComposeContentType(str(raw.get("content_type") or ""))
    except ValueError:
        raise ComposeFailure(ComposeFailureCode.PLAN_INVALID) from None
    title = " ".join(str(raw.get("title") or "").split())[:300]
    if not title:
        raise ComposeFailure(ComposeFailureCode.PLAN_INVALID)
    slug = str(raw.get("slug") or "").strip().casefold()
    if not _SLUG_VALID.match(slug):
        slug = slugify(title)
    if not slug:
        raise ComposeFailure(ComposeFailureCode.PLAN_INVALID)
    base, counter = slug[:190], 2
    while slug in existing_slugs:
        slug = f"{base}-{counter}"
        counter += 1
    try:
        target_kind = ContentTargetKind(str(raw.get("target_kind") or "new_page"))
    except ValueError:
        target_kind = ContentTargetKind.NEW_PAGE
    reference = str(raw.get("target_reference") or "").strip()
    if target_kind is ContentTargetKind.NEW_PAGE:
        if not reference.startswith("/") or reference.startswith("//"):
            reference = f"/{'blog' if content_type not in _PAGE_TYPES else 'pages'}/{slug}/"
        if reference.casefold().rstrip("/") in inventory_urls:
            # The page Hermes named already exists; a new piece needs its own address.
            reference = f"/{'blog' if content_type not in _PAGE_TYPES else 'pages'}/{slug}/"
    elif reference.casefold().rstrip("/") not in inventory_urls:
        raise ComposeFailure(ComposeFailureCode.PLAN_INVALID)

    def strings(key: str, limit: int, size: int = 200) -> list[str]:
        value = raw.get(key)
        if not isinstance(value, list):
            return []
        return [" ".join(str(x).split())[:size] for x in value if str(x).strip()][:limit]

    links = [
        path
        for path in strings("link_targets", 12, 500)
        if path.casefold().rstrip("/") in inventory_urls
    ]
    return ComposePlan(
        content_type=content_type,
        title=title,
        slug=slug,
        target_kind=target_kind,
        target_reference=reference[:500],
        audience=" ".join(str(raw.get("audience") or "local customers").split())[:500],
        intent=" ".join(str(raw.get("intent") or "inform").split())[:500],
        primary_topic=" ".join(str(raw.get("primary_topic") or title).split())[:300],
        keywords=strings("keywords", 8),
        local_references=strings("local_references", 20),
        link_targets=links,
        prompt_claims=strings("prompt_claims", 12, 400),
    )


class ContentComposeService:
    def __init__(
        self,
        *,
        content: ContentService | None = None,
        execution: ExecutionService | None = None,
        gateway: AIGateway | None = None,
    ) -> None:
        self.content = content or ContentService()
        self.execution = execution or ExecutionService()
        self._gateway = gateway

    @property
    def gateway(self) -> AIGateway:
        return self._gateway or self.content.ai_gateway

    async def start(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: ComposeCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
        opportunity_id: UUID | None = None,
    ) -> tuple[ContentItem, WorkflowRun]:
        """Reserve the placeholder item and start the durable run. Idempotent per key."""
        website = await session.scalar(
            select(SEOWebsite).where(
                SEOWebsite.organization_id == organization_id,
                SEOWebsite.id == command.website_id,
            )
        )
        if website is None:
            raise ContentComposeWebsiteNotFoundError
        item_id = compose_item_id(organization_id, command.idempotency_key)
        item = await session.scalar(
            select(ContentItem).where(
                ContentItem.organization_id == organization_id, ContentItem.id == item_id
            )
        )
        if item is None:
            item = ContentItem(
                id=item_id,
                organization_id=organization_id,
                location_id=website.location_id,
                opportunity_id=opportunity_id,
                content_type=(command.content_type or ComposeContentType.BLOG_POST).value,
                title=provisional_title(command.prompt),
                slug=f"draft-{item_id.hex[:12]}",
                status="drafting",
            )
            session.add(item)
            await session.flush()
            await self.content._audit(
                session,
                event="content.compose.requested",
                organization_id=organization_id,
                location_id=website.location_id,
                actor_id=actor_id,
                resource_type="content_item",
                resource_id=item.id,
                correlation_id=correlation_id,
                summary="Content composition requested from a prompt.",
                metadata={
                    "website_id": str(website.id),
                    "content_type": command.content_type.value if command.content_type else None,
                    "prompt_length": len(command.prompt),
                    "opportunity_id": str(opportunity_id) if opportunity_id else None,
                },
            )
        run = await self.execution.start_named(
            session,
            organization_id,
            "content.compose",
            idempotency_key=f"content-compose-{command.idempotency_key}",
            location_id=website.location_id,
            input_document={
                "item_id": str(item.id),
                "website_id": str(website.id),
                "prompt": command.prompt,
                "content_type": command.content_type.value if command.content_type else None,
                "idempotency_key": command.idempotency_key,
                "user_id": str(actor_id) if actor_id else None,
                "opportunity_id": str(opportunity_id) if opportunity_id else None,
            },
            correlation_id=correlation_id,
            actor_id=actor_id,
            enqueue_job=True,
        )
        return item, run

    async def execute(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        input_document: dict[str, Any],
        workflow_run_id: UUID,
        correlation_id: str,
    ) -> ContentRevision:
        """Run one compose request to a reviewable draft revision, or raise typed."""
        item_id = UUID(str(input_document["item_id"]))
        website_id = UUID(str(input_document["website_id"]))
        prompt = str(input_document["prompt"])
        idempotency_key = str(input_document["idempotency_key"])
        user_id = UUID(str(input_document["user_id"])) if input_document.get("user_id") else None
        forced_type = (
            ComposeContentType(str(input_document["content_type"]))
            if input_document.get("content_type")
            else None
        )

        item = await session.scalar(
            select(ContentItem)
            .where(ContentItem.organization_id == organization_id, ContentItem.id == item_id)
            .with_for_update()
        )
        if item is None:
            raise ContentItemNotFoundError
        website = await session.scalar(
            select(SEOWebsite).where(
                SEOWebsite.organization_id == organization_id, SEOWebsite.id == website_id
            )
        )
        if website is None:
            raise ContentComposeWebsiteNotFoundError

        brief = await session.scalar(
            select(ContentBrief).where(
                ContentBrief.organization_id == organization_id,
                ContentBrief.content_item_id == item.id,
                ContentBrief.validation_requirements["compose_key"].astext == idempotency_key,
            )
        )
        if brief is None:
            brief = await self._plan_and_brief(
                session,
                organization_id=organization_id,
                item=item,
                website=website,
                prompt=prompt,
                forced_type=forced_type,
                idempotency_key=idempotency_key,
                user_id=user_id,
                correlation_id=correlation_id,
            )
        # Drafting: the one shared pipeline. A repeat of this run replays the stored execution.
        revision, _execution = await self.content.execute_ai_draft_workflow(
            session,
            organization_id=organization_id,
            item_id=item.id,
            brief_id=brief.id,
            idempotency_key=f"compose-draft-{idempotency_key}"[:128],
            workflow_run_id=workflow_run_id,
            user_id=user_id,
            correlation_id=correlation_id,
        )
        return revision

    async def _plan_and_brief(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        item: ContentItem,
        website: SEOWebsite,
        prompt: str,
        forced_type: ComposeContentType | None,
        idempotency_key: str,
        user_id: UUID | None,
        correlation_id: str,
    ) -> ContentBrief:
        link_context = await self.content.website_link_context(
            session, organization_id, website, topic=prompt, exclude_item_id=item.id
        )
        raw_inventory = link_context.get("link_inventory")
        if not isinstance(raw_inventory, list) or not raw_inventory:
            # Every long-form piece must link to verified pages; with no crawl there are none.
            raise ComposeFailure(ComposeFailureCode.WEBSITE_NOT_CRAWLED)
        inventory_urls = {
            str(row["url"]).casefold().rstrip("/") or "/"
            for row in raw_inventory
            if isinstance(row, dict)
        }

        # The prompt is an instruction, not a business fact: it stays on the brief as
        # `source_prompt`. Only the claims it makes are recorded as facts, below.
        facts = await approved_governed_facts(session, organization_id, item.location_id)
        if not facts:
            raise ComposeFailure(ComposeFailureCode.NO_APPROVED_FACTS)
        existing = list(
            await session.scalars(
                select(ContentItem).where(
                    ContentItem.organization_id == organization_id, ContentItem.id != item.id
                )
            )
        )
        location = await session.scalar(
            select(Location).where(
                Location.organization_id == organization_id,
                *(
                    [Location.id == item.location_id]
                    if item.location_id
                    else [Location.is_primary.is_(True)]
                ),
            )
        )
        knowledge = await BusinessKnowledgeService().retrieve_for_content(
            session,
            organization_id=organization_id,
            location_id=item.location_id,
            content_title=prompt[:200],
            audience="local customers",
            intent=prompt[:300],
            content_type=(forced_type or ComposeContentType.BLOG_POST).value,
        )
        task = await self._plan_task(session)
        fact_ids = tuple(UUID(f["revision_id"]) for f in facts)
        request = AIGatewayRequest(
            organization_id=organization_id,
            location_id=item.location_id,
            task_key=PLAN_TASK_KEY,
            input_document={
                "source_prompt": prompt,
                "content_type": forced_type.value if forced_type else None,
                "allowed_content_types": [t.value for t in ComposeContentType],
                "governed_facts": facts,
                "knowledge": knowledge,
                "link_targets": link_context.get("recommended_link_targets"),
                "existing_content": [
                    {"title": c.title, "slug": c.slug, "type": c.content_type} for c in existing
                ][:100],
                "location": (
                    {
                        "name": location.name,
                        "city": location.city,
                        "region": location.region,
                        "service_area": location.service_area_description,
                    }
                    if location
                    else None
                ),
                "manual_fallback": "{}",
            },
            input_references=(item.id,),
            approved_fact_revision_ids=fact_ids,
            maximum_cost_microunits=task.maximum_cost_microunits,
            maximum_latency_ms=task.maximum_latency_ms,
        )
        output = await self.gateway.execute(request)
        plan = build_plan(
            output.get("plan"),
            forced_type=forced_type,
            existing_slugs={c.slug for c in existing},
            inventory_urls=inventory_urls,
        )

        # What the prompt itself claims, recorded honestly as operator-verified facts.
        claim_fact_ids: list[UUID] = []
        for claim in plan.prompt_claims:
            fact = await record_operator_claim(
                session,
                organization_id,
                item.location_id,
                claim,
                user_id or item.organization_id,
                source="operator_prompt",
            )
            claim_fact_ids.append(fact.id)
        grounded = {*(UUID(f["revision_id"]) for f in facts), *claim_fact_ids}

        item.title, item.slug = plan.title, plan.slug
        item.content_type = plan.content_type.value
        await session.flush()
        brief = await self.content.create_brief(
            session,
            organization_id,
            item.id,
            BriefCreate(
                audience=plan.audience,
                intent=plan.intent,
                target_kind=plan.target_kind,
                target_reference=plan.target_reference,
                approved_fact_revision_ids=sorted(grounded, key=str)[:100],
                required_claims=plan.prompt_claims,
                required_local_references=plan.local_references,
                source_evidence_references=[f"operator-prompt:{_digest(prompt)}"],
                validation_requirements={
                    "compose_key": idempotency_key,
                    "website_id": str(website.id),
                    "primary_topic": plan.primary_topic,
                    "keywords": plan.keywords,
                    "link_targets": plan.link_targets,
                },
                source_prompt=prompt,
            ),
            actor_id=user_id,
            correlation_id=correlation_id,
        )
        return brief

    async def _plan_task(self, session: AsyncSession) -> AITaskDefinition:
        task = await session.scalar(
            select(AITaskDefinition).where(
                AITaskDefinition.key == PLAN_TASK_KEY, AITaskDefinition.status == "active"
            )
        )
        if task is None:
            task = AITaskDefinition(
                key=PLAN_TASK_KEY,
                version=1,
                owning_product="content",
                purpose="Resolve a plain operator prompt into a structured content plan.",
                input_schema={"source_prompt": "string"},
                output_schema={"plan": "object"},
                risk_level="low",
                maximum_cost_microunits=0,
                maximum_latency_ms=120_000,
                requires_human_review=True,
                retention_policy_key="content.ai_draft.default",
                status="active",
            )
            session.add(task)
            await session.flush()
        return task


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:16]
