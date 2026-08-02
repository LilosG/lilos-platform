"""PostgreSQL models for organization-owned location groups and memberships."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.app.location_groups.enums import LocationGroupStatus


def _status_values(enum_class: type[LocationGroupStatus]) -> list[str]:
    return [item.value for item in enum_class]


class LocationGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "location_groups"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) BETWEEN 1 AND 120", name="name_length"),
        CheckConstraint("char_length(key) BETWEEN 3 AND 63", name="key_length"),
        CheckConstraint("key = lower(btrim(key))", name="key_normalized"),
        CheckConstraint("key ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'", name="key_format"),
        CheckConstraint(
            "key NOT IN ('admin', 'api', 'internal', 'platform', 'public', "
            "'system', 'support', 'www')",
            name="key_not_reserved",
        ),
        CheckConstraint(
            "description IS NULL OR length(btrim(description)) BETWEEN 1 AND 1000",
            name="description_length",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR "
            "(status <> 'archived' AND archived_at IS NULL)",
            name="archived_timestamp_matches_status",
        ),
        UniqueConstraint("organization_id", "id", name="uq_location_groups_organization_id_id"),
        UniqueConstraint("organization_id", "key", name="uq_location_groups_organization_id_key"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_location_groups_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key: Mapped[str] = mapped_column(String(63), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1_000))
    status: Mapped[LocationGroupStatus] = mapped_column(
        Enum(
            LocationGroupStatus,
            name="location_group_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=_status_values,
            length=16,
        ),
        nullable=False,
        default=LocationGroupStatus.ACTIVE,
        server_default=text("'active'"),
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


Index(
    "ix_location_groups_organization_created_at_id",
    LocationGroup.organization_id,
    LocationGroup.created_at,
    LocationGroup.id,
)


class LocationGroupMembership(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "location_group_memberships"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "location_group_id"],
            ["location_groups.organization_id", "location_groups.id"],
            name="fk_lg_memberships_organization_group",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            name="fk_lg_memberships_organization_location",
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "organization_id",
            "location_group_id",
            "location_id",
            name="uq_lg_memberships_organization_group_location",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_lg_memberships_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    location_group_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    location_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


Index(
    "ix_location_group_memberships_organization_group_created_at_id",
    LocationGroupMembership.organization_id,
    LocationGroupMembership.location_group_id,
    LocationGroupMembership.created_at,
    LocationGroupMembership.id,
)
