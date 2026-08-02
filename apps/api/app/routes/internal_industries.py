"""Temporary bootstrap routes for the global industry registry."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.app.database.session import get_database_session
from apps.api.app.errors import request_correlation_id
from apps.api.app.industries.contracts import (
    IndustryCreate,
    IndustryData,
    IndustryListResponse,
    IndustryPagination,
    IndustryResponse,
    IndustryTransition,
)
from apps.api.app.industries.enums import IndustryLifecycleAction
from apps.api.app.industries.service import IndustryService
from apps.api.app.schemas import ResponseMeta

router = APIRouter(
    prefix="/internal/industries",
    tags=["internal-platform-administration"],
    responses={
        404: {"description": "Industry not found"},
        409: {"description": "Key, lifecycle, or version conflict"},
    },
)
service = IndustryService()
DatabaseSession = Annotated[AsyncSession, Depends(get_database_session)]


def industry_response(request: Request, industry: object) -> IndustryResponse:
    return IndustryResponse(
        data=IndustryData.model_validate(industry),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.post(
    "",
    response_model=IndustryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an industry (temporary internal bootstrap route)",
)
async def create_industry(
    request: Request, command: IndustryCreate, session: DatabaseSession
) -> IndustryResponse:
    industry = await service.create(
        session, command, correlation_id=request_correlation_id(request)
    )
    return industry_response(request, industry)


@router.get(
    "",
    response_model=IndustryListResponse,
    summary="List industries (temporary internal bootstrap route)",
)
async def list_industries(
    request: Request,
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> IndustryListResponse:
    industries, has_more = await service.list(session, limit=limit, offset=offset)
    return IndustryListResponse(
        data=[IndustryData.model_validate(item) for item in industries],
        pagination=IndustryPagination(
            limit=limit,
            offset=offset,
            next_offset=offset + limit if has_more else None,
            has_more=has_more,
        ),
        meta=ResponseMeta(correlation_id=request_correlation_id(request)),
    )


@router.get(
    "/{industry_id}",
    response_model=IndustryResponse,
    summary="Get an industry (temporary internal bootstrap route)",
)
async def get_industry(
    request: Request, industry_id: UUID, session: DatabaseSession
) -> IndustryResponse:
    return industry_response(request, await service.get(session, industry_id))


async def transition_industry(
    request: Request,
    industry_id: UUID,
    command: IndustryTransition,
    session: AsyncSession,
    action: IndustryLifecycleAction,
) -> IndustryResponse:
    industry = await service.transition(
        session,
        industry_id,
        action=action,
        expected_version=command.expected_version,
        correlation_id=request_correlation_id(request),
    )
    return industry_response(request, industry)


@router.post("/{industry_id}/deprecate", response_model=IndustryResponse)
async def deprecate(
    request: Request,
    industry_id: UUID,
    command: IndustryTransition,
    session: DatabaseSession,
) -> IndustryResponse:
    return await transition_industry(
        request, industry_id, command, session, IndustryLifecycleAction.DEPRECATE
    )


@router.post("/{industry_id}/reactivate", response_model=IndustryResponse)
async def reactivate(
    request: Request,
    industry_id: UUID,
    command: IndustryTransition,
    session: DatabaseSession,
) -> IndustryResponse:
    return await transition_industry(
        request, industry_id, command, session, IndustryLifecycleAction.REACTIVATE
    )


@router.post("/{industry_id}/archive", response_model=IndustryResponse)
async def archive(
    request: Request,
    industry_id: UUID,
    command: IndustryTransition,
    session: DatabaseSession,
) -> IndustryResponse:
    return await transition_industry(
        request, industry_id, command, session, IndustryLifecycleAction.ARCHIVE
    )
