"""Explicit idempotent seed orchestration for controlled initial industries."""

from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.industries.contracts import IndustryCreate
from apps.api.app.industries.errors import IndustrySeedConflictError
from apps.api.app.industries.service import IndustryService

INITIAL_INDUSTRIES: tuple[tuple[str, str], ...] = (
    ("restaurant", "Restaurant"),
    ("bar", "Bar"),
    ("home_services", "Home Services"),
    ("professional_services", "Professional Services"),
    ("general_local_business", "General Local Business"),
)


@dataclass(frozen=True, slots=True)
class IndustrySeedResult:
    created: tuple[str, ...]
    existing: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IndustrySeeder:
    service: IndustryService = field(default_factory=IndustryService)

    async def run(self, session: AsyncSession) -> IndustrySeedResult:
        created: list[str] = []
        existing: list[str] = []
        for key, name in INITIAL_INDUSTRIES:
            stored = await self.service.repository.get_by_key(session, key)
            if stored is not None:
                if stored.name != name:
                    raise IndustrySeedConflictError
                existing.append(key)
                continue
            await self.service.create(
                session,
                IndustryCreate(key=key, name=name),
                correlation_id=f"industry-seed-{key}",
            )
            created.append(key)
        return IndustrySeedResult(created=tuple(created), existing=tuple(existing))
