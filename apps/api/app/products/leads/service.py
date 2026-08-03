"""Consent-first lead intake, suppression, and durable communication eligibility."""

import hashlib
import json
import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.products.leads.contracts import CommunicationCreate, ConsentRecord, LeadIntake
from apps.api.app.products.leads.models import (
    Lead,
    LeadCommunication,
    LeadConsent,
    LeadSource,
    LeadStatusHistory,
    LeadSubmission,
    LeadSuppression,
)


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


async def set_tenant(session: AsyncSession, organization_id: UUID) -> None:
    await session.execute(
        select(text("set_config('lilos.organization_id', :tenant, true)")).params(
            tenant=str(organization_id)
        )
    )


class LeadService:
    async def intake(
        self, session: AsyncSession, organization_id: UUID, command: LeadIntake
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
            raise LookupError("approved lead source not found")
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
        return lead, submission, True

    async def record_consent(
        self, session: AsyncSession, organization_id: UUID, lead_id: UUID, command: ConsentRecord
    ) -> LeadConsent:
        await set_tenant(session, organization_id)
        lead = await session.scalar(
            select(Lead).where(Lead.organization_id == organization_id, Lead.id == lead_id)
        )
        if not lead:
            raise LookupError("lead not found")
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
        return item

    async def plan_communication(
        self,
        session: AsyncSession,
        organization_id: UUID,
        lead_id: UUID,
        command: CommunicationCreate,
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
        return item
