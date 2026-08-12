"""Correct product catalog: GBP and Reviews do not require LocationProfile.

GBP and Reviews services operate from Organization, Location, business facts,
and provider (Google) state.  They do not consume the platform LocationProfile
entity.  The catalog entries that set requires_location_profile=True for these
products were incorrect.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260812_0001"
down_revision: str | None = "20260811_0002"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE products SET requires_location_profile = false "
        "WHERE key IN ('gbp', 'reviews')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE products SET requires_location_profile = true "
        "WHERE key IN ('gbp', 'reviews')"
    )
