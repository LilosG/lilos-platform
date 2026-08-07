"""Shared Python test fixtures."""

from pathlib import Path
from urllib.parse import urlsplit

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from apps.api.app.config import Settings

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def postgresql_test_url() -> str:
    """Return a guarded PostgreSQL-only integration-test URL."""
    database_url = Settings().integration_test_database_url()
    if database_url is None:
        pytest.skip("LILOS_TEST_DATABASE_URL is required for PostgreSQL integration tests")

    database_name = urlsplit(database_url).path.removeprefix("/")
    if "test" not in database_name.lower():
        pytest.fail(
            "LILOS_TEST_DATABASE_URL must identify a database containing 'test' in its name"
        )
    return database_url


@pytest.fixture(scope="session")
def alembic_head() -> str:
    """Derive the current Alembic head revision from the script directory.

    This avoids hard-coding revision IDs in migration tests, so adding a new
    migration never requires editing unrelated historical migration tests.
    """
    config = Config(ROOT / "alembic.ini")
    script_dir = ScriptDirectory.from_config(config)
    head = script_dir.get_current_head()
    assert head is not None, "no Alembic head revision found"
    return head
