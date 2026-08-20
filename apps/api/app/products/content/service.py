"""Governed content opportunities, briefs, grounded revisions, approval, and publication intent."""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import TypedDict, cast
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.administration.knowledge_service import BusinessKnowledgeService
from apps.api.app.administration.models import BusinessFactRevision
from apps.api.app.ai.factory import build_ai_gateway
from apps.api.app.ai.gateway import AIGatewayRequest
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.repository import AuditEventRepository
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import IntegrationConnection, Provider
from apps.api.app.integrations.secrets import FernetSecretStore
from apps.api.app.notifications.models import NotificationTemplate
from apps.api.app.notifications.service import NotificationService
from apps.api.app.products.content.adapter import validate_target_path
from apps.api.app.products.content.contracts import (
    AIDraftCreate,
    ApprovalDecision,
    BriefCreate,
    GitHubConnectionCreate,
    ItemCreate,
    OpportunityCreate,
    OpportunityDecision,
    PublicationCreate,
    RevisionCreate,
    TargetCreate,
)
from apps.api.app.products.content.errors import (
    ContentApprovalStageConflictError,
    ContentBriefNotFoundError,
    ContentGitHubProviderNotConfiguredError,
    ContentItemNotFoundError,
    ContentOpportunityNotDecidableError,
    ContentOpportunityNotFoundError,
    ContentPublicationRequiresApprovedRevisionError,
    ContentQueryInvalidError,
    ContentRevisionNotFoundError,
    ContentTargetNotConfiguredError,
)
from apps.api.app.products.content.models import (
    ContentBrief,
    ContentItem,
    ContentOpportunity,
    ContentPublication,
    ContentRevision,
    PublishingTarget,
)

SECRET_PATTERN = re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]")


def _cast_str_list(value: object) -> list[str]:
    """Cast a dynamic value to a list of strings for mypy-safe unpacking."""
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


AI_TASK_KEY = "content.draft_revision"
NOTIFICATION_TEMPLATES = {
    "content.revision.awaiting_editorial": ("in_app", "A content revision needs editorial review."),
    "content.revision.awaiting_client": ("in_app", "A content revision needs client approval."),
    "content.publication.reserved": ("in_app", "A content publication was reserved."),
}


class ContentValidation(TypedDict):
    valid: bool
    errors: list[str]


def validate_content(
    body: str, frontmatter: dict[str, object], prohibited_claims: list[str], fact_ids: list[UUID]
) -> ContentValidation:
    errors = []
    lower = body.casefold()
    if not fact_ids:
        errors.append("approved_fact_grounding_missing")
    if any(claim.casefold() in lower for claim in prohibited_claims):
        errors.append("prohibited_claim")
    if SECRET_PATTERN.search(body) or any(
        key.casefold() in {"secret", "token", "password", "api_key"} for key in frontmatter
    ):
        errors.append("secret_like_content")
    if "<script" in lower:
        errors.append("executable_content")
    return {"valid": not errors, "errors": sorted(set(errors))}


# ---------------------------------------------------------------------------
# Governed business-fact resolution
# ---------------------------------------------------------------------------


class FactResolutionError(ValueError):
    """Raised when a supplied fact revision is invalid for the organization/scope."""


class GovernedFact(TypedDict):
    fact_key: str
    value: object
    authority: str
    revision_id: str


async def resolve_governed_facts(
    session: AsyncSession,
    organization_id: UUID,
    fact_revision_ids: list[UUID],
    *,
    location_id: UUID | None = None,
) -> list[GovernedFact]:
    """Resolve approved business-fact revision IDs into their actual values.

    Validates:
    - organization ownership
    - active/approved status
    - applicable location scope where relevant
    - fact identity/key present

    Returns a list of ``GovernedFact`` dicts suitable for AI input.
    Raises ``FactResolutionError`` if any supplied fact revision is invalid.
    """
    if not fact_revision_ids:
        return []

    revisions = (
        await session.scalars(
            select(BusinessFactRevision).where(
                BusinessFactRevision.organization_id == organization_id,
                BusinessFactRevision.id.in_(fact_revision_ids),
            )
        )
    ).all()

    found_ids = {r.id for r in revisions}
    missing = set(fact_revision_ids) - found_ids
    if missing:
        raise FactResolutionError(
            f"fact revisions not found for organization: {[str(m) for m in missing]}"
        )

    results: list[GovernedFact] = []
    for rev in revisions:
        if rev.status not in ("approved", "active"):
            raise FactResolutionError(
                f"fact revision {rev.id} has non-operational status: {rev.status}"
            )
        # Canonical fact scope semantics (mirrors AdministrationRepository.
        # candidates): organization-wide facts may ground organization- or
        # location-scoped content where otherwise valid; location-scoped facts
        # may only ground content scoped to that same location. A location-
        # scoped fact must never silently feed organization-wide content
        # (location_id=None), and mismatched locations fail closed.
        if rev.location_id is not None and rev.location_id != location_id:
            if location_id is None:
                raise FactResolutionError(
                    f"fact revision {rev.id} is location-scoped and cannot ground "
                    "organization-wide content"
                )
            raise FactResolutionError(f"fact revision {rev.id} is scoped to a different location")
        results.append(
            {
                "fact_key": rev.fact_key,
                "value": rev.value,
                "authority": rev.authority,
                "revision_id": str(rev.id),
            }
        )
    return results


CONTENT_AI_LATENCY_MS = 120_000  # 2 minutes, realistic for content generation


class ContentService:
    def __init__(self) -> None:
        self.audit = AuditEventService()
        self.audit_repository = AuditEventRepository()
        self.notifications = NotificationService()
        self.ai_gateway = build_ai_gateway()
        self.execution = ExecutionService()

    async def _audit(
        self,
        session: AsyncSession,
        *,
        event: str,
        organization_id: UUID,
        location_id: UUID | None,
        actor_id: UUID | None,
        resource_type: str,
        resource_id: UUID,
        correlation_id: str,
        summary: str,
        metadata: dict[str, object],
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=event,
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                organization_id=organization_id,
                location_id=location_id,
                product_key="content",
                resource_type=resource_type,
                resource_id=resource_id,
                correlation_id=correlation_id,
                summary=summary,
                metadata=cast(dict[str, JsonValue], metadata),
            ),
        )

    async def _notify(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        location_id: UUID | None,
        event_type: str,
        idempotency_key: str,
        context: dict[str, object],
        priority: str = "normal",
    ) -> None:
        channel, body = NOTIFICATION_TEMPLATES[event_type]
        template = await session.scalar(
            select(NotificationTemplate).where(
                NotificationTemplate.organization_id == organization_id,
                NotificationTemplate.key == event_type,
                NotificationTemplate.status == "active",
            )
        )
        if template is None:
            template = NotificationTemplate(
                organization_id=organization_id,
                key=event_type,
                version=1,
                channel=channel,
                body_template=body,
                status="active",
            )
            session.add(template)
            await session.flush()
        await self.notifications.create_event(
            session,
            organization_id=organization_id,
            template_id=template.id,
            event_type=event_type,
            idempotency_key=idempotency_key,
            context=context,
            priority=priority,
            location_id=location_id,
        )

    async def create_opportunity(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: OpportunityCreate,
        *,
        correlation_id: str,
    ) -> ContentOpportunity:
        digest = hashlib.sha256(
            f"{command.product_key}|{command.target_reference}|{command.opportunity_type}|"
            f"{command.source_reference}".encode()
        ).hexdigest()
        existing = await session.scalar(
            select(ContentOpportunity).where(
                ContentOpportunity.organization_id == organization_id,
                ContentOpportunity.evidence_hash == digest,
            )
        )
        if existing:
            return existing
        opportunity = ContentOpportunity(
            organization_id=organization_id,
            location_id=command.location_id,
            product_key=command.product_key,
            target_reference=command.target_reference,
            opportunity_type=command.opportunity_type,
            source_type=command.source_type,
            source_reference=command.source_reference,
            evidence_document=command.evidence_document,
            evidence_hash=digest,
            priority_score=command.priority_score,
            status="identified",
        )
        session.add(opportunity)
        await session.flush()
        await self._audit(
            session,
            event="content.opportunity.identified",
            organization_id=organization_id,
            location_id=command.location_id,
            actor_id=None,
            resource_type="content_opportunity",
            resource_id=opportunity.id,
            correlation_id=correlation_id,
            summary="Content opportunity identified.",
            metadata={"opportunity_type": command.opportunity_type},
        )
        return opportunity

    async def list_opportunities(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        status_filter: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContentOpportunity], bool]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ContentQueryInvalidError
        statement: Select[tuple[ContentOpportunity]] = select(ContentOpportunity).where(
            ContentOpportunity.organization_id == organization_id
        )
        if status_filter is not None:
            statement = statement.where(ContentOpportunity.status == status_filter)
        statement = statement.order_by(ContentOpportunity.priority_score.desc())
        rows = list(await session.scalars(statement.limit(limit + 1).offset(offset)))
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def decide_opportunity(
        self,
        session: AsyncSession,
        organization_id: UUID,
        opportunity_id: UUID,
        command: OpportunityDecision,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> ContentOpportunity:
        opportunity = await session.scalar(
            select(ContentOpportunity)
            .where(
                ContentOpportunity.organization_id == organization_id,
                ContentOpportunity.id == opportunity_id,
            )
            .with_for_update()
        )
        if not opportunity or opportunity.status not in {"identified", "validated"}:
            raise ContentOpportunityNotDecidableError
        opportunity.status = "accepted" if command.accept else "rejected"
        await session.flush()
        await self._audit(
            session,
            event="content.opportunity.decided",
            organization_id=organization_id,
            location_id=opportunity.location_id,
            actor_id=actor_id,
            resource_type="content_opportunity",
            resource_id=opportunity.id,
            correlation_id=correlation_id,
            summary=f"Content opportunity {opportunity.status}.",
            metadata={"accept": command.accept},
        )
        return opportunity

    async def create_item(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: ItemCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> ContentItem:
        if command.opportunity_id is not None:
            opportunity = await session.scalar(
                select(ContentOpportunity)
                .where(
                    ContentOpportunity.organization_id == organization_id,
                    ContentOpportunity.id == command.opportunity_id,
                    ContentOpportunity.status == "accepted",
                )
                .with_for_update()
            )
            if not opportunity:
                raise ContentOpportunityNotFoundError
            opportunity.status = "converted"
        item = ContentItem(
            organization_id=organization_id,
            location_id=command.location_id,
            opportunity_id=command.opportunity_id,
            content_type=command.content_type,
            title=command.title,
            slug=command.slug,
            status="briefing" if command.opportunity_id else "idea",
        )
        session.add(item)
        await session.flush()
        await self._audit(
            session,
            event="content.item.created",
            organization_id=organization_id,
            location_id=command.location_id,
            actor_id=actor_id,
            resource_type="content_item",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary=f"Content item created: {item.title}.",
            metadata={"content_type": item.content_type},
        )
        return item

    async def get_item(
        self, session: AsyncSession, organization_id: UUID, item_id: UUID
    ) -> ContentItem:
        item = await session.scalar(
            select(ContentItem).where(
                ContentItem.organization_id == organization_id, ContentItem.id == item_id
            )
        )
        if not item:
            raise ContentItemNotFoundError
        return item

    async def list_items(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        status_filter: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ContentItem], bool]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ContentQueryInvalidError
        statement: Select[tuple[ContentItem]] = select(ContentItem).where(
            ContentItem.organization_id == organization_id
        )
        if status_filter is not None:
            statement = statement.where(ContentItem.status == status_filter)
        if search:
            pattern = f"%{search.casefold()}%"
            statement = statement.where(func.lower(ContentItem.title).like(pattern))
        statement = statement.order_by(ContentItem.created_at.desc())
        rows = list(await session.scalars(statement.limit(limit + 1).offset(offset)))
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def create_brief(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
        command: BriefCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> ContentBrief:
        item = await session.scalar(
            select(ContentItem)
            .where(ContentItem.organization_id == organization_id, ContentItem.id == item_id)
            .with_for_update()
        )
        if not item:
            raise ContentItemNotFoundError
        last = await session.scalar(
            select(ContentBrief.revision_number)
            .where(ContentBrief.content_item_id == item_id)
            .order_by(ContentBrief.revision_number.desc())
            .limit(1)
        )
        brief = ContentBrief(
            organization_id=organization_id,
            content_item_id=item_id,
            revision_number=(last or 0) + 1,
            audience=command.audience,
            intent=command.intent,
            target_reference=command.target_reference,
            approved_fact_revision_ids=[str(x) for x in command.approved_fact_revision_ids],
            required_claims=command.required_claims,
            prohibited_claims=command.prohibited_claims,
            required_local_references=command.required_local_references,
            source_evidence_references=command.source_evidence_references,
            validation_requirements=command.validation_requirements,
            status="ready",
        )
        session.add(brief)
        item.status = "brief_ready"
        await session.flush()
        await self._audit(
            session,
            event="content.brief.created",
            organization_id=organization_id,
            location_id=item.location_id,
            actor_id=actor_id,
            resource_type="content_item",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary="Content brief created.",
            metadata={"brief_id": str(brief.id), "revision": brief.revision_number},
        )
        return brief

    async def list_briefs(
        self, session: AsyncSession, organization_id: UUID, item_id: UUID
    ) -> list[ContentBrief]:
        return list(
            await session.scalars(
                select(ContentBrief)
                .where(
                    ContentBrief.organization_id == organization_id,
                    ContentBrief.content_item_id == item_id,
                )
                .order_by(ContentBrief.revision_number.desc())
            )
        )

    async def create_revision(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
        command: RevisionCreate,
        user_id: UUID,
        *,
        correlation_id: str,
    ) -> ContentRevision:
        item = await session.scalar(
            select(ContentItem)
            .where(ContentItem.organization_id == organization_id, ContentItem.id == item_id)
            .with_for_update()
        )
        if not item:
            raise ContentItemNotFoundError
        validation = validate_content(
            command.body,
            command.frontmatter,
            command.prohibited_claims,
            command.approved_fact_revision_ids,
        )
        last = await session.scalar(
            select(ContentRevision.revision_number)
            .where(ContentRevision.content_item_id == item_id)
            .order_by(ContentRevision.revision_number.desc())
            .limit(1)
        )
        digest = hashlib.sha256(
            (command.body + repr(sorted(command.frontmatter.items()))).encode()
        ).hexdigest()
        revision = ContentRevision(
            organization_id=organization_id,
            content_item_id=item_id,
            revision_number=(last or 0) + 1,
            body=command.body,
            frontmatter=command.frontmatter,
            content_hash=digest,
            created_by_type=command.created_by_type,
            created_by_user_id=user_id if command.created_by_type == "user" else None,
            ai_execution_id=command.ai_execution_id,
            approved_fact_revision_ids=[str(x) for x in command.approved_fact_revision_ids],
            status="awaiting_editorial" if validation["valid"] else "validation_failed",
            validation_document=validation,
        )
        session.add(revision)
        item.status = "reviewing" if validation["valid"] else "failed"
        await session.flush()
        await self._audit(
            session,
            event="content.revision.drafted",
            organization_id=organization_id,
            location_id=item.location_id,
            actor_id=user_id if command.created_by_type == "user" else None,
            resource_type="content_item",
            resource_id=item.id,
            correlation_id=correlation_id,
            summary=f"Content revision drafted ({command.created_by_type}).",
            metadata={"revision": revision.revision_number, "valid": validation["valid"]},
        )
        if validation["valid"]:
            await self._notify(
                session,
                organization_id=organization_id,
                location_id=item.location_id,
                event_type="content.revision.awaiting_editorial",
                idempotency_key=f"content.awaiting_editorial.{revision.id}",
                context={"content_item_id": str(item.id), "revision_id": str(revision.id)},
            )
        return revision

    async def execute_ai_draft_workflow(
        self,
        session: AsyncSession,
        *,
        organization_id: UUID,
        item_id: UUID,
        brief_id: UUID,
        idempotency_key: str,
        workflow_run_id: UUID | None = None,
        user_id: UUID | None = None,
        correlation_id: str,
    ) -> tuple[ContentRevision, AIExecution]:
        """Execute the AI content draft generation as a durable workflow step.

        Called by the ``content.draft_revision`` workflow handler. Resolves
        governed business facts, calls the AI provider through the shared
        gateway, and persists the AIExecution and ContentRevision with full
        observability metadata.

        Idempotent: duplicate calls with the same *idempotency_key* return
        the already-persisted execution and revision.
        """
        item = await session.scalar(
            select(ContentItem).where(
                ContentItem.organization_id == organization_id, ContentItem.id == item_id
            )
        )
        if not item:
            raise ContentItemNotFoundError
        brief = await session.scalar(
            select(ContentBrief).where(
                ContentBrief.organization_id == organization_id,
                ContentBrief.id == brief_id,
                ContentBrief.content_item_id == item_id,
            )
        )
        if not brief:
            raise ContentBriefNotFoundError

        task = await session.scalar(
            select(AITaskDefinition).where(
                AITaskDefinition.key == AI_TASK_KEY, AITaskDefinition.status == "active"
            )
        )
        if task is None:
            task = AITaskDefinition(
                key=AI_TASK_KEY,
                version=1,
                owning_product="content",
                purpose="Draft grounded, policy-compliant content for editorial and client review.",
                input_schema={"audience": "string", "intent": "string"},
                output_schema={"draft": "string"},
                risk_level="medium",
                maximum_cost_microunits=0,
                maximum_latency_ms=CONTENT_AI_LATENCY_MS,
                requires_human_review=True,
                retention_policy_key="content.ai_draft.default",
                status="active",
            )
            session.add(task)
            await session.flush()

        fact_ids = [UUID(str(x)) for x in brief.approved_fact_revision_ids]

        # --- idempotency guard ---
        existing_execution = await session.scalar(
            select(AIExecution).where(
                AIExecution.organization_id == organization_id,
                AIExecution.idempotency_key == idempotency_key,
            )
        )
        if existing_execution is not None:
            # Resolve the previously-created revision
            revision = await session.scalar(
                select(ContentRevision).where(
                    ContentRevision.ai_execution_id == existing_execution.id,
                )
            )
            return revision or (
                await self._create_ai_revision(
                    session,
                    organization_id,
                    item,
                    brief,
                    existing_execution,
                    user_id,
                    correlation_id,
                )
            ), existing_execution

        # --- resolve governed business facts ---
        governed_facts = await resolve_governed_facts(
            session,
            organization_id,
            fact_ids,
            location_id=item.location_id,
        )

        # --- retrieve source-backed business knowledge ---
        knowledge_service = BusinessKnowledgeService()
        knowledge = await knowledge_service.retrieve_for_content(
            session,
            organization_id=organization_id,
            location_id=item.location_id,
            content_title=item.title,
            audience=brief.audience,
            intent=brief.intent,
            content_type=item.content_type,
        )

        # --- build AI input with resolved fact values and knowledge ---
        fallback = (
            f"# {item.title}\n\nContent for {brief.audience} addressing {brief.intent}. "
            "This draft requires human review before publication."
        )
        request = AIGatewayRequest(
            organization_id=organization_id,
            location_id=item.location_id,
            task_key=AI_TASK_KEY,
            input_document={
                "audience": brief.audience,
                "intent": brief.intent,
                "manual_fallback": fallback,
                "content_title": item.title,
                "content_type": item.content_type,
                "governed_facts": governed_facts,
                "knowledge": knowledge,
            },
            input_references=(brief.id,),
            approved_fact_revision_ids=tuple(fact_ids),
            maximum_cost_microunits=task.maximum_cost_microunits,
            maximum_latency_ms=task.maximum_latency_ms,
        )
        output = await self.ai_gateway.execute(request)

        # --- persist AI execution ---
        usage = output.get("usage", {}) or {}
        execution = AIExecution(
            organization_id=organization_id,
            location_id=item.location_id,
            task_definition_id=task.id,
            workflow_run_id=workflow_run_id,
            idempotency_key=idempotency_key,
            status="completed",
            provider_key=str(output.get("provider")),
            model_key=str(output.get("model")),
            input_references=[
                str(brief.id),
                *_cast_str_list(knowledge.get("source_document_ids", [])),
            ],
            approved_fact_revision_ids=[str(x) for x in fact_ids],
            output_document=output,
            output_hash=hashlib.sha256(str(output.get("draft", "")).encode()).hexdigest(),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            estimated_cost_microunits=output.get("cost_microunits"),
            latency_ms=output.get("latency_ms"),
            requires_human_review=bool(output.get("requires_human_review", True)),
            completed_at=datetime.now(UTC),
        )
        session.add(execution)
        await session.flush()

        # --- create content revision ---
        revision = await self._create_ai_revision(
            session, organization_id, item, brief, execution, user_id, correlation_id
        )
        return revision, execution

    async def _create_ai_revision(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item: ContentItem,
        brief: ContentBrief,
        execution: AIExecution,
        user_id: UUID | None,
        correlation_id: str,
    ) -> ContentRevision:
        """Create a ContentRevision from an AI execution output."""
        fact_ids = [UUID(str(x)) for x in brief.approved_fact_revision_ids]
        draft_text = str((execution.output_document or {}).get("draft", ""))
        return await self.create_revision(
            session,
            organization_id,
            item.id,
            RevisionCreate(
                body=draft_text,
                frontmatter={"title": item.title},
                created_by_type="ai",
                approved_fact_revision_ids=fact_ids,
                ai_execution_id=execution.id,
                prohibited_claims=[str(x) for x in brief.prohibited_claims],
            ),
            user_id or item.organization_id,
            correlation_id=correlation_id,
        )

    async def generate_ai_draft(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
        command: AIDraftCreate,
        user_id: UUID | None,
        *,
        correlation_id: str,
    ) -> tuple[ContentRevision, AIExecution]:
        """Generate a content draft through the shared AI Gateway.

        Routes through the configured production provider (or deterministic
        fixture in local/test). Always requires human (editorial then client)
        review before publication.
        """
        item = await session.scalar(
            select(ContentItem).where(
                ContentItem.organization_id == organization_id, ContentItem.id == item_id
            )
        )
        if not item:
            raise ContentItemNotFoundError
        brief = await session.scalar(
            select(ContentBrief).where(
                ContentBrief.organization_id == organization_id,
                ContentBrief.id == command.brief_id,
                ContentBrief.content_item_id == item_id,
            )
        )
        if not brief:
            raise ContentBriefNotFoundError

        task = await session.scalar(
            select(AITaskDefinition).where(
                AITaskDefinition.key == AI_TASK_KEY, AITaskDefinition.status == "active"
            )
        )
        if task is None:
            task = AITaskDefinition(
                key=AI_TASK_KEY,
                version=1,
                owning_product="content",
                purpose="Draft grounded, policy-compliant content for editorial and client review.",
                input_schema={"audience": "string", "intent": "string"},
                output_schema={"draft": "string"},
                risk_level="medium",
                maximum_cost_microunits=0,
                maximum_latency_ms=CONTENT_AI_LATENCY_MS,
                requires_human_review=True,
                retention_policy_key="content.ai_draft.default",
                status="active",
            )
            session.add(task)
            await session.flush()

        fact_ids = [UUID(str(x)) for x in brief.approved_fact_revision_ids]
        existing_execution = await session.scalar(
            select(AIExecution).where(
                AIExecution.organization_id == organization_id,
                AIExecution.idempotency_key == command.idempotency_key,
            )
        )
        if existing_execution is None:
            # --- resolve governed business facts ---
            governed_facts = await resolve_governed_facts(
                session,
                organization_id,
                fact_ids,
                location_id=item.location_id,
            )

            # --- retrieve source-backed business knowledge ---
            knowledge_service = BusinessKnowledgeService()
            knowledge = await knowledge_service.retrieve_for_content(
                session,
                organization_id=organization_id,
                location_id=item.location_id,
                content_title=item.title,
                audience=brief.audience,
                intent=brief.intent,
                content_type=item.content_type,
            )

            fallback = (
                f"# {item.title}\n\nContent for {brief.audience} addressing {brief.intent}. "
                "This draft requires human review before publication."
            )
            request = AIGatewayRequest(
                organization_id=organization_id,
                location_id=item.location_id,
                task_key=AI_TASK_KEY,
                input_document={
                    "audience": brief.audience,
                    "intent": brief.intent,
                    "manual_fallback": fallback,
                    "content_title": item.title,
                    "content_type": item.content_type,
                    "governed_facts": governed_facts,
                    "knowledge": knowledge,
                },
                input_references=(brief.id,),
                approved_fact_revision_ids=tuple(fact_ids),
                maximum_cost_microunits=task.maximum_cost_microunits,
                maximum_latency_ms=task.maximum_latency_ms,
            )
            output = await self.ai_gateway.execute(request)
            usage = output.get("usage", {}) or {}
            execution = AIExecution(
                organization_id=organization_id,
                location_id=item.location_id,
                task_definition_id=task.id,
                idempotency_key=command.idempotency_key,
                status="completed",
                provider_key=str(output.get("provider")),
                model_key=str(output.get("model")),
                input_references=[
                    str(brief.id),
                    *_cast_str_list(knowledge.get("source_document_ids", [])),
                ],
                approved_fact_revision_ids=[str(x) for x in fact_ids],
                output_document=output,
                output_hash=hashlib.sha256(str(output.get("draft", "")).encode()).hexdigest(),
                input_tokens=usage.get("input_tokens"),
                output_tokens=usage.get("output_tokens"),
                estimated_cost_microunits=output.get("cost_microunits"),
                latency_ms=output.get("latency_ms"),
                requires_human_review=bool(output.get("requires_human_review", True)),
                completed_at=datetime.now(UTC),
            )
            session.add(execution)
            await session.flush()
            draft_text = str(output.get("draft", ""))
        else:
            execution = existing_execution
            draft_text = str((execution.output_document or {}).get("draft", ""))

        revision = await self.create_revision(
            session,
            organization_id,
            item_id,
            RevisionCreate(
                body=draft_text,
                frontmatter={"title": item.title},
                created_by_type="ai",
                approved_fact_revision_ids=fact_ids,
                ai_execution_id=execution.id,
                prohibited_claims=[str(x) for x in brief.prohibited_claims],
            ),
            user_id or item.organization_id,
            correlation_id=correlation_id,
        )
        return revision, execution

    async def decide(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        command: ApprovalDecision,
        user_id: UUID,
        *,
        correlation_id: str,
    ) -> ContentRevision:
        revision = await session.scalar(
            select(ContentRevision)
            .where(
                ContentRevision.organization_id == organization_id,
                ContentRevision.id == revision_id,
            )
            .with_for_update()
        )
        if not revision:
            raise ContentRevisionNotFoundError
        if not command.approve:
            revision.status = "rejected"
        elif command.stage == "editorial" and revision.status == "awaiting_editorial":
            revision.editorial_approved_by = user_id
            revision.status = "awaiting_client"
            await self._notify(
                session,
                organization_id=organization_id,
                location_id=None,
                event_type="content.revision.awaiting_client",
                idempotency_key=f"content.awaiting_client.{revision.id}",
                context={"revision_id": str(revision.id)},
            )
        elif command.stage == "client" and revision.status == "awaiting_client":
            revision.client_approved_by = user_id
            revision.status = "approved"
            revision.approved_at = datetime.now(UTC)
        else:
            raise ContentApprovalStageConflictError
        await session.flush()
        await self._audit(
            session,
            event="content.revision.decided",
            organization_id=organization_id,
            location_id=None,
            actor_id=user_id,
            resource_type="content_revision",
            resource_id=revision.id,
            correlation_id=correlation_id,
            summary=f"Content revision {revision.status}.",
            metadata={"stage": command.stage, "approve": command.approve},
        )
        return revision

    async def list_revisions(
        self, session: AsyncSession, organization_id: UUID, item_id: UUID
    ) -> list[ContentRevision]:
        return list(
            await session.scalars(
                select(ContentRevision)
                .where(
                    ContentRevision.organization_id == organization_id,
                    ContentRevision.content_item_id == item_id,
                )
                .order_by(ContentRevision.revision_number.desc())
            )
        )

    async def reserve_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
        revision_id: UUID,
        command: PublicationCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> ContentPublication:
        existing = await session.scalar(
            select(ContentPublication).where(
                ContentPublication.organization_id == organization_id,
                ContentPublication.idempotency_key == command.idempotency_key,
            )
        )
        if existing:
            return existing
        revision = await session.scalar(
            select(ContentRevision).where(
                ContentRevision.organization_id == organization_id,
                ContentRevision.id == revision_id,
                ContentRevision.content_item_id == item_id,
                ContentRevision.status == "approved",
            )
        )
        target = await session.scalar(
            select(PublishingTarget).where(
                PublishingTarget.organization_id == organization_id,
                PublishingTarget.id == command.publishing_target_id,
                PublishingTarget.status == "active",
            )
        )
        if not revision:
            raise ContentPublicationRequiresApprovedRevisionError
        if not target:
            raise ContentTargetNotConfiguredError
        connection = await session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.id == target.connection_id,
                IntegrationConnection.status == "connected",
            )
        )
        if not connection:
            raise ContentTargetNotConfiguredError
        workflow_run = await self.execution.resolve_for_consumption(
            session, organization_id, command.workflow_run_id, "content.publish"
        )
        path = validate_target_path(command.target_path, target.allowed_path_prefix)
        publication = ContentPublication(
            organization_id=organization_id,
            content_item_id=item_id,
            content_revision_id=revision.id,
            publishing_target_id=target.id,
            workflow_run_id=workflow_run.id,
            idempotency_key=command.idempotency_key,
            status="reserved",
            target_path=path,
        )
        session.add(publication)
        await session.flush()
        await self._audit(
            session,
            event="content.publication.reserved",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="content_item",
            resource_id=item_id,
            correlation_id=correlation_id,
            summary="Content publication reserved.",
            metadata={"publication_id": str(publication.id), "target_path": path},
        )
        await self._notify(
            session,
            organization_id=organization_id,
            location_id=None,
            event_type="content.publication.reserved",
            idempotency_key=f"content.publication.reserved.{publication.id}",
            context={"publication_id": str(publication.id)},
        )
        return publication

    async def list_publications(
        self, session: AsyncSession, organization_id: UUID, item_id: UUID
    ) -> list[ContentPublication]:
        return list(
            await session.scalars(
                select(ContentPublication)
                .where(
                    ContentPublication.organization_id == organization_id,
                    ContentPublication.content_item_id == item_id,
                )
                .order_by(ContentPublication.created_at.desc())
            )
        )

    async def list_targets(
        self, session: AsyncSession, organization_id: UUID
    ) -> list[PublishingTarget]:
        return list(
            await session.scalars(
                select(PublishingTarget)
                .where(PublishingTarget.organization_id == organization_id)
                .order_by(PublishingTarget.key)
            )
        )

    async def list_github_connections(
        self, session: AsyncSession, organization_id: UUID
    ) -> list[IntegrationConnection]:
        """List GitHub integration connections available for publishing targets."""
        return list(
            await session.scalars(
                select(IntegrationConnection)
                .join(Provider, Provider.id == IntegrationConnection.provider_id)
                .where(
                    IntegrationConnection.organization_id == organization_id,
                    Provider.key == "github",
                    IntegrationConnection.status != "disconnected",
                )
                .order_by(IntegrationConnection.created_at.desc())
            )
        )

    async def register_github_connection(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        command: GitHubConnectionCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> IntegrationConnection:
        """Register an application-side GitHub connection for content publishing.

        The GitHub access token is an externally-obtained credential; this
        stores it encrypted-at-rest through the platform secret store and
        records the opaque ``credential_reference`` on a ``connected`` row.
        The github provider must already be seeded (platform configuration).
        """
        provider = await session.scalar(select(Provider).where(Provider.key == "github"))
        if provider is None:
            raise ContentGitHubProviderNotConfiguredError

        store = FernetSecretStore.create(session, settings)
        credential_reference = await store.put(json.dumps({"access_token": command.access_token}))

        connection = IntegrationConnection(
            organization_id=organization_id,
            provider_id=provider.id,
            external_account_reference=command.external_account_reference,
            credential_reference=credential_reference,
            status="connected",
        )
        session.add(connection)
        await session.flush()
        await self._audit(
            session,
            event="content.github_connection.registered",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="integration_connection",
            resource_id=connection.id,
            correlation_id=correlation_id,
            summary="GitHub publishing connection registered.",
            metadata={"external_account_reference": command.external_account_reference or ""},
        )
        return connection

    async def create_target(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: TargetCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> PublishingTarget:
        """Configure a repository publishing target referencing a GitHub connection."""
        connection = await session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.organization_id == organization_id,
                IntegrationConnection.id == command.connection_id,
            )
        )
        if connection is None or connection.status != "connected":
            raise ContentTargetNotConfiguredError
        target = PublishingTarget(
            organization_id=organization_id,
            connection_id=connection.id,
            key=command.key,
            target_type=command.target_type,
            repository_id=command.repository_id,
            base_branch=command.base_branch,
            allowed_path_prefix=command.allowed_path_prefix,
            deployment_target_reference=command.deployment_target_reference,
            status="active",
            version=1,
        )
        session.add(target)
        await session.flush()
        await self._audit(
            session,
            event="content.target.configured",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="publishing_target",
            resource_id=target.id,
            correlation_id=correlation_id,
            summary="Publishing target configured.",
            metadata={
                "key": command.key,
                "repository_id": command.repository_id,
                "base_branch": command.base_branch,
            },
        )
        return target

    async def summary(self, session: AsyncSession, organization_id: UUID) -> dict[str, object]:
        rows = (
            await session.execute(
                select(ContentItem.status, func.count())
                .where(ContentItem.organization_id == organization_id)
                .group_by(ContentItem.status)
            )
        ).all()
        open_opportunities = await session.scalar(
            select(func.count()).where(
                ContentOpportunity.organization_id == organization_id,
                ContentOpportunity.status.in_(("identified", "validated")),
            )
        )
        return {
            "by_status": {status: count for status, count in rows},
            "open_opportunities": int(open_opportunities or 0),
        }

    async def resource_history(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        resource_type: str,
        resource_id: UUID,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        events = await self.audit_repository.list_for_resource(
            session,
            organization_id=organization_id,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit,
        )
        return [
            {
                "id": str(event.id),
                "event_type": event.event_type,
                "action": event.action,
                "result": event.result,
                "occurred_at": event.occurred_at,
                "summary": event.summary,
                "actor_type": event.actor_type,
            }
            for event in events
        ]
