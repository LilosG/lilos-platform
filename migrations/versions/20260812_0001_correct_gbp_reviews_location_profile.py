"""Correct product catalog: GBP and Reviews do not require LocationProfile.

GBP and Reviews services operate from Organization, Location, business facts,
and provider (Google) state.  They do not consume the platform LocationProfile
entity.  The catalog entries that set requires_location_profile=True for these
products were incorrect.

The ``products_governed_immutability`` trigger installed by
``20260803_0001_shared_administration`` prevents direct UPDATEs on the
``products`` table during normal runtime.  This migration temporarily
disables that trigger before performing the catalog correction, then
re-enables it so immutability enforcement is fully restored before the
transaction commits.
"""

from alembic import op

revision: str = "20260812_0001"
down_revision: str | None = "20260811_0002"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None

_TRIGGER = "products_governed_immutability"
_CORRECTION = (
    "UPDATE products SET requires_location_profile = {value} WHERE key IN ('gbp', 'reviews')"
)


def upgrade() -> None:
    op.execute(f"ALTER TABLE products DISABLE TRIGGER {_TRIGGER}")
    op.execute(_CORRECTION.format(value="false"))
    op.execute(f"ALTER TABLE products ENABLE TRIGGER {_TRIGGER}")


def downgrade() -> None:
    op.execute(f"ALTER TABLE products DISABLE TRIGGER {_TRIGGER}")
    op.execute(_CORRECTION.format(value="true"))
    op.execute(f"ALTER TABLE products ENABLE TRIGGER {_TRIGGER}")
