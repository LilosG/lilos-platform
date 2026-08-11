# ruff: noqa: E501
"""Remaining provider-capability-governed GBP records."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
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


class GBPCapabilitySnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_capability_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "gbp_location_id"],
            ["gbp_locations.organization_id", "gbp_locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_gbp_capability_snapshots_org_id"),
        UniqueConstraint("gbp_location_id", "content_hash", name="uq_gbp_capability_snapshot"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
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
        ForeignKeyConstraint(
            ["organization_id", "gbp_location_id"],
            ["gbp_locations.organization_id", "gbp_locations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "capability_snapshot_id"],
            [
                "gbp_capability_snapshots.organization_id",
                "gbp_capability_snapshots.id",
            ],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_gbp_change_set_idempotency"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    capability_snapshot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    field_changes: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    risk: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)


class GBPSpecialHours(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_special_hours"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "gbp_location_id"],
            ["gbp_locations.organization_id", "gbp_locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "gbp_location_id", "service_date", "revision", name="uq_gbp_special_hours_revision"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    periods: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)


class GBPMedia(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_media"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "gbp_location_id"],
            ["gbp_locations.organization_id", "gbp_locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_gbp_media_idempotency"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    media_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    rights_authority: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_media_id: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GBPPostRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "gbp_post_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "gbp_location_id"],
            ["gbp_locations.organization_id", "gbp_locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_gbp_post_revisions_org_id"),
        UniqueConstraint("post_key", "revision", name="uq_gbp_post_revision"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
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
        ForeignKeyConstraint(
            ["organization_id", "post_revision_id"],
            ["gbp_post_revisions.organization_id", "gbp_post_revisions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            ondelete="RESTRICT",
        ),
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
    post_revision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_post_id: Mapped[str | None] = mapped_column(String(500))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GBPProviderPost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Read-side snapshot of a Local Post returned by Google.

    This is deliberately separate from governed LILOs post revisions and
    publications: provider truth may include posts created outside LILOs and
    must never be mistaken for an approved local draft.
    """

    __tablename__ = "gbp_provider_posts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "gbp_location_id"],
            ["gbp_locations.organization_id", "gbp_locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_gbp_provider_posts_org_id"),
        UniqueConstraint(
            "organization_id",
            "gbp_location_id",
            "provider_post_name",
            name="uq_gbp_provider_post_name",
        ),
        CheckConstraint("status IN ('present','not_seen')", name="status"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    provider_post_name: Mapped[str] = mapped_column(String(500), nullable=False)
    post_type: Mapped[str | None] = mapped_column(String(32))
    state: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[str | None] = mapped_column(String(1500))
    provider_payload: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="present")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class GBPSuspensionCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_suspension_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "gbp_location_id"],
            ["gbp_locations.organization_id", "gbp_locations.id"],
            ondelete="RESTRICT",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    provider_status: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    provider_case_reference: Mapped[str | None] = mapped_column(String(500))
    safe_timeline: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
