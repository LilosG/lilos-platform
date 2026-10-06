"""Hold uploaded photos by storage reference; allow special hours that close the whole day."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261005_0002"
down_revision: str | Sequence[str] | None = "20261005_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MEDIA_COLUMNS: tuple[tuple[str, sa.types.TypeEngine[object]], ...] = (
    ("storage_bucket", sa.String(63)),
    ("storage_path", sa.String(512)),
    ("content_type", sa.String(64)),
    ("byte_size", sa.Integer()),
    ("width", sa.Integer()),
    ("height", sa.Integer()),
)
CHECK = "ck_gbp_media_has_source"  # the naming convention prefixes the model's "has_source"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    hours = {column["name"] for column in inspector.get_columns("gbp_special_hours")}
    if "closed" not in hours:
        op.add_column(
            "gbp_special_hours",
            sa.Column("closed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    media = {column["name"] for column in inspector.get_columns("gbp_media")}
    op.alter_column("gbp_media", "source_reference", existing_type=sa.String(1000), nullable=True)
    for name, kind in MEDIA_COLUMNS:
        if name not in media:
            op.add_column("gbp_media", sa.Column(name, kind, nullable=True))
    checks = {check["name"] for check in inspector.get_check_constraints("gbp_media")}
    if CHECK not in checks:
        op.create_check_constraint(
            op.f(CHECK), "gbp_media", "source_reference IS NOT NULL OR storage_path IS NOT NULL"
        )


def downgrade() -> None:
    op.drop_constraint(op.f(CHECK), "gbp_media", type_="check")
    for name, _ in reversed(MEDIA_COLUMNS):
        op.drop_column("gbp_media", name)
    # An uploaded photo has no address to fall back to, so it cannot survive the downgrade.
    op.execute("DELETE FROM gbp_media WHERE source_reference IS NULL")
    op.alter_column("gbp_media", "source_reference", existing_type=sa.String(1000), nullable=False)
    op.drop_column("gbp_special_hours", "closed")
