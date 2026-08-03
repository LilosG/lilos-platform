"""Provider registry, connection, OAuth intent, and external resource mappings."""

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


class Provider(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_providers"
    __table_args__ = (
        UniqueConstraint("key", name="uq_integration_providers_key"),
        CheckConstraint("status IN ('active','deprecated')", name="status"),
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    capabilities: Mapped[list[object]] = mapped_column(JSONB, nullable=False)
    manifest_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class IntegrationConnection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            name="fk_connections_org_location",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_connections_org_id"),
        UniqueConstraint(
            "organization_id",
            "provider_id",
            "external_account_reference",
            name="uq_connections_account",
        ),
        CheckConstraint(
            "status IN ('pending','connected','degraded','reconnect_required','disconnected')",
            name="status",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    location_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    provider_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("integration_providers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    external_account_reference: Mapped[str | None] = mapped_column(String(255))
    credential_reference: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="pending")
    granted_capabilities: Mapped[list[object]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")


class OAuthAuthorizationIntent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "oauth_authorization_intents"
    __table_args__ = (
        UniqueConstraint("state_hash", name="uq_oauth_intents_state_hash"),
        CheckConstraint("status IN ('pending','consumed','expired','failed')", name="status"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    connection_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("integration_connections.id", ondelete="RESTRICT"),
        nullable=False,
    )
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    pkce_verifier_reference: Mapped[str | None] = mapped_column(String(500))
    exact_redirect_uri: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ProviderResourceMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_resource_mappings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["integration_connections.organization_id", "integration_connections.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "connection_id",
            "resource_type",
            "external_resource_id",
            name="uq_provider_resource_mapping",
        ),
        CheckConstraint("status IN ('active','stale','disconnected')", name="status"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    external_resource_id: Mapped[str] = mapped_column(String(500), nullable=False)
    platform_resource_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default="active")
