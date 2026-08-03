# ruff: noqa: E501
"""Versioned analytical definitions, observations, goals, reports, and evidence."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class InsightSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "insight_sources"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_insight_sources_org_id"),
        UniqueConstraint("organization_id", "key", name="uq_insight_source_org_key"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    product_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    authority_scope: Mapped[str] = mapped_column(String(64), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MetricDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "metric_definitions"
    __table_args__ = (UniqueConstraint("key", "version", name="uq_metric_definition_version"),)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    source_product: Mapped[str] = mapped_column(String(64), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), nullable=False)
    aggregation_behavior: Mapped[str] = mapped_column(String(32), nullable=False)
    supported_dimensions: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    required_filters: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    freshness_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    partial_period_behavior: Mapped[str] = mapped_column(String(32), nullable=False)
    missing_data_behavior: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)


class MetricObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "metric_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "source_id"],
            ["insight_sources.organization_id", "insight_sources.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "source_id",
            "metric_definition_id",
            "period_start",
            "period_end",
            "dimension_hash",
            name="uq_metric_observation_identity",
        ),
        CheckConstraint(
            "quality_state IN ('valid','zero','missing','unavailable','unsupported','stale','partial','delayed','invalid','suppressed')",
            name="quality_state",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    metric_definition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("metric_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dimensions: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    dimension_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    quality_state: Mapped[str] = mapped_column(String(24), nullable=False)
    completeness: Mapped[Decimal | None] = mapped_column(Numeric(8, 6))
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class InsightGoal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "insight_goals"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    metric_definition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("metric_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    baseline_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    target_value: Mapped[Decimal] = mapped_column(Numeric(30, 10), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class InsightAnnotation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "insight_annotations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    causal_claim: Mapped[bool] = mapped_column(nullable=False, server_default="false")


class ReportDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_report_definitions_org_id"),
        UniqueConstraint("organization_id", "key", name="uq_report_definition_org_key"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    requested_scope: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    metric_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    delivery_policy_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class ReportRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "report_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "report_definition_id"],
            ["report_definitions.organization_id", "report_definitions.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_report_revisions_org_id"),
        UniqueConstraint("report_definition_id", "revision", name="uq_report_revision"),
        UniqueConstraint("snapshot_hash", name="uq_report_snapshot_hash"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    report_definition_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metric_snapshot: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    metric_versions: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReportDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "report_deliveries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "report_revision_id"],
            ["report_revisions.organization_id", "report_revisions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "notification_delivery_id"],
            ["notification_deliveries.organization_id", "notification_deliveries.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_report_delivery_idempotency"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    report_revision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    notification_delivery_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    artifact_reference: Mapped[str | None] = mapped_column(String(1000))


class InsightRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "insight_records"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    insight_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    metric_versions: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    severity: Mapped[str] = mapped_column(String(24), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    validation_state: Mapped[str] = mapped_column(String(24), nullable=False)
    limitations: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
