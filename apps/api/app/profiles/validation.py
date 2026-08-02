"""Normalization and bounds for controlled profile string collections."""

import json
from typing import Any

MAX_COLLECTION_ITEMS = 50
MAX_COLLECTION_BYTES = 16_384


def normalize_string_collection(
    value: Any,
    *,
    field_name: str,
    item_max_length: int,
) -> list[str] | None:
    """Return a detached normalized list and reject duplicate or oversized entries."""
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be an array of strings")
    if len(value) > MAX_COLLECTION_ITEMS:
        raise ValueError(f"{field_name} must contain at most {MAX_COLLECTION_ITEMS} items")
    normalized: list[str] = []
    identities: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain only strings")
        cleaned = " ".join(item.split())
        if not cleaned:
            raise ValueError(f"{field_name} items must not be blank")
        if len(cleaned) > item_max_length:
            raise ValueError(f"{field_name} items must not exceed {item_max_length} characters")
        identity = cleaned.casefold()
        if identity in identities:
            raise ValueError(f"{field_name} must not contain duplicate items")
        identities.add(identity)
        normalized.append(cleaned)
    encoded = json.dumps(normalized, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_COLLECTION_BYTES:
        raise ValueError(f"{field_name} must not exceed {MAX_COLLECTION_BYTES} serialized bytes")
    return normalized


def reject_claim_overlap(
    approved_claims: list[str] | None,
    prohibited_claims: list[str] | None,
) -> None:
    """Reject one normalized claim appearing in both controlled lists."""
    approved = {item.casefold() for item in approved_claims or []}
    prohibited = {item.casefold() for item in prohibited_claims or []}
    if approved & prohibited:
        raise ValueError("a claim must not be both approved and prohibited")
