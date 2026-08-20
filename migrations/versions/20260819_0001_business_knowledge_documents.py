# ruff: noqa: E501
"""Create business_knowledge_documents table and add body_text to seo_pages.

business_knowledge_documents stores source-backed knowledge extracted from
GBP snapshots, crawled website pages, and organization/location identity
data.  Every record is organization-scoped and optionally location-scoped
with full provenance (source_type, source_reference, content_hash,
authority, observed_at).

seo_pages.body_text stores normalized page body text from successful
crawls for downstream knowledge retrieval.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import UUID

revision = "20260819_0001"
down_revision: str | Sequence[str] | None = "20260818_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_knowledge_documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("location_id", UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(32), nullable=False),
        sa.Column("source_reference", sa.String(500), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("authority", sa.String(32), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("supersedes_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_foreign_key(
        "fk_business_knowledge_location",
        "business_knowledge_documents",
        "locations",
        ["organization_id", "location_id"],
        ["organization_id", "id"],
        ondelete="RESTRICT",
    )

    op.create_unique_constraint(
        "uq_knowledge_doc_source_hash",
        "business_knowledge_documents",
        ["organization_id", "source_type", "source_reference", "content_hash"],
    )

    op.execute("ALTER TABLE seo_pages ADD COLUMN IF NOT EXISTS body_text TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE seo_pages DROP COLUMN IF EXISTS body_text")
    op.execute("DROP TABLE IF EXISTS business_knowledge_documents CASCADE")
