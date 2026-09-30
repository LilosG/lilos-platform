"""Scripts an operator runs from the Render shell: clear one-line failures, audited suspension."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.audit.models import AuditEvent
from apps.api.app.config import Settings
from apps.api.app.integrations.errors import IntegrationReconnectRequiredError
from apps.api.app.organizations.enums import OrganizationStatus, OrganizationType
from apps.api.app.organizations.models import Organization
from apps.api.app.products.seo.errors import SEOSearchPropertyNotFoundError
from apps.api.app.products.seo.models import SEOCrawlRun, SEOWebsite
from scripts._cli import (
    EXIT_BAD_ENVIRONMENT,
    EXIT_EXPECTED_ERROR,
    EXIT_RECONNECT_REQUIRED,
    run_script,
)
from scripts.reevaluate_active_websites import reevaluate_active_websites
from scripts.suspend_organization import (
    EXIT_NOT_RESOLVED,
    EXIT_NOT_SUSPENDABLE,
    suspend_organization,
)

from .test_reevaluate_active_websites import FakeSearchConsoleService, _site_with_property

# --- run_script: one line, never a traceback ---------------------------------


def test_missing_release_is_one_clear_line_and_main_never_runs(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("LILOS_RELEASE", raising=False)
    ran = False

    async def main() -> int:
        nonlocal ran
        ran = True
        return 0

    assert run_script("suspend_organization", main) == EXIT_BAD_ENVIRONMENT
    err = capsys.readouterr().err
    assert ran is False
    assert err.count("\n") == 1 and "Traceback" not in err
    assert 'LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.suspend_organization' in err

    monkeypatch.setenv("LILOS_RELEASE", "   ")  # blank is as good as missing
    assert run_script("suspend_organization", main) == EXIT_BAD_ENVIRONMENT


def test_reconnect_required_is_one_clear_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LILOS_RELEASE", "abc123")

    async def main() -> int:
        raise IntegrationReconnectRequiredError

    assert run_script("reevaluate_active_websites", main) == EXIT_RECONNECT_REQUIRED
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "Traceback" not in err
    assert "INTEGRATION_RECONNECT_REQUIRED" in err and "reconnect" in err.lower()


def test_expected_application_errors_are_one_line_but_bugs_still_raise(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LILOS_RELEASE", "abc123")

    async def expected() -> int:
        raise SEOSearchPropertyNotFoundError

    assert run_script("x", expected) == EXIT_EXPECTED_ERROR
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and SEOSearchPropertyNotFoundError.code in err

    async def bug() -> int:
        raise RuntimeError("a real defect must not be swallowed")

    with pytest.raises(RuntimeError):
        run_script("x", bug)


def test_unreachable_database_is_one_clear_line(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LILOS_RELEASE", "abc123")

    async def main() -> int:
        raise ConnectionRefusedError(61, "Connect call failed")

    assert run_script("x", main) == EXIT_EXPECTED_ERROR
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "Traceback" not in err
    assert "database could not be reached" in err and "ConnectionRefusedError" in err


def test_successful_run_returns_the_scripts_own_exit_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LILOS_RELEASE", "abc123")

    async def main() -> int:
        return 0

    assert run_script("x", main) == 0


# --- suspend_organization ------------------------------------------------------


async def _org_with_site(session: AsyncSession, domain: str) -> UUID:
    org = Organization(
        name=f"Suspend target {domain}",
        slug=f"suspend-{uuid4().hex[:8]}",
        organization_type=OrganizationType.TEST,
        status=OrganizationStatus.ACTIVE,
        timezone="UTC",
        default_currency="USD",
        version=1,
    )
    session.add(org)
    await session.flush()
    session.add(
        SEOWebsite(
            organization_id=org.id,
            location_id=None,
            key="primary",
            name="site",
            canonical_origin=f"https://www.{domain}",
            status="active",
            ownership_status="verified",
            version=1,
        )
    )
    await session.flush()
    return org.id


async def _status_and_version(
    factory: async_sessionmaker[AsyncSession], organization_id: UUID
) -> tuple[OrganizationStatus, int]:
    async with factory() as session:
        org = await session.get(Organization, organization_id)
        assert org is not None
        return org.status, org.version


async def _lifecycle_events(
    factory: async_sessionmaker[AsyncSession], organization_id: UUID
) -> list[AuditEvent]:
    async with factory() as session:
        return list(
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.organization_id == organization_id,
                    AuditEvent.event_type == "platform.organization.lifecycle_changed",
                )
            )
        )


@pytest.mark.integration
@pytest.mark.anyio
async def test_suspend_organization_dry_run_writes_nothing(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org_id = await _org_with_site(session, "suspend-dry.example.invalid")

    result = await suspend_organization(
        seo_session_factory,
        organization_id=None,
        website_domain="Suspend-Dry.example.invalid",  # case and www are normalized
        apply=False,
    )

    assert result.exit_code == 0 and result.applied is False
    assert result.message.startswith("DRY RUN: would suspend")
    assert await _status_and_version(seo_session_factory, org_id) == (OrganizationStatus.ACTIVE, 1)
    assert await _lifecycle_events(seo_session_factory, org_id) == []


@pytest.mark.integration
@pytest.mark.anyio
async def test_suspend_organization_transitions_via_service_with_audit(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        org_id = await _org_with_site(session, "suspend-apply.example.invalid")

    result = await suspend_organization(
        seo_session_factory,
        organization_id=None,
        website_domain="suspend-apply.example.invalid",
        apply=True,
    )

    assert result.exit_code == 0 and result.applied is True
    assert (result.status_before, result.status_after) == (
        OrganizationStatus.ACTIVE,
        OrganizationStatus.SUSPENDED,
    )
    assert await _status_and_version(seo_session_factory, org_id) == (
        OrganizationStatus.SUSPENDED,
        2,
    )
    events = await _lifecycle_events(seo_session_factory, org_id)
    assert len(events) == 1
    assert events[0].action == "organization.suspend"
    assert events[0].event_metadata["from_status"] == "active"
    assert events[0].event_metadata["to_status"] == "suspended"

    # Idempotent: running it again is a no-op, not an error and not a second event.
    again = await suspend_organization(
        seo_session_factory,
        organization_id=org_id,
        website_domain=None,
        apply=True,
    )
    assert again.exit_code == 0 and again.applied is False and "already suspended" in again.message
    assert len(await _lifecycle_events(seo_session_factory, org_id)) == 1


@pytest.mark.integration
@pytest.mark.anyio
async def test_suspend_organization_refuses_ambiguous_unknown_and_unsuspendable(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        first = await _org_with_site(session, "shared-domain.example.invalid")
        second = await _org_with_site(session, "shared-domain.example.invalid")
        offboarding = await _org_with_site(session, "leaving.example.invalid")
        org = await session.get(Organization, offboarding)
        assert org is not None
        org.status = OrganizationStatus.OFFBOARDING

    ambiguous = await suspend_organization(
        seo_session_factory,
        organization_id=None,
        website_domain="shared-domain.example.invalid",
        apply=True,
    )
    assert ambiguous.exit_code == EXIT_NOT_RESOLVED and "2 organizations" in ambiguous.message
    unknown = await suspend_organization(
        seo_session_factory,
        organization_id=None,
        website_domain="nobody.example.invalid",
        apply=True,
    )
    assert unknown.exit_code == EXIT_NOT_RESOLVED and "no website" in unknown.message
    leaving = await suspend_organization(
        seo_session_factory, organization_id=offboarding, website_domain=None, apply=True
    )
    assert leaving.exit_code == EXIT_NOT_SUSPENDABLE and "offboarding" in leaving.message
    # Nothing was changed by any refused attempt.
    assert (await _status_and_version(seo_session_factory, first))[0] is OrganizationStatus.ACTIVE
    assert (await _status_and_version(seo_session_factory, second))[0] is OrganizationStatus.ACTIVE


@pytest.mark.integration
@pytest.mark.anyio
async def test_a_suspended_organization_drops_out_of_reevaluation(
    seo_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with seo_session_factory.begin() as session:
        _, kept_site, _ = await _site_with_property(session, key="kept")
        dropped_org, dropped_site, _ = await _site_with_property(session, key="dropped")
        # `_site_with_property` names its domain `<key>.example.invalid` (no www).
    await suspend_organization(
        seo_session_factory, organization_id=dropped_org, website_domain=None, apply=True
    )

    summary = await reevaluate_active_websites(
        seo_session_factory, Settings(), search_console=FakeSearchConsoleService()
    )

    assert summary.websites == 1
    async with seo_session_factory() as session:
        queued = {run.website_id for run in await session.scalars(select(SEOCrawlRun))}
    assert queued == {kept_site} and dropped_site not in queued
