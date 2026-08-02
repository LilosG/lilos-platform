"""Create the organization tenant boundary and bind audit scope.

Revision ID: 20260802_0001
Revises: 20260801_0002
Create Date: 2026-08-02

Reason: establish organization as the platform's primary tenant ownership boundary.
Tables affected: organizations; audit_events receives one nullable organization foreign key.
Constraints: UUID primary key, unique immutable-shape slug, stable type/status checks, bounded
fields, lifecycle/archive consistency, currency shape, positive optimistic-lock version, and a
trigger rejecting slug changes.
Indexes: deterministic administrative listing by created_at and id; slug uniqueness is provided by
its named unique constraint.
Data backfill: none. Existing non-null audit organization references must identify an organization;
because organizations did not previously exist, valid deployments are expected to have none.
Application compatibility: additive; temporary internal routes remain disabled by default.
Lock risk: creation is additive. Adding the audit foreign key briefly locks audit_events and fails
rather than accepting an invalid pre-existing organization reference.
Rollback: drop the audit foreign key before organizations, preserving audit_events and its trigger.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0001"
down_revision: str | Sequence[str] | None = "20260801_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_TYPES = ("client", "internal", "partner", "demo", "test")
ORGANIZATION_STATUSES = (
    "prospect",
    "onboarding",
    "active",
    "paused",
    "suspended",
    "offboarding",
    "archived",
)


def _quoted_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    """Create organization ownership and enforce valid audit organization references."""
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=63), nullable=False),
        sa.Column("organization_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="prospect", nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("default_currency", sa.String(length=3), nullable=False),
        sa.Column("legal_name", sa.String(length=200), nullable=True),
        sa.Column("website_url", sa.String(length=2048), nullable=True),
        sa.Column("primary_contact_name", sa.String(length=200), nullable=True),
        sa.Column("primary_contact_email", sa.String(length=254), nullable=True),
        sa.Column("primary_contact_phone", sa.String(length=32), nullable=True),
        sa.Column("billing_email", sa.String(length=254), nullable=True),
        sa.Column("external_reference", sa.String(length=200), nullable=True),
        sa.Column("onboarding_status", sa.String(length=64), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "version",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "slug ~ '^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$'",
            name="slug_format",
        ),
        sa.CheckConstraint(
            "slug NOT IN ('admin', 'api', 'internal', 'platform', 'public', "
            "'system', 'support', 'www')",
            name="slug_not_reserved",
        ),
        sa.CheckConstraint(
            f"organization_type IN ({_quoted_values(ORGANIZATION_TYPES)})",
            name="organization_type",
        ),
        sa.CheckConstraint(
            f"status IN ({_quoted_values(ORGANIZATION_STATUSES)})",
            name="organization_status",
        ),
        sa.CheckConstraint("default_currency ~ '^[A-Z]{3}$'", name="currency_format"),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        sa.CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR "
            "(status <> 'archived' AND archived_at IS NULL)",
            name="archived_timestamp_matches_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index(
        "ix_organizations_created_at_id",
        "organizations",
        ["created_at", "id"],
    )
    op.create_foreign_key(
        "fk_audit_events_organization_id_organizations",
        "audit_events",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.execute(
        """
        CREATE FUNCTION prevent_organization_slug_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $organization_slug_immutable$
        BEGIN
            IF NEW.slug IS DISTINCT FROM OLD.slug THEN
                RAISE EXCEPTION 'organization slug is immutable' USING ERRCODE = '55000';
            END IF;
            RETURN NEW;
        END;
        $organization_slug_immutable$
        """
    )
    op.execute(
        """
        CREATE TRIGGER organization_slug_immutable
        BEFORE UPDATE ON organizations
        FOR EACH ROW EXECUTE FUNCTION prevent_organization_slug_change()
        """
    )


def downgrade() -> None:
    """Remove organization ownership while retaining the immutable audit foundation."""
    op.drop_constraint(
        "fk_audit_events_organization_id_organizations",
        "audit_events",
        type_="foreignkey",
    )
    op.drop_table("organizations")
    op.execute("DROP FUNCTION prevent_organization_slug_change()")
