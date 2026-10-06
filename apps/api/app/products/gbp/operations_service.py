"""Governed GBP capability, hours, media, posts, and suspension-case service."""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.repository import AuditEventRepository
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.execution.models import Job, JobAttempt, WorkflowRun
from apps.api.app.execution.service import ExecutionService
from apps.api.app.integrations.errors import IntegrationReconnectRequiredError
from apps.api.app.notifications.models import NotificationTemplate
from apps.api.app.notifications.service import NotificationService
from apps.api.app.products.gbp.media_upload import ImageFacts
from apps.api.app.products.gbp.models import GBPLocation, GBPProfileSnapshot
from apps.api.app.products.gbp.operations import (
    Capability,
    completeness,
    conflicts,
    require_capability,
)
from apps.api.app.products.gbp.operations import validate_hours as validate_hours_periods
from apps.api.app.products.gbp.operations_contracts import (
    ChangeSetPropose,
    MediaDecision,
    MediaUploadPropose,
    PostRevisionCreate,
    SpecialHoursPropose,
    SuspensionCaseReport,
)
from apps.api.app.products.gbp.operations_errors import (
    GBPCapabilitySnapshotNotFoundError,
    GBPCapabilityUnavailableError,
    GBPChangeSetNotDecidableError,
    GBPInvalidHoursError,
    GBPLocationNotFoundError,
    GBPLocationNotWriteEnabledError,
    GBPMediaNotFoundError,
    GBPMediaNotPublishEligibleError,
    GBPPostNotPublishEligibleError,
    GBPPostPublicationExistsError,
    GBPPostPublicationNotActionableError,
    GBPPostRevisionNotFoundError,
    GBPSpecialHoursNotFoundError,
)
from apps.api.app.products.gbp.operations_models import (
    GBPCapabilitySnapshot,
    GBPChangeSet,
    GBPMedia,
    GBPPostPublication,
    GBPPostRevision,
    GBPProviderPost,
    GBPSpecialHours,
    GBPSuspensionCase,
)
from apps.api.app.products.gbp.post_generation_models import GBPPostAsset
from apps.api.app.storage.objects import GBP_MEDIA_BUCKET, ObjectStorage

NOTIFICATION_TEMPLATES = {
    "gbp.suspension_case.reported": ("in_app", "A Business Profile suspension case was reported."),
    "gbp.change_set.awaiting_approval": ("in_app", "A Business Profile change set needs approval."),
}

PRE_DISPATCH_SAFE_ERRORS = frozenset(
    {
        "NO_CONNECTED_INTEGRATION",
        "TOKEN_REFRESH_FAILED",
        "SECRET_RESOLUTION_FAILED",
        "TOKEN_RESOLUTION_FAILED",
        "POST_MEDIA_URL_UNAVAILABLE",
    }
)
LEGACY_PRE_DISPATCH_FOLLOWUP_ERRORS = PRE_DISPATCH_SAFE_ERRORS | {"AMBIGUOUS_PROVIDER_RESULT"}
ACTIVE_JOB_STATUSES = ("queued", "claimed", "running", "retry_scheduled")

# An ambiguous write is only judged once Google has had time to list the new post.
AMBIGUOUS_POST_REREAD_DELAY = timedelta(minutes=5)
AMBIGUOUS_POST_CODES = frozenset(
    {
        "PROVIDER_WRITE_AMBIGUOUS",
        "PROVIDER_RETURNED_NO_RESOURCE_NAME",
        "AMBIGUOUS_PROVIDER_RESULT",
    }
)
POST_NOT_ON_GOOGLE = "POST_NOT_ON_GOOGLE"
POST_REPOSTED = "REPOSTED_AS_NEW_REVISION"
POST_DISCARDED = "DISCARDED_BY_OPERATOR"
# Typed codes a publish run is settled with once its post is retired (see settle_publication_run).
GBP_POST_NOT_PUBLISHED = "GBP_POST_NOT_PUBLISHED"
GBP_POST_DISCARDED = "GBP_POST_DISCARDED"
GBP_POST_REPOSTED = "GBP_POST_REPOSTED"


def settlement_code(status: str, safe_error_code: str | None) -> str | None:
    """The run-settlement code for a retired publication, or None when it is still live."""
    if status == "not_published":
        return GBP_POST_NOT_PUBLISHED
    if status == "discarded":
        return GBP_POST_REPOSTED if safe_error_code == POST_REPOSTED else GBP_POST_DISCARDED
    return None


@dataclass(frozen=True, slots=True)
class GBPPostRevisionReadModel:
    revision: GBPPostRevision
    publication: GBPPostPublication | None
    recovery_allowed: bool


@dataclass(frozen=True, slots=True)
class GBPPostRecoveryResult:
    accepted: bool
    publication: GBPPostPublication
    recovery_mode: str | None = None
    denial_code: str | None = None


def _canonical_hash(value: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _capabilities_from_document(document: dict[str, object]) -> dict[str, Capability]:
    result: dict[str, Capability] = {}
    for key, raw in document.items():
        if not isinstance(raw, dict):
            continue
        result[key] = Capability(
            key=key,
            readable=bool(raw.get("readable", False)),
            writable=bool(raw.get("writable", False)),
            reason=cast(str | None, raw.get("reason")),
        )
    return result


class GBPOperationsService:
    def __init__(self) -> None:
        self.audit = AuditEventService()
        self.audit_repository = AuditEventRepository()
        self.notifications = NotificationService()
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
        result: AuditResult = AuditResult.SUCCEEDED,
    ) -> None:
        await self.audit.record(
            session,
            AuditEventCreate(
                event_type=event,
                action=event,
                result=result,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                organization_id=organization_id,
                location_id=location_id,
                product_key="gbp",
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

    async def _get_gbp_location(
        self, session: AsyncSession, organization_id: UUID, gbp_location_id: UUID
    ) -> GBPLocation:
        location = await session.scalar(
            select(GBPLocation).where(
                GBPLocation.organization_id == organization_id, GBPLocation.id == gbp_location_id
            )
        )
        if not location:
            raise GBPLocationNotFoundError
        return location

    async def latest_capability_snapshot(
        self, session: AsyncSession, organization_id: UUID, gbp_location_id: UUID
    ) -> GBPCapabilitySnapshot:
        snapshot = await session.scalar(
            select(GBPCapabilitySnapshot)
            .where(
                GBPCapabilitySnapshot.organization_id == organization_id,
                GBPCapabilitySnapshot.gbp_location_id == gbp_location_id,
            )
            .order_by(GBPCapabilitySnapshot.observed_at.desc())
            .limit(1)
        )
        if not snapshot:
            raise GBPCapabilitySnapshotNotFoundError
        return snapshot

    async def record_capability_snapshot(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        capabilities: dict[str, object],
        observed_at: datetime,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> GBPCapabilitySnapshot:
        await self._get_gbp_location(session, organization_id, gbp_location_id)
        digest = _canonical_hash(capabilities)
        existing = await session.scalar(
            select(GBPCapabilitySnapshot).where(
                GBPCapabilitySnapshot.gbp_location_id == gbp_location_id,
                GBPCapabilitySnapshot.content_hash == digest,
            )
        )
        if existing:
            return existing
        snapshot = GBPCapabilitySnapshot(
            organization_id=organization_id,
            gbp_location_id=gbp_location_id,
            capabilities=capabilities,
            content_hash=digest,
            observed_at=observed_at,
        )
        session.add(snapshot)
        await session.flush()
        await self._audit(
            session,
            event="gbp.capability_snapshot.recorded",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="gbp_location",
            resource_id=gbp_location_id,
            correlation_id=correlation_id,
            summary="GBP capability snapshot recorded.",
            metadata={"snapshot_id": str(snapshot.id)},
        )
        return snapshot

    async def propose_change_set(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        command: ChangeSetPropose,
        idempotency_key: str,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> GBPChangeSet:
        snapshot = await self.latest_capability_snapshot(session, organization_id, gbp_location_id)
        try:
            require_capability(
                _capabilities_from_document(snapshot.capabilities),
                command.capability_key,
                write=True,
            )
        except ValueError as error:
            raise GBPCapabilityUnavailableError from error
        existing = await session.scalar(
            select(GBPChangeSet).where(
                GBPChangeSet.organization_id == organization_id,
                GBPChangeSet.idempotency_key == idempotency_key,
            )
        )
        if existing:
            return existing
        last = await session.scalar(
            select(GBPChangeSet.revision)
            .where(GBPChangeSet.gbp_location_id == gbp_location_id)
            .order_by(GBPChangeSet.revision.desc())
            .limit(1)
        )
        change_set = GBPChangeSet(
            organization_id=organization_id,
            gbp_location_id=gbp_location_id,
            capability_snapshot_id=snapshot.id,
            idempotency_key=idempotency_key,
            revision=(last or 0) + 1,
            field_changes=command.field_changes,
            evidence=command.evidence,
            risk=command.risk,
            status="awaiting_approval",
        )
        session.add(change_set)
        await session.flush()
        await self._audit(
            session,
            event="gbp.change_set.proposed",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="gbp_location",
            resource_id=gbp_location_id,
            correlation_id=correlation_id,
            summary=f"GBP change set proposed for {command.capability_key}.",
            metadata={
                "capability_key": command.capability_key,
                "change_set_id": str(change_set.id),
            },
        )
        await self._notify(
            session,
            organization_id=organization_id,
            location_id=None,
            event_type="gbp.change_set.awaiting_approval",
            idempotency_key=f"gbp.change_set.awaiting.{change_set.id}",
            context={"change_set_id": str(change_set.id)},
        )
        return change_set

    async def decide_change_set(
        self,
        session: AsyncSession,
        organization_id: UUID,
        change_set_id: UUID,
        approve: bool,
        user_id: UUID,
        *,
        correlation_id: str,
    ) -> GBPChangeSet:
        change_set = await session.scalar(
            select(GBPChangeSet)
            .where(
                GBPChangeSet.organization_id == organization_id, GBPChangeSet.id == change_set_id
            )
            .with_for_update()
        )
        if not change_set or change_set.status != "awaiting_approval":
            raise GBPChangeSetNotDecidableError
        change_set.status = "approved" if approve else "rejected"
        await session.flush()
        await self._audit(
            session,
            event="gbp.change_set.decided",
            organization_id=organization_id,
            location_id=None,
            actor_id=user_id,
            resource_type="gbp_location",
            resource_id=change_set.gbp_location_id,
            correlation_id=correlation_id,
            summary=f"GBP change set {change_set.status}.",
            metadata={"approve": approve, "change_set_id": str(change_set.id)},
        )
        return change_set

    async def list_change_sets(
        self, session: AsyncSession, organization_id: UUID, gbp_location_id: UUID
    ) -> list[GBPChangeSet]:
        return list(
            await session.scalars(
                select(GBPChangeSet)
                .where(
                    GBPChangeSet.organization_id == organization_id,
                    GBPChangeSet.gbp_location_id == gbp_location_id,
                )
                .order_by(GBPChangeSet.revision.desc())
            )
        )

    async def propose_special_hours(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        command: SpecialHoursPropose,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> GBPSpecialHours:
        await self._get_gbp_location(session, organization_id, gbp_location_id)
        periods: list[tuple[date, time, time]] = [
            (
                command.service_date,
                time.fromisoformat(period.opens),
                time.fromisoformat(period.closes),
            )
            for period in command.periods
        ]
        if command.closed == bool(command.periods):
            # Closed all day carries no periods; open hours need at least one.
            raise GBPInvalidHoursError
        try:
            validate_hours_periods(periods)
        except ValueError as error:
            raise GBPInvalidHoursError from error
        last = await session.scalar(
            select(GBPSpecialHours.revision)
            .where(
                GBPSpecialHours.gbp_location_id == gbp_location_id,
                GBPSpecialHours.service_date == command.service_date,
            )
            .order_by(GBPSpecialHours.revision.desc())
            .limit(1)
        )
        record = GBPSpecialHours(
            organization_id=organization_id,
            gbp_location_id=gbp_location_id,
            service_date=command.service_date,
            revision=(last or 0) + 1,
            periods=[period.model_dump() for period in command.periods],
            closed=command.closed,
            source=command.source,
            status="awaiting_approval",
        )
        session.add(record)
        await session.flush()
        await self._audit(
            session,
            event="gbp.special_hours.proposed",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="gbp_location",
            resource_id=gbp_location_id,
            correlation_id=correlation_id,
            summary=f"Special hours proposed for {command.service_date.isoformat()}.",
            metadata={"revision": record.revision, "closed": record.closed},
        )
        return record

    async def decide_special_hours(
        self,
        session: AsyncSession,
        organization_id: UUID,
        special_hours_id: UUID,
        approve: bool,
        user_id: UUID,
        *,
        correlation_id: str,
    ) -> GBPSpecialHours:
        record = await session.scalar(
            select(GBPSpecialHours)
            .where(
                GBPSpecialHours.organization_id == organization_id,
                GBPSpecialHours.id == special_hours_id,
            )
            .with_for_update()
        )
        if not record:
            raise GBPSpecialHoursNotFoundError
        record.status = "approved" if approve else "rejected"
        await session.flush()
        await self._audit(
            session,
            event="gbp.special_hours.decided",
            organization_id=organization_id,
            location_id=None,
            actor_id=user_id,
            resource_type="gbp_location",
            resource_id=record.gbp_location_id,
            correlation_id=correlation_id,
            summary=f"Special hours {record.status}.",
            metadata={"revision": record.revision},
        )
        return record

    async def list_special_hours(
        self, session: AsyncSession, organization_id: UUID, gbp_location_id: UUID
    ) -> list[GBPSpecialHours]:
        return list(
            await session.scalars(
                select(GBPSpecialHours)
                .where(
                    GBPSpecialHours.organization_id == organization_id,
                    GBPSpecialHours.gbp_location_id == gbp_location_id,
                )
                .order_by(GBPSpecialHours.service_date.desc())
            )
        )

    async def propose_media_upload(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        command: MediaUploadPropose,
        image: ImageFacts,
        data: bytes,
        storage: ObjectStorage,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> GBPMedia:
        """Store an uploaded photo privately and record it as awaiting approval."""
        await self._get_gbp_location(session, organization_id, gbp_location_id)
        existing = await session.scalar(
            select(GBPMedia).where(
                GBPMedia.organization_id == organization_id,
                GBPMedia.idempotency_key == command.idempotency_key,
            )
        )
        if existing:
            return existing
        media_id = uuid4()
        path = f"{organization_id}/{gbp_location_id}/{media_id}.{image.extension}"
        await storage.put(GBP_MEDIA_BUCKET, path, data, image.content_type)
        media = GBPMedia(
            id=media_id,
            organization_id=organization_id,
            gbp_location_id=gbp_location_id,
            media_type=command.media_type,
            source_reference=None,
            storage_bucket=GBP_MEDIA_BUCKET,
            storage_path=path,
            content_type=image.content_type,
            byte_size=image.byte_size,
            width=image.width,
            height=image.height,
            rights_authority=command.rights_authority,
            idempotency_key=command.idempotency_key,
            status="awaiting_approval",
        )
        try:
            session.add(media)
            await session.flush()
        except Exception:
            await storage.delete(GBP_MEDIA_BUCKET, path)
            raise
        await self._audit(
            session,
            event="gbp.media.proposed",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="gbp_location",
            resource_id=gbp_location_id,
            correlation_id=correlation_id,
            summary=f"Photo uploaded: {command.media_type}.",
            metadata={
                "media_id": str(media.id),
                "source": "upload",
                "byte_size": image.byte_size,
            },
        )
        return media

    async def list_media(
        self, session: AsyncSession, organization_id: UUID, gbp_location_id: UUID
    ) -> list[GBPMedia]:
        return list(
            await session.scalars(
                select(GBPMedia).where(
                    GBPMedia.organization_id == organization_id,
                    GBPMedia.gbp_location_id == gbp_location_id,
                )
            )
        )

    async def get_media(
        self, session: AsyncSession, organization_id: UUID, media_id: UUID
    ) -> GBPMedia:
        media = await session.scalar(
            select(GBPMedia).where(
                GBPMedia.organization_id == organization_id, GBPMedia.id == media_id
            )
        )
        if not media:
            raise GBPMediaNotFoundError
        return media

    async def decide_media(
        self,
        session: AsyncSession,
        organization_id: UUID,
        media_id: UUID,
        command: MediaDecision,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> GBPMedia:
        media = await self.get_media(session, organization_id, media_id)
        if media.status != "awaiting_approval":
            raise GBPMediaNotPublishEligibleError
        media.status = "approved" if command.approve else "rejected"
        await session.flush()
        await self._audit(
            session,
            event="gbp.media.decided",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="gbp_media",
            resource_id=media.id,
            correlation_id=correlation_id,
            summary=f"Media {'approved' if command.approve else 'rejected'}.",
            metadata={"media_type": media.media_type},
        )
        return media

    async def reserve_media_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        media_id: UUID,
        workflow_run_id: UUID,
        idempotency_key: str,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> GBPMedia:
        media = await self.get_media(session, organization_id, media_id)
        if media.status != "approved":
            raise GBPMediaNotPublishEligibleError
        location = await self._get_gbp_location(session, organization_id, media.gbp_location_id)
        if not location.write_enabled or location.mapping_status != "confirmed":
            raise GBPLocationNotWriteEnabledError
        workflow_run = await self.execution.resolve_for_consumption(
            session, organization_id, workflow_run_id, "gbp.upload_media"
        )
        media.status = "publishing"
        await session.flush()
        workflow_run.input_document = {
            **(workflow_run.input_document or {}),
            "media_id": str(media.id),
        }
        await self._audit(
            session,
            event="gbp.media.publication_reserved",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="gbp_media",
            resource_id=media.id,
            correlation_id=correlation_id,
            summary="GBP media publication reserved.",
            metadata={"media_type": media.media_type},
        )
        await self.execution.enqueue_consumed_run(session, workflow_run)
        return media

    async def create_post_revision(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        command: PostRevisionCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> GBPPostRevision:
        await self._get_gbp_location(session, organization_id, gbp_location_id)
        post_key = command.post_key or uuid4()
        last = await session.scalar(
            select(GBPPostRevision.revision)
            .where(GBPPostRevision.post_key == post_key)
            .order_by(GBPPostRevision.revision.desc())
            .limit(1)
        )
        revision = GBPPostRevision(
            organization_id=organization_id,
            gbp_location_id=gbp_location_id,
            post_key=post_key,
            revision=(last or 0) + 1,
            post_type=command.post_type,
            content=command.content,
            call_to_action=command.call_to_action,
            event_or_offer=command.event_or_offer,
            status="awaiting_approval",
            created_at=datetime.now(UTC),
        )
        session.add(revision)
        await session.flush()
        await self._audit(
            session,
            event="gbp.post.drafted",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="gbp_post_revision",
            resource_id=revision.id,
            correlation_id=correlation_id,
            summary=f"GBP post drafted ({command.post_type}).",
            metadata={"revision": revision.revision},
        )
        return revision

    async def decide_post_revision(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        approve: bool,
        user_id: UUID,
        *,
        correlation_id: str,
    ) -> GBPPostRevision:
        revision = await session.scalar(
            select(GBPPostRevision)
            .where(
                GBPPostRevision.organization_id == organization_id,
                GBPPostRevision.id == revision_id,
            )
            .with_for_update()
        )
        if not revision:
            raise GBPPostRevisionNotFoundError
        revision.status = "approved" if approve else "rejected"
        await session.flush()
        await self._audit(
            session,
            event="gbp.post.decided",
            organization_id=organization_id,
            location_id=None,
            actor_id=user_id,
            resource_type="gbp_post_revision",
            resource_id=revision.id,
            correlation_id=correlation_id,
            summary=f"GBP post {revision.status}.",
            metadata={"approve": approve},
        )
        return revision

    async def reserve_post_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        revision_id: UUID,
        workflow_run_id: UUID,
        idempotency_key: str,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> GBPPostPublication:
        revision = await session.scalar(
            select(GBPPostRevision)
            .where(
                GBPPostRevision.organization_id == organization_id,
                GBPPostRevision.id == revision_id,
                GBPPostRevision.status == "approved",
            )
            .with_for_update()
        )
        if not revision:
            raise GBPPostNotPublishEligibleError
        existing = await session.scalar(
            select(GBPPostPublication).where(
                GBPPostPublication.organization_id == organization_id,
                GBPPostPublication.post_revision_id == revision_id,
            )
        )
        if existing:
            if existing.idempotency_key == idempotency_key:
                return existing
            raise GBPPostPublicationExistsError
        location = await self._get_gbp_location(session, organization_id, revision.gbp_location_id)
        if not location.write_enabled or location.mapping_status != "confirmed":
            raise GBPLocationNotWriteEnabledError
        workflow_run = await self.execution.resolve_for_consumption(
            session, organization_id, workflow_run_id, "gbp.publish_post"
        )
        publication = GBPPostPublication(
            organization_id=organization_id,
            post_revision_id=revision.id,
            workflow_run_id=workflow_run.id,
            idempotency_key=idempotency_key,
            status="reserved",
        )
        session.add(publication)
        await session.flush()
        workflow_run.input_document = {
            **(workflow_run.input_document or {}),
            "publication_id": str(publication.id),
        }
        await self._audit(
            session,
            event="gbp.post.publication_reserved",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="gbp_post_revision",
            resource_id=revision.id,
            correlation_id=correlation_id,
            summary="GBP post publication reserved.",
            metadata={"publication_id": str(publication.id)},
        )
        await self.execution.enqueue_consumed_run(session, workflow_run)
        return publication

    async def _has_active_publication_job(
        self,
        session: AsyncSession,
        organization_id: UUID,
        workflow_run_id: UUID,
    ) -> bool:
        return (
            await session.scalar(
                select(Job.id)
                .where(
                    Job.organization_id == organization_id,
                    Job.workflow_run_id == workflow_run_id,
                    Job.status.in_(ACTIVE_JOB_STATUSES),
                )
                .limit(1)
            )
        ) is not None

    async def _legacy_pre_dispatch_failure_is_proven(
        self,
        session: AsyncSession,
        publication: GBPPostPublication,
    ) -> bool:
        attempts = list(
            await session.scalars(
                select(JobAttempt)
                .join(
                    Job,
                    (Job.organization_id == JobAttempt.organization_id)
                    & (Job.id == JobAttempt.job_id),
                )
                .where(
                    Job.organization_id == publication.organization_id,
                    Job.workflow_run_id == publication.workflow_run_id,
                )
                .order_by(JobAttempt.started_at, JobAttempt.attempt_number)
            )
        )
        if not attempts or attempts[0].safe_error not in PRE_DISPATCH_SAFE_ERRORS:
            return False
        return all(
            attempt.completed_at is not None
            and attempt.safe_error in LEGACY_PRE_DISPATCH_FOLLOWUP_ERRORS
            for attempt in attempts
        )

    async def _publication_recovery_allowed(
        self,
        session: AsyncSession,
        publication: GBPPostPublication,
    ) -> bool:
        if publication.status not in {"reserved", "failed", "reconciliation_required"}:
            return False
        if await self._has_active_publication_job(
            session, publication.organization_id, publication.workflow_run_id
        ):
            return False
        if publication.provider_post_id:
            return publication.status == "reconciliation_required"
        if publication.dispatched_at is not None:
            return False
        if (
            publication.status == "reserved"
            and publication.safe_error_code in PRE_DISPATCH_SAFE_ERRORS
        ):
            return True
        return await self._legacy_pre_dispatch_failure_is_proven(session, publication)

    async def list_post_revision_read_models(
        self, session: AsyncSession, organization_id: UUID, gbp_location_id: UUID
    ) -> list[GBPPostRevisionReadModel]:
        revisions = list(
            await session.scalars(
                select(GBPPostRevision)
                .where(
                    GBPPostRevision.organization_id == organization_id,
                    GBPPostRevision.gbp_location_id == gbp_location_id,
                )
                .order_by(GBPPostRevision.created_at.desc())
            )
        )
        if not revisions:
            return []
        publications = list(
            await session.scalars(
                select(GBPPostPublication)
                .where(
                    GBPPostPublication.organization_id == organization_id,
                    GBPPostPublication.post_revision_id.in_(
                        [revision.id for revision in revisions]
                    ),
                )
                .order_by(GBPPostPublication.created_at.desc())
            )
        )
        publication_by_revision: dict[UUID, GBPPostPublication] = {}
        for candidate in publications:
            publication_by_revision.setdefault(candidate.post_revision_id, candidate)
        read_models: list[GBPPostRevisionReadModel] = []
        for revision in revisions:
            publication = publication_by_revision.get(revision.id)
            read_models.append(
                GBPPostRevisionReadModel(
                    revision=revision,
                    publication=publication,
                    recovery_allowed=(
                        await self._publication_recovery_allowed(session, publication)
                        if publication is not None
                        else False
                    ),
                )
            )
        return read_models

    async def _scoped_post_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        publication_id: UUID,
        *,
        for_update: bool = False,
    ) -> tuple[GBPPostPublication, GBPPostRevision] | None:
        statement = (
            select(GBPPostPublication, GBPPostRevision)
            .join(
                GBPPostRevision,
                (GBPPostRevision.organization_id == GBPPostPublication.organization_id)
                & (GBPPostRevision.id == GBPPostPublication.post_revision_id),
            )
            .join(
                GBPLocation,
                (GBPLocation.organization_id == GBPPostRevision.organization_id)
                & (GBPLocation.id == GBPPostRevision.gbp_location_id),
            )
            .where(
                GBPPostPublication.organization_id == organization_id,
                GBPPostPublication.id == publication_id,
                GBPLocation.location_id == location_id,
            )
        )
        if for_update:
            statement = statement.with_for_update(of=GBPPostPublication)
        row = (await session.execute(statement)).one_or_none()
        if row is None:
            return None
        return row[0], row[1]

    @staticmethod
    def _provider_post_matches_publication(
        provider_post: GBPProviderPost,
        revision: GBPPostRevision,
        publication: GBPPostPublication,
    ) -> bool:
        if publication.dispatched_at is None:
            return False
        raw_created_at = provider_post.provider_payload.get("createTime")
        if not isinstance(raw_created_at, str):
            return False
        try:
            created_at = datetime.fromisoformat(raw_created_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        if created_at.tzinfo is None:
            return False
        dispatch_delta = created_at.astimezone(UTC) - publication.dispatched_at.astimezone(UTC)
        return (
            -timedelta(seconds=30) <= dispatch_delta <= timedelta(minutes=10)
            and provider_post.status == "present"
            and (provider_post.summary or "").strip() == revision.content.strip()
            and (provider_post.post_type or "").upper() == revision.post_type.upper()
        )

    async def recover_post_publication(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        location_id: UUID,
        publication_id: UUID,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> GBPPostRecoveryResult:
        """Reconcile first, then resume only from durable duplicate-safe evidence."""
        scoped = await self._scoped_post_publication(
            session, organization_id, location_id, publication_id
        )
        if scoped is None:
            raise GBPPostRevisionNotFoundError
        publication, revision = scoped

        # Provider reconciliation remains the canonical read path and precedes
        # every recovery decision, including a provably pre-dispatch retry.
        from apps.api.app.products.gbp.discovery_service import GBPDiscoveryService

        await GBPDiscoveryService().reconcile_local_posts(
            session,
            settings,
            organization_id,
            revision.gbp_location_id,
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

        scoped = await self._scoped_post_publication(
            session,
            organization_id,
            location_id,
            publication_id,
            for_update=True,
        )
        if scoped is None:
            raise GBPPostRevisionNotFoundError
        publication, revision = scoped

        recovery_mode: str | None = None
        denial_code: str | None = None
        if publication.provider_post_id:
            if publication.status == "reconciliation_required":
                recovery_mode = "provider_identity"
            else:
                denial_code = "PUBLICATION_NOT_RECOVERABLE"
        elif await self._publication_recovery_allowed(session, publication):
            publication.status = "reserved"
            publication.safe_error_code = None
            recovery_mode = "pre_dispatch"
        else:
            provider_posts = list(
                await session.scalars(
                    select(GBPProviderPost).where(
                        GBPProviderPost.organization_id == organization_id,
                        GBPProviderPost.gbp_location_id == revision.gbp_location_id,
                    )
                )
            )
            matching_posts = [
                post
                for post in provider_posts
                if self._provider_post_matches_publication(post, revision, publication)
            ]
            if len(matching_posts) == 1:
                publication.provider_post_id = matching_posts[0].provider_post_name
                publication.status = "reconciliation_required"
                publication.safe_error_code = "POST_RECOVERY_PROVIDER_MATCHED"
                recovery_mode = "provider_match"
            elif len(matching_posts) > 1:
                denial_code = "AMBIGUOUS_PROVIDER_MATCH"
            else:
                denial_code = "AMBIGUOUS_PROVIDER_RESULT"

        if recovery_mode is None:
            if publication.status in {"reserved", "dispatched", "reconciliation_required"}:
                publication.status = "reconciliation_required"
                publication.safe_error_code = denial_code
            await self._audit(
                session,
                event="gbp.post.publication_recovery_denied",
                organization_id=organization_id,
                location_id=location_id,
                actor_id=actor_id,
                resource_type="gbp_post_publication",
                resource_id=publication.id,
                correlation_id=correlation_id,
                summary="GBP post publication recovery remained in operator attention.",
                metadata={"reason": denial_code or "PUBLICATION_NOT_RECOVERABLE"},
                result=AuditResult.FAILED,
            )
            return GBPPostRecoveryResult(
                accepted=False,
                publication=publication,
                denial_code=denial_code or "PUBLICATION_NOT_RECOVERABLE",
            )

        await self.execution.enqueue_recovery_run(
            session,
            organization_id,
            publication.workflow_run_id,
            recovery_reference=f"gbp-post-publication:{publication.id}",
            actor_id=actor_id,
            correlation_id=correlation_id,
        )
        await self._audit(
            session,
            event="gbp.post.publication_recovery_enqueued",
            organization_id=organization_id,
            location_id=location_id,
            actor_id=actor_id,
            resource_type="gbp_post_publication",
            resource_id=publication.id,
            correlation_id=correlation_id,
            summary="GBP post publication recovery enqueued.",
            metadata={"recovery_mode": recovery_mode},
        )
        return GBPPostRecoveryResult(
            accepted=True,
            publication=publication,
            recovery_mode=recovery_mode,
        )

    async def ambiguous_post_publication_ids(
        self, session: AsyncSession, *, limit: int = 50
    ) -> list[tuple[UUID, UUID]]:
        """Publications whose Google result is still unknown and old enough to re-read."""
        rows = await session.execute(
            select(GBPPostPublication.organization_id, GBPPostPublication.id)
            .where(
                GBPPostPublication.status == "reconciliation_required",
                GBPPostPublication.safe_error_code.in_(AMBIGUOUS_POST_CODES),
                GBPPostPublication.provider_post_id.is_(None),
                GBPPostPublication.dispatched_at.is_not(None),
                GBPPostPublication.dispatched_at <= datetime.now(UTC) - AMBIGUOUS_POST_REREAD_DELAY,
            )
            .order_by(GBPPostPublication.dispatched_at)
            .limit(limit)
        )
        return [(row[0], row[1]) for row in rows.all()]

    async def auto_reconcile_ambiguous_post(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        publication_id: UUID,
    ) -> str:
        """Re-read Google for one ambiguous post and settle it, without a person.

        Exactly one matching post: the post is on Google, so the publication resumes
        and verifies it. No matching post: it is `not_published`. Several matches, or
        Google cannot be read: it stays for a person, with a plain reason code. Only an
        ambiguous publication is touched, so running this twice is a no-op.
        """
        correlation_id = f"gbp.post.auto_reconcile:{publication_id}"
        publication = await session.scalar(
            select(GBPPostPublication)
            .where(
                GBPPostPublication.organization_id == organization_id,
                GBPPostPublication.id == publication_id,
                GBPPostPublication.status == "reconciliation_required",
                GBPPostPublication.safe_error_code.in_(AMBIGUOUS_POST_CODES),
                GBPPostPublication.provider_post_id.is_(None),
            )
            .with_for_update(skip_locked=True)
        )
        if publication is None:
            return "skipped"
        revision = await session.get(GBPPostRevision, publication.post_revision_id)
        if revision is None or revision.organization_id != organization_id:
            return "skipped"

        from apps.api.app.products.gbp.discovery_service import GBPDiscoveryService

        try:
            await GBPDiscoveryService().reconcile_local_posts(
                session,
                settings,
                organization_id,
                revision.gbp_location_id,
                actor_id=None,
                correlation_id=correlation_id,
            )
        except IntegrationReconnectRequiredError:
            return await self._park_ambiguous_post(
                session, publication, "GOOGLE_RECONNECT_REQUIRED", correlation_id
            )
        except Exception:
            return await self._park_ambiguous_post(
                session, publication, "GOOGLE_READ_FAILED", correlation_id
            )

        provider_posts = list(
            await session.scalars(
                select(GBPProviderPost).where(
                    GBPProviderPost.organization_id == organization_id,
                    GBPProviderPost.gbp_location_id == revision.gbp_location_id,
                )
            )
        )
        matches = [
            post
            for post in provider_posts
            if self._provider_post_matches_publication(post, revision, publication)
        ]
        if len(matches) > 1:
            return await self._park_ambiguous_post(
                session, publication, "AMBIGUOUS_PROVIDER_MATCH", correlation_id
            )
        if len(matches) == 1:
            publication.provider_post_id = matches[0].provider_post_name
            publication.safe_error_code = "POST_RECOVERY_PROVIDER_MATCHED"
            await self.execution.enqueue_recovery_run(
                session,
                organization_id,
                publication.workflow_run_id,
                recovery_reference=f"gbp-post-publication:{publication.id}",
                actor_id=None,
                correlation_id=correlation_id,
            )
            await self._audit(
                session,
                event="gbp.post.auto_reconciled_published",
                organization_id=organization_id,
                location_id=None,
                actor_id=None,
                resource_type="gbp_post_publication",
                resource_id=publication.id,
                correlation_id=correlation_id,
                summary="Google shows this post exactly once; verification resumed.",
                metadata={"provider_post_name": matches[0].provider_post_name},
            )
            return "published"
        publication.status = "not_published"
        publication.safe_error_code = POST_NOT_ON_GOOGLE
        await self._settle_publication_run(session, publication)
        await self._audit(
            session,
            event="gbp.post.auto_reconciled_not_published",
            organization_id=organization_id,
            location_id=None,
            actor_id=None,
            resource_type="gbp_post_publication",
            resource_id=publication.id,
            correlation_id=correlation_id,
            summary="Google does not show this post; it was not published.",
            metadata={"previous_code": "PROVIDER_WRITE_AMBIGUOUS"},
        )
        return "not_published"

    async def _settle_publication_run(
        self, session: AsyncSession, publication: GBPPostPublication
    ) -> None:
        """Settle the escalated publish run of a retired post through the canonical outcome path."""
        code = settlement_code(publication.status, publication.safe_error_code)
        if code is None:
            return
        run = await session.get(WorkflowRun, publication.workflow_run_id)
        if run is not None and run.organization_id == publication.organization_id:
            await self.execution.settle_cancelled(session, run, "gbp.publish_post", code)

    async def _park_ambiguous_post(
        self,
        session: AsyncSession,
        publication: GBPPostPublication,
        code: str,
        correlation_id: str,
    ) -> str:
        """Keep the post for a person with a reason code; this ends automatic retries."""
        publication.safe_error_code = code
        await self._audit(
            session,
            event="gbp.post.auto_reconcile_needs_operator",
            organization_id=publication.organization_id,
            location_id=None,
            actor_id=None,
            resource_type="gbp_post_publication",
            resource_id=publication.id,
            correlation_id=correlation_id,
            summary="Google could not settle this post automatically.",
            metadata={"reason": code},
            result=AuditResult.FAILED,
        )
        return "needs_operator"

    async def repost_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        publication_id: UUID,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> GBPPostRevision:
        """Start a fresh post from a `not_published` one, through the normal approval gate.

        This creates a new revision awaiting approval; nothing is sent to Google until a
        person approves and publishes it. Repeating the request returns that same revision.
        """
        scoped = await self._scoped_post_publication(
            session, organization_id, location_id, publication_id, for_update=True
        )
        if scoped is None:
            raise GBPPostRevisionNotFoundError
        publication, source = scoped
        if publication.status == "discarded" and publication.safe_error_code == POST_REPOSTED:
            reposted = await session.scalar(
                select(GBPPostRevision)
                .where(
                    GBPPostRevision.organization_id == organization_id,
                    GBPPostRevision.post_key == source.post_key,
                    GBPPostRevision.revision > source.revision,
                )
                .order_by(GBPPostRevision.revision)
                .limit(1)
            )
            if reposted is not None:
                return reposted
        if publication.status != "not_published":
            raise GBPPostPublicationNotActionableError
        last = await session.scalar(
            select(GBPPostRevision.revision)
            .where(GBPPostRevision.post_key == source.post_key)
            .order_by(GBPPostRevision.revision.desc())
            .limit(1)
        )
        new_revision = GBPPostRevision(
            organization_id=organization_id,
            gbp_location_id=source.gbp_location_id,
            post_key=source.post_key,
            revision=(last or source.revision) + 1,
            post_type=source.post_type,
            content=source.content,
            call_to_action=source.call_to_action,
            event_or_offer=source.event_or_offer,
            publication_requirements=source.publication_requirements,
            status="awaiting_approval",
            created_at=datetime.now(UTC),
        )
        session.add(new_revision)
        await session.flush()
        asset = await session.scalar(
            select(GBPPostAsset).where(
                GBPPostAsset.organization_id == organization_id,
                GBPPostAsset.post_revision_id == source.id,
                GBPPostAsset.status == "selected",
            )
        )
        if asset is not None:
            session.add(
                GBPPostAsset(
                    organization_id=organization_id,
                    post_revision_id=new_revision.id,
                    source_type=asset.source_type,
                    source_reference=asset.source_reference,
                    provider_fetch_url=asset.provider_fetch_url,
                    metadata_document=asset.metadata_document,
                    status="selected",
                )
            )
        publication.status = "discarded"
        publication.safe_error_code = POST_REPOSTED
        await self._settle_publication_run(session, publication)
        await session.flush()
        await self._audit(
            session,
            event="gbp.post.reposted",
            organization_id=organization_id,
            location_id=location_id,
            actor_id=actor_id,
            resource_type="gbp_post_publication",
            resource_id=publication.id,
            correlation_id=correlation_id,
            summary="A post Google does not show was reposted as a new revision awaiting approval.",
            metadata={
                "source_revision_id": str(source.id),
                "new_revision_id": str(new_revision.id),
            },
        )
        return new_revision

    async def discard_publication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        location_id: UUID,
        publication_id: UUID,
        *,
        actor_id: UUID,
        correlation_id: str,
    ) -> GBPPostPublication:
        """Retire a `not_published` post for good. Discarding twice changes nothing."""
        scoped = await self._scoped_post_publication(
            session, organization_id, location_id, publication_id, for_update=True
        )
        if scoped is None:
            raise GBPPostRevisionNotFoundError
        publication, source = scoped
        if publication.status == "discarded" and publication.safe_error_code == POST_DISCARDED:
            return publication
        if publication.status != "not_published":
            raise GBPPostPublicationNotActionableError
        publication.status = "discarded"
        publication.safe_error_code = POST_DISCARDED
        await self._settle_publication_run(session, publication)
        await session.flush()
        await self._audit(
            session,
            event="gbp.post.discarded",
            organization_id=organization_id,
            location_id=location_id,
            actor_id=actor_id,
            resource_type="gbp_post_publication",
            resource_id=publication.id,
            correlation_id=correlation_id,
            summary="A post Google does not show was discarded.",
            metadata={"revision_id": str(source.id)},
        )
        return publication

    async def report_suspension_case(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        command: SuspensionCaseReport,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> GBPSuspensionCase:
        await self._get_gbp_location(session, organization_id, gbp_location_id)
        case = GBPSuspensionCase(
            organization_id=organization_id,
            gbp_location_id=gbp_location_id,
            provider_status=command.provider_status,
            status="open",
            evidence_references=command.evidence_references,
            safe_timeline=[
                {"status": "open", "at": datetime.now(UTC).isoformat(), "source": "manual_report"}
            ],
            version=1,
        )
        session.add(case)
        await session.flush()
        await self._audit(
            session,
            event="gbp.suspension_case.reported",
            organization_id=organization_id,
            location_id=None,
            actor_id=actor_id,
            resource_type="gbp_location",
            resource_id=gbp_location_id,
            correlation_id=correlation_id,
            summary=f"GBP suspension case reported: {command.provider_status}.",
            metadata={"case_id": str(case.id)},
        )
        await self._notify(
            session,
            organization_id=organization_id,
            location_id=None,
            event_type="gbp.suspension_case.reported",
            idempotency_key=f"gbp.suspension_case.{case.id}",
            context={"case_id": str(case.id), "provider_status": command.provider_status},
            priority="high",
        )
        return case

    async def list_suspension_cases(
        self, session: AsyncSession, organization_id: UUID, gbp_location_id: UUID
    ) -> list[GBPSuspensionCase]:
        return list(
            await session.scalars(
                select(GBPSuspensionCase).where(
                    GBPSuspensionCase.organization_id == organization_id,
                    GBPSuspensionCase.gbp_location_id == gbp_location_id,
                )
            )
        )

    async def completeness_report(
        self, session: AsyncSession, organization_id: UUID, gbp_location_id: UUID
    ) -> dict[str, object]:
        snapshot = await self.latest_capability_snapshot(session, organization_id, gbp_location_id)
        profile = await session.scalar(
            select(GBPProfileSnapshot)
            .where(
                GBPProfileSnapshot.organization_id == organization_id,
                GBPProfileSnapshot.gbp_location_id == gbp_location_id,
            )
            .order_by(GBPProfileSnapshot.observed_at.desc())
            .limit(1)
        )
        supported = {
            key
            for key, capability in _capabilities_from_document(snapshot.capabilities).items()
            if capability.readable
        }
        observed = profile.normalized_profile if profile else {}
        return completeness(supported, observed)

    async def conflicts_report(
        self,
        session: AsyncSession,
        organization_id: UUID,
        gbp_location_id: UUID,
        desired: dict[str, object],
    ) -> list[dict[str, object]]:
        profile = await session.scalar(
            select(GBPProfileSnapshot)
            .where(
                GBPProfileSnapshot.organization_id == organization_id,
                GBPProfileSnapshot.gbp_location_id == gbp_location_id,
            )
            .order_by(GBPProfileSnapshot.observed_at.desc())
            .limit(1)
        )
        observed = profile.normalized_profile if profile else {}
        change_sets = await self.list_change_sets(session, organization_id, gbp_location_id)
        approved: dict[str, object] = {}
        for change_set in change_sets:
            if change_set.status == "approved":
                for change in change_set.field_changes:
                    if isinstance(change, dict) and "field" in change and "value" in change:
                        approved[str(change["field"])] = change["value"]
        return conflicts(approved, desired, observed)

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
