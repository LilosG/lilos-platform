"""Record who wrote a Google review: display name, photo and a typed identity class."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261006_0002"
down_revision: str | Sequence[str] | None = "20261005_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHECK = "ck_reviews_reviewer_identity"


def upgrade() -> None:
    # An older migration builds `reviews` from the live model, so a fresh database
    # may already have these columns; only existing databases need them added.
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("reviews")}
    if "reviewer_display_name" not in existing:
        op.add_column("reviews", sa.Column("reviewer_display_name", sa.String(255), nullable=True))
    if "reviewer_photo_url" not in existing:
        op.add_column("reviews", sa.Column("reviewer_photo_url", sa.String(1000), nullable=True))
    if "reviewer_identity" not in existing:
        op.add_column(
            "reviews",
            sa.Column(
                "reviewer_identity",
                sa.String(16),
                nullable=False,
                server_default=sa.text("'unknown'"),
            ),
        )
    checks = {check["name"] for check in inspector.get_check_constraints("reviews")}
    if CHECK not in checks:
        op.create_check_constraint(
            op.f(CHECK), "reviews", "reviewer_identity IN ('named','anonymous','unknown')"
        )


def downgrade() -> None:
    op.drop_constraint(op.f(CHECK), "reviews", type_="check")
    op.drop_column("reviews", "reviewer_identity")
    op.drop_column("reviews", "reviewer_photo_url")
    op.drop_column("reviews", "reviewer_display_name")
