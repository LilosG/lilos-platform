"""Reconcile SEO website verification from successful Search Console evidence."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260820_0002"
down_revision: str | Sequence[str] | None = "20260820_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    """Promote stale pending websites only when provider sync evidence exists."""
    op.execute(
        sa.text(
            """
            UPDATE seo_websites AS website
            SET
                status = 'active',
                ownership_status = 'verified',
                verified_at = COALESCE(
                    website.verified_at,
                    evidence.last_synced_at,
                    CURRENT_TIMESTAMP
                )
            FROM (
                SELECT
                    organization_id,
                    website_id,
                    MAX(last_synced_at) AS last_synced_at
                FROM seo_search_properties
                WHERE provider = 'google_search_console'
                  AND mapping_status = 'mapped'
                  AND last_synced_at IS NOT NULL
                GROUP BY organization_id, website_id
            ) AS evidence
            WHERE website.organization_id = evidence.organization_id
              AND website.id = evidence.website_id
              AND website.status = 'pending_verification'
            """
        )
    )


def downgrade() -> None:
    """Do not erase provider-backed verification evidence on downgrade."""
    # The prior state cannot be reconstructed safely: some websites may have
    # become legitimately verified after this reconciliation ran.
    pass
