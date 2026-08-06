"""Regression test for `scripts/provision_platform_administrator.py`.

Runs as a real subprocess (not an in-process import) for the same reason
`test_provision_gbp_entitlement_script.py` does: writing an `AuditEvent`
requires `organizations`/`user_profiles`/`platform_administrators` to already
be registered with `Base.metadata`, which only happens if some module in the
running process has imported those models — a defect class that only
reproduces in a fresh process such as a Render Job, never inside the full
test suite where dozens of other modules already imported them.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def existing_platform_user_email(
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[str]:
    email = f"script-test-{uuid4().hex[:8]}@example.invalid"

    async def create() -> None:
        async with platform_administration_session_factory.begin() as session:
            session.add(
                UserProfile(auth_user_id=uuid4(), email=email, status=UserStatus.ACTIVE, version=1)
            )

    asyncio.run(create())
    yield email


@pytest.mark.integration
def test_provision_platform_administrator_runs_as_a_standalone_process_and_is_idempotent(
    postgresql_test_url: str,
    existing_platform_user_email: str,
) -> None:
    env = {
        **os.environ,
        "LILOS_ENV": "test",
        "LILOS_DATABASE_URL": postgresql_test_url,
        "PLATFORM_ADMINISTRATOR_EMAIL": existing_platform_user_email,
    }
    first = subprocess.run(
        [sys.executable, "-m", "scripts.provision_platform_administrator"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert first.returncode == 0, first.stderr
    assert "platform administrator grant created" in first.stdout
    assert existing_platform_user_email not in first.stdout
    assert "NoReferencedTableError" not in first.stderr

    second = subprocess.run(
        [sys.executable, "-m", "scripts.provision_platform_administrator"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert second.returncode == 0, second.stderr
    assert "already active" in second.stdout


@pytest.mark.integration
def test_provision_platform_administrator_blocks_for_unknown_email(
    postgresql_test_url: str,
    platform_administration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    env = {
        **os.environ,
        "LILOS_ENV": "test",
        "LILOS_DATABASE_URL": postgresql_test_url,
        "PLATFORM_ADMINISTRATOR_EMAIL": f"never-signed-in-{uuid4().hex[:8]}@example.invalid",
    }
    result = subprocess.run(
        [sys.executable, "-m", "scripts.provision_platform_administrator"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode != 0
    assert "no user profile exists yet" in result.stderr
