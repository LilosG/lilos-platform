"""Request-scoped context shared by handlers and structured logging."""

from contextvars import ContextVar, Token

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def bind_correlation_id(correlation_id: str) -> Token[str | None]:
    """Bind a correlation ID to the current execution context."""
    return _correlation_id.set(correlation_id)


def reset_correlation_id(token: Token[str | None]) -> None:
    """Restore the correlation context that preceded a request."""
    _correlation_id.reset(token)


def current_correlation_id() -> str | None:
    """Return the correlation ID bound to the current execution context."""
    return _correlation_id.get()
