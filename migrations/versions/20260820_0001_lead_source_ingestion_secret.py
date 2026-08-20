# ruff: noqa: E501
"""Add ingestion_key and ingestion_secret_hash to lead_sources.

ingestion_key is a server-generated, globally-unique, opaque identifier
used for machine-to-machine lead intake.  It is distinct from the
human-readable, org-scoped ``key`` column so that two organizations may
both use ``key="website"`` without ambiguity.

ingestion_secret_hash stores a PBKDF2-hashed secret.  The plaintext is
generated at source creation, returned once, and never persisted.
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
    if "ingestion_key" not in columns:
        op.add_column(
            "lead_sources",
            sa.Column("ingestion_key", sa.String(length=64), nullable=True),
        )
        op.create_unique_constraint(
            "uq_lead_sources_ingestion_key", "lead_sources", ["ingestion_key"]
        )
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
    if "ingestion_key" in columns:
        op.drop_constraint("uq_lead_sources_ingestion_key", "lead_sources")
        op.drop_column("lead_sources", "ingestion_key")
