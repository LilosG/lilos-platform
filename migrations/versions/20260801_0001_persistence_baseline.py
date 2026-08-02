"""Establish the persistence migration baseline.

Revision ID: 20260801_0001
Revises: None
Create Date: 2026-08-01

Reason: prove deterministic Alembic revision movement before domain schema work.
Tables affected: none; Alembic manages only its own version table.
Constraints and indexes: none.
Data backfill: none.
Application compatibility: compatible with database-optional API startup.
Rollback: downgrade to base removes the revision marker without domain data loss.
"""

from collections.abc import Sequence

revision: str = "20260801_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Mark the persistence baseline without creating domain tables."""


def downgrade() -> None:
    """Remove the baseline revision marker without dropping domain data."""
