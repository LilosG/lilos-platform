"""Reclassify SEO required integrations as optional.

The self-contained SEO crawl/analysis path requires no external integration.
Google Search Console and Google Analytics are optional, separately-classified
enhancements (SEOSearchProperty) and must not block the crawl path or mark the
SEO product unavailable.  Reconcile the already-seeded ``products`` row for
``seo`` so the catalog signature matches the updated catalog and the readiness
engine no longer emits CONNECTION_REQUIRED for Search Console/Analytics.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260806_0002"
down_revision: str | Sequence[str] | None = "20260806_0001"
branch_labels = depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "products" not in sa.inspect(bind).get_table_names():
        return
    # The ``products_governed_immutability`` trigger prevents all updates to
    # the products catalog.  This is a one-time catalog reconciliation to
    # reclassify SEO's required integrations, so temporarily disable the
    # trigger, apply the correction, and re-enable it.
    op.execute("ALTER TABLE products DISABLE TRIGGER products_governed_immutability")
    op.execute(
        "UPDATE products SET required_integrations = '[]'::jsonb, updated_at = now() "
        "WHERE key = 'seo'"
    )
    op.execute("ALTER TABLE products ENABLE TRIGGER products_governed_immutability")


def downgrade() -> None:
    bind = op.get_bind()
    if "products" not in sa.inspect(bind).get_table_names():
        return
    op.execute("ALTER TABLE products DISABLE TRIGGER products_governed_immutability")
    op.execute(
        "UPDATE products SET required_integrations = "
        '\'["google_search_console","google_analytics"]\'::jsonb, '
        "updated_at = now() WHERE key = 'seo'"
    )
    op.execute("ALTER TABLE products ENABLE TRIGGER products_governed_immutability")
