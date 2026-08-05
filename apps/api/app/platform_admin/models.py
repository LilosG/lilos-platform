"""SQLAlchemy model for cross-organization platform administrator grants."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlatformAdministrator(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A revocable, cross-organization platform administrator grant.

    Additive to the existing per-organization RBAC engine: this table has no
    relationship to ``organization_memberships``, ``roles``, or
    ``membership_role_assignments``. A user may accumulate multiple rows over
    time (grant, revoke, re-grant), but only one may be active at once — see
    ``uq_platform_administrators_active_user`` below, which follows the same
    partial-unique idiom as ``uq_invitations_pending_organization_email``.
    """

    __tablename__ = "platform_administrators"
    __table_args__ = (
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= granted_at",
            name="revoked_not_before_granted",
        ),
    )

    user_profile_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    granted_by_user_profile_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="RESTRICT"),
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


Index(
    "uq_platform_administrators_active_user",
    PlatformAdministrator.user_profile_id,
    unique=True,
    postgresql_where=PlatformAdministrator.revoked_at.is_(None),
)
