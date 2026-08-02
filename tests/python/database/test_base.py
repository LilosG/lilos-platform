from datetime import UTC
from uuid import UUID

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase

from apps.api.app.database.base import (
    NAMING_CONVENTION,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
    utc_now,
)


class ConventionTestBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class ConventionProbe(UUIDPrimaryKeyMixin, TimestampMixin, ConventionTestBase):
    __tablename__ = "phase_01_convention_probe"


def test_uuid_primary_key_convention_uses_uuid4() -> None:
    default_factory = ConventionProbe.__table__.c.id.default

    assert default_factory is not None
    generated = default_factory.arg(None)
    assert isinstance(generated, UUID)
    assert generated.version == 4
    assert ConventionProbe.__table__.c.id.primary_key


def test_timestamp_convention_is_timezone_aware_utc() -> None:
    now = utc_now()
    created_at_type = ConventionProbe.__table__.c.created_at.type
    updated_at_type = ConventionProbe.__table__.c.updated_at.type

    assert now.tzinfo is UTC
    assert isinstance(created_at_type, DateTime)
    assert isinstance(updated_at_type, DateTime)
    assert created_at_type.timezone is True
    assert updated_at_type.timezone is True
    assert ConventionProbe.__table__.c.updated_at.onupdate is not None


def test_constraint_naming_convention_is_explicit() -> None:
    assert NAMING_CONVENTION == {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
