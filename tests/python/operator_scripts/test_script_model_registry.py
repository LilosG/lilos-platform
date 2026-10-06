"""Every operator script starts with a complete ORM registry.

A script imports only what it uses, so a foreign key to a model nobody imported used to
fail at the first flush in production (``growth_initiatives.approved_by_user_id`` ->
``user_profiles``) while every test passed, because tests import the whole app. These
tests run each script in a fresh subprocess, which is the only way to see that.
"""

import os
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "scripts"
MAPPER_ERRORS = (
    "NoReferencedTableError",
    "NoReferencedColumnError",
    "InvalidRequestError",
    "ArgumentError",
    "Traceback",
)

# Dry-run (or read-only) arguments and the exit code each script returns against an empty
# database. A new script that uses run_script must be listed here, so it cannot skip this check.
SCRIPT_RUNS: dict[str, tuple[list[str], int]] = {
    "archive_test_records": ([], 0),
    "retire_stale_growth_work": ([], 0),
    "reevaluate_active_websites": ([], 0),
    "ensure_client_schedules": ([], 0),
    "ensure_storage_buckets": ([], 2),  # dry run; Supabase Storage is not configured here
    "recover_stuck_publications": ([], 0),
    "seed_publishing_target_contracts": ([], 0),
    "suspend_organization": (["--organization-id", str(uuid4())], 1),  # organization not found
}


def _scripts_using_run_script() -> set[str]:
    return {
        path.stem
        for path in SCRIPTS.glob("*.py")
        if path.stem != "_cli" and "run_script(" in path.read_text()
    }


def _python(code: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )


@pytest.fixture
def empty_database_env(
    postgresql_test_url: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[dict[str, str]]:
    monkeypatch.setenv("LILOS_MIGRATION_DATABASE_URL", postgresql_test_url)
    config = Config(ROOT / "alembic.ini")
    command.upgrade(config, "head")
    command.downgrade(config, "20260801_0001")  # drops every later table: nothing to write to
    command.upgrade(config, "head")
    env = {key: value for key, value in os.environ.items() if not key.startswith("LILOS_")}
    env.update({"LILOS_RELEASE": "registry-test", "LILOS_DATABASE_URL": postgresql_test_url})
    yield env


def test_every_script_using_run_script_is_covered() -> None:
    assert _scripts_using_run_script() == set(SCRIPT_RUNS)


@pytest.mark.integration
@pytest.mark.parametrize("name", sorted(SCRIPT_RUNS))
def test_script_starts_with_a_complete_model_registry(
    name: str, empty_database_env: dict[str, str]
) -> None:
    arguments, expected_exit = SCRIPT_RUNS[name]

    result = _python(["-m", f"scripts.{name}", *arguments], empty_database_env)

    output = result.stdout + result.stderr
    for marker in MAPPER_ERRORS:
        assert marker not in output, f"{name}: {marker}\n{output[-2000:]}"
    assert result.returncode == expected_exit, output[-2000:]


def test_a_script_without_the_registry_reproduces_the_production_failure() -> None:
    """Importing only the Growth models leaves ``user_profiles`` unregistered."""
    env = {**os.environ, "LILOS_RELEASE": "registry-test"}
    snippet = (
        "from apps.api.app.growth.models import GrowthInitiative\n"
        "from apps.api.app.database.base import Base\n"
        "Base.metadata.sorted_tables\n"
    )
    broken = _python(["-c", snippet], env)
    assert "NoReferencedTableError" in broken.stderr

    fixed = _python(
        [
            "-c",
            "from apps.api.app.growth.models import GrowthInitiative\n"
            "from apps.api.app.database.model_registry import load_all_models\n"
            "load_all_models()\n",
        ],
        env,
    )
    assert fixed.returncode == 0, fixed.stderr[-2000:]


def test_the_registry_covers_every_table_the_full_app_registers() -> None:
    """Discovery by naming convention must not miss a model the app itself imports."""
    env = {**os.environ, "LILOS_RELEASE": "registry-test"}
    listing = (
        "from apps.api.app.database.base import Base\n"
        "print(','.join(sorted(Base.metadata.tables)))\n"
    )
    registry_only = _python(
        [
            "-c",
            "from apps.api.app.database.model_registry import load_all_models\nload_all_models()\n"
            + listing,
        ],
        env,
    )
    full_app = _python(
        ["-c", "import apps.api.app.main\n" + listing],
        env,
    )
    assert registry_only.returncode == 0, registry_only.stderr[-2000:]
    assert full_app.returncode == 0, full_app.stderr[-2000:]
    registry_tables = set(registry_only.stdout.strip().split(","))
    app_tables = set(full_app.stdout.strip().split(","))
    assert app_tables <= registry_tables, sorted(app_tables - registry_tables)
    assert re.search(r"user_profiles", registry_only.stdout)
