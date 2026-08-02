import asyncio
from typing import Annotated, NoReturn

import pytest
from fastapi import Depends
from pydantic import PostgresDsn, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from starlette.testclient import TestClient

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.database.session import get_database_session
from apps.api.app.main import create_app

POSTGRES_DSN_ADAPTER = TypeAdapter(PostgresDsn)
PROBE_TABLE = "phase_01_transaction_probe"
SessionDependency = Annotated[AsyncSession, Depends(get_database_session)]


async def reset_probe_table(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP TABLE IF EXISTS "{PROBE_TABLE}"'))
            await connection.execute(text(f'CREATE TABLE "{PROBE_TABLE}" (value INTEGER NOT NULL)'))
    finally:
        await engine.dispose()


async def drop_probe_table(database_url: str) -> None:
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP TABLE IF EXISTS "{PROBE_TABLE}"'))
    finally:
        await engine.dispose()


async def probe_row_count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(text(f'SELECT count(*) FROM "{PROBE_TABLE}"'))
            return int(result.scalar_one())
    finally:
        await engine.dispose()


@pytest.mark.integration
def test_session_dependency_commits_and_rolls_back(postgresql_test_url: str) -> None:
    asyncio.run(reset_probe_table(postgresql_test_url))
    settings = Settings(
        environment=EnvironmentName.TEST,
        database_url=POSTGRES_DSN_ADAPTER.validate_python(postgresql_test_url),
    )
    app = create_app(settings)

    @app.post("/_test/database/commit")
    async def commit_probe(session: SessionDependency) -> dict[str, str]:
        await session.execute(text(f'INSERT INTO "{PROBE_TABLE}" (value) VALUES (1)'))
        return {"status": "inserted"}

    @app.post("/_test/database/rollback", response_model=None)
    async def rollback_probe(session: SessionDependency) -> NoReturn:
        await session.execute(text(f'INSERT INTO "{PROBE_TABLE}" (value) VALUES (2)'))
        raise RuntimeError("forced rollback")

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            committed = client.post("/_test/database/commit")
            rolled_back = client.post("/_test/database/rollback")

        assert committed.status_code == 200
        assert rolled_back.status_code == 500
        assert asyncio.run(probe_row_count(postgresql_test_url)) == 1
    finally:
        asyncio.run(drop_probe_table(postgresql_test_url))
