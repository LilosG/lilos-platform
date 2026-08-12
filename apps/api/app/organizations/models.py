"""SQLAlchemy model for the organization tenant boundary."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType


def _enum_values(enum_class: type[OrganizationType] | type[OrganizationStatus]) -> list[str]:
    return [item.value for item in enum_class]


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Highest-level platform ownership and isolation boundary."""

    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("char_length(slug) BETWEEN 3 AND 63", name="slug_length"),
        CheckConstraint("slug = lower(btrim(slug))", name="slug_normalized"),
        CheckConstraint(
            "slug ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'",
            name="slug_format",
        ),
        CheckConstraint(
            "slug NOT IN ('admin', 'api', 'internal', 'platform', 'public', "
            "'system', 'support', 'www')",
            name="slug_not_reserved",
        ),
        CheckConstraint("default_currency ~ '^[A-Z]{3}$'", name="currency_format"),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR "
            "(status <> 'archived' AND archived_at IS NULL)",
            name="archived_timestamp_matches_status",
        ),
        CheckConstraint(
            "onboarding_mode IS NULL OR "
            "onboarding_mode IN ('managed', 'co_managed', 'self_service')",
            name="onboarding_mode",
        ),
        UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(63), nullable=False)
    organization_type: Mapped[OrganizationType] = mapped_column(
        Enum(
            OrganizationType,
            name="organization_type",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=_enum_values,
            length=16,
        ),
        nullable=False,
    )
    status: Mapped[OrganizationStatus] = mapped_column(
        Enum(
            OrganizationStatus,
            name="organization_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=_enum_values,
            length=16,
        ),
        nullable=False,
        default=OrganizationStatus.PROSPECT,
        server_default=text("'prospect'"),
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(200))
    website_url: Mapped[str | None] = mapped_column(String(2048))
    primary_contact_name: Mapped[str | None] = mapped_column(String(200))
    primary_contact_email: Mapped[str | None] = mapped_column(String(254))
    primary_contact_phone: Mapped[str | None] = mapped_column(String(32))
    billing_email: Mapped[str | None] = mapped_column(String(254))
    external_reference: Mapped[str | None] = mapped_column(String(200))
    onboarding_status: Mapped[str | None] = mapped_column(String(64))
    onboarding_mode: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        default=None,
        comment=(
            "Onboarding responsibility mode. NULL resolves to managed (legacy). "
            "Valid: managed, co_managed, self_service."
        ),
    )
    industry_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "industries.id",
            name="fk_organizations_industry_id_industries",
            ondelete="RESTRICT",
        ),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
    )


Index("ix_organizations_created_at_id", Organization.created_at, Organization.id)
