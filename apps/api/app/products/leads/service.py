"""Consent-first lead intake, suppression, and durable communication eligibility."""

import hashlib
import hmac
import json
import re
import secrets
from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import Select, func, or_, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.access_control.service import AccessControlService
from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.repository import AuditEventRepository
from apps.api.app.audit.service import AuditEventService
from apps.api.app.notifications.models import NotificationTemplate
from apps.api.app.notifications.service import NotificationService
from apps.api.app.products.leads.contracts import (
    CommunicationCreate,
    ConsentRecord,
    LeadIntake,
    LeadIntakeBySource,
    LeadSourceCreate,
    LeadSourceUpdate,
)
from apps.api.app.products.leads.errors import (
    InvalidLeadQueryError,
    InvalidLeadTransitionError,
    LeadAssigneeNotFoundError,
    LeadNotFoundError,
    LeadSourceKeyConflictError,
    LeadSourceNotFoundError,
    LeadTaskNotFoundError,
)
from apps.api.app.products.leads.models import (
    Lead,
    LeadCommunication,
    LeadConsent,
    LeadNote,
    LeadSource,
    LeadStatusHistory,
    LeadSubmission,
    LeadSuppression,
    LeadTask,
)

TERMINAL_STATUSES = {
    "converted",
    "disqualified",
    "lost",
    "spam",
    "duplicate",
    "cancelled",
    "archived",
}
FIRST_CONTACT_STATUSES = {"contacted"}
NOTIFICATION_TEMPLATES = {
    "leads.lead.assigned": ("in_app", "A lead was assigned to you."),
    "leads.lead.converted": ("in_app", "A lead was marked as converted."),
}


def can_transition(from_status: str, to_status: str) -> bool:
    if from_status == to_status:
        return False
    if from_status in TERMINAL_STATUSES:
        return to_status == "archived"
    return True


def normalize_email(value: str | None) -> str | None:
    return value.strip().casefold() if value and value.strip() else None


def normalize_phone(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return f"+{digits}" if 7 <= len(digits) <= 15 else None


def submission_hash(command: LeadIntake) -> str:
    document = command.model_dump(mode="json", exclude={"external_submission_id"})
    return hashlib.sha256(
        json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


_INGESTION_SECRET_BYTES = 32


def generate_ingestion_secret() -> tuple[str, str]:
    """Return (plaintext_secret, hash_for_storage)."""
    plaintext = secrets.token_urlsafe(_INGESTION_SECRET_BYTES)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", plaintext.encode(), salt, iterations=600_000)
    stored = f"pbkdf2:sha256:600000:{salt.hex()}:{digest.hex()}"
    return plaintext, stored


def verify_ingestion_secret(*, plaintext: str, stored_hash: str) -> bool:
    """Constant-time comparison of a plaintext secret against a stored hash."""
    try:
        algo, hash_name, iterations_str, salt_hex, digest_hex = stored_hash.split(":")
    except ValueError:
        return False
    if algo != "pbkdf2" or hash_name != "sha256":
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    actual = hashlib.pbkdf2_hmac("sha256", plaintext.encode(), salt, iterations=int(iterations_str))
    return hmac.compare_digest(actual, expected)


async def set_tenant(session: AsyncSession, organization_id: UUID) -> None:
    await session.execute(
        select(text("set_config('lilos.organization_id', :tenant, true)")).params(
            tenant=str(organization_id)
        )
    )


class LeadService:
    def __init__(self) -> None:
        self.access = AccessControlService()
        self.audit = AuditEventService()
        self.audit_repository = AuditEventRepository()
        self.notifications = NotificationService()

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
                product_key="leads",
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

    async def intake(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: LeadIntake,
        *,
        correlation_id: str,
    ) -> tuple[Lead, LeadSubmission, bool]:
        await set_tenant(session, organization_id)
        source = await session.scalar(
            select(LeadSource).where(
                LeadSource.organization_id == organization_id,
                LeadSource.id == command.source_id,
                LeadSource.status == "active",
            )
        )
        if not source:
            raise LeadSourceNotFoundError
        existing = await session.scalar(
            select(LeadSubmission).where(
                LeadSubmission.organization_id == organization_id,
                LeadSubmission.source_id == source.id,
                LeadSubmission.external_submission_id == command.external_submission_id,
            )
        )
        if existing:
            return (await session.get(Lead, existing.lead_id)), existing, False  # type: ignore[return-value]
        email = normalize_email(command.email)
        phone = normalize_phone(command.phone)
        duplicate = (
            await session.scalar(
                select(Lead)
                .where(
                    Lead.organization_id == organization_id,
                    Lead.status.notin_(("archived", "cancelled")),
                    ((Lead.normalized_email == email) & (email is not None))
                    | ((Lead.normalized_phone == phone) & (phone is not None)),
                )
                .order_by(Lead.received_at.desc())
                .limit(1)
            )
            if email or phone
            else None
        )
        lead = Lead(
            organization_id=organization_id,
            location_id=command.location_id,
            source_id=source.id,
            status="duplicate" if duplicate else "new",
            first_name=command.first_name,
            last_name=command.last_name,
            normalized_email=email,
            normalized_phone=phone,
            service_id=command.service_id,
            message=command.message,
            urgency="unknown",
            location_match_status="matched" if command.location_id else "unmatched",
            duplicate_of_lead_id=duplicate.id if duplicate else None,
            received_at=command.received_at,
        )
        session.add(lead)
        await session.flush()
        submission = LeadSubmission(
            organization_id=organization_id,
            lead_id=lead.id,
            source_id=source.id,
            external_submission_id=command.external_submission_id,
            submission_hash=submission_hash(command),
            normalized_payload={
                "service_id": str(command.service_id) if command.service_id else None,
                "location_id": str(command.location_id) if command.location_id else None,
            },
            status="accepted",
        )
        session.add_all(
            [
                submission,
                LeadStatusHistory(
                    organization_id=organization_id,
                    lead_id=lead.id,
                    from_status=None,
                    to_status=lead.status,
                    actor_type="source",
                    safe_reason="Approved source intake",
                ),
            ]
        )
        await session.flush()
        await self._audit(
            session,
            event="leads.lead.intaken",
            organization_id=organization_id,
            location_id=lead.location_id,
            actor_id=None,
            resource_type="lead",
            resource_id=lead.id,
            correlation_id=correlation_id,
            summary="Lead intaken from approved source.",
            metadata={"status": lead.status, "source_id": str(source.id)},
        )
        return lead, submission, True

    async def record_consent(
        self,
        session: AsyncSession,
        organization_id: UUID,
        lead_id: UUID,
        command: ConsentRecord,
        *,
        correlation_id: str,
    ) -> LeadConsent:
        await set_tenant(session, organization_id)
        lead = await session.scalar(
            select(Lead).where(Lead.organization_id == organization_id, Lead.id == lead_id)
        )
        if not lead:
            raise LeadNotFoundError
        withdrawn = datetime.now(UTC) if command.status == "withdrawn" else None
        item = LeadConsent(
            organization_id=organization_id,
            lead_id=lead_id,
            channel=command.channel,
            consent_type=command.consent_type,
            status=command.status,
            source=command.source,
            disclosure_version=command.disclosure_version,
            evidence_reference=command.evidence_reference,
            captured_at=command.captured_at,
            withdrawn_at=withdrawn,
        )
        session.add(item)
        if command.status in {"withdrawn", "denied"}:
            session.add(
                LeadSuppression(
                    organization_id=organization_id,
                    lead_id=lead_id,
                    channel=command.channel,
                    reason="opt_out",
                    status="active",
                    effective_at=datetime.now(UTC),
                )
            )
            await session.execute(
                update(LeadCommunication)
                .where(
                    LeadCommunication.organization_id == organization_id,
                    LeadCommunication.lead_id == lead_id,
                    LeadCommunication.channel == command.channel,
                    LeadCommunication.status.in_(("planned", "queued")),
                )
                .values(status="cancelled")
            )
        await session.flush()
        await self._audit(
            session,
            event="leads.consent.recorded",
            organization_id=organization_id,
            location_id=lead.location_id,
            actor_id=None,
            resource_type="lead",
            resource_id=lead_id,
            correlation_id=correlation_id,
            summary=f"Consent {command.status} recorded for {command.channel}.",
            metadata={"channel": command.channel, "status": command.status},
        )
        return item

    async def plan_communication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        lead_id: UUID,
        command: CommunicationCreate,
        *,
        correlation_id: str,
    ) -> LeadCommunication:
        await set_tenant(session, organization_id)
        existing = await session.scalar(
            select(LeadCommunication).where(
                LeadCommunication.organization_id == organization_id,
                LeadCommunication.idempotency_key == command.idempotency_key,
            )
        )
        if existing:
            return existing
        lead = await session.scalar(
            select(Lead).where(Lead.organization_id == organization_id, Lead.id == lead_id)
        )
        if not lead:
            raise LeadNotFoundError
        suppressed = await session.scalar(
            select(LeadSuppression.id).where(
                LeadSuppression.organization_id == organization_id,
                LeadSuppression.lead_id == lead_id,
                LeadSuppression.channel == command.channel,
                LeadSuppression.status == "active",
            )
        )
        latest = await session.scalar(
            select(LeadConsent)
            .where(
                LeadConsent.organization_id == organization_id,
                LeadConsent.lead_id == lead_id,
                LeadConsent.channel == command.channel,
                LeadConsent.consent_type == command.consent_type,
            )
            .order_by(LeadConsent.captured_at.desc())
            .limit(1)
        )
        eligible = (
            not suppressed and latest is not None and latest.status in {"granted", "not_required"}
        )
        item = LeadCommunication(
            organization_id=organization_id,
            location_id=lead.location_id,
            lead_id=lead_id,
            direction="outbound",
            channel=command.channel,
            status="planned" if eligible else "suppressed",
            message_reference=command.message_reference,
            workflow_run_id=command.workflow_run_id,
            idempotency_key=command.idempotency_key,
        )
        session.add(item)
        await session.flush()
        await self._audit(
            session,
            event="leads.communication.planned",
            organization_id=organization_id,
            location_id=lead.location_id,
            actor_id=None,
            resource_type="lead",
            resource_id=lead_id,
            correlation_id=correlation_id,
            summary=f"Communication {item.status} on {command.channel}.",
            metadata={"channel": command.channel, "status": item.status},
        )
        return item

    async def _load_lead(self, session: AsyncSession, organization_id: UUID, lead_id: UUID) -> Lead:
        lead = await session.scalar(
            select(Lead)
            .where(Lead.organization_id == organization_id, Lead.id == lead_id)
            .with_for_update()
        )
        if not lead:
            raise LeadNotFoundError
        return lead

    async def transition_status(
        self,
        session: AsyncSession,
        organization_id: UUID,
        lead_id: UUID,
        to_status: str,
        *,
        actor_id: UUID | None,
        correlation_id: str,
        safe_reason: str | None = None,
    ) -> Lead:
        await set_tenant(session, organization_id)
        lead = await self._load_lead(session, organization_id, lead_id)
        if not can_transition(lead.status, to_status):
            raise InvalidLeadTransitionError
        from_status = lead.status
        lead.status = to_status
        now = datetime.now(UTC)
        if to_status == "acknowledged" and lead.acknowledged_at is None:
            lead.acknowledged_at = now
        if to_status == "contact_attempted" and lead.first_outbound_attempt_at is None:
            lead.first_outbound_attempt_at = now
        if to_status in FIRST_CONTACT_STATUSES and lead.first_human_contact_at is None:
            lead.first_human_contact_at = now
        if to_status == "converted":
            lead.converted_at = now
        session.add(
            LeadStatusHistory(
                organization_id=organization_id,
                lead_id=lead_id,
                from_status=from_status,
                to_status=to_status,
                actor_type="user" if actor_id else "system",
                actor_id=actor_id,
                safe_reason=safe_reason,
            )
        )
        await session.flush()
        await self._audit(
            session,
            event="leads.lead.status_changed",
            organization_id=organization_id,
            location_id=lead.location_id,
            actor_id=actor_id,
            resource_type="lead",
            resource_id=lead.id,
            correlation_id=correlation_id,
            summary=f"Lead status changed {from_status} -> {to_status}.",
            metadata={"from_status": from_status, "to_status": to_status},
        )
        if to_status == "converted":
            await self._notify(
                session,
                organization_id=organization_id,
                location_id=lead.location_id,
                event_type="leads.lead.converted",
                idempotency_key=f"leads.converted.{lead.id}",
                context={"lead_id": str(lead.id)},
            )
        return lead

    async def assign(
        self,
        session: AsyncSession,
        organization_id: UUID,
        lead_id: UUID,
        assignee_user_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> Lead:
        await set_tenant(session, organization_id)
        lead = await self._load_lead(session, organization_id, lead_id)
        assignable_members = await self.access.list_assignable_members(session, organization_id)
        if not any(member.user_profile_id == assignee_user_id for member in assignable_members):
            raise LeadAssigneeNotFoundError
        lead.assigned_to_user_id = assignee_user_id
        if lead.status in {"new", "unassigned", "validating"}:
            previous_status = lead.status
            lead.status = "assigned"
            session.add(
                LeadStatusHistory(
                    organization_id=organization_id,
                    lead_id=lead_id,
                    from_status=previous_status,
                    to_status="assigned",
                    actor_type="user" if actor_id else "system",
                    actor_id=actor_id,
                    safe_reason="Lead assigned",
                )
            )
        await session.flush()
        await self._audit(
            session,
            event="leads.lead.assigned",
            organization_id=organization_id,
            location_id=lead.location_id,
            actor_id=actor_id,
            resource_type="lead",
            resource_id=lead.id,
            correlation_id=correlation_id,
            summary="Lead assigned.",
            metadata={"assigned_to_user_id": str(assignee_user_id)},
        )
        await self._notify(
            session,
            organization_id=organization_id,
            location_id=lead.location_id,
            event_type="leads.lead.assigned",
            idempotency_key=f"leads.assigned.{lead.id}.{assignee_user_id}",
            context={"lead_id": str(lead.id), "assigned_to_user_id": str(assignee_user_id)},
            priority="high",
        )
        return lead

    async def record_conversion(
        self,
        session: AsyncSession,
        organization_id: UUID,
        lead_id: UUID,
        *,
        converted_value_cents: int | None,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> Lead:
        lead = await self.transition_status(
            session,
            organization_id,
            lead_id,
            "converted",
            actor_id=actor_id,
            correlation_id=correlation_id,
            safe_reason="Lead converted",
        )
        lead.converted_value_cents = converted_value_cents
        await session.flush()
        return lead

    async def record_loss(
        self,
        session: AsyncSession,
        organization_id: UUID,
        lead_id: UUID,
        *,
        to_status: str,
        loss_reason: str,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> Lead:
        lead = await self.transition_status(
            session,
            organization_id,
            lead_id,
            to_status,
            actor_id=actor_id,
            correlation_id=correlation_id,
            safe_reason=loss_reason,
        )
        lead.loss_reason = loss_reason
        await session.flush()
        return lead

    async def add_note(
        self,
        session: AsyncSession,
        organization_id: UUID,
        lead_id: UUID,
        *,
        author_id: UUID | None,
        body: str,
        correlation_id: str,
    ) -> LeadNote:
        await set_tenant(session, organization_id)
        lead = await session.scalar(
            select(Lead).where(Lead.organization_id == organization_id, Lead.id == lead_id)
        )
        if not lead:
            raise LeadNotFoundError
        note = LeadNote(
            organization_id=organization_id, lead_id=lead_id, author_user_id=author_id, body=body
        )
        session.add(note)
        await session.flush()
        await self._audit(
            session,
            event="leads.note.added",
            organization_id=organization_id,
            location_id=lead.location_id,
            actor_id=author_id,
            resource_type="lead",
            resource_id=lead_id,
            correlation_id=correlation_id,
            summary="Note added to lead.",
            metadata={"note_id": str(note.id)},
        )
        return note

    async def list_notes(
        self, session: AsyncSession, organization_id: UUID, lead_id: UUID
    ) -> list[LeadNote]:
        return list(
            await session.scalars(
                select(LeadNote)
                .where(LeadNote.organization_id == organization_id, LeadNote.lead_id == lead_id)
                .order_by(LeadNote.created_at.desc())
            )
        )

    async def create_task(
        self,
        session: AsyncSession,
        organization_id: UUID,
        lead_id: UUID,
        *,
        title: str,
        description: str | None,
        due_at: datetime | None,
        assigned_to_user_id: UUID | None,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> LeadTask:
        await set_tenant(session, organization_id)
        lead = await session.scalar(
            select(Lead).where(Lead.organization_id == organization_id, Lead.id == lead_id)
        )
        if not lead:
            raise LeadNotFoundError
        task = LeadTask(
            organization_id=organization_id,
            lead_id=lead_id,
            title=title,
            description=description,
            due_at=due_at,
            assigned_to_user_id=assigned_to_user_id,
            status="open",
        )
        session.add(task)
        await session.flush()
        await self._audit(
            session,
            event="leads.task.created",
            organization_id=organization_id,
            location_id=lead.location_id,
            actor_id=actor_id,
            resource_type="lead",
            resource_id=lead_id,
            correlation_id=correlation_id,
            summary=f"Follow-up task created: {title}.",
            metadata={"task_id": str(task.id)},
        )
        return task

    async def list_tasks(
        self, session: AsyncSession, organization_id: UUID, lead_id: UUID
    ) -> list[LeadTask]:
        return list(
            await session.scalars(
                select(LeadTask)
                .where(LeadTask.organization_id == organization_id, LeadTask.lead_id == lead_id)
                .order_by(LeadTask.due_at.asc().nulls_last())
            )
        )

    async def complete_task(
        self,
        session: AsyncSession,
        organization_id: UUID,
        lead_id: UUID,
        task_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> LeadTask:
        await set_tenant(session, organization_id)
        task = await session.scalar(
            select(LeadTask)
            .where(
                LeadTask.organization_id == organization_id,
                LeadTask.lead_id == lead_id,
                LeadTask.id == task_id,
            )
            .with_for_update()
        )
        if not task:
            raise LeadTaskNotFoundError
        task.status = "completed"
        task.completed_at = datetime.now(UTC)
        await session.flush()
        lead = await session.get(Lead, lead_id)
        await self._audit(
            session,
            event="leads.task.completed",
            organization_id=organization_id,
            location_id=lead.location_id if lead else None,
            actor_id=actor_id,
            resource_type="lead",
            resource_id=lead_id,
            correlation_id=correlation_id,
            summary=f"Follow-up task completed: {task.title}.",
            metadata={"task_id": str(task.id)},
        )
        return task

    async def get(self, session: AsyncSession, organization_id: UUID, lead_id: UUID) -> Lead:
        await set_tenant(session, organization_id)
        lead = await session.scalar(
            select(Lead).where(Lead.organization_id == organization_id, Lead.id == lead_id)
        )
        if not lead:
            raise LeadNotFoundError
        return lead

    async def list_leads(
        self,
        session: AsyncSession,
        organization_id: UUID,
        *,
        status_filter: str | None = None,
        urgency_filter: str | None = None,
        assigned_to_user_id: UUID | None = None,
        location_id: UUID | None = None,
        search: str | None = None,
        sort: str = "recent",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Lead], bool]:
        await set_tenant(session, organization_id)
        if not 1 <= limit <= 100:
            raise InvalidLeadQueryError
        if offset < 0:
            raise InvalidLeadQueryError
        statement: Select[tuple[Lead]] = select(Lead).where(Lead.organization_id == organization_id)
        if status_filter is not None:
            statement = statement.where(Lead.status == status_filter)
        if urgency_filter is not None:
            statement = statement.where(Lead.urgency == urgency_filter)
        if assigned_to_user_id is not None:
            statement = statement.where(Lead.assigned_to_user_id == assigned_to_user_id)
        if location_id is not None:
            statement = statement.where(Lead.location_id == location_id)
        if search:
            pattern = f"%{search.casefold()}%"
            statement = statement.where(
                or_(
                    func.lower(Lead.first_name).like(pattern),
                    func.lower(Lead.last_name).like(pattern),
                    func.lower(Lead.normalized_email).like(pattern),
                    func.lower(Lead.message).like(pattern),
                )
            )
        statement = statement.order_by(
            Lead.received_at.asc() if sort == "oldest" else Lead.received_at.desc()
        )
        rows = list(await session.scalars(statement.limit(limit + 1).offset(offset)))
        has_more = len(rows) > limit
        return rows[:limit], has_more

    async def list_communications(
        self, session: AsyncSession, organization_id: UUID, lead_id: UUID
    ) -> list[LeadCommunication]:
        return list(
            await session.scalars(
                select(LeadCommunication)
                .where(
                    LeadCommunication.organization_id == organization_id,
                    LeadCommunication.lead_id == lead_id,
                )
                .order_by(LeadCommunication.created_at.desc())
            )
        )

    async def list_consents(
        self, session: AsyncSession, organization_id: UUID, lead_id: UUID
    ) -> list[LeadConsent]:
        return list(
            await session.scalars(
                select(LeadConsent)
                .where(
                    LeadConsent.organization_id == organization_id,
                    LeadConsent.lead_id == lead_id,
                )
                .order_by(LeadConsent.captured_at.desc())
            )
        )

    async def summary(self, session: AsyncSession, organization_id: UUID) -> dict[str, object]:
        await set_tenant(session, organization_id)
        rows = (
            await session.execute(
                select(Lead.status, func.count())
                .where(Lead.organization_id == organization_id)
                .group_by(Lead.status)
            )
        ).all()
        open_urgent = await session.scalar(
            select(func.count()).where(
                Lead.organization_id == organization_id,
                Lead.urgency.in_(("urgent", "emergency")),
                Lead.status.notin_(tuple(TERMINAL_STATUSES)),
            )
        )
        avg_seconds = await session.scalar(
            select(
                func.avg(func.extract("epoch", Lead.first_human_contact_at - Lead.received_at))
            ).where(
                Lead.organization_id == organization_id,
                Lead.first_human_contact_at.is_not(None),
            )
        )
        return {
            "by_status": {status: count for status, count in rows},
            "open_urgent_count": int(open_urgent or 0),
            "average_speed_to_lead_seconds": (
                float(avg_seconds) if avg_seconds is not None else None
            ),
        }

    async def source_performance(
        self, session: AsyncSession, organization_id: UUID
    ) -> list[dict[str, object]]:
        await set_tenant(session, organization_id)
        rows = (
            await session.execute(
                select(
                    LeadSource.id,
                    LeadSource.name,
                    func.count(Lead.id),
                    func.count(Lead.id).filter(Lead.status == "converted"),
                )
                .select_from(LeadSource)
                .join(Lead, Lead.source_id == LeadSource.id, isouter=True)
                .where(LeadSource.organization_id == organization_id)
                .group_by(LeadSource.id, LeadSource.name)
            )
        ).all()
        return [
            {
                "source_id": str(source_id),
                "name": name,
                "lead_count": int(lead_count or 0),
                "converted_count": int(converted_count or 0),
            }
            for source_id, name, lead_count, converted_count in rows
        ]

    async def create_source(
        self,
        session: AsyncSession,
        organization_id: UUID,
        command: LeadSourceCreate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> tuple[LeadSource, str | None]:
        await set_tenant(session, organization_id)
        existing = await session.scalar(
            select(LeadSource).where(
                LeadSource.organization_id == organization_id,
                LeadSource.key == command.key,
            )
        )
        if existing:
            raise LeadSourceKeyConflictError
        plaintext_secret, secret_hash = generate_ingestion_secret()
        source = LeadSource(
            organization_id=organization_id,
            location_id=command.location_id,
            key=command.key,
            source_type=command.source_type,
            name=command.name,
            integration_connection_id=command.integration_connection_id,
            status=command.status,
            consent_capabilities=command.consent_capabilities,
            verification_reference=command.verification_reference,
            raw_payload_retention_policy=command.raw_payload_retention_policy,
            ingestion_secret_hash=secret_hash,
            version=1,
        )
        session.add(source)
        try:
            await session.flush()
        except IntegrityError:
            raise LeadSourceKeyConflictError from None
        await self._audit(
            session,
            event="leads.source.created",
            organization_id=organization_id,
            location_id=source.location_id,
            actor_id=actor_id,
            resource_type="lead_source",
            resource_id=source.id,
            correlation_id=correlation_id,
            summary=f"Lead source created: {source.name}.",
            metadata={
                "key": source.key,
                "source_type": source.source_type,
                "status": source.status,
            },
        )
        return source, plaintext_secret

    async def update_source(
        self,
        session: AsyncSession,
        organization_id: UUID,
        source_id: UUID,
        command: LeadSourceUpdate,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> LeadSource:
        await set_tenant(session, organization_id)
        source = await session.scalar(
            select(LeadSource)
            .where(
                LeadSource.organization_id == organization_id,
                LeadSource.id == source_id,
            )
            .with_for_update()
        )
        if not source:
            raise LeadSourceNotFoundError
        changed: dict[str, object] = {}
        for field in (
            "name",
            "location_id",
            "integration_connection_id",
            "status",
            "consent_capabilities",
            "verification_reference",
            "raw_payload_retention_policy",
        ):
            value = getattr(command, field)
            if value is not None and getattr(source, field) != value:
                changed[field] = value
                setattr(source, field, value)
        if changed:
            await session.flush()
            await self._audit(
                session,
                event="leads.source.updated",
                organization_id=organization_id,
                location_id=source.location_id,
                actor_id=actor_id,
                resource_type="lead_source",
                resource_id=source.id,
                correlation_id=correlation_id,
                summary=f"Lead source updated: {source.name}.",
                metadata=changed,
            )
        return source

    async def get_source(
        self, session: AsyncSession, organization_id: UUID, source_id: UUID
    ) -> LeadSource:
        await set_tenant(session, organization_id)
        source = await session.scalar(
            select(LeadSource).where(
                LeadSource.organization_id == organization_id,
                LeadSource.id == source_id,
            )
        )
        if not source:
            raise LeadSourceNotFoundError
        return source

    async def list_sources(self, session: AsyncSession, organization_id: UUID) -> list[LeadSource]:
        await set_tenant(session, organization_id)
        return list(
            await session.scalars(
                select(LeadSource)
                .where(LeadSource.organization_id == organization_id)
                .order_by(LeadSource.created_at.desc())
            )
        )

    async def intake_by_source(
        self,
        session: AsyncSession,
        *,
        source_key: str,
        source_secret: str,
        command: LeadIntakeBySource,
        correlation_id: str,
    ) -> tuple[Lead, LeadSubmission, bool]:
        """Machine-to-machine lead intake authenticated by source key + secret.

        Resolves the source by key across all organizations, verifies the
        secret, then delegates to the standard intake path.  No organization_id
        appears in the URL — the source key resolves the tenant.
        """
        source = await session.scalar(
            select(LeadSource).where(
                LeadSource.key == source_key,
                LeadSource.status == "active",
            )
        )
        if not source or not source.ingestion_secret_hash:
            raise LeadSourceNotFoundError
        if not verify_ingestion_secret(
            plaintext=source_secret, stored_hash=source.ingestion_secret_hash
        ):
            raise LeadSourceNotFoundError
        intake_cmd = LeadIntake(
            source_id=source.id,
            external_submission_id=command.external_submission_id,
            location_id=command.location_id,
            first_name=command.first_name,
            last_name=command.last_name,
            email=command.email,
            phone=command.phone,
            service_id=command.service_id,
            message=command.message,
            received_at=command.received_at,
        )
        return await self.intake(
            session, source.organization_id, intake_cmd, correlation_id=correlation_id
        )

    async def rotate_source_secret(
        self,
        session: AsyncSession,
        organization_id: UUID,
        source_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> tuple[LeadSource, str]:
        """Rotate the ingestion secret for a source. Returns the new plaintext secret."""
        await set_tenant(session, organization_id)
        source = await session.scalar(
            select(LeadSource)
            .where(
                LeadSource.organization_id == organization_id,
                LeadSource.id == source_id,
            )
            .with_for_update()
        )
        if not source:
            raise LeadSourceNotFoundError
        plaintext_secret, secret_hash = generate_ingestion_secret()
        source.ingestion_secret_hash = secret_hash
        await session.flush()
        await self._audit(
            session,
            event="leads.source.secret_rotated",
            organization_id=organization_id,
            location_id=source.location_id,
            actor_id=actor_id,
            resource_type="lead_source",
            resource_id=source.id,
            correlation_id=correlation_id,
            summary=f"Lead source secret rotated: {source.name}.",
            metadata={"key": source.key},
        )
        return source, plaintext_secret

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
