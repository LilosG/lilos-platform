# ruff: noqa: E501
"""Registered AI tasks and governed execution records."""

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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AITaskDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_task_definitions"
    __table_args__ = (
        UniqueConstraint("key", "version", name="uq_ai_tasks_key_version"),
        CheckConstraint("risk_level IN ('low','medium','high','prohibited')", name="risk"),
        CheckConstraint("version>=1", name="version_positive"),
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    owning_product: Mapped[str] = mapped_column(String(64), nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    input_schema: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    output_schema: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    maximum_cost_microunits: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    retention_policy_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")


class AIExecution(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_executions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_ai_execution_idempotency"),
        CheckConstraint(
            "status IN ('queued','running','completed','validation_failed','provider_failed','rejected')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    task_definition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ai_task_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    workflow_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    provider_key: Mapped[str | None] = mapped_column(String(64))
    model_key: Mapped[str | None] = mapped_column(String(128))
    input_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    approved_fact_revision_ids: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    output_document: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    output_hash: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_microunits: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    requires_human_review: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
