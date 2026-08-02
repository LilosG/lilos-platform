"""Platform user profile mapped one-to-one to a Supabase Auth subject."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.authentication.enums import UserStatus
from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_profiles"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "(status = 'deactivated' AND deactivated_at IS NOT NULL) OR "
            "(status = 'active' AND deactivated_at IS NULL)",
            name="deactivated_timestamp_matches_status",
        ),
        UniqueConstraint("auth_user_id", name="uq_user_profiles_auth_user_id"),
    )

    auth_user_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    email: Mapped[str | None] = mapped_column(String(254))
    display_name: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_profile_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=lambda enum: [item.value for item in enum],
            length=16,
        ),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=text("'active'"),
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
