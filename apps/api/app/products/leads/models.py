# ruff: noqa: E501
"""Tenant-isolated leads, evidence, consent, suppression, communication, and CRM state."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LeadSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "key", name="uq_lead_sources_org_key"),
        CheckConstraint(
            "status IN ('draft','verified','active','paused','archived')", name="status"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    integration_connection_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("integration_connections.id", ondelete="RESTRICT")
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    consent_capabilities: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    verification_reference: Mapped[str | None] = mapped_column(String(500))
    raw_payload_retention_policy: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "leads"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_leads_org_id"),
        CheckConstraint(
            "status IN ('new','validating','unassigned','assigned','acknowledged','contact_attempted','contacted','qualifying','qualified','appointment_requested','appointment_scheduled','converted','nurture','unresponsive','disqualified','lost','spam','duplicate','cancelled','archived')",
            name="status",
        ),
        CheckConstraint(
            "urgency IN ('routine','same_day','urgent','emergency','unknown')", name="urgency"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("lead_sources.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="new")
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    normalized_email: Mapped[str | None] = mapped_column(String(320))
    normalized_phone: Mapped[str | None] = mapped_column(String(32))
    service_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("service_catalog.id", ondelete="RESTRICT")
    )
    message: Mapped[str | None] = mapped_column(String(10000))
    urgency: Mapped[str] = mapped_column(String(16), nullable=False, server_default="unknown")
    location_match_status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="unmatched"
    )
    assigned_to_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    duplicate_of_lead_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="RESTRICT")
    )
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_outbound_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_human_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    converted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class LeadSubmission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "lead_submissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "source_id",
            "external_submission_id",
            name="uq_lead_submission_external",
        ),
        UniqueConstraint(
            "organization_id", "source_id", "submission_hash", name="uq_lead_submission_hash"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    lead_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("lead_sources.id", ondelete="RESTRICT"), nullable=False
    )
    external_submission_id: Mapped[str] = mapped_column(String(500), nullable=False)
    submission_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    raw_payload_reference: Mapped[str | None] = mapped_column(String(500))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)


class LeadConsent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_consents"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "lead_id", "channel", "consent_type", "captured_at", name="uq_lead_consent_evidence"
        ),
        CheckConstraint("channel IN ('email','sms','phone')", name="channel"),
        CheckConstraint(
            "consent_type IN ('transactional_email','transactional_sms','marketing_email','marketing_sms','phone_call','automated_call')",
            name="consent_type",
        ),
        CheckConstraint(
            "status IN ('granted','denied','unknown','not_required','withdrawn','expired')",
            name="status",
        ),
        CheckConstraint(
            "(status='withdrawn') = (withdrawn_at IS NOT NULL)", name="withdrawal_consistent"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    lead_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    consent_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    disclosure_version: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LeadSuppression(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_suppressions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("lead_id", "channel", "status", name="uq_lead_active_suppression"),
        CheckConstraint("status IN ('active','released')", name="status"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    lead_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LeadStatusHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "lead_status_history"
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    lead_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("leads.id", ondelete="RESTRICT"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    workflow_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="RESTRICT")
    )
    safe_reason: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class LeadCommunication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lead_communications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_lead_communication_idempotency"
        ),
        CheckConstraint("direction IN ('inbound','outbound','internal')", name="direction"),
        CheckConstraint(
            "status IN ('planned','queued','sent','delivered','failed','ambiguous','suppressed','cancelled')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    lead_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    message_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    notification_delivery_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("notification_deliveries.id", ondelete="RESTRICT")
    )
    workflow_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_message_id: Mapped[str | None] = mapped_column(String(500))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CRMLeadMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crm_lead_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "lead_id"],
            ["leads.organization_id", "leads.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "connection_id", "external_lead_id", name="uq_crm_external_lead"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    lead_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("integration_connections.id", ondelete="RESTRICT"),
        nullable=False,
    )
    external_lead_id: Mapped[str] = mapped_column(String(500), nullable=False)
    last_platform_hash: Mapped[str | None] = mapped_column(String(64))
    last_provider_hash: Mapped[str | None] = mapped_column(String(64))
    sync_status: Mapped[str] = mapped_column(String(24), nullable=False)
    conflict_document: Mapped[dict[str, object] | None] = mapped_column(JSONB)
