"""Migrations only on the guarded disposable integration database."""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture
def staging_test_database(postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(Path(__file__).resolve().parents[3] / "alembic.ini")
    # Capture only configuration names, never print secret-bearing environment values.
    assert os.environ["LILOS_MIGRATION_DATABASE_URL"] == postgresql_test_url
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    return postgresql_test_url
