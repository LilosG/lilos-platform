"""Validation and defensive copying for structured audit metadata."""

import json
import math
import re
from collections.abc import Mapping
from typing import Any

type JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]

MAX_METADATA_BYTES = 16_384
MAX_METADATA_DEPTH = 5
MAX_METADATA_ENTRIES = 50
MAX_METADATA_NODES = 200
MAX_METADATA_KEY_LENGTH = 64
MAX_METADATA_STRING_LENGTH = 1_024
METADATA_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$", re.ASCII)
PROHIBITED_NORMALIZED_KEYS = frozenset(
    {
        "accesstoken",
        "apikey",
        "authorization",
        "clientsecret",
        "cookie",
        "credential",
        "credentials",
        "idtoken",
        "passphrase",
        "passwd",
        "password",
        "privatekey",
        "refreshtoken",
        "secret",
        "setcookie",
        "token",
    }
)


class AuditMetadataError(ValueError):
    """Audit metadata violates its privacy or size contract."""


def normalize_audit_metadata(value: Any) -> dict[str, JsonValue]:
    """Return a detached JSON-compatible object after enforcing audit policy."""
    node_count = [0]
    normalized = _normalize_value(value, depth=1, node_count=node_count)
    if not isinstance(normalized, dict):
        raise AuditMetadataError("Audit metadata must be a JSON object")

    try:
        encoded = json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AuditMetadataError("Audit metadata must be JSON-compatible") from exc
    if len(encoded) > MAX_METADATA_BYTES:
        raise AuditMetadataError(
            f"Audit metadata must not exceed {MAX_METADATA_BYTES} serialized bytes"
        )
    return normalized


def _normalize_value(value: Any, *, depth: int, node_count: list[int]) -> JsonValue:
    node_count[0] += 1
    if node_count[0] > MAX_METADATA_NODES:
        raise AuditMetadataError(f"Audit metadata must not exceed {MAX_METADATA_NODES} values")
    if depth > MAX_METADATA_DEPTH:
        raise AuditMetadataError(f"Audit metadata must not exceed {MAX_METADATA_DEPTH} levels")

    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AuditMetadataError("Audit metadata numbers must be finite")
        return value
    if isinstance(value, str):
        if len(value) > MAX_METADATA_STRING_LENGTH:
            raise AuditMetadataError(
                f"Audit metadata strings must not exceed {MAX_METADATA_STRING_LENGTH} characters"
            )
        return value
    if isinstance(value, Mapping):
        if len(value) > MAX_METADATA_ENTRIES:
            raise AuditMetadataError(
                f"Audit metadata objects must not exceed {MAX_METADATA_ENTRIES} entries"
            )
        normalized_object: dict[str, JsonValue] = {}
        for key, child in value.items():
            if not isinstance(key, str) or METADATA_KEY_PATTERN.fullmatch(key) is None:
                raise AuditMetadataError(
                    "Audit metadata keys must be 1-64 bounded ASCII identifier characters"
                )
            normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized_key in PROHIBITED_NORMALIZED_KEYS:
                raise AuditMetadataError(f"Audit metadata key '{key}' is prohibited")
            normalized_object[key] = _normalize_value(
                child,
                depth=depth + 1,
                node_count=node_count,
            )
        return normalized_object
    if isinstance(value, list):
        if len(value) > MAX_METADATA_ENTRIES:
            raise AuditMetadataError(
                f"Audit metadata arrays must not exceed {MAX_METADATA_ENTRIES} entries"
            )
        return [_normalize_value(child, depth=depth + 1, node_count=node_count) for child in value]
    raise AuditMetadataError("Audit metadata contains a non-JSON-compatible value")
