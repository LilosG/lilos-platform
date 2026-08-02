# ruff: noqa: E501
"""Create organization-owned locations and bind audit location scope.

Revision ID: 20260802_0002
Revises: 20260802_0001
Create Date: 2026-08-02

The table is additive, has no business-domain descendants, and uses organization-scoped
uniqueness. The audit foreign key is validated when existing references are resolvable; preserved
historical references after a destructive disposable downgrade remain unvalidated while the
constraint still protects all new writes. Downgrade retains all organization and append-only audit
infrastructure without rewriting immutable audit evidence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0002"
down_revision: str | Sequence[str] | None = "20260802_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOCATION_TYPES = ("physical", "service_area", "hybrid", "virtual")
LOCATION_STATUSES = (
    "setup_required",
    "active",
    "paused",
    "closed_temporarily",
    "closed_permanently",
    "archived",
)


def _values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("location_type", sa.String(16), nullable=False),
        sa.Column("status", sa.String(24), server_default="setup_required", nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("address_line_1", sa.String(200)),
        sa.Column("address_line_2", sa.String(200)),
        sa.Column("city", sa.String(100)),
        sa.Column("region", sa.String(100)),
        sa.Column("postal_code", sa.String(32)),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(10, 6)),
        sa.Column("service_area_description", sa.String(1000)),
        sa.Column("phone", sa.String(32)),
        sa.Column("email", sa.String(254)),
        sa.Column("website_url", sa.String(2048)),
        sa.Column("external_reference", sa.String(200)),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        sa.CheckConstraint("char_length(slug) BETWEEN 3 AND 63", name="slug_length"),
        sa.CheckConstraint("slug = lower(btrim(slug))", name="slug_normalized"),
        sa.CheckConstraint("slug ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'", name="slug_format"),
        sa.CheckConstraint(
            "slug NOT IN ('admin', 'api', 'internal', 'platform', 'public', 'system', 'support', 'www')",
            name="slug_not_reserved",
        ),
        sa.CheckConstraint(f"location_type IN ({_values(LOCATION_TYPES)})", name="location_type"),
        sa.CheckConstraint(f"status IN ({_values(LOCATION_STATUSES)})", name="location_status"),
        sa.CheckConstraint("country_code ~ '^[A-Z]{2}$'", name="country_code_format"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR (status <> 'archived' AND archived_at IS NULL)",
            name="archived_timestamp_matches_status",
        ),
        sa.CheckConstraint(
            "location_type <> 'physical' OR (address_line_1 IS NOT NULL AND city IS NOT NULL AND region IS NOT NULL AND postal_code IS NOT NULL)",
            name="physical_address_required",
        ),
        sa.CheckConstraint(
            "location_type <> 'service_area' OR (service_area_description IS NOT NULL AND ((address_line_1 IS NULL AND city IS NULL AND region IS NULL AND postal_code IS NULL) OR (address_line_1 IS NOT NULL AND city IS NOT NULL AND region IS NOT NULL AND postal_code IS NOT NULL)))",
            name="service_area_shape",
        ),
        sa.CheckConstraint(
            "location_type <> 'hybrid' OR (address_line_1 IS NOT NULL AND city IS NOT NULL AND region IS NOT NULL AND postal_code IS NOT NULL AND service_area_description IS NOT NULL)",
            name="hybrid_requirements",
        ),
        sa.CheckConstraint(
            "location_type <> 'virtual' OR (website_url IS NOT NULL AND address_line_1 IS NULL AND address_line_2 IS NULL AND city IS NULL AND region IS NULL AND postal_code IS NULL AND latitude IS NULL AND longitude IS NULL AND service_area_description IS NULL)",
            name="virtual_requirements",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_locations_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_locations"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_locations_organization_id_slug"),
    )
    op.create_index(
        "ix_locations_organization_created_at_id",
        "locations",
        ["organization_id", "created_at", "id"],
    )
    op.create_index("ix_locations_organization_id_id", "locations", ["organization_id", "id"])
    op.create_index(
        "uq_locations_primary_per_organization",
        "locations",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("is_primary IS true"),
    )
    op.execute(
        "ALTER TABLE audit_events ADD CONSTRAINT "
        "fk_audit_events_location_id_locations FOREIGN KEY (location_id) "
        "REFERENCES locations(id) ON DELETE RESTRICT NOT VALID"
    )
    op.execute(
        """
        DO $validate_audit_location_fk$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM audit_events AS audit
                WHERE audit.location_id IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM locations WHERE locations.id = audit.location_id
                  )
            ) THEN
                ALTER TABLE audit_events
                VALIDATE CONSTRAINT fk_audit_events_location_id_locations;
            END IF;
        END;
        $validate_audit_location_fk$
        """
    )
    op.create_index(
        "ix_audit_events_location_occurred_at_id",
        "audit_events",
        ["location_id", sa.text("occurred_at DESC"), sa.text("id DESC")],
    )
    op.execute("""
        CREATE FUNCTION prevent_location_slug_change() RETURNS trigger LANGUAGE plpgsql AS $location_slug_immutable$
        BEGIN
            IF NEW.slug IS DISTINCT FROM OLD.slug THEN
                RAISE EXCEPTION 'location slug is immutable' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $location_slug_immutable$
    """)
    op.execute(
        "CREATE TRIGGER location_slug_immutable BEFORE UPDATE ON locations FOR EACH ROW EXECUTE FUNCTION prevent_location_slug_change()"
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_location_occurred_at_id", table_name="audit_events")
    op.drop_constraint("fk_audit_events_location_id_locations", "audit_events", type_="foreignkey")
    op.drop_table("locations")
    op.execute("DROP FUNCTION prevent_location_slug_change()")
