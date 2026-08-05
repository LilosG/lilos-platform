"""Create the provider_secrets table."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.integrations.secrets import ProviderSecret

revision = "20260805_0001"
down_revision: str | Sequence[str] | None = "20260804_0002"
branch_labels = depends_on = None
TABLES = tuple(cast(Table, model.__table__) for model in (ProviderSecret,))


def upgrade() -> None:
    for table in TABLES:
        table.create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for table in reversed(TABLES):
        table.drop(bind=op.get_bind(), checkfirst=False)
