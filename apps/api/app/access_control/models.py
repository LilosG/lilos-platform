"""SQLAlchemy models for organization access data."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.access_control.enums import (
    InvitationStatus,
    MembershipStatus,
    MembershipType,
    RoleStatus,
    ScopeType,
)
from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


def enum_values(enum_class: type[object]) -> list[str]:
    return [item.value for item in enum_class]  # type: ignore[attr-defined]


class OrganizationMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "(status IN ('active','suspended') AND activated_at IS NOT NULL) OR "
            "(status IN ('invited','expired') AND activated_at IS NULL) OR status='revoked'",
            name="activated_timestamp_consistent",
        ),
        CheckConstraint(
            "(status='suspended') = (suspended_at IS NOT NULL)",
            name="suspended_timestamp_consistent",
        ),
        CheckConstraint(
            "(status='revoked') = (revoked_at IS NOT NULL)",
            name="revoked_timestamp_consistent",
        ),
        CheckConstraint(
            "(status='expired') = (expired_at IS NOT NULL)",
            name="expired_timestamp_consistent",
        ),
        CheckConstraint(
            "status NOT IN ('invited','expired') OR invited_at IS NOT NULL",
            name="invited_timestamp_consistent",
        ),
        UniqueConstraint(
            "organization_id", "user_profile_id", name="uq_memberships_organization_user"
        ),
        UniqueConstraint("organization_id", "id", name="uq_memberships_organization_id_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_profile_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("user_profiles.id", ondelete="RESTRICT"),
        nullable=False,
    )
    membership_type: Mapped[MembershipType] = mapped_column(
        Enum(
            MembershipType,
            name="membership_type",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=16,
        ),
        nullable=False,
    )
    status: Mapped[MembershipStatus] = mapped_column(
        Enum(
            MembershipStatus,
            name="membership_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=16,
        ),
        nullable=False,
    )
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class OrganizationInvitation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint("octet_length(token_hash)=32", name="token_hash_sha256"),
        CheckConstraint(
            "(status='accepted') = (accepted_at IS NOT NULL)",
            name="accepted_timestamp_consistent",
        ),
        CheckConstraint(
            "(status='accepted') = (accepted_by_user_profile_id IS NOT NULL)",
            name="accepted_actor_consistent",
        ),
        CheckConstraint(
            "(status='cancelled') = (cancelled_at IS NOT NULL)",
            name="cancelled_timestamp_consistent",
        ),
        ForeignKeyConstraint(
            ["organization_id", "membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("membership_id", name="uq_invitations_membership_id"),
        UniqueConstraint("token_hash", name="uq_invitations_token_hash"),
        UniqueConstraint("organization_id", "id", name="uq_invitations_organization_id_id"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    normalized_email: Mapped[str] = mapped_column(String(320), nullable=False)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary(32), nullable=False)
    status: Mapped[InvitationStatus] = mapped_column(
        Enum(
            InvitationStatus,
            name="invitation_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=16,
        ),
        nullable=False,
        default=InvitationStatus.PENDING,
        server_default=text("'pending'"),
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invited_by_user_profile_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    accepted_by_user_profile_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("user_profiles.id", ondelete="RESTRICT")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("status='active'", name="status_active"),
        CheckConstraint("is_system", name="system_only"),
        CheckConstraint("version=1", name="version_immutable"),
        UniqueConstraint("key", name="uq_roles_key"),
    )

    key: Mapped[str] = mapped_column(String(63), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[RoleStatus] = mapped_column(
        Enum(
            RoleStatus,
            name="role_status",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=16,
        ),
        nullable=False,
        default=RoleStatus.ACTIVE,
        server_default=text("'active'"),
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


class Permission(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "permissions"
    __table_args__ = (
        CheckConstraint("key ~ '^[a-z][a-z0-9_]*(?:\\.[a-z][a-z0-9_]*)+$'", name="key_format"),
        UniqueConstraint("key", name="uq_permissions_key"),
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    resource: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class MembershipRoleAssignment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "membership_role_assignments"
    __table_args__ = (
        CheckConstraint(
            "(scope_type='organization' AND location_id IS NULL) OR "
            "(scope_type='location' AND location_id IS NOT NULL)",
            name="scope_identity_consistent",
        ),
        ForeignKeyConstraint(
            ["organization_id", "membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    role_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    scope_type: Mapped[ScopeType] = mapped_column(
        Enum(
            ScopeType,
            name="assignment_scope_type",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=16,
        ),
        nullable=False,
    )
    location_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class MembershipPermissionDeny(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "membership_permission_denies"
    __table_args__ = (
        CheckConstraint(
            "(scope_type='organization' AND location_id IS NULL) OR "
            "(scope_type='location' AND location_id IS NOT NULL)",
            name="scope_identity_consistent",
        ),
        ForeignKeyConstraint(
            ["organization_id", "membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "location_id"],
            ["locations.organization_id", "locations.id"],
            ondelete="RESTRICT",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    membership_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    permission_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scope_type: Mapped[ScopeType] = mapped_column(
        Enum(
            ScopeType,
            name="deny_scope_type",
            native_enum=False,
            create_constraint=True,
            values_callable=enum_values,
            length=16,
        ),
        nullable=False,
    )
    location_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


Index(
    "ix_memberships_organization_created_id",
    OrganizationMembership.organization_id,
    OrganizationMembership.created_at,
    OrganizationMembership.id,
)
Index(
    "ix_invitations_organization_created_id",
    OrganizationInvitation.organization_id,
    OrganizationInvitation.created_at,
    OrganizationInvitation.id,
)
Index(
    "uq_invitations_pending_organization_email",
    OrganizationInvitation.organization_id,
    OrganizationInvitation.normalized_email,
    unique=True,
    postgresql_where=OrganizationInvitation.status == InvitationStatus.PENDING,
)
Index(
    "uq_role_assignments_organization_scope",
    MembershipRoleAssignment.organization_id,
    MembershipRoleAssignment.membership_id,
    MembershipRoleAssignment.role_id,
    unique=True,
    postgresql_where=MembershipRoleAssignment.location_id.is_(None),
)
Index(
    "uq_role_assignments_location_scope",
    MembershipRoleAssignment.organization_id,
    MembershipRoleAssignment.membership_id,
    MembershipRoleAssignment.role_id,
    MembershipRoleAssignment.location_id,
    unique=True,
    postgresql_where=MembershipRoleAssignment.location_id.is_not(None),
)
Index(
    "uq_permission_denies_organization_scope",
    MembershipPermissionDeny.organization_id,
    MembershipPermissionDeny.membership_id,
    MembershipPermissionDeny.permission_id,
    unique=True,
    postgresql_where=MembershipPermissionDeny.location_id.is_(None),
)
Index(
    "uq_permission_denies_location_scope",
    MembershipPermissionDeny.organization_id,
    MembershipPermissionDeny.membership_id,
    MembershipPermissionDeny.permission_id,
    MembershipPermissionDeny.location_id,
    unique=True,
    postgresql_where=MembershipPermissionDeny.location_id.is_not(None),
)
