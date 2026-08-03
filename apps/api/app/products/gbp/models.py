# ruff: noqa: E501
"""Tenant-scoped GBP discovery, profile, change, and publication records."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
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


class GBPAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_accounts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["integration_connections.organization_id", "integration_connections.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "connection_id",
            "external_account_id",
            name="uq_gbp_accounts_external",
        ),
        CheckConstraint(
            "status IN ('discovered','selected','unavailable','archived')", name="status"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="discovered")
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    freshness_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GBPLocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_locations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            name="fk_gbp_locations_org_location",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["integration_connections.organization_id", "integration_connections.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_gbp_locations_org_id"),
        UniqueConstraint(
            "organization_id",
            "connection_id",
            "external_location_id",
            name="uq_gbp_locations_external",
        ),
        CheckConstraint(
            "mapping_status IN ('unmapped','suggested','confirmed','conflicted','disconnected','archived')",
            name="mapping_status",
        ),
        CheckConstraint(
            "write_enabled = false OR mapping_status = 'confirmed'", name="confirmed_before_write"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    account_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("gbp_accounts.id", ondelete="RESTRICT"), nullable=False
    )
    integration_resource_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("provider_resource_mappings.id", ondelete="RESTRICT")
    )
    external_location_id: Mapped[str] = mapped_column(String(500), nullable=False)
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mapping_status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="unmapped"
    )
    write_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    confirmed_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    capability_document: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    last_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GBPProfileSnapshot(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "gbp_profile_snapshots"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "gbp_location_id"],
            ["gbp_locations.organization_id", "gbp_locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "gbp_location_id",
            "content_hash",
            name="uq_gbp_profile_snapshot_hash",
        ),
        CheckConstraint("completeness IN ('full','partial')", name="completeness"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    normalized_profile: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    completeness: Mapped[str] = mapped_column(String(16), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class GBPProfileChangeRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_profile_change_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "gbp_location_id"],
            ["gbp_locations.organization_id", "gbp_locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("change_identity", "revision_number", name="uq_gbp_change_revision"),
        CheckConstraint("revision_number>=1", name="revision_positive"),
        CheckConstraint(
            "status IN ('draft','validation_failed','awaiting_approval','approved','superseded','rejected','publishing','published','failed','reconciliation_required')",
            name="status",
        ),
        CheckConstraint("risk_level IN ('low','medium','high')", name="risk_level"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    gbp_location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    change_identity: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    base_snapshot_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("gbp_profile_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    desired_fields: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    diff_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    fact_revision_ids: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approval_policy_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GBPPublication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gbp_publications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_gbp_publication_idempotency"
        ),
        CheckConstraint(
            "status IN ('reserved','queued','dispatched','verified','failed','reconciliation_required','cancelled')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    change_revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("gbp_profile_change_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sync_change_intent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sync_change_intents.id", ondelete="RESTRICT")
    )
    workflow_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="reserved")
    update_mask: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    provider_operation_reference: Mapped[str | None] = mapped_column(String(500))
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
