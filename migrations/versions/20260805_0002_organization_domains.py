"""Create the organization_domains table."""

from collections.abc import Sequence
from typing import cast

from alembic import op
from sqlalchemy import Table

from apps.api.app.domains.models import OrganizationDomain

revision = "20260805_0002"
down_revision: str | Sequence[str] | None = "20260805_0001"
branch_labels = depends_on = None
TABLES = tuple(cast(Table, model.__table__) for model in (OrganizationDomain,))


def upgrade() -> None:
    for table in TABLES:
        table.create(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    for table in reversed(TABLES):
        table.drop(bind=op.get_bind(), checkfirst=False)
