"""Secure reconciliation for a pre-existing GitHub App owner installation.

The LILOs GitHub App can already be installed on the account that owns the App
before an organization has a local IntegrationConnection. In that case GitHub
opens the existing installation settings page instead of producing a fresh
post-install callback. This service repairs that state without trusting an
unverified installation id from the browser.

Only the installation whose GitHub account id exactly matches the GitHub App
owner is eligible for automatic reconciliation. Customer/third-party
installations still use the normal state-bound install callback flow.
"""

from dataclasses import dataclass, field
from typing import Any, cast
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue
from apps.api.app.audit.service import AuditEventService
from apps.api.app.config import Settings
from apps.api.app.integrations.models import IntegrationConnection
from apps.api.app.products.content.github_app_service import (
    GITHUB_API,
    GITHUB_INSTALLATION_PREFIX,
    GITHUB_PAGE_SIZE,
    MAX_GITHUB_PAGES,
    GitHubAppService,
    installation_id_from_reference,
)


@dataclass(frozen=True, slots=True)
class ReconciledInstallation:
    connection: IntegrationConnection
    installation_id: str


@dataclass(slots=True)
class GitHubOwnerInstallationReconciler:
    """Bind the App owner's existing installation to a LILOs organization."""

    github: GitHubAppService
    audit: AuditEventService = field(default_factory=AuditEventService)

    async def reconcile(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> ReconciledInstallation | None:
        existing = await self.github.find_connection(session, organization_id)
        existing_installation_id = installation_id_from_reference(
            existing.external_account_reference if existing is not None else None
        )
        if existing is not None and existing_installation_id is not None:
            return ReconciledInstallation(existing, existing_installation_id)

        installation_id = await self.find_owner_installation(settings)
        if installation_id is None:
            return None

        provider = await self.github.get_provider(session)
        connection = existing
        if connection is None:
            connection = IntegrationConnection(
                organization_id=organization_id,
                provider_id=provider.id,
                status="pending",
            )
            session.add(connection)
            await session.flush()

        connection.external_account_reference = (
            f"{GITHUB_INSTALLATION_PREFIX}{installation_id}"
        )
        connection.credential_reference = None
        connection.status = "connected"
        await session.flush()

        await self.audit.record(
            session,
            AuditEventCreate(
                event_type="content.github_app.owner_installation_reconciled",
                action="content.github_app.owner_installation_reconciled",
                result=AuditResult.SUCCEEDED,
                actor_type=AuditActorType.USER if actor_id else AuditActorType.SYSTEM,
                actor_id=actor_id,
                organization_id=organization_id,
                product_key="content",
                resource_type="integration_connection",
                resource_id=connection.id,
                correlation_id=correlation_id,
                summary="Existing GitHub App owner installation reconciled.",
                metadata=cast(
                    dict[str, JsonValue],
                    {"installation_id": installation_id, "ownership": "app_owner"},
                ),
            ),
        )
        return ReconciledInstallation(connection, installation_id)

    async def find_owner_installation(self, settings: Settings) -> str | None:
        """Return the active installation owned by the GitHub App owner.

        GitHub explicitly warns that an installation_id supplied to a setup URL
        is not proof of ownership. We therefore discover installations with the
        App JWT and only auto-bind the installation whose account id is the same
        as the App owner's account id. This keeps automatic recovery limited to
        LILOs' own App installation and leaves third-party installations on the
        normal state-bound authorization path.
        """
        app_jwt = self.github.sign_app_jwt(settings)
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with self.github.http_client_factory() as client:
            app_response = await client.get(
                f"{GITHUB_API}/app",
                headers=headers,
                timeout=self.github.timeout_seconds,
            )
        if app_response.status_code != 200:
            raise RuntimeError(
                "GitHub App lookup returned "
                f"{app_response.status_code}: {app_response.text[:200]}"
            )
        app_payload = app_response.json()
        if not isinstance(app_payload, dict):
            raise RuntimeError("invalid GitHub App response")
        owner = app_payload.get("owner")
        if not isinstance(owner, dict) or owner.get("id") is None:
            raise RuntimeError("GitHub App owner is missing")
        owner_id = str(owner["id"])

        matches: list[str] = []
        for page_number in range(1, MAX_GITHUB_PAGES + 1):
            async with self.github.http_client_factory() as client:
                response = await client.get(
                    f"{GITHUB_API}/app/installations",
                    headers=headers,
                    params={"page": page_number, "per_page": GITHUB_PAGE_SIZE},
                    timeout=self.github.timeout_seconds,
                )
            if response.status_code != 200:
                raise RuntimeError(
                    "GitHub App installations lookup returned "
                    f"{response.status_code}: {response.text[:200]}"
                )
            payload = response.json()
            if not isinstance(payload, list) or not all(
                isinstance(item, dict) for item in payload
            ):
                raise RuntimeError("invalid GitHub App installations response")
            installations = cast(list[dict[str, Any]], payload)
            for installation in installations:
                account = installation.get("account")
                installation_id = installation.get("id")
                if (
                    isinstance(account, dict)
                    and account.get("id") is not None
                    and str(account["id"]) == owner_id
                    and installation_id is not None
                    and installation.get("suspended_at") is None
                ):
                    matches.append(str(installation_id))
            if len(installations) < GITHUB_PAGE_SIZE:
                break
        else:
            raise RuntimeError("GitHub App installation pagination exceeded safety limit")

        unique_matches = list(dict.fromkeys(matches))
        if not unique_matches:
            return None
        if len(unique_matches) > 1:
            raise RuntimeError("multiple active GitHub App owner installations found")
        return unique_matches[0]
