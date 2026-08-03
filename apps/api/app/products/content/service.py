"""Grounded revision, approval, and durable repository-publication intent."""

import hashlib
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.content.adapter import validate_target_path
from apps.api.app.products.content.contracts import (
    ApprovalDecision,
    PublicationCreate,
    RevisionCreate,
)
from apps.api.app.products.content.models import (
    ContentItem,
    ContentPublication,
    ContentRevision,
    PublishingTarget,
)

SECRET_PATTERN = re.compile(r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]")


def validate_content(
    body: str, frontmatter: dict[str, object], prohibited_claims: list[str], fact_ids: list[UUID]
) -> dict[str, object]:
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
    async def create_revision(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
        command: RevisionCreate,
        user_id: UUID,
    ) -> ContentRevision:
        item = await session.scalar(
            select(ContentItem)
            .where(ContentItem.organization_id == organization_id, ContentItem.id == item_id)
            .with_for_update()
        )
        if not item:
            raise LookupError("content item not found")
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
        return revision

    async def decide(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        command: ApprovalDecision,
        user_id: UUID,
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
            raise LookupError("content revision not found")
        if not command.approve:
            revision.status = "rejected"
        elif command.stage == "editorial" and revision.status == "awaiting_editorial":
            revision.editorial_approved_by = user_id
            revision.status = "awaiting_client"
        elif command.stage == "client" and revision.status == "awaiting_client":
            revision.client_approved_by = user_id
            revision.status = "approved"
            revision.approved_at = datetime.now(UTC)
        else:
            raise ValueError("approval stage conflict")
        await session.flush()
        return revision

    async def reserve_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        item_id: UUID,
        revision_id: UUID,
        command: PublicationCreate,
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
        if not revision or not target:
            raise ValueError("approved revision and active target required")
        path = validate_target_path(command.target_path, target.allowed_path_prefix)
        publication = ContentPublication(
            organization_id=organization_id,
            content_item_id=item_id,
            content_revision_id=revision.id,
            publishing_target_id=target.id,
            workflow_run_id=command.workflow_run_id,
            idempotency_key=command.idempotency_key,
            status="reserved",
            target_path=path,
        )
        session.add(publication)
        await session.flush()
        return publication
