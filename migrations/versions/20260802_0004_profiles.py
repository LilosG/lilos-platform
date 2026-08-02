# ruff: noqa: E501
"""Create organization and location controlled profile foundations.

Revision ID: 20260802_0004
Revises: 20260802_0003
Create Date: 2026-08-02

The migration adds a supporting organization/location uniqueness constraint, then creates one
optional profile table per parent. It does not backfill, compose, infer, or seed profile content.
Profile IDs remain ordinary audit resource references rather than audit foreign keys, so downgrade
can preserve immutable audit history without rewriting evidence.
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260802_0004"
down_revision: str | Sequence[str] | None = "20260802_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _collection_checks(*fields: str) -> list[sa.CheckConstraint]:
    checks: list[sa.CheckConstraint] = []
    for field_name in fields:
        checks.extend(
            (
                sa.CheckConstraint(
                    f"{field_name} IS NULL OR cardinality({field_name}) <= 50",
                    name=f"{field_name}_count",
                ),
                sa.CheckConstraint(
                    f"{field_name} IS NULL OR octet_length(array_to_json({field_name})::text) <= 16384",
                    name=f"{field_name}_size",
                ),
            )
        )
    return checks


def _identity_columns() -> list[sa.Column[Any]]:
    return [
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
    ]


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_locations_organization_id_id", "locations", ["organization_id", "id"]
    )
    op.create_table(
        "organization_profiles",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brand_name", sa.String(200)),
        sa.Column("brand_summary", sa.String(1_000)),
        sa.Column("business_description", sa.String(8_000)),
        sa.Column("value_proposition", sa.String(4_000)),
        sa.Column("target_customer", sa.String(4_000)),
        sa.Column("primary_services", postgresql.ARRAY(sa.String(500))),
        sa.Column("approved_claims", postgresql.ARRAY(sa.String(500))),
        sa.Column("prohibited_claims", postgresql.ARRAY(sa.String(500))),
        sa.Column("tone_guidelines", postgresql.ARRAY(sa.String(500))),
        sa.Column("legal_disclaimers", postgresql.ARRAY(sa.String(2_000))),
        sa.Column("default_call_to_action", sa.String(1_000)),
        *_identity_columns(),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        *_collection_checks(
            "primary_services",
            "approved_claims",
            "prohibited_claims",
            "tone_guidelines",
            "legal_disclaimers",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_organization_profiles_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_profiles"),
        sa.UniqueConstraint("organization_id", name="uq_organization_profiles_organization_id"),
    )
    op.create_table(
        "location_profiles",
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("local_description", sa.String(8_000)),
        sa.Column("primary_services", postgresql.ARRAY(sa.String(500))),
        sa.Column("service_area", sa.String(4_000)),
        sa.Column("local_landmarks", postgresql.ARRAY(sa.String(500))),
        sa.Column("local_references", postgresql.ARRAY(sa.String(500))),
        sa.Column("approved_claims", postgresql.ARRAY(sa.String(500))),
        sa.Column("prohibited_claims", postgresql.ARRAY(sa.String(500))),
        sa.Column("tone_overrides", postgresql.ARRAY(sa.String(500))),
        sa.Column("call_to_action_override", sa.String(1_000)),
        *_identity_columns(),
        sa.CheckConstraint("version >= 1", name="version_positive"),
        *_collection_checks(
            "primary_services",
            "local_landmarks",
            "local_references",
            "approved_claims",
            "prohibited_claims",
            "tone_overrides",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_location_profiles_organization_id_organizations",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            name="fk_location_profiles_organization_location_locations",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_location_profiles"),
        sa.UniqueConstraint("location_id", name="uq_location_profiles_location_id"),
    )


def downgrade() -> None:
    op.drop_table("location_profiles")
    op.drop_table("organization_profiles")
    op.drop_constraint("uq_locations_organization_id_id", "locations", type_="unique")
