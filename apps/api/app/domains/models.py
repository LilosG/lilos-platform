"""SQLAlchemy model for organization-owned approved domains."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
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
from apps.api.app.domains.enums import OrganizationDomainStatus


def _status_values(enum_class: type[OrganizationDomainStatus]) -> list[str]:
    return [item.value for item in enum_class]


class OrganizationDomain(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One approved domain (primary or additional) owned by an organization."""

    __tablename__ = "organization_domains"
    __table_args__ = (
        CheckConstraint("char_length(domain) BETWEEN 3 AND 253", name="domain_length"),
        CheckConstraint("domain = lower(btrim(domain))", name="domain_normalized"),
        CheckConstraint(
            r"domain ~ '^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?"
            r"(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$'",
            name="domain_format",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR "
            "(status <> 'archived' AND archived_at IS NULL)",
            name="archived_timestamp_matches_status",
        ),
        UniqueConstraint("organization_id", "domain", name="uq_organization_domains_org_domain"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_organization_domains_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(String(253), nullable=False)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    status: Mapped[OrganizationDomainStatus] = mapped_column(
        Enum(
            OrganizationDomainStatus,
            name="organization_domain_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=_status_values,
            length=16,
        ),
        nullable=False,
        default=OrganizationDomainStatus.ACTIVE,
        server_default=text("'active'"),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


Index(
    "uq_organization_domains_primary_per_organization",
    OrganizationDomain.organization_id,
    unique=True,
    postgresql_where=(OrganizationDomain.is_primary.is_(True))
    & (OrganizationDomain.status == OrganizationDomainStatus.ACTIVE),
)

Index(
    "ix_organization_domains_organization_created_at_id",
    OrganizationDomain.organization_id,
    OrganizationDomain.created_at,
    OrganizationDomain.id,
)
