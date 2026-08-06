"""One-off, idempotent, production-safe first-platform-administrator provisioning.

There is no self-service or API path to grant the cross-organization
``PlatformAdministrator`` role (`apps.api.app.platform_admin`) — by design, no
authenticated caller can grant it to themselves or anyone else, since that
would be a privilege-escalation route into every organization on the
platform. The very first platform administrator must therefore be
provisioned out-of-band, exactly once, by an operator with direct access to
the target database.

This reuses `PlatformAdministrationService.grant_administrator` verbatim (the
same governed service the future `/api/v1/platform/administrators` route, if
one is ever added, would call) rather than duplicating any grant logic here.
It resolves the target purely by email against an *existing* `UserProfile` —
a `UserProfile` is only ever created on that person's own first real sign-in
via Supabase, so this script never fabricates or pre-provisions an identity,
and never accepts a raw UUID from the environment.

Never mounted as an HTTP route. Run manually with direct access to the target
database (`LILOS_DATABASE_URL` already present in the process environment),
for example as a Render one-off Job on the `lilos-api` service.

Required environment variable:
    PLATFORM_ADMINISTRATOR_EMAIL   Email of the already-registered platform
                                    user (normalized case-insensitively) to
                                    grant platform-administrator access to.

Idempotent: if that user already holds an active grant, nothing is created
and the existing grant id is reported. Only internal IDs and created/existing
booleans are printed; the email itself, and any token or secret, is never
logged.
"""

import asyncio
import os

from apps.api.app.access_control.errors import UserAccountNotFoundError
from apps.api.app.audit.models import AuditEvent
from apps.api.app.authentication.models import UserProfile
from apps.api.app.config import Settings
from apps.api.app.database.runtime import create_database_runtime
from apps.api.app.platform_admin.models import PlatformAdministrator
from apps.api.app.platform_admin.service import PlatformAdministrationService

assert AuditEvent.metadata is UserProfile.metadata is PlatformAdministrator.metadata


def _required_str(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"provisioning blocked: missing required environment variable {name}")
    return value


async def provision() -> None:
    email = _required_str("PLATFORM_ADMINISTRATOR_EMAIL")
    correlation_id = "provision-platform-administrator"

    runtime = create_database_runtime(Settings())
    session_factory = runtime.require_session_factory()
    service = PlatformAdministrationService()

    try:
        async with session_factory.begin() as session:
            try:
                result = await service.grant_administrator(
                    session,
                    email=email,
                    granted_by_user_profile_id=None,
                    reason="First production platform-administrator bootstrap.",
                    source="provision_platform_administrator_script",
                    correlation_id=correlation_id,
                )
            except UserAccountNotFoundError:
                raise SystemExit(
                    "provisioning blocked: no user profile exists yet for that email — "
                    "the operator must sign in to the application at least once first, "
                    "then re-run this script"
                ) from None
    finally:
        await runtime.dispose()

    if result.grant_created:
        print(
            "platform administrator grant created: "
            f"grant_id={result.grant_id} user_profile_id={result.user_profile_id}"
        )
    else:
        print(
            "platform administrator grant already active: "
            f"grant_id={result.grant_id} user_profile_id={result.user_profile_id}"
        )


if __name__ == "__main__":
    asyncio.run(provision())
