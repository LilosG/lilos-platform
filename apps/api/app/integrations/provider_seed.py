"""Explicit idempotent seed orchestration for the provider registry.

Mirrors `apps.api.app.industries.seed.IndustrySeeder`: providers are platform
catalog rows, not organization-owned data, and must exist before any connection
can reference them. This replaces ad hoc, lazy provider creation inside request
handling with the same explicit, audited, re-runnable seed convention used
everywhere else in this codebase.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.service import AuditEventService
from apps.api.app.integrations.models import Provider

INITIAL_PROVIDERS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("google_business_profile", "Google Business Profile", ("profile.read", "profile.write")),
    ("github", "GitHub", ("content.publish",)),
)


class ProviderSeedConflictError(Exception):
    """Raised when a provider key already exists with a different name or status."""


@dataclass(frozen=True, slots=True)
class ProviderSeedResult:
    created: tuple[str, ...]
    existing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProviderCatalogSeeder:
    audit: AuditEventService = field(default_factory=AuditEventService)

    async def run(self, session: AsyncSession) -> ProviderSeedResult:
        created: list[str] = []
        existing: list[str] = []
        for key, name, capabilities in INITIAL_PROVIDERS:
            stored = await session.scalar(select(Provider).where(Provider.key == key))
            if stored is not None:
                if stored.name != name or stored.status != "active":
                    raise ProviderSeedConflictError
                existing.append(key)
                continue
            provider = Provider(
                key=key,
                name=name,
                status="active",
                capabilities=list(capabilities),
            )
            session.add(provider)
            await session.flush()
            await self.audit.record(
                session,
                AuditEventCreate(
                    event_type="integration.provider.seeded",
                    action="integration.provider.seeded",
                    result=AuditResult.SUCCEEDED,
                    actor_type=AuditActorType.SYSTEM,
                    resource_type="integration_provider",
                    resource_id=provider.id,
                    correlation_id=f"provider-seed-{key}",
                    summary=f"Provider '{name}' registered.",
                    metadata={"key": key},
                ),
            )
            created.append(key)
        return ProviderSeedResult(created=tuple(created), existing=tuple(existing))
