# ruff: noqa: E501
"""SQLAlchemy persistence for shared Phase 4 administration."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ServiceDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_catalog"
    __table_args__ = (
        CheckConstraint("key ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'", name="key_format"),
        CheckConstraint("status IN ('active','archived')", name="status"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "(status='archived') = (archived_at IS NOT NULL)", name="archive_consistent"
        ),
        UniqueConstraint("organization_id", "key", name="uq_service_catalog_organization_key"),
        UniqueConstraint("organization_id", "id", name="uq_service_catalog_organization_id_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(63), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ServiceAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "service_assignments"
    __table_args__ = (
        CheckConstraint("scope_type IN ('organization','location')", name="scope"),
        CheckConstraint(
            "(scope_type='organization' AND location_id IS NULL) OR (scope_type='location' AND location_id IS NOT NULL)",
            name="scope_identity",
        ),
        CheckConstraint("status IN ('active','removed')", name="status"),
        CheckConstraint("version >= 1", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "service_id"],
            ["service_catalog.organization_id", "service_catalog.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_service_assignments_organization_id_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    service_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    location_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class BusinessFactRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "business_fact_revisions"
    __table_args__ = (
        CheckConstraint(r"fact_key ~ '^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$'", name="key_format"),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint(
            "status IN ('proposed','pending_approval','approved','active','disputed','superseded','expired','rejected')",
            name="status",
        ),
        CheckConstraint(
            "authority IN ('client_approved','operator_verified','provider_observed','imported','system_derived','industry_default','ai_suggested')",
            name="authority",
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from", name="effective_period"
        ),
        CheckConstraint(
            "status NOT IN ('approved','active') OR approved_at IS NOT NULL",
            name="approval_consistent",
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "supersedes_id"],
            ["business_fact_revisions.organization_id", "business_fact_revisions.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_business_facts_organization_id_id"),
        UniqueConstraint("fact_identity", "revision", name="uq_business_facts_identity_revision"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    fact_identity: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    fact_key: Mapped[str] = mapped_column(String(128), nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[object] = mapped_column(JSONB, nullable=False)
    source: Mapped[str] = mapped_column(String(200), nullable=False)
    authority: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="proposed", server_default="proposed"
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    proposed_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class Product(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("key ~ '^[a-z][a-z0-9_]*$'", name="key_format"),
        CheckConstraint("status='registered'", name="status_registered"),
        CheckConstraint("version=1", name="version_immutable"),
        UniqueConstraint("key", name="uq_products_key"),
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), nullable=False)
    owning_module: Mapped[str] = mapped_column(String(100), nullable=False)
    current_product_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="registered", server_default="registered"
    )
    required_capabilities: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    required_configuration_keys: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    required_business_fact_keys: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    required_integrations: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    requires_organization_profile: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    requires_location_profile: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    requires_approval_policy: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    runtime_control_namespace: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ProductEntitlement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_entitlements"
    __table_args__ = (
        CheckConstraint(
            "status IN ('not_enabled','setup_required','configuration_required','connection_required','ready','active','paused','degraded','suspended','archived')",
            name="status",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from", name="effective_period"
        ),
        UniqueConstraint(
            "organization_id", "product_id", name="uq_entitlements_organization_product"
        ),
        UniqueConstraint("organization_id", "id", name="uq_entitlements_organization_id_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="setup_required", server_default="setup_required"
    )
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    service_tier: Mapped[str | None] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ProductEntitlementLocation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "product_entitlement_locations"
    __table_args__ = (
        CheckConstraint("status IN ('active','removed')", name="status"),
        CheckConstraint("version >= 1", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "entitlement_id"],
            ["product_entitlements.organization_id", "product_entitlements.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "entitlement_id",
            "location_id",
            name="uq_entitlement_locations_scope",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entitlement_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    location_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class ConfigurationDefinition(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "configuration_definitions"
    __table_args__ = (
        CheckConstraint(r"key ~ '^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$'", name="key_format"),
        CheckConstraint("schema_version >= 1", name="schema_version_positive"),
        CheckConstraint(
            "merge_strategy IN ('replace','object_merge','append_unique')", name="merge_strategy"
        ),
        UniqueConstraint("key", "schema_version", name="uq_configuration_definitions_key_version"),
    )
    key: Mapped[str] = mapped_column(String(128), nullable=False)
    owning_module: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    value_type: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    platform_default: Mapped[object | None] = mapped_column(JSONB)
    industry_defaults: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    allowed_scopes: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    merge_strategy: Mapped[str] = mapped_column(String(24), nullable=False)
    lower_scope_override_allowed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    sensitivity: Mapped[str] = mapped_column(
        String(32), nullable=False, default="business", server_default="business"
    )
    deprecated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ConfigurationRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "configuration_revisions"
    __table_args__ = (
        CheckConstraint("scope_type IN ('organization','location','product')", name="scope"),
        CheckConstraint(
            "(scope_type='organization' AND location_id IS NULL AND product_id IS NULL) OR (scope_type='location' AND location_id IS NOT NULL AND product_id IS NULL) OR (scope_type='product' AND product_id IS NOT NULL)",
            name="scope_identity",
        ),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint(
            "status IN ('draft','validation_failed','pending_approval','approved','scheduled','active','superseded','revoked','expired','archived')",
            name="status",
        ),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from", name="effective_period"
        ),
        CheckConstraint(
            "status NOT IN ('approved','scheduled','active','superseded','expired') OR approved_at IS NOT NULL",
            name="approval_consistent",
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "supersedes_id"],
            ["configuration_revisions.organization_id", "configuration_revisions.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "id", name="uq_configuration_revisions_organization_id_id"
        ),
        UniqueConstraint(
            "configuration_identity",
            "revision",
            name="uq_configuration_revisions_identity_revision",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    definition_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("configuration_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    configuration_identity: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    location_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    product_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT")
    )
    document: Mapped[object] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="draft", server_default="draft"
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    supersedes_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class PolicyRevision(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "policy_revisions"
    __table_args__ = (
        CheckConstraint(r"policy_key ~ '^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$'", name="key_format"),
        CheckConstraint("category IN ('general','approval','notification')", name="category"),
        CheckConstraint("scope_type IN ('organization','location','product')", name="scope"),
        CheckConstraint(
            "status IN ('draft','validation_failed','pending_approval','approved','scheduled','active','superseded','revoked','expired','archived')",
            name="status",
        ),
        CheckConstraint(
            "status NOT IN ('approved','scheduled','active','superseded','expired','archived') OR (approved_by IS NOT NULL AND approved_at IS NOT NULL)",
            name="approval_consistent",
        ),
        CheckConstraint(
            "(scope_type='organization' AND location_id IS NULL AND product_id IS NULL) OR (scope_type='location' AND location_id IS NOT NULL AND product_id IS NULL) OR (scope_type='product' AND product_id IS NOT NULL)",
            name="scope_identity",
        ),
        CheckConstraint("revision >= 1", name="revision_positive"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from", name="effective_period"
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_policy_revisions_organization_id_id"),
        UniqueConstraint(
            "policy_identity", "revision", name="uq_policy_revisions_identity_revision"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_identity: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    policy_key: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(24), nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    location_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    product_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT")
    )
    document: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class FeatureFlagRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "feature_flag_revisions"
    __table_args__ = (
        CheckConstraint(r"flag_key ~ '^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$'", name="key_format"),
        CheckConstraint("scope_type IN ('organization','location')", name="scope"),
        CheckConstraint(
            "(scope_type='organization' AND location_id IS NULL) OR (scope_type='location' AND location_id IS NOT NULL)",
            name="scope_identity",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from", name="effective_period"
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_feature_flags_organization_id_id"),
        UniqueConstraint("flag_identity", "version", name="uq_feature_flags_identity_version"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    flag_identity: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    flag_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    location_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False)
    risk_class: Mapped[str] = mapped_column(String(32), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class RuntimeControlRevision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "runtime_control_revisions"
    __table_args__ = (
        CheckConstraint(
            r"capability ~ '^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$'", name="capability_format"
        ),
        CheckConstraint("scope_type IN ('organization','location','product')", name="scope"),
        CheckConstraint(
            "(scope_type='organization' AND location_id IS NULL AND product_id IS NULL) OR (scope_type='location' AND location_id IS NOT NULL AND product_id IS NULL) OR (scope_type='product' AND product_id IS NOT NULL)",
            name="scope_identity",
        ),
        CheckConstraint(
            "control_state IN ('allowed','degraded','paused','disabled')", name="state"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "effective_until IS NULL OR effective_until > effective_from", name="effective_period"
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_runtime_controls_organization_id_id"),
        UniqueConstraint(
            "control_identity", "version", name="uq_runtime_controls_identity_version"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    control_identity: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    capability: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    location_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    product_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT")
    )
    control_state: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class OnboardingChecklistItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "onboarding_checklist_items"
    __table_args__ = (
        CheckConstraint(r"item_key ~ '^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$'", name="key_format"),
        CheckConstraint(
            "status IN ('pending','completed','blocked','not_applicable')", name="status"
        ),
        CheckConstraint("severity IN ('blocker','warning')", name="severity"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "(status='completed') = (completed_at IS NOT NULL)", name="completion_consistent"
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "item_key",
            "location_id",
            "product_id",
            name="uq_onboarding_items_scope_key",
        ),
        UniqueConstraint("organization_id", "id", name="uq_onboarding_items_organization_id_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    product_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT")
    )
    item_key: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending", server_default="pending"
    )
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    automated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    evidence: Mapped[str | None] = mapped_column(String(1000))
    remediation: Mapped[str] = mapped_column(String(1000), nullable=False)
    required_permission: Mapped[str] = mapped_column(String(100), nullable=False)
    completed_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class OffboardingPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offboarding_plans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planned','in_progress','blocked','completed','cancelled')", name="status"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        UniqueConstraint("organization_id", "id", name="uq_offboarding_plans_organization_id_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="planned", server_default="planned"
    )
    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    target_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


class OffboardingStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "offboarding_steps"
    __table_args__ = (
        CheckConstraint(r"step_key ~ '^[a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*$'", name="key_format"),
        CheckConstraint(
            "status IN ('pending','completed','blocked','not_applicable')", name="status"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        ForeignKeyConstraint(
            ["organization_id", "plan_id"],
            ["offboarding_plans.organization_id", "offboarding_plans.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id", "plan_id", "step_key", name="uq_offboarding_steps_plan_key"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    plan_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    step_key: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="pending", server_default="pending"
    )
    blocking: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    requirement: Mapped[str] = mapped_column(String(1000), nullable=False)
    evidence: Mapped[str | None] = mapped_column(String(1000))
    completed_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")


Index(
    "ix_service_catalog_organization_created_id",
    ServiceDefinition.organization_id,
    ServiceDefinition.created_at,
    ServiceDefinition.id,
)
Index(
    "ix_business_facts_resolve",
    BusinessFactRevision.organization_id,
    BusinessFactRevision.fact_key,
    BusinessFactRevision.effective_from,
)
Index(
    "ix_configuration_resolve",
    ConfigurationRevision.organization_id,
    ConfigurationRevision.definition_id,
    ConfigurationRevision.effective_from,
)
Index(
    "ix_policy_resolve",
    PolicyRevision.organization_id,
    PolicyRevision.policy_key,
    PolicyRevision.effective_from,
)
Index(
    "ix_feature_flags_resolve",
    FeatureFlagRevision.organization_id,
    FeatureFlagRevision.flag_key,
    FeatureFlagRevision.effective_from,
)
Index(
    "ix_runtime_controls_resolve",
    RuntimeControlRevision.organization_id,
    RuntimeControlRevision.capability,
    RuntimeControlRevision.effective_from,
)
Index(
    "uq_service_assignments_organization",
    ServiceAssignment.organization_id,
    ServiceAssignment.service_id,
    unique=True,
    postgresql_where=ServiceAssignment.scope_type == "organization",
)
Index(
    "uq_service_assignments_location",
    ServiceAssignment.organization_id,
    ServiceAssignment.service_id,
    ServiceAssignment.location_id,
    unique=True,
    postgresql_where=ServiceAssignment.scope_type == "location",
)


class BusinessKnowledgeDocument(UUIDPrimaryKeyMixin, Base):
    """Source-backed business knowledge extracted from GBP, website, and identity data.

    Each record represents a single piece of knowledge (structured facts,
    page text, or identity) with full provenance — source type, reference,
    content hash, authority level, and observation timestamp.

    Organization-scoped.  Optionally location-scoped for location-specific
    knowledge such as service-area pages.
    """

    __tablename__ = "business_knowledge_documents"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('gbp_profile_snapshot','seo_page','organization_profile',"
            "'location_profile')",
            name="ck_knowledge_source_type",
        ),
        CheckConstraint(
            "authority IN ('provider_observed','system_derived','operator_verified',"
            "'client_approved')",
            name="ck_knowledge_authority",
        ),
        CheckConstraint(
            "content_type IN ('structured_facts','page_text','identity')",
            name="ck_knowledge_content_type",
        ),
        CheckConstraint(
            "status IN ('active','superseded','expired')",
            name="ck_knowledge_status",
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "source_type",
            "source_reference",
            "content_hash",
            name="uq_knowledge_doc_source_hash",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    location_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))

    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    authority: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    content_type: Mapped[str] = mapped_column(String(32), nullable=False)

    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="active", server_default="active"
    )
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
