"""Suspend an organization through the audited lifecycle path.

A suspended organization is dropped from re-evaluation, syncing and other
ACTIVE-only work, and the suspension is reversible (`activate`). This goes through
`OrganizationService.transition` -- the same compare-and-swap, audited transition
the platform administration routes use -- never a direct write.

Dry run by default: it resolves the organization and says what it would do. Pass
`--apply` to perform the transition.

Run (Render shell):

    LILOS_RELEASE="$RENDER_GIT_COMMIT" python -m scripts.suspend_organization \\
        --website-domain example.com --apply
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.organizations.enums import OrganizationLifecycleAction, OrganizationStatus
from apps.api.app.organizations.models import Organization
from apps.api.app.organizations.service import OrganizationService
from apps.api.app.products.seo.models import SEOWebsite
from scripts._cli import run_script

assert SEOWebsite.metadata is Organization.metadata

EXIT_NOT_RESOLVED = 4
EXIT_NOT_SUSPENDABLE = 5
SUSPENDABLE = frozenset({OrganizationStatus.ACTIVE, OrganizationStatus.PAUSED})


@dataclass(frozen=True, slots=True)
class SuspendResult:
    organization_id: UUID | None
    name: str | None
    status_before: OrganizationStatus | None
    status_after: OrganizationStatus | None
    applied: bool
    message: str
    exit_code: int


def _normalize_domain(domain: str) -> str:
    cleaned = domain.strip().lower()
    host = urlsplit(cleaned if "//" in cleaned else f"//{cleaned}").hostname or cleaned
    return host.removeprefix("www.")


async def resolve_organization_id(
    session: AsyncSession, *, organization_id: UUID | None, website_domain: str | None
) -> tuple[UUID | None, str]:
    """The one organization named, or None with the reason it could not be resolved."""
    if organization_id is not None:
        return organization_id, ""
    assert website_domain is not None
    wanted = _normalize_domain(website_domain)
    rows = await session.execute(select(SEOWebsite.organization_id, SEOWebsite.canonical_origin))
    matches = {
        org_id
        for org_id, origin in rows
        if _normalize_domain(urlsplit(origin).hostname or origin) == wanted
    }
    if not matches:
        return None, f"no website with domain {wanted!r} was found"
    if len(matches) > 1:
        return (
            None,
            f"domain {wanted!r} belongs to {len(matches)} organizations; use --organization-id",
        )
    return next(iter(matches)), ""


async def suspend_organization(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    organization_id: UUID | None,
    website_domain: str | None,
    apply: bool,
    service: OrganizationService | None = None,
) -> SuspendResult:
    service = service or OrganizationService()
    async with session_factory.begin() as session:
        resolved, reason = await resolve_organization_id(
            session, organization_id=organization_id, website_domain=website_domain
        )
        if resolved is None:
            return SuspendResult(None, None, None, None, False, reason, EXIT_NOT_RESOLVED)
        organization = await service.get(session, resolved)
        before = organization.status
        label = f"{organization.name} ({organization.id})"
        if before is OrganizationStatus.SUSPENDED:
            return SuspendResult(
                organization.id,
                organization.name,
                before,
                before,
                False,
                f"{label} is already suspended; nothing to do.",
                0,
            )
        if before not in SUSPENDABLE:
            return SuspendResult(
                organization.id,
                organization.name,
                before,
                before,
                False,
                f"{label} is {before.value}; only active or paused organizations can be suspended.",
                EXIT_NOT_SUSPENDABLE,
            )
        if not apply:
            return SuspendResult(
                organization.id,
                organization.name,
                before,
                before,
                False,
                f"DRY RUN: would suspend {label} (currently {before.value}). "
                "Re-run with --apply to do it.",
                0,
            )
        updated = await service.transition(
            session,
            organization.id,
            action=OrganizationLifecycleAction.SUSPEND,
            expected_version=organization.version,
            correlation_id=f"suspend-organization:{uuid4().hex[:12]}",
        )
        return SuspendResult(
            updated.id,
            updated.name,
            before,
            updated.status,
            True,
            f"Suspended {label}: {before.value} -> {updated.status.value}.",
            0,
        )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--organization-id", type=UUID)
    target.add_argument("--website-domain", help="the domain of one of the organization's websites")
    parser.add_argument(
        "--apply", action="store_true", help="perform the transition (default: dry run)"
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    runtime = create_database_runtime(Settings())
    try:
        result = await suspend_organization(
            runtime.require_session_factory(),
            organization_id=args.organization_id,
            website_domain=args.website_domain,
            apply=args.apply,
        )
    finally:
        await runtime.dispose()
    print(result.message)
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(run_script("suspend_organization", main))
