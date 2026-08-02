"""Isolated PostgreSQL fixtures for organization tests."""

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def organization_session_factory(
    postgresql_test_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[async_sessionmaker[AsyncSession]]:
    """Recreate audit and organization tables and provide transaction-capable sessions."""
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(REPOSITORY_ROOT / "alembic.ini")
    command.upgrade(config, "head")
    command.downgrade(config, "20260801_0001")
    command.upgrade(config, "head")

    engine = create_async_engine(postgresql_test_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        asyncio.run(engine.dispose())
