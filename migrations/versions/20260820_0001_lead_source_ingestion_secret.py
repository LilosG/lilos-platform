# ruff: noqa: E501
"""Add ingestion_secret_hash to lead_sources for machine-to-machine intake.

Each LeadSource may carry an optional bcrypt-hashed ingestion secret.
When present, an external system (web form, CRM, automation) can submit
leads through the source-scoped intake endpoint by presenting the
source key and plaintext secret.  The secret is generated server-side
at source creation and returned once; it is never stored in plaintext.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260820_0001"
down_revision: str | Sequence[str] | None = "20260819_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("lead_sources")}
    if "ingestion_secret_hash" not in columns:
        op.add_column(
            "lead_sources",
            sa.Column("ingestion_secret_hash", sa.String(length=256), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("lead_sources")}
    if "ingestion_secret_hash" in columns:
        op.drop_column("lead_sources", "ingestion_secret_hash")
