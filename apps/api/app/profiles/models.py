"""SQLAlchemy models for controlled organization and location profiles."""

from uuid import UUID

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def _collection_checks(*fields: str) -> tuple[CheckConstraint, ...]:
    checks: list[CheckConstraint] = []
    for field_name in fields:
        checks.extend(
            (
                CheckConstraint(
                    f"{field_name} IS NULL OR cardinality({field_name}) <= 50",
                    name=f"{field_name}_count",
                ),
                CheckConstraint(
                    f"{field_name} IS NULL OR "
                    f"octet_length(array_to_json({field_name})::text) <= 16384",
                    name=f"{field_name}_size",
                ),
            )
        )
    return tuple(checks)


class OrganizationProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One optional controlled business-context record per organization."""

    __tablename__ = "organization_profiles"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        *_collection_checks(
            "primary_services",
            "approved_claims",
            "prohibited_claims",
            "tone_guidelines",
            "legal_disclaimers",
        ),
        UniqueConstraint("organization_id", name="uq_organization_profiles_organization_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_organization_profiles_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    brand_name: Mapped[str | None] = mapped_column(String(200))
    brand_summary: Mapped[str | None] = mapped_column(String(1_000))
    business_description: Mapped[str | None] = mapped_column(String(8_000))
    value_proposition: Mapped[str | None] = mapped_column(String(4_000))
    target_customer: Mapped[str | None] = mapped_column(String(4_000))
    primary_services: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    approved_claims: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    prohibited_claims: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    tone_guidelines: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    legal_disclaimers: Mapped[list[str] | None] = mapped_column(ARRAY(String(2_000)))
    default_call_to_action: Mapped[str | None] = mapped_column(String(1_000))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class LocationProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One optional controlled context override record per organization-owned location."""

    __tablename__ = "location_profiles"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        *_collection_checks(
            "primary_services",
            "local_landmarks",
            "local_references",
            "approved_claims",
            "prohibited_claims",
            "tone_overrides",
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            name="fk_location_profiles_organization_location_locations",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("location_id", name="uq_location_profiles_location_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "organizations.id",
            name="fk_location_profiles_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    location_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    local_description: Mapped[str | None] = mapped_column(String(8_000))
    primary_services: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    service_area: Mapped[str | None] = mapped_column(String(4_000))
    local_landmarks: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    local_references: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    approved_claims: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    prohibited_claims: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    tone_overrides: Mapped[list[str] | None] = mapped_column(ARRAY(String(500)))
    call_to_action_override: Mapped[str | None] = mapped_column(String(1_000))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
