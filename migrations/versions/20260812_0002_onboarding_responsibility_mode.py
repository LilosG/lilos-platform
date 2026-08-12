"""Add onboarding_mode and co-managed step assignments for unified onboarding.

Supports managed, co_managed, and self_service operating modes over ONE
onboarding engine. The onboarding_mode column is nullable; existing NULL
organizations resolve to "managed" (deterministic legacy contract).

The onboarding_step_assignments table persists co-managed step delegation
across API processes, worker restarts, and browser sessions so that
onboarding is fully resumable from authoritative database state.
"""

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0002"
down_revision: str | None = "20260812_0001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # --- onboarding_mode on organizations ---
    op.add_column(
        "organizations",
        sa.Column(
            "onboarding_mode",
            sa.String(16),
            nullable=True,
            server_default=None,
        ),
    )
    op.execute(
        "ALTER TABLE organizations ADD CONSTRAINT ck_organizations_onboarding_mode "
        "CHECK (onboarding_mode IS NULL OR "
        "onboarding_mode IN ('managed', 'co_managed', 'self_service'))"
    )
    op.execute(
        "COMMENT ON COLUMN organizations.onboarding_mode IS "
        "'Onboarding responsibility mode. NULL resolves to managed (legacy). "
        "Valid: managed, co_managed, self_service.'"
    )

    # --- co-managed step assignments ---
    op.create_table(
        "onboarding_step_assignments",
        sa.Column(
            "id",
            sa.Uuid(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "organization_id",
            sa.Uuid(),
            sa.ForeignKey(
                "organizations.id",
                ondelete="CASCADE",
                name="fk_onboarding_step_assignments_organization_id_organizations",
            ),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(64), nullable=False),
        sa.Column(
            "assigned_to",
            sa.String(16),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "assigned_to IN ('agency', 'client')",
            name="assigned_to",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "step_key",
            name="uq_onboarding_step_assignments_org_step",
        ),
    )
    op.create_index(
        "ix_onboarding_step_assignments_organization_id",
        "onboarding_step_assignments",
        ["organization_id"],
    )
    op.execute(
        "COMMENT ON TABLE onboarding_step_assignments IS "
        "'Co-managed onboarding step delegation. One row per step per org. "
        "assigned_to is ''agency'' or ''client''. Deleted rows mean the step "
        "reverts to agency control.'"
    )


def downgrade() -> None:
    op.drop_table("onboarding_step_assignments")
    op.execute(
        "ALTER TABLE organizations DROP CONSTRAINT IF EXISTS ck_organizations_onboarding_mode"
    )
    op.drop_column("organizations", "onboarding_mode")
