"""Deterministically bind unmapped GA4 properties to their organization's sole website.

`routes/insights.py`'s GA4 mapping route hardcoded `website_id=None` on every
call, so every organization's `analytics_properties` row has a NULL
`website_id` regardless of how many SEO websites the organization has. That
route has been replaced by `POST /integrations/google/analytics/properties/map`,
which always requires and persists a real `website_id`; this migration
repairs the rows already written by the old route.

Only unambiguous cases are backfilled: an `analytics_properties` row with
`website_id IS NULL` whose organization has exactly one `seo_websites` row.
An organization with zero or multiple websites is left NULL -- Integrations
surfaces a "bind property to website" action for those instead of guessing.

Revision ID: 20260929_0003
Revises: 20260929_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260929_0003"
down_revision: str | Sequence[str] | None = "20260929_0002"
branch_labels = depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE analytics_properties AS ap
            SET website_id = single_website.id
            FROM (
                SELECT organization_id, (array_agg(id))[1] AS id
                FROM seo_websites
                GROUP BY organization_id
                HAVING COUNT(*) = 1
            ) AS single_website
            WHERE ap.website_id IS NULL
              AND ap.organization_id = single_website.organization_id
            """
        )
    )


def downgrade() -> None:
    """Data repair has no meaningful reverse; nothing to do."""
