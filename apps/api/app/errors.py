"""Standard API exceptions and exception handlers."""

import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import cast

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from apps.api.app.middleware import CORRELATION_ID_HEADER
from apps.api.app.schemas import (
    ErrorBody,
    ErrorCategory,
    ErrorDetail,
    ErrorResponse,
    ResponseMeta,
)

logger = logging.getLogger("lilos.api.errors")
ExceptionHandler = Callable[[Request, Exception], Awaitable[Response]]


class ApiError(Exception):
    """Base exception for deliberate, safe API errors."""

    status_code = HTTPStatus.INTERNAL_SERVER_ERROR
    code = "INTERNAL_SERVER_ERROR"
    category = ErrorCategory.SYSTEM
    retryable = False
    public_message = "An unexpected error occurred."
    response_headers: dict[str, str] = {}


class NotFoundError(ApiError):
    """Requested application resource does not exist."""

    status_code = HTTPStatus.NOT_FOUND
    code = "RESOURCE_NOT_FOUND"
    category = ErrorCategory.NOT_FOUND
    public_message = "The requested resource was not found."


class AuthorizationError(ApiError):
    """The current actor is not permitted to perform an operation."""

    status_code = HTTPStatus.FORBIDDEN
    code = "PERMISSION_DENIED"
    category = ErrorCategory.AUTHORIZATION
    public_message = "You do not have permission to perform this action."


class ConflictError(ApiError):
    """The requested operation conflicts with current state."""

    status_code = HTTPStatus.CONFLICT
    code = "RESOURCE_CONFLICT"
    category = ErrorCategory.CONFLICT
    public_message = "The request conflicts with the current resource state."


class DatabaseUnavailableError(ApiError):
    """Required PostgreSQL functionality is unavailable."""

    status_code = HTTPStatus.SERVICE_UNAVAILABLE
    code = "DATABASE_UNAVAILABLE"
    category = ErrorCategory.SYSTEM
    retryable = True
    public_message = "The database is currently unavailable."


def request_correlation_id(request: Request) -> str:
    """Read the correlation ID established by middleware."""
    correlation_id = getattr(request.state, "correlation_id", None)
    return correlation_id if isinstance(correlation_id, str) else "unavailable"


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    category: ErrorCategory,
    retryable: bool = False,
    details: list[ErrorDetail] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build the standard safe JSON error envelope."""
    correlation_id = request_correlation_id(request)
    content = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            category=category,
            retryable=retryable,
            details=details or [],
        ),
        meta=ResponseMeta(correlation_id=correlation_id),
    )
    return JSONResponse(
        status_code=status_code,
        content=content.model_dump(mode="json"),
        headers={CORRELATION_ID_HEADER: correlation_id, **(headers or {})},
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return sanitized field-level validation failures."""
    details = [
        ErrorDetail(
            field=".".join(str(part) for part in error["loc"]),
            code=str(error["type"]),
            message=str(error["msg"]),
        )
        for error in exc.errors()
    ]
    return error_response(
        request,
        status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
        code="VALIDATION_FAILED",
        message="The request did not pass validation.",
        category=ErrorCategory.VALIDATION,
        details=details,
    )


async def api_exception_handler(request: Request, exc: ApiError) -> JSONResponse:
    """Return the declared safe contract for an application exception."""
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.public_message,
        category=exc.category,
        retryable=exc.retryable,
        headers=exc.response_headers,
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Normalize framework HTTP exceptions without exposing arbitrary detail."""
    contracts: dict[int, tuple[str, str, ErrorCategory]] = {
        HTTPStatus.UNAUTHORIZED: (
            "AUTHENTICATION_REQUIRED",
            "Authentication is required.",
            ErrorCategory.AUTHENTICATION,
        ),
        HTTPStatus.FORBIDDEN: (
            "PERMISSION_DENIED",
            "You do not have permission to perform this action.",
            ErrorCategory.AUTHORIZATION,
        ),
        HTTPStatus.NOT_FOUND: (
            "RESOURCE_NOT_FOUND",
            "The requested resource was not found.",
            ErrorCategory.NOT_FOUND,
        ),
        HTTPStatus.CONFLICT: (
            "RESOURCE_CONFLICT",
            "The request conflicts with the current resource state.",
            ErrorCategory.CONFLICT,
        ),
    }
    contract = contracts.get(exc.status_code)
    if contract is None:
        try:
            message = HTTPStatus(exc.status_code).phrase
        except ValueError:
            message = "The request could not be completed."
        contract = ("HTTP_ERROR", message, ErrorCategory.SYSTEM)
    code, message, category = contract
    return error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        category=category,
    )


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log an opaque internal failure and return a safe generic response."""
    correlation_id = request_correlation_id(request)
    logger.error(
        "Unhandled API exception",
        extra={
            "event_name": "api.request.unhandled_error",
            "correlation_id": correlation_id,
            "outcome": "failure",
            "normalized_error_code": "INTERNAL_SERVER_ERROR",
            "exception_type": type(exc).__name__,
        },
    )
    return error_response(
        request,
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred.",
        category=ErrorCategory.SYSTEM,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register every standard API exception handler."""
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_exception_handler),
    )
    app.add_exception_handler(ApiError, cast(ExceptionHandler, api_exception_handler))
    app.add_exception_handler(
        StarletteHTTPException,
        cast(ExceptionHandler, http_exception_handler),
    )
    app.add_exception_handler(Exception, unexpected_exception_handler)
