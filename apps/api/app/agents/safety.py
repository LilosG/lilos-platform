"""Bounded, secret-safe projection helpers for Hermes events and tools."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from typing import Any, cast

from apps.api.app.audit.metadata import PROHIBITED_NORMALIZED_KEYS

MAX_EVENT_TEXT = 20_000
MAX_TOOL_RESULT_BYTES = 48_000

_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._~+/=-]{8,}")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(api[_-]?key|access[_-]?token|refresh[_-]?token|password|secret|credential)"
    r"\s*[:=]\s*[^\s,;}]+"
)


def has_secret_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
            if normalized in PROHIBITED_NORMALIZED_KEYS or has_secret_key(child):
                return True
    elif isinstance(value, (list, tuple)):
        return any(has_secret_key(child) for child in value)
    elif isinstance(value, str):
        return bool(_BEARER.search(value) or _SECRET_ASSIGNMENT.search(value))
    return False


def redact_text(value: object, *, limit: int = MAX_EVENT_TEXT) -> str:
    text = str(value or "")[:limit]
    text = _BEARER.sub("[REDACTED]", text)
    return _SECRET_ASSIGNMENT.sub("[REDACTED]", text)


def safe_argument_metadata(arguments: dict[str, Any]) -> dict[str, object]:
    """Return auditable argument shape/hash without persisting model values."""
    if has_secret_key(arguments):
        raise ValueError("secret-bearing tool arguments rejected")
    encoded = json.dumps(arguments, sort_keys=True, separators=(",", ":"), default=str).encode()
    return {
        "argument_names": sorted(str(key)[:64] for key in arguments)[:50],
        "argument_hash": sha256(encoded).hexdigest(),
        "argument_bytes": len(encoded),
    }


def safe_event_document(event: dict[str, Any]) -> dict[str, object] | None:
    """Project only structured lifecycle/result events; drop private reasoning."""
    event_type = str(event.get("event", ""))
    if event_type in {"reasoning.available", "message.delta", "_thinking", "subagent.tool"}:
        return None
    if event_type == "tool.started":
        return {"tool": redact_text(event.get("tool"), limit=128)}
    if event_type in {"tool.completed", "tool.failed"}:
        return {
            "tool": redact_text(event.get("tool"), limit=128),
            "duration_seconds": event.get("duration"),
            "error": event_type == "tool.failed" or bool(event.get("error")),
        }
    if event_type == "approval.request":
        return {
            "approval_id": redact_text(event.get("approval_id"), limit=200),
            "tool": redact_text(event.get("tool"), limit=128),
            "choices": [redact_text(item, limit=32) for item in event.get("choices", [])[:8]],
        }
    if event_type == "approval.responded":
        return {
            "choice": redact_text(event.get("choice"), limit=32),
            "resolved": int(event.get("resolved") or 0),
        }
    if event_type in {"subagent.start", "subagent.complete"}:
        return {
            key: event[key]
            for key in (
                "subagent_id",
                "child_session_id",
                "parent_id",
                "depth",
                "model",
                "status",
                "duration_seconds",
                "input_tokens",
                "output_tokens",
                "reasoning_tokens",
                "api_calls",
                "cost_usd",
            )
            if key in event
        }
    if event_type in {"run.steered", "run.stopping", "run.cancelled"}:
        return {"accepted": bool(event.get("accepted", True))}
    if event_type == "run.completed":
        raw_usage = event.get("usage")
        usage = cast(dict[str, Any], raw_usage) if isinstance(raw_usage, dict) else {}
        return {
            "output": (
                "[REDACTED_SECRET_BEARING_OUTPUT]"
                if has_secret_key(event.get("output"))
                else redact_text(event.get("output"))
            ),
            "usage": {
                key: usage.get(key)
                for key in ("input_tokens", "output_tokens", "total_tokens")
                if usage.get(key) is not None
            },
        }
    if event_type == "run.failed":
        return {"safe_error": redact_text(event.get("error"), limit=500)}
    return None
