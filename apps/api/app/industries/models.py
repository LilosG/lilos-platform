"""SQLAlchemy model for reusable global industry defaults."""

from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from apps.api.app.industries.enums import IndustryStatus


def _enum_values(enum_class: type[IndustryStatus]) -> list[str]:
    return [item.value for item in enum_class]


class Industry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "industries"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("char_length(key) BETWEEN 3 AND 63", name="key_length"),
        CheckConstraint("key = lower(btrim(key))", name="key_normalized"),
        CheckConstraint("key ~ '^[a-z][a-z0-9]*(_[a-z0-9]+)*$'", name="key_format"),
        CheckConstraint(
            "jsonb_typeof(default_configuration) = 'object'", name="configuration_object"
        ),
        CheckConstraint("jsonb_typeof(default_risk_policy) = 'object'", name="risk_policy_object"),
        CheckConstraint(
            "jsonb_typeof(default_content_policy) = 'object'", name="content_policy_object"
        ),
        CheckConstraint(
            "octet_length(default_configuration::text) <= 16384", name="configuration_size"
        ),
        CheckConstraint(
            "octet_length(default_risk_policy::text) <= 16384", name="risk_policy_size"
        ),
        CheckConstraint(
            "octet_length(default_content_policy::text) <= 16384", name="content_policy_size"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
        CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR "
            "(status <> 'archived' AND archived_at IS NULL)",
            name="archived_timestamp_matches_status",
        ),
    )

    key: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[IndustryStatus] = mapped_column(
        Enum(
            IndustryStatus,
            name="industry_status",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
            values_callable=_enum_values,
            length=16,
        ),
        nullable=False,
        default=IndustryStatus.ACTIVE,
        server_default=text("'active'"),
    )
    description: Mapped[str | None] = mapped_column(String(1000))
    default_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    default_risk_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    default_content_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )


Index("ix_industries_created_at_id", Industry.created_at, Industry.id)
