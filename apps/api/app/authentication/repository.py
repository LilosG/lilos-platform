"""Narrow persistence boundary for platform user profiles."""

from typing import cast
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.authentication.enums import UserStatus
from apps.api.app.authentication.models import UserProfile
from apps.api.app.database.base import utc_now


class UserProfileRepository:
    async def add(self, session: AsyncSession, profile: UserProfile) -> UserProfile:
        session.add(profile)
        await session.flush()
        return profile

    async def get_by_id(self, session: AsyncSession, user_id: UUID) -> UserProfile | None:
        return await session.get(UserProfile, user_id)

    async def get_by_auth_user_id(
        self, session: AsyncSession, auth_user_id: UUID
    ) -> UserProfile | None:
        return cast(
            UserProfile | None,
            await session.scalar(
                select(UserProfile).where(UserProfile.auth_user_id == auth_user_id)
            ),
        )

    async def transition_status(
        self,
        session: AsyncSession,
        *,
        user_id: UUID,
        expected_status: UserStatus,
        expected_version: int,
        target_status: UserStatus,
    ) -> UserProfile | None:
        now = utc_now()
        return cast(
            UserProfile | None,
            await session.scalar(
                update(UserProfile)
                .where(
                    UserProfile.id == user_id,
                    UserProfile.status == expected_status,
                    UserProfile.version == expected_version,
                )
                .values(
                    status=target_status,
                    deactivated_at=now if target_status is UserStatus.DEACTIVATED else None,
                    updated_at=now,
                    version=UserProfile.version + 1,
                )
                .returning(UserProfile)
            ),
        )
