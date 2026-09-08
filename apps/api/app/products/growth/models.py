"""Tenant-scoped cross-product growth opportunities, plans, actions, and outcomes.

Growth records intentionally reference canonical product evidence rather than
copying SEO, Analytics, GBP, Reviews, or Content source data. The product is a
coordination layer over those authoritative systems.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GrowthOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One business-level opportunity synthesized from canonical evidence."""

    __tablename__ = "growth_opportunities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_growth_opportunities_org_id"),
        UniqueConstraint(
            "organization_id",
            "deduplication_key",
            name="uq_growth_opportunities_org_deduplication_key",
        ),
        CheckConstraint(
            "status IN ('detected','planning','planned','executing','measuring','succeeded',"
            "'no_material_change','negative','dismissed','archived')",
            name="status",
        ),
        CheckConstraint("impact_score >= 0 AND impact_score <= 100", name="impact_score_range"),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100",
            name="confidence_score_range",
        ),
        CheckConstraint(
            "priority_score >= 0 AND priority_score <= 100", name="priority_score_range"
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    primary_topic: Mapped[str | None] = mapped_column(String(500))
    target_reference: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="detected")
    impact_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    priority_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    evidence_summary: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    baseline_metrics: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GrowthActionPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Versioned strategy for resolving one growth opportunity."""

    __tablename__ = "growth_action_plans"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "opportunity_id"],
            ["growth_opportunities.organization_id", "growth_opportunities.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_growth_action_plans_org_id"),
        UniqueConstraint(
            "organization_id",
            "opportunity_id",
            "plan_version",
            name="uq_growth_action_plans_opportunity_version",
        ),
        CheckConstraint(
            "status IN ('draft','ready','executing','blocked','completed','cancelled')",
            name="status",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    opportunity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    plan_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    strategy: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft")
    source_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
    planner_metadata: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)


class GrowthActionItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One governed execution primitive inside a growth action plan."""

    __tablename__ = "growth_action_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "plan_id"],
            ["growth_action_plans.organization_id", "growth_action_plans.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_growth_action_items_org_id"),
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_growth_action_items_org_idempotency_key",
        ),
        CheckConstraint("risk_level IN ('low','medium','high','restricted')", name="risk_level"),
        CheckConstraint(
            "approval_mode IN ('inherit','automatic','human_required')", name="approval_mode"
        ),
        CheckConstraint(
            "status IN ('planned','waiting_approval','authorized','queued','executing','verifying',"
            "'completed','failed','cancelled','skipped')",
            name="status",
        ),
        CheckConstraint(
            "verification_status IN ('pending','not_required','verified','failed')",
            name="verification_status",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_reference: Mapped[str | None] = mapped_column(Text)
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    approval_mode: Mapped[str] = mapped_column(String(24), nullable=False, default="inherit")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="planned")
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    workflow_run_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    verification_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    verification_evidence: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GrowthActionDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Directed dependency edge between two action items in the same tenant."""

    __tablename__ = "growth_action_dependencies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "action_item_id"],
            ["growth_action_items.organization_id", "growth_action_items.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["organization_id", "depends_on_action_item_id"],
            ["growth_action_items.organization_id", "growth_action_items.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "organization_id",
            "action_item_id",
            "depends_on_action_item_id",
            name="uq_growth_action_dependency_edge",
        ),
        CheckConstraint("action_item_id <> depends_on_action_item_id", name="not_self_dependency"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    action_item_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    depends_on_action_item_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class GrowthMeasurement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Canonical outcome snapshot for a fixed measurement window."""

    __tablename__ = "growth_measurements"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "opportunity_id"],
            ["growth_opportunities.organization_id", "growth_opportunities.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "action_plan_id"],
            ["growth_action_plans.organization_id", "growth_action_plans.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_growth_measurements_org_id"),
        UniqueConstraint(
            "organization_id",
            "opportunity_id",
            "window_days",
            name="uq_growth_measurement_window",
        ),
        CheckConstraint("window_days IN (0,7,14,28,56)", name="window_days"),
        CheckConstraint(
            "outcome_classification IN ('baseline','pending','improved','no_material_change',"
            "'negative','insufficient_evidence')",
            name="outcome_classification",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    opportunity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action_plan_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    outcome_classification: Mapped[str] = mapped_column(String(32), nullable=False)
    metric_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    comparison: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    source_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list)
