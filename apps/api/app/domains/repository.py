"""Strictly organization-scoped domain persistence."""

from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.base import utc_now
from apps.api.app.domains.enums import OrganizationDomainStatus
from apps.api.app.domains.models import OrganizationDomain

MAX_ORGANIZATION_DOMAIN_LIST_LIMIT = 100


class OrganizationDomainRepository:
    async def add(self, session: AsyncSession, domain: OrganizationDomain) -> OrganizationDomain:
        session.add(domain)
        await session.flush()
        return domain

    async def get(
        self, session: AsyncSession, organization_id: UUID, domain_id: UUID, *, lock: bool = False
    ) -> OrganizationDomain | None:
        statement = select(OrganizationDomain).where(
            OrganizationDomain.organization_id == organization_id,
            OrganizationDomain.id == domain_id,
        )
        if lock:
            statement = statement.with_for_update()
        return cast(OrganizationDomain | None, await session.scalar(statement))

    async def list(self, session: AsyncSession, organization_id: UUID) -> list[OrganizationDomain]:
        result = await session.scalars(
            select(OrganizationDomain)
            .where(OrganizationDomain.organization_id == organization_id)
            .order_by(
                OrganizationDomain.is_primary.desc(),
                OrganizationDomain.created_at.asc(),
                OrganizationDomain.id.asc(),
            )
            .limit(MAX_ORGANIZATION_DOMAIN_LIST_LIMIT)
        )
        return list(result)

    async def clear_primary(self, session: AsyncSession, organization_id: UUID) -> None:
        await session.execute(
            update(OrganizationDomain)
            .where(
                OrganizationDomain.organization_id == organization_id,
                OrganizationDomain.is_primary.is_(True),
                OrganizationDomain.status == OrganizationDomainStatus.ACTIVE,
            )
            .values(is_primary=False, version=OrganizationDomain.version + 1, updated_at=utc_now())
        )

    async def set_primary(
        self,
        session: AsyncSession,
        organization_id: UUID,
        domain_id: UUID,
        *,
        expected_version: int,
    ) -> OrganizationDomain | None:
        return cast(
            OrganizationDomain | None,
            await session.scalar(
                update(OrganizationDomain)
                .where(
                    OrganizationDomain.organization_id == organization_id,
                    OrganizationDomain.id == domain_id,
                    OrganizationDomain.status == OrganizationDomainStatus.ACTIVE,
                    OrganizationDomain.version == expected_version,
                )
                .values(
                    is_primary=True,
                    version=OrganizationDomain.version + 1,
                    updated_at=utc_now(),
                )
                .returning(OrganizationDomain)
            ),
        )

    async def archive(
        self,
        session: AsyncSession,
        organization_id: UUID,
        domain_id: UUID,
        *,
        expected_version: int,
    ) -> OrganizationDomain | None:
        now = utc_now()
        return cast(
            OrganizationDomain | None,
            await session.scalar(
                update(OrganizationDomain)
                .where(
                    OrganizationDomain.organization_id == organization_id,
                    OrganizationDomain.id == domain_id,
                    OrganizationDomain.status == OrganizationDomainStatus.ACTIVE,
                    OrganizationDomain.version == expected_version,
                )
                .values(
                    status=OrganizationDomainStatus.ARCHIVED,
                    is_primary=False,
                    archived_at=now,
                    version=OrganizationDomain.version + 1,
                    updated_at=now,
                )
                .returning(OrganizationDomain)
            ),
        )
