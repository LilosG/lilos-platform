"""SQLAlchemy model for co-managed onboarding step assignments.

Each row delegates one onboarding step to "agency" or "client" for a
single organization. The unique constraint on (organization_id, step_key)
ensures at most one assignment per step per org. Deleting a row reverts
the step to agency control.

This model is owned by the onboarding module and persisted in the
``onboarding_step_assignments`` table created by migration
``20260812_0002_onboarding_responsibility_mode``.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, UUIDPrimaryKeyMixin


class OnboardingStepAssignmentRecord(UUIDPrimaryKeyMixin, Base):
    """Persisted co-managed step delegation for one organization-step pair."""

    __tablename__ = "onboarding_step_assignments"
    __table_args__ = (
        CheckConstraint(
            "assigned_to IN ('agency', 'client')",
            name="assigned_to",
        ),
        UniqueConstraint(
            "organization_id",
            "step_key",
            name="uq_onboarding_step_assignments_org_step",
        ),
        {
            "comment": (
                "Co-managed onboarding step delegation. One row per step per org. "
                "assigned_to is 'agency' or 'client'. Deleted rows mean the step "
                "reverts to agency control."
            ),
        },
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    assigned_to: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


Index(
    "ix_onboarding_step_assignments_organization_id",
    OnboardingStepAssignmentRecord.organization_id,
)
