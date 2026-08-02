"""Bounded validation for controlled industry default-policy documents."""

import json
import math
import re
from collections.abc import Mapping
from typing import Any

type PolicyScalar = str | int | float | bool | None
type PolicyValue = PolicyScalar | list[PolicyValue] | dict[str, PolicyValue]

MAX_POLICY_BYTES = 16_384
MAX_POLICY_DEPTH = 5
MAX_POLICY_ENTRIES = 50
MAX_POLICY_NODES = 200
MAX_POLICY_KEY_LENGTH = 64
MAX_POLICY_STRING_LENGTH = 1_024
POLICY_KEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$", re.ASCII)
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


class IndustryPolicyError(ValueError):
    """An industry policy document violates its privacy or size contract."""


def normalize_policy_document(value: Any) -> dict[str, PolicyValue]:
    """Return a detached JSON object after enforcing the controlled-document policy."""
    node_count = [0]
    normalized = _normalize_value(value, depth=1, node_count=node_count)
    if not isinstance(normalized, dict):
        raise IndustryPolicyError("Industry policy documents must be JSON objects")
    try:
        encoded = json.dumps(
            normalized,
            allow_nan=False,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise IndustryPolicyError("Industry policy documents must be JSON-compatible") from exc
    if len(encoded) > MAX_POLICY_BYTES:
        raise IndustryPolicyError(
            f"Industry policy documents must not exceed {MAX_POLICY_BYTES} serialized bytes"
        )
    return normalized


def _normalize_value(value: Any, *, depth: int, node_count: list[int]) -> PolicyValue:
    node_count[0] += 1
    if node_count[0] > MAX_POLICY_NODES:
        raise IndustryPolicyError(
            f"Industry policy documents must not exceed {MAX_POLICY_NODES} values"
        )
    if depth > MAX_POLICY_DEPTH:
        raise IndustryPolicyError(
            f"Industry policy documents must not exceed {MAX_POLICY_DEPTH} levels"
        )
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise IndustryPolicyError("Industry policy numbers must be finite")
        return value
    if isinstance(value, str):
        if len(value) > MAX_POLICY_STRING_LENGTH:
            raise IndustryPolicyError(
                f"Industry policy strings must not exceed {MAX_POLICY_STRING_LENGTH} characters"
            )
        return value
    if isinstance(value, Mapping):
        if len(value) > MAX_POLICY_ENTRIES:
            raise IndustryPolicyError(
                f"Industry policy objects must not exceed {MAX_POLICY_ENTRIES} entries"
            )
        normalized_object: dict[str, PolicyValue] = {}
        for key, child in value.items():
            if not isinstance(key, str) or POLICY_KEY_PATTERN.fullmatch(key) is None:
                raise IndustryPolicyError(
                    "Industry policy keys must be 1-64 bounded ASCII identifier characters"
                )
            normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
            if normalized_key in PROHIBITED_NORMALIZED_KEYS:
                raise IndustryPolicyError(f"Industry policy key '{key}' is prohibited")
            normalized_object[key] = _normalize_value(child, depth=depth + 1, node_count=node_count)
        return normalized_object
    if isinstance(value, list):
        if len(value) > MAX_POLICY_ENTRIES:
            raise IndustryPolicyError(
                f"Industry policy arrays must not exceed {MAX_POLICY_ENTRIES} entries"
            )
        return [_normalize_value(item, depth=depth + 1, node_count=node_count) for item in value]
    raise IndustryPolicyError("Industry policy documents contain a non-JSON-compatible value")
