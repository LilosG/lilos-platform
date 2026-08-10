"""PostgreSQL fixture for SEO-domain tests."""

import asyncio
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def preserve_application_logger_state() -> Iterator[None]:
    """Prevent Alembic fileConfig from disabling loggers used by later suites."""
    manager = logging.Logger.manager.loggerDict
    existing = {
        name: value.disabled
        for name, value in manager.items()
        if name == "lilos" or name.startswith("lilos.")
        if isinstance(value, logging.Logger)
    }
    yield
    for name, value in manager.items():
        if (name == "lilos" or name.startswith("lilos.")) and isinstance(value, logging.Logger):
            value.disabled = existing.get(name, False)


@pytest.fixture
def seo_session_factory(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[async_sessionmaker[AsyncSession]]:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.upgrade(config, "head")
    command.downgrade(config, "20260801_0001")
    command.upgrade(config, "head")
    engine = create_async_engine(postgresql_test_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        asyncio.run(engine.dispose())
