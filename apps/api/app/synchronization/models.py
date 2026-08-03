# ruff: noqa: E501
"""Durable synchronization state, checkpoints, changes, and conflicts."""

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


class SyncDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_definitions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["integration_connections.organization_id", "integration_connections.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "key", name="uq_sync_definitions_org_key"),
        CheckConstraint("direction IN ('pull','push','bidirectional')", name="direction"),
        CheckConstraint("version>=1", name="version_positive"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    capability: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class SyncRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_sync_runs_org_id"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_sync_runs_idempotency"),
        CheckConstraint(
            "status IN ('queued','running','partial','completed','failed','cancelled','blocked')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    definition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sync_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    job_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("jobs.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="queued")
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(64))


class SyncCheckpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_checkpoints"
    __table_args__ = (
        UniqueConstraint("organization_id", "definition_id", name="uq_sync_checkpoint_definition"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    definition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sync_definitions.id", ondelete="RESTRICT"), nullable=False
    )
    cursor_reference: Mapped[str | None] = mapped_column(String(500))
    page_reference: Mapped[str | None] = mapped_column(String(500))
    observed_through: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stale_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class ProviderStateSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "provider_state_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "mapping_id", "content_hash", name="uq_provider_state_snapshot"
        ),
        CheckConstraint("authority IN ('provider_observed','platform_desired')", name="authority"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    mapping_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("provider_resource_mappings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    authority: Mapped[str] = mapped_column(String(24), nullable=False)
    normalized_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SyncChangeIntent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_change_intents"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_sync_change_intents_idempotency"
        ),
        CheckConstraint(
            "status IN ('proposed','approval_required','approved','queued','dispatched','verified','conflicted','failed','cancelled')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    sync_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sync_runs.id", ondelete="RESTRICT"), nullable=False
    )
    mapping_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("provider_resource_mappings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    diff_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    approval_reference_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncConflict(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sync_conflicts"
    __table_args__ = (
        UniqueConstraint(
            "change_intent_id", "classification", name="uq_sync_conflict_classification"
        ),
        CheckConstraint(
            "status IN ('unresolved','resolved_platform','resolved_provider','cancelled')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    change_intent_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("sync_change_intents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    classification: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unresolved")
    safe_summary: Mapped[str] = mapped_column(String(500), nullable=False)
