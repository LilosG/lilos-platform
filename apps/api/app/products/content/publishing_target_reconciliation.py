"""Reconcile a connected GitHub App installation to the client's primary publishing target.

A GitHub authorization and a Content publishing destination are distinct records.
This service closes that gap deterministically across all clients without guessing:

1. reuse an existing active target;
2. use the only accessible repository when exactly one exists;
3. otherwise match one repository to the client's primary domain / website URL by
   exact repository homepage host;
4. otherwise match one repository by an exact normalized repository-name vs
   organization slug / primary-domain stem.

Ambiguous installations remain explicit and require an operator selection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.config import Settings
from apps.api.app.domains.enums import OrganizationDomainStatus
from apps.api.app.domains.models import OrganizationDomain
from apps.api.app.organizations.models import Organization
from apps.api.app.products.content.contracts import TargetCreate
from apps.api.app.products.content.github_app_service import (
    DiscoveredRepository,
    GitHubAppService,
    installation_id_from_reference,
)
from apps.api.app.products.content.models import PublishingTarget
from apps.api.app.products.content.service import ContentService


def _host(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    return host or None


def _slug(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def _domain_stem(domain: str | None) -> str:
    host = _host(domain)
    if not host:
        return ""
    return _slug(host.split(".", 1)[0])


def select_repository_for_client(
    repositories: list[DiscoveredRepository],
    *,
    primary_domain: str | None,
    website_url: str | None,
    organization_slug: str | None,
) -> DiscoveredRepository | None:
    """Return one repository only when client identity makes the choice deterministic."""
    if len(repositories) == 1:
        return repositories[0]
    if not repositories:
        return None

    expected_hosts = {
        value for value in (_host(primary_domain), _host(website_url)) if value
    }
    homepage_matches = [
        repository for repository in repositories if _host(repository.homepage) in expected_hosts
    ]
    if len(homepage_matches) == 1:
        return homepage_matches[0]
    if len(homepage_matches) > 1:
        return None

    expected_names = {
        value
        for value in (_slug(organization_slug), _domain_stem(primary_domain))
        if value
    }
    name_matches = [
        repository for repository in repositories if _slug(repository.name) in expected_names
    ]
    return name_matches[0] if len(name_matches) == 1 else None


@dataclass(slots=True)
class GitHubPublishingTargetReconciler:
    github: GitHubAppService = field(default_factory=GitHubAppService)
    content: ContentService = field(default_factory=ContentService)

    async def reconcile(
        self,
        session: AsyncSession,
        settings: Settings,
        organization_id: UUID,
        *,
        actor_id: UUID | None,
        correlation_id: str,
    ) -> PublishingTarget | None:
        existing = [
            target
            for target in await self.content.list_targets(session, organization_id)
            if target.status == "active"
        ]
        if existing:
            return existing[0] if len(existing) == 1 else None

        connection = await self.github.find_connection(session, organization_id)
        if connection is None or connection.status != "connected":
            return None
        installation_id = installation_id_from_reference(connection.external_account_reference)
        if installation_id is None:
            return None

        repositories = await self.github.list_installation_repositories(settings, installation_id)
        repository = await self._select_repository(session, organization_id, repositories)
        if repository is None:
            return None

        return await self.content.create_target(
            session,
            organization_id,
            TargetCreate(
                key="primary-site",
                connection_id=connection.id,
                target_type="github_astro",
                repository_id=repository.repository_id,
                base_branch=repository.default_branch or "main",
                allowed_path_prefix="src/content/blog",
                deployment_target_reference=None,
            ),
            actor_id=actor_id,
            correlation_id=correlation_id,
        )

    async def _select_repository(
        self,
        session: AsyncSession,
        organization_id: UUID,
        repositories: list[DiscoveredRepository],
    ) -> DiscoveredRepository | None:
        if len(repositories) == 1:
            return repositories[0]
        if not repositories:
            return None

        organization = await session.get(Organization, organization_id)
        primary_domain = await session.scalar(
            select(OrganizationDomain).where(
                OrganizationDomain.organization_id == organization_id,
                OrganizationDomain.is_primary.is_(True),
                OrganizationDomain.status == OrganizationDomainStatus.ACTIVE,
            )
        )

        return select_repository_for_client(
            repositories,
            primary_domain=primary_domain.domain if primary_domain else None,
            website_url=organization.website_url if organization else None,
            organization_slug=organization.slug if organization else None,
        )
