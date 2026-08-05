"""Regression test for `scripts/provision_gbp_entitlement.py`.

Reproduces the same class of defect fixed in
`scripts/seed_integration_providers.py`: writing an `AuditEvent` requires the
`organizations`/`locations` tables to already be registered with
`Base.metadata`, which only happens if some module in the running process has
imported those models. A script that never does so raises
`sqlalchemy.exc.NoReferencedTableError` in a fresh process (e.g. a Render Job)
even though the exact same code runs fine inside the test suite, where dozens
of other modules have already imported those models. This must run the script
as a real subprocess to catch that class of bug at all.
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

from apps.api.app.administration.catalog import AdministrationCatalogSeeder
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def gbp_entitlement_organization_id(
    administration_session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[str]:
    async def create() -> str:
        async with administration_session_factory.begin() as session:
            await AdministrationCatalogSeeder().seed(session, correlation_id="script-test-admin")
            organization = Organization(
                name="Provision Script Test Org",
                slug=f"provision-script-test-org-{uuid4().hex[:8]}",
                organization_type=OrganizationType.TEST,
                status=OrganizationStatus.ACTIVE,
                timezone="UTC",
                default_currency="USD",
                version=1,
            )
            session.add(organization)
            await session.flush()
            return str(organization.id)

    yield asyncio.run(create())


@pytest.mark.integration
def test_provision_gbp_entitlement_runs_as_a_standalone_process_and_is_idempotent(
    postgresql_test_url: str,
    gbp_entitlement_organization_id: str,
) -> None:
    env = {
        **os.environ,
        "LILOS_ENV": "test",
        "LILOS_DATABASE_URL": postgresql_test_url,
        "GBP_ENTITLEMENT_ORGANIZATION_ID": gbp_entitlement_organization_id,
    }
    first = subprocess.run(
        [sys.executable, "-m", "scripts.provision_gbp_entitlement"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert first.returncode == 0, first.stderr
    assert "GBP entitlement created" in first.stdout
    assert "NoReferencedTableError" not in first.stderr

    second = subprocess.run(
        [sys.executable, "-m", "scripts.provision_gbp_entitlement"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert second.returncode == 0, second.stderr
    assert "already effective" in second.stdout
