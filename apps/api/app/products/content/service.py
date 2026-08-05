"""Governed content opportunities, briefs, grounded revisions, approval, and publication intent."""

import hashlib
import re
from datetime import UTC, datetime
from typing import TypedDict, cast
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.ai.gateway import AIGateway, AIGatewayRequest, DeterministicAIProvider
from apps.api.app.ai.models import AIExecution, AITaskDefinition
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.repository import AuditEventRepository
from apps.api.app.audit.service import AuditEventService
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.notifications.models import NotificationTemplate
from apps.api.app.notifications.service import NotificationService
from apps.api.app.products.content.adapter import validate_target_path
from apps.api.app.products.content.contracts import (
    AIDraftCreate,
    ApprovalDecision,
    BriefCreate,
    ItemCreate,
    OpportunityCreate,
    OpportunityDecision,
    PublicationCreate,
    RevisionCreate,
)
from apps.api.app.products.content.errors import (
    ContentApprovalStageConflictError,
    ContentBriefNotFoundError,
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


class ContentService:
    def __init__(self) -> None:
        self.audit = AuditEventService()
        self.audit_repository = AuditEventRepository()
        self.notifications = NotificationService()
        self.ai_gateway = AIGateway(DeterministicAIProvider())
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

        Uses the gateway's deterministic, always-safe fallback provider — a real,
        governed execution path requiring human (editorial then client) review,
        not a live large-language-model integration.
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
                maximum_latency_ms=5_000,
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
                },
                input_references=(brief.id,),
                approved_fact_revision_ids=tuple(fact_ids),
                maximum_cost_microunits=task.maximum_cost_microunits,
                maximum_latency_ms=task.maximum_latency_ms,
            )
            output = await self.ai_gateway.execute(request)
            execution = AIExecution(
                organization_id=organization_id,
                location_id=item.location_id,
                task_definition_id=task.id,
                idempotency_key=command.idempotency_key,
                status="completed",
                provider_key=str(output.get("provider")),
                model_key=str(output.get("model")),
                input_references=[str(brief.id)],
                approved_fact_revision_ids=[str(x) for x in fact_ids],
                output_document=output,
                output_hash=hashlib.sha256(str(output.get("draft", "")).encode()).hexdigest(),
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
        self, session: AsyncSession, *, resource_type: str, resource_id: UUID, limit: int = 50
    ) -> list[dict[str, object]]:
        events = await self.audit_repository.list_for_resource(
            session, resource_type=resource_type, resource_id=resource_id, limit=limit
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
