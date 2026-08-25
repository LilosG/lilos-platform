import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def agent_session_factory(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[async_sessionmaker[AsyncSession]]:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.upgrade(config, "head")
    command.downgrade(config, "20260824_0001")
    command.upgrade(config, "head")
    engine = create_async_engine(postgresql_test_url, poolclass=NullPool)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        asyncio.run(engine.dispose())
