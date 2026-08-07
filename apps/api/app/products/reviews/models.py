# ruff: noqa: E501
"""Review ingestion, immutable revisions, risk, response, and escalation."""

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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Review(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_reviews_org_id"),
        UniqueConstraint(
            "organization_id",
            "integration_resource_id",
            "external_review_id",
            name="uq_reviews_provider_identity",
        ),
        CheckConstraint(
            "status IN ('new','classified','triaged','drafting','awaiting_approval','approved','publishing','responded','publication_failed','escalated','disputed','closed','archived','removed')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    integration_resource_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("provider_resource_mappings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    external_review_id: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    reviewer_reference: Mapped[str | None] = mapped_column(String(255))
    rating: Mapped[float | None] = mapped_column(Numeric(4, 2))
    language: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="new")
    sentiment: Mapped[str] = mapped_column(String(24), nullable=False, server_default="unknown")
    topics: Mapped[list[object]] = mapped_column(JSONB, nullable=False, server_default="[]")
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False, server_default="unknown")
    current_revision_number: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1"
    )
    review_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReviewRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "review_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "review_id"],
            ["reviews.organization_id", "reviews.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("review_id", "revision_number", name="uq_review_revision_number"),
        UniqueConstraint("review_id", "content_hash", name="uq_review_revision_hash"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    review_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[float | None] = mapped_column(Numeric(4, 2))
    title: Mapped[str | None] = mapped_column(String(500))
    body: Mapped[str | None] = mapped_column(String(10000))
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    change_summary: Mapped[str | None] = mapped_column(String(500))


class ReviewRiskFlag(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "review_risk_flags"
    __table_args__ = (
        UniqueConstraint("review_revision_id", "risk_type", name="uq_review_risk_revision_type"),
        CheckConstraint(
            "risk_type IN ('legal','injury','discrimination','harassment','fraud','charge_dispute','food_safety','threat','privacy','employee_misconduct','media_risk','refund')",
            name="risk_type",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    review_revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("review_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    risk_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_code: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReviewResponseRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_response_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "review_id"],
            ["reviews.organization_id", "reviews.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("review_id", "revision_number", name="uq_review_response_revision"),
        CheckConstraint(
            "status IN ('draft','generated','awaiting_approval','approved','publishing','published','failed','rejected','superseded','reconciliation_required')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    review_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    review_revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("review_revisions.id", ondelete="RESTRICT"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    response_text: Mapped[str] = mapped_column(String(5000), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_by_type: Mapped[str] = mapped_column(String(16), nullable=False)
    ai_execution_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_executions.id", ondelete="RESTRICT")
    )
    approved_fact_revision_ids: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    approval_reference_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    external_response_id: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    safe_error_code: Mapped[str | None] = mapped_column(String(128))


class ReviewEscalation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "review_escalations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','investigating','awaiting_client','resolved','closed')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    review_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("reviews.id", ondelete="RESTRICT"), nullable=False
    )
    case_type: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="open")
    restricted: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    safe_reason: Mapped[str] = mapped_column(String(500), nullable=False)
