"""Create secure integration connection foundation."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.integrations.models import (
    IntegrationConnection,
    OAuthAuthorizationIntent,
    Provider,
    ProviderResourceMapping,
)

revision = "20260803_0004"
down_revision: str | Sequence[str] | None = "20260803_0003"
branch_labels = depends_on = None
TABLES = tuple(
    cast(Table, m.__table__)
    for m in (Provider, IntegrationConnection, OAuthAuthorizationIntent, ProviderResourceMapping)
)


def upgrade() -> None:
    for t in TABLES:
        t.create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for t in reversed(TABLES):
        t.drop(bind=op.get_bind(), checkfirst=False)
