# ruff: noqa: E501
"""Cross-product initiatives that coordinate existing product-domain executors."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GrowthInitiative(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One evidence-backed cross-product objective proposed by the planner."""

    __tablename__ = "growth_initiatives"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "planner_agent_run_id"],
            ["agent_runs.organization_id", "agent_runs.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_growth_initiatives_org_id"),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_growth_initiatives_idempotency"
        ),
        CheckConstraint("priority_score BETWEEN 0 AND 100", name="priority_score"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence"),
        CheckConstraint(
            "status IN ('proposed','approved','rejected','executing','completed','cancelled')",
            name="status",
        ),
        Index(
            "ix_growth_initiatives_scope_status",
            "organization_id",
            "location_id",
            "status",
            "created_at",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    planner_agent_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    objective: Mapped[str] = mapped_column(String(2000), nullable=False)
    rationale: Mapped[str] = mapped_column(String(5000), nullable=False)
    source_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="proposed")
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class GrowthAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One ordered action delegated to an existing governed product workflow."""

    __tablename__ = "growth_actions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "initiative_id"],
            ["growth_initiatives.organization_id", "growth_initiatives.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_growth_actions_org_id"),
        UniqueConstraint("initiative_id", "action_key", name="uq_growth_actions_plan_key"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint("execution_mode IN ('workflow','manual','monitor')", name="execution_mode"),
        CheckConstraint(
            "(execution_mode = 'workflow' AND executor_workflow_key IS NOT NULL) OR "
            "(execution_mode <> 'workflow' AND executor_workflow_key IS NULL)",
            name="executor_binding",
        ),
        CheckConstraint("risk IN ('low','medium','high')", name="risk"),
        CheckConstraint("effort IN ('low','medium','high')", name="effort"),
        CheckConstraint(
            "status IN ('proposed','approved','queued','running','waiting_approval','completed','failed','skipped','cancelled')",
            name="status",
        ),
        Index("ix_growth_actions_initiative_position", "initiative_id", "position"),
        Index("ix_growth_actions_scope_status", "organization_id", "status", "created_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    initiative_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action_key: Mapped[str] = mapped_column(String(128), nullable=False)
    product_key: Mapped[str] = mapped_column(String(64), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    executor_workflow_key: Mapped[str | None] = mapped_column(String(128))
    dependency_keys: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    evidence_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    expected_result_hypothesis: Mapped[str] = mapped_column(String(2000), nullable=False)
    verification_plan: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    risk: Mapped[str] = mapped_column(String(16), nullable=False)
    effort: Mapped[str] = mapped_column(String(16), nullable=False)
    approval_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="proposed")
    workflow_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    result_reference: Mapped[str | None] = mapped_column(String(500))
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GrowthOutcome(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Measured result for a completed or attempted growth action."""

    __tablename__ = "growth_outcomes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "action_id"],
            ["growth_actions.organization_id", "growth_actions.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "classification IN ('improved','unchanged','regressed','inconclusive')",
            name="classification",
        ),
        Index("ix_growth_outcomes_action_observed", "action_id", "observed_at"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    action_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    classification: Mapped[str] = mapped_column(String(24), nullable=False)
    baseline: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    measurement: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
