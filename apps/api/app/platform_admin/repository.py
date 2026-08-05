"""Narrow persistence for platform administrator grants."""

from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.platform_admin.models import PlatformAdministrator


class PlatformAdministratorRepository:
    async def add(
        self, session: AsyncSession, item: PlatformAdministrator
    ) -> PlatformAdministrator:
        session.add(item)
        await session.flush()
        return item

    async def get_active_by_user_profile_id(
        self, session: AsyncSession, user_profile_id: UUID
    ) -> PlatformAdministrator | None:
        return cast(
            PlatformAdministrator | None,
            await session.scalar(
                select(PlatformAdministrator).where(
                    PlatformAdministrator.user_profile_id == user_profile_id,
                    PlatformAdministrator.revoked_at.is_(None),
                )
            ),
        )
