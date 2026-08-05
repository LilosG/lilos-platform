"""Regression test for a real production defect: the standalone
`python -m scripts.seed_integration_providers` command raised
`sqlalchemy.exc.NoReferencedTableError` for `audit_events.organization_id ->
organizations.id` (and `.location_id -> locations.id`), because the script's own
module-level imports never registered the `Organization`/`Location` models with
`Base.metadata`. SQLAlchemy resolves string `ForeignKey("organizations.id", ...)`
references lazily against whatever tables happen to be registered in the running
process -- a script that never imports a referenced model's module never
registers its table, and the failure only shows up in a *fresh* process where
nothing else happened to import that module first. A normal in-process pytest
call to `ProviderCatalogSeeder().run(...)` would not reproduce this: by the time
any test runs, dozens of other modules have already imported `Organization` and
`Location` elsewhere in the suite. This test instead runs the real production
command as a subprocess against the isolated test database.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.integration
def test_seed_integration_providers_runs_as_a_standalone_process(
    postgresql_test_url: str,
    integrations_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    env = {
        **os.environ,
        "LILOS_ENV": "test",
        "LILOS_DATABASE_URL": postgresql_test_url,
    }
    result = subprocess.run(
        [sys.executable, "-m", "scripts.seed_integration_providers"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "Provider seed complete" in result.stdout
    assert "NoReferencedTableError" not in result.stderr
