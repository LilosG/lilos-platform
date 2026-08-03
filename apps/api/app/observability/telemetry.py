"""Bounded, redacted telemetry contracts shared by every process."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

SENSITIVE_KEYS: Final = frozenset(
    {
        "authorization",
        "cookie",
        "password",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "oauth_code",
        "oauth_state",
        "email",
        "phone",
        "connection_string",
        "database_url",
        "raw_payload",
        "content_draft",
        "review_content",
        "lead_message",
    }
)
SAFE_METRIC_LABELS: Final = frozenset(
    {"service", "environment", "product", "provider", "operation", "outcome", "status_class"}
)
MAX_TEXT = 512
MAX_FIELDS = 32
MAX_DEPTH = 5


def _is_sensitive(key: str) -> bool:
    normalized = key.casefold().replace("-", "_")
    return normalized in SENSITIVE_KEYS or any(
        normalized.endswith(f"_{suffix}") for suffix in ("token", "secret", "password")
    )


def redact(value: object, *, depth: int = 0) -> object:
    """Return a defensive, bounded copy with sensitive values removed."""
    if depth >= MAX_DEPTH:
        return "[TRUNCATED]"
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for index, (raw_key, item) in enumerate(value.items()):
            if index >= MAX_FIELDS:
                result["_truncated"] = True
                break
            key = str(raw_key)[:128]
            result[key] = "[REDACTED]" if _is_sensitive(key) else redact(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [redact(item, depth=depth + 1) for item in value[:MAX_FIELDS]]
    if isinstance(value, str):
        return value[:MAX_TEXT]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:MAX_TEXT]


@dataclass(frozen=True, slots=True)
class TraceContext:
    correlation_id: str
    trace_id: str
    span_id: str

    def job_headers(self) -> dict[str, str]:
        return {
            "correlation_id": self.correlation_id[:64],
            "trace_id": self.trace_id[:64],
            "parent_span_id": self.span_id[:32],
        }


@dataclass(frozen=True, slots=True)
class MetricPoint:
    name: str
    value: float
    labels: tuple[tuple[str, str], ...]
    recorded_at: datetime

    @classmethod
    def create(cls, name: str, value: float, labels: Mapping[str, str]) -> "MetricPoint":
        if not name or len(name) > 128:
            raise ValueError("metric name is invalid")
        unexpected = set(labels) - SAFE_METRIC_LABELS
        if unexpected:
            raise ValueError("metric labels contain unsafe or high-cardinality fields")
        bounded = tuple(sorted((key, label[:64]) for key, label in labels.items()))
        return cls(name=name, value=value, labels=bounded, recorded_at=datetime.now(UTC))
