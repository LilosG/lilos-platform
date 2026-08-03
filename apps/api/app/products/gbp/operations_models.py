# ruff: noqa: E501
"""Remaining provider-capability-governed GBP records."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class GBPCapabilitySnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_capability_snapshots"
    __table_args__ = (
        UniqueConstraint("gbp_location_id", "content_hash", name="uq_gbp_capability_snapshot"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("gbp_locations.id", ondelete="RESTRICT"), nullable=False
    )
    capabilities: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GBPCategory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_categories"
    __table_args__ = (
        UniqueConstraint(
            "provider", "external_category_id", "locale", name="uq_gbp_category_provider_locale"
        ),
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_category_id: Mapped[str] = mapped_column(String(255), nullable=False)
    locale: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    supported_services: Mapped[list[object]] = mapped_column(JSONB, nullable=False)


class GBPChangeSet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_change_sets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_gbp_change_set_idempotency"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("gbp_locations.id", ondelete="RESTRICT"), nullable=False
    )
    capability_snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("gbp_capability_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    field_changes: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    risk: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class GBPSpecialHours(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_special_hours"
    __table_args__ = (
        UniqueConstraint(
            "gbp_location_id", "service_date", "revision", name="uq_gbp_special_hours_revision"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("gbp_locations.id", ondelete="RESTRICT"), nullable=False
    )
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    periods: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)


class GBPMedia(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_media"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_gbp_media_idempotency"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("gbp_locations.id", ondelete="RESTRICT"), nullable=False
    )
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    rights_authority: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_media_id: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GBPPostRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "gbp_post_revisions"
    __table_args__ = (UniqueConstraint("post_key", "revision", name="uq_gbp_post_revision"),)
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("gbp_locations.id", ondelete="RESTRICT"), nullable=False
    )
    post_key: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    post_type: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(String(1500), nullable=False)
    call_to_action: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    event_or_offer: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GBPPostPublication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_post_publications"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_gbp_post_publication_idempotency"
        ),
        CheckConstraint(
            "status IN ('reserved','scheduled','dispatched','verified','failed','reconciliation_required','cancelled','expired')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    post_revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("gbp_post_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    workflow_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_post_id: Mapped[str | None] = mapped_column(String(500))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GBPSuspensionCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_suspension_cases"
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("gbp_locations.id", ondelete="RESTRICT"), nullable=False
    )
    provider_status: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    provider_case_reference: Mapped[str | None] = mapped_column(String(500))
    safe_timeline: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
