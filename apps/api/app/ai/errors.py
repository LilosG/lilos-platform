"""Provider-neutral AI error categories for safe operator and client visibility."""

from __future__ import annotations

from enum import StrEnum


class AIProviderFailureCode(StrEnum):
    """Why one provider call failed. The class of failure, never the provider's prose."""

    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    HTTP_RATE_LIMITED = "HTTP_RATE_LIMITED"
    HTTP_SERVER = "HTTP_SERVER"
    HTTP_OTHER = "HTTP_OTHER"
    UNPARSEABLE_RESPONSE = "UNPARSEABLE_RESPONSE"
    NO_CHOICES = "NO_CHOICES"
    OUTPUT_TRUNCATED = "OUTPUT_TRUNCATED"
    MALFORMED_OUTPUT = "MALFORMED_OUTPUT"
    EMPTY_DRAFT = "EMPTY_DRAFT"


# A second identical call can succeed for these. A cut-off or malformed answer is
# deterministic enough that repeating it only spends another few minutes.
RETRYABLE_FAILURE_CODES = frozenset(
    {
        AIProviderFailureCode.TIMEOUT,
        AIProviderFailureCode.CONNECTION,
        AIProviderFailureCode.HTTP_RATE_LIMITED,
        AIProviderFailureCode.HTTP_SERVER,
    }
)


class AIProviderError(Exception):
    """A governed AI provider failure with a safe, non-secret-bearing message."""

    def __init__(
        self,
        category: str,
        safe_message: str,
        *,
        code: AIProviderFailureCode | None = None,
        http_status: int | None = None,
        elapsed_ms: int | None = None,
        finish_reason: str | None = None,
        output_tokens: int | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.category = category
        self.safe_message = safe_message
        self.code = code
        self.http_status = http_status
        self.elapsed_ms = elapsed_ms
        self.finish_reason = finish_reason
        self.output_tokens = output_tokens

    @property
    def retryable(self) -> bool:
        return self.code in RETRYABLE_FAILURE_CODES

    def log_fields(self, task_key: str) -> dict[str, object]:
        """Structured log fields: the class of failure and its measurements, no prompt or secret."""
        return {
            "task_key": task_key,
            "failure_code": self.code.value if self.code else None,
            "http_status": self.http_status,
            "elapsed_ms": self.elapsed_ms,
            "finish_reason": self.finish_reason,
            "output_tokens": self.output_tokens,
        }


class AIProviderConfigurationError(AIProviderError):
    """The AI provider is not correctly configured for this environment."""

    def __init__(self, safe_message: str) -> None:
        super().__init__("configuration", safe_message)
