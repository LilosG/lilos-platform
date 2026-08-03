"""Tenant-scoped SEO collection, evidence, recommendation, and outcome records."""

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
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class SEOWebsite(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seo_websites"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_seo_websites_org_id"),
        UniqueConstraint("organization_id", "key", name="uq_seo_websites_org_key"),
        CheckConstraint(
            "status IN ('pending_verification','active','paused','archived')", name="status"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    canonical_origin: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    ownership_status: Mapped[str] = mapped_column(String(32), nullable=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class SEOSearchProperty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seo_search_properties"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "website_id"],
            ["seo_websites.organization_id", "seo_websites.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["integration_connections.organization_id", "integration_connections.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_seo_search_properties_org_id"),
        UniqueConstraint(
            "organization_id",
            "provider",
            "external_property_id",
            name="uq_seo_search_property_external",
        ),
        CheckConstraint("property_type IN ('domain','url_prefix')", name="property_type"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_property_id: Mapped[str] = mapped_column(String(1000), nullable=False)
    property_type: Mapped[str] = mapped_column(String(16), nullable=False)
    mapping_status: Mapped[str] = mapped_column(String(16), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    freshness_status: Mapped[str] = mapped_column(String(16), nullable=False)


class SEOPage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seo_pages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "website_id"],
            ["seo_websites.organization_id", "seo_websites.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_seo_pages_org_id"),
        UniqueConstraint("website_id", "normalized_url", name="uq_seo_page_normalized_url"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    observed_url: Mapped[str] = mapped_column(String(2000), nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(String(2000))
    normalization_reasons: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    indexability: Mapped[str] = mapped_column(String(24), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SEOCrawlRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seo_crawl_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "website_id"],
            ["seo_websites.organization_id", "seo_websites.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_seo_crawl_idempotency"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    max_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    safe_result: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SEOSearchObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seo_search_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "search_property_id"],
            ["seo_search_properties.organization_id", "seo_search_properties.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "page_id"],
            ["seo_pages.organization_id", "seo_pages.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "search_property_id",
            "date_start",
            "date_end",
            "dimension_hash",
            name="uq_seo_search_observation",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    search_property_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    page_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    query: Mapped[str | None] = mapped_column(String(1000))
    date_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dimensions: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    dimension_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    clicks: Mapped[int | None] = mapped_column(Integer)
    impressions: Mapped[int | None] = mapped_column(Integer)
    ctr: Mapped[float | None] = mapped_column(Numeric(12, 8))
    position: Mapped[float | None] = mapped_column(Numeric(12, 4))
    quality_status: Mapped[str] = mapped_column(String(24), nullable=False)
    partial: Mapped[bool] = mapped_column(nullable=False)


class SEOOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seo_opportunities"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "website_id"],
            ["seo_websites.organization_id", "seo_websites.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "page_id"],
            ["seo_pages.organization_id", "seo_pages.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_seo_opportunities_org_id"),
        UniqueConstraint(
            "organization_id",
            "deduplication_key",
            "active_marker",
            name="uq_seo_active_opportunity",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    website_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    page_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    opportunity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    deduplication_key: Mapped[str] = mapped_column(String(128), nullable=False)
    active_marker: Mapped[str | None] = mapped_column(
        String(8), nullable=False, server_default="active"
    )
    evidence: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    source_versions: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    score_version: Mapped[int] = mapped_column(Integer, nullable=False)
    priority_score: Mapped[int] = mapped_column(Integer, nullable=False)
    score_explanation: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class SEORecommendationRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "seo_recommendation_revisions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "opportunity_id"],
            ["seo_opportunities.organization_id", "seo_opportunities.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_seo_recommendation_revisions_org_id"),
        UniqueConstraint(
            "opportunity_id", "revision_number", name="uq_seo_recommendation_revision"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    opportunity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    proposed_action: Mapped[str] = mapped_column(String(10000), nullable=False)
    evidence_references: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    expected_result_hypothesis: Mapped[str] = mapped_column(String(2000), nullable=False)
    risk: Mapped[str] = mapped_column(String(24), nullable=False)
    effort: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    approved_by_user_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SEOImplementationTask(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seo_implementation_tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "recommendation_revision_id"],
            ["seo_recommendation_revisions.organization_id", "seo_recommendation_revisions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "workflow_run_id"],
            ["workflow_runs.organization_id", "workflow_runs.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_seo_implementation_tasks_org_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    recommendation_revision_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    workflow_run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    verification_evidence: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SEOOutcome(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "seo_outcomes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "implementation_task_id"],
            ["seo_implementation_tasks.organization_id", "seo_implementation_tasks.id"],
            ondelete="RESTRICT",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    implementation_task_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    baseline_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    baseline_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    measurement_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    measurement_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    classification: Mapped[str] = mapped_column(String(24), nullable=False)
    metrics: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    limitations: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
