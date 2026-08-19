# ruff: noqa: E501
"""Content evidence, briefs, immutable revisions, targets, publications, and verification."""

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


class ContentOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_opportunities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "evidence_hash", name="uq_content_opportunity_evidence"
        ),
        CheckConstraint(
            "status IN ('identified','validated','accepted','rejected','converted','archived')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    product_key: Mapped[str] = mapped_column(String(64), nullable=False)
    target_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    opportunity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    evidence_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    evidence_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class ContentItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_content_items_org_id"),
        CheckConstraint(
            "status IN ('idea','briefing','brief_ready','drafting','draft_ready','reviewing','revision_requested','approved','publishing','published','failed','reconciliation_required','archived')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    opportunity_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("content_opportunities.id", ondelete="RESTRICT")
    )
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="idea")
    publishing_target_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("publishing_targets.id", ondelete="RESTRICT")
    )
    approved_revision_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class ContentBrief(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_briefs"
    __table_args__ = (
        UniqueConstraint("content_item_id", "revision_number", name="uq_content_brief_revision"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    content_item_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("content_items.id", ondelete="RESTRICT"), nullable=False
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    audience: Mapped[str] = mapped_column(String(500), nullable=False)
    intent: Mapped[str] = mapped_column(String(500), nullable=False)
    target_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    approved_fact_revision_ids: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    required_claims: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    prohibited_claims: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    required_local_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    source_evidence_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    validation_requirements: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    approval_policy_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class ContentRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "content_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "content_item_id"],
            ["content_items.organization_id", "content_items.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("content_item_id", "revision_number", name="uq_content_revision_number"),
        UniqueConstraint("content_item_id", "content_hash", name="uq_content_revision_hash"),
        CheckConstraint(
            "status IN ('draft','validation_failed','awaiting_editorial','awaiting_client','approved','rejected','superseded','published')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    content_item_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(String(200000), nullable=False)
    frontmatter: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_type: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    ai_execution_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ai_executions.id", ondelete="RESTRICT")
    )
    approved_fact_revision_ids: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    validation_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    editorial_approved_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    client_approved_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PublishingTarget(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "publishing_targets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["integration_connections.organization_id", "integration_connections.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "key", name="uq_publishing_targets_org_key"),
        CheckConstraint("target_type IN ('github_astro')", name="target_type"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    repository_id: Mapped[str] = mapped_column(String(255), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    allowed_path_prefix: Mapped[str] = mapped_column(String(500), nullable=False)
    deployment_target_reference: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class ContentPublication(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_publications"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_content_publication_idempotency"
        ),
        CheckConstraint(
            "status IN ('reserved','branch_created','pull_request_created','checks_running','checks_failed','merged','deployment_pending','deployed','verified','failed','reconciliation_required','rolled_back')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    content_item_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("content_items.id", ondelete="RESTRICT"), nullable=False
    )
    content_revision_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("content_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    publishing_target_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("publishing_targets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    workflow_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="reserved")
    target_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    base_commit: Mapped[str | None] = mapped_column(String(64))
    branch_name: Mapped[str | None] = mapped_column(String(255))
    external_pull_request_id: Mapped[str | None] = mapped_column(String(255))
    external_revision_id: Mapped[str | None] = mapped_column(String(255))
    build_status: Mapped[str | None] = mapped_column(String(32))
    deployment_status: Mapped[str | None] = mapped_column(String(32))
    published_url: Mapped[str | None] = mapped_column(String(1000))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rollback_of_publication_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("content_publications.id", ondelete="RESTRICT")
    )
    safe_error_code: Mapped[str | None] = mapped_column(String(64))
