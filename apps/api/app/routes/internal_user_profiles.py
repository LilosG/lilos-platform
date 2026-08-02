"""Temporary guarded platform-user bootstrap administration routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.authentication.contracts import (
    UserLifecycleCommand,
    UserProfileCreate,
    UserProfileData,
    UserProfileResponse,
)
from apps.api.app.authentication.enums import UserLifecycleAction
from apps.api.app.authentication.service import UserAdministrationService
from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.schemas import ResponseMeta

router = APIRouter(prefix="/internal/user-profiles", tags=["internal-platform-administration"])
service = UserAdministrationService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def response_for(request: Request, profile: object) -> UserProfileResponse:
    return UserProfileResponse(
        data=UserProfileData.model_validate(profile),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.post("", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED)
async def provision(
    request: Request, command: UserProfileCreate, session: DatabaseSession
) -> UserProfileResponse:
    profile = await service.provision(
        session, command, correlation_id=request_correlation_id(request)
    )
    return response_for(request, profile)


@router.get("/{user_id}", response_model=UserProfileResponse)
async def get_profile(
    request: Request, user_id: UUID, session: DatabaseSession
) -> UserProfileResponse:
    return response_for(request, await service.get(session, user_id))


async def transition(
    request: Request,
    user_id: UUID,
    command: UserLifecycleCommand,
    session: AsyncSession,
    action: UserLifecycleAction,
) -> UserProfileResponse:
    profile = await service.transition(
        session,
        user_id,
        action=action,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return response_for(request, profile)


@router.post("/{user_id}/deactivate", response_model=UserProfileResponse)
async def deactivate(
    request: Request,
    user_id: UUID,
    command: UserLifecycleCommand,
    session: DatabaseSession,
) -> UserProfileResponse:
    return await transition(request, user_id, command, session, UserLifecycleAction.DEACTIVATE)


@router.post("/{user_id}/reactivate", response_model=UserProfileResponse)
async def reactivate(
    request: Request,
    user_id: UUID,
    command: UserLifecycleCommand,
    session: DatabaseSession,
) -> UserProfileResponse:
    return await transition(request, user_id, command, session, UserLifecycleAction.REACTIVATE)
