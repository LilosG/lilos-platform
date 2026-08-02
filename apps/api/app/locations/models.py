# ruff: noqa: E501
"""SQLAlchemy model for organization-owned operating locations."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.app.locations.enums import LocationStatus, LocationType


def _enum_values(enum_class: type[LocationType] | type[LocationStatus]) -> list[str]:
    return [item.value for item in enum_class]


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One operating unit owned by exactly one organization."""

    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("char_length(slug) BETWEEN 3 AND 63", name="slug_length"),
        CheckConstraint("slug = lower(btrim(slug))", name="slug_normalized"),
        CheckConstraint("slug ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'", name="slug_format"),
        CheckConstraint(
            "slug NOT IN ('admin', 'api', 'internal', 'platform', 'public', 'system', 'support', 'www')",
            name="slug_not_reserved",
        ),
        CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="country_code_format"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR (status <> 'archived' AND archived_at IS NULL)",
            name="archived_timestamp_matches_status",
        ),
        CheckConstraint(
            "location_type <> 'physical' OR (address_line_1 IS NOT NULL AND city IS NOT NULL AND region IS NOT NULL AND postal_code IS NOT NULL)",
            name="physical_address_required",
        ),
        CheckConstraint(
            "location_type <> 'service_area' OR (service_area_description IS NOT NULL AND ((address_line_1 IS NULL AND city IS NULL AND region IS NULL AND postal_code IS NULL) OR (address_line_1 IS NOT NULL AND city IS NOT NULL AND region IS NOT NULL AND postal_code IS NOT NULL)))",
            name="service_area_shape",
        ),
        CheckConstraint(
            "location_type <> 'hybrid' OR (address_line_1 IS NOT NULL AND city IS NOT NULL AND region IS NOT NULL AND postal_code IS NOT NULL AND service_area_description IS NOT NULL)",
            name="hybrid_requirements",
        ),
        CheckConstraint(
            "location_type <> 'virtual' OR (website_url IS NOT NULL AND address_line_1 IS NULL AND address_line_2 IS NULL AND city IS NULL AND region IS NULL AND postal_code IS NULL AND latitude IS NULL AND longitude IS NULL AND service_area_description IS NULL)",
            name="virtual_requirements",
        ),
        UniqueConstraint("organization_id", "id", name="uq_locations_organization_id_id"),
        UniqueConstraint("organization_id", "slug", name="uq_locations_organization_id_slug"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_locations_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    location_type: Mapped[LocationType] = mapped_column(
        Enum(
            LocationType,
            name="location_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=_enum_values,
            length=16,
        ),
        nullable=False,
    )
    status: Mapped[LocationStatus] = mapped_column(
        Enum(
            LocationStatus,
            name="location_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=_enum_values,
            length=24,
        ),
        nullable=False,
        default=LocationStatus.SETUP_REQUIRED,
        server_default=text("'setup_required'"),
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    address_line_1: Mapped[str | None] = mapped_column(String(200))
    address_line_2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(32))
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    service_area_description: Mapped[str | None] = mapped_column(String(1000))
    phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(254))
    website_url: Mapped[str | None] = mapped_column(String(2048))
    external_reference: Mapped[str | None] = mapped_column(String(200))
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


Index(
    "ix_locations_organization_created_at_id",
    Location.organization_id,
    Location.created_at,
    Location.id,
)
Index("ix_locations_organization_id_id", Location.organization_id, Location.id)
Index(
    "uq_locations_primary_per_organization",
    Location.organization_id,
    unique=True,
    postgresql_where=Location.is_primary.is_(True),
)
