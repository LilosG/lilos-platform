# ruff: noqa: E501
"""Minimal Hermes binding, scoped session, and bounded event projection."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AgentSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_sessions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_agent_sessions_organization_id_id"),
        UniqueConstraint("namespace_hash", name="uq_agent_sessions_namespace"),
        UniqueConstraint("hermes_session_key", name="uq_agent_sessions_hermes_key"),
        CheckConstraint("status IN ('active','expired')", name="status"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    skill_key: Mapped[str] = mapped_column(String(128), nullable=False)
    namespace_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    hermes_session_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "agent_session_id"],
            ["agent_sessions.organization_id", "agent_sessions.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_agent_runs_organization_id_id"),
        UniqueConstraint("workflow_run_id", name="uq_agent_runs_workflow_run"),
        UniqueConstraint("hermes_run_id", name="uq_agent_runs_hermes_run"),
        CheckConstraint(
            "status IN ('queued','running','waiting_approval','stopping','completed','cancelled','failed','capability_unavailable')",
            name="status",
        ),
        Index("ix_agent_runs_scope_created", "organization_id", "location_id", "created_at"),
        Index(
            "uq_agent_runs_active_session",
            "agent_session_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running','waiting_approval','stopping')"),
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    workflow_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    ai_execution_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_executions.id", ondelete="RESTRICT")
    )
    agent_session_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    skill_key: Mapped[str] = mapped_column(String(128), nullable=False)
    skill_version: Mapped[int] = mapped_column(Integer, nullable=False)
    hermes_run_id: Mapped[str | None] = mapped_column(String(128))
    hermes_session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="queued")
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False, server_default="hermes")
    model_key: Mapped[str | None] = mapped_column(String(128))
    capability_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    current_approval: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    output_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    source_references: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    final_output: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    event_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_microunits: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentRunEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "agent_run_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "agent_run_id"],
            ["agent_runs.organization_id", "agent_runs.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("agent_run_id", "sequence", name="uq_agent_run_events_sequence"),
        Index("ix_agent_run_events_run_created", "agent_run_id", "created_at"),
        Index("ix_agent_run_events_org_expires", "organization_id", "expires_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    agent_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
