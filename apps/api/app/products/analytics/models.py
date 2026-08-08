"""GA4 Analytics property mapping for the Insights product."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnalyticsProperty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An operator-selected GA4 property bound to the shared Google connection.

    Mirrors ``SEOSearchProperty``: idempotent mapping keyed on
    (organization, provider, external property id), with freshness state. The
    numeric GA4 property id is stored separately for the Analytics Data API
    path. The optional ``website_id`` link enables canonical-domain
    recommendation against the same SEO website origin.
    """

    __tablename__ = "analytics_properties"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "connection_id"],
            ["integration_connections.organization_id", "integration_connections.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "website_id"],
            ["seo_websites.organization_id", "seo_websites.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("organization_id", "id", name="uq_analytics_properties_org_id"),
        UniqueConstraint(
            "organization_id",
            "provider",
            "external_property_id",
            name="uq_analytics_property_external",
        ),
        CheckConstraint(
            "mapping_status IN ('mapped','stale','disconnected')", name="mapping_status"
        ),
        CheckConstraint(
            "freshness_status IN ('never_synced','fresh','stale')", name="freshness_status"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    connection_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    website_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    external_property_id: Mapped[str] = mapped_column(String(500), nullable=False)
    property_number: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(300), nullable=False)
    mapping_status: Mapped[str] = mapped_column(String(16), nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    freshness_status: Mapped[str] = mapped_column(String(16), nullable=False)
