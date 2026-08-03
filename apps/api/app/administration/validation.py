"""Bounded validation for governed structured Phase 4 values."""

import json
import re
from copy import deepcopy
from typing import Any

SECRET_KEY = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|credential|private[_-]?key|authorization)",
    re.IGNORECASE,
)
EXECUTABLE_KEY = re.compile(r"(?:script|code|expression|query|template_engine)", re.IGNORECASE)
MAX_DOCUMENT_BYTES = 65_536
MAX_DEPTH = 8
MAX_ENTRIES = 500


def validate_governed_document(value: Any, *, policy: bool = False) -> Any:
    """Return a detached JSON value after bounds and forbidden-key checks."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("document must be JSON-compatible") from exc
    if len(encoded.encode()) > MAX_DOCUMENT_BYTES:
        raise ValueError("document exceeds 65536 bytes")
    entries = 0

    def walk(item: Any, depth: int) -> None:
        nonlocal entries
        if depth > MAX_DEPTH:
            raise ValueError("document nesting exceeds 8 levels")
        if isinstance(item, dict):
            entries += len(item)
            for key, nested in item.items():
                if not isinstance(key, str) or not key:
                    raise ValueError("object keys must be non-empty strings")
                if SECRET_KEY.search(key):
                    raise ValueError("secret-bearing keys are prohibited")
                if policy and EXECUTABLE_KEY.search(key):
                    raise ValueError("executable policy content is prohibited")
                walk(nested, depth + 1)
        elif isinstance(item, list):
            entries += len(item)
            for nested in item:
                walk(nested, depth + 1)
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ValueError("document contains an unsupported value")
        if entries > MAX_ENTRIES:
            raise ValueError("document exceeds 500 entries")

    walk(value, 0)
    return deepcopy(value)


def validate_typed_value(value_type: str, value: Any) -> Any:
    expected: dict[str, type[Any]] = {
        "string": str,
        "number": (int, float),  # type: ignore[dict-item]
        "boolean": bool,
        "object": dict,
        "string_list": list,
    }
    if value_type not in expected:
        raise ValueError("unsupported value type")
    if value_type == "number" and isinstance(value, bool):
        raise ValueError("boolean is not a number")
    if not isinstance(value, expected[value_type]):
        raise ValueError("value does not match value_type")
    if value_type == "string_list" and (
        not all(isinstance(item, str) for item in value) or len(value) > 100
    ):
        raise ValueError("string_list must contain at most 100 strings")
    return validate_governed_document(value)


def validate_against_definition(value: Any, schema: dict[str, Any]) -> list[str]:
    """Validate the intentionally bounded schema subset registered by Phase 4."""
    errors: list[str] = []
    schema_type_value = schema.get("type")
    schema_type = schema_type_value if isinstance(schema_type_value, str) else ""
    type_map: dict[str, type[Any] | tuple[type[Any], ...]] = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }
    expected = type_map.get(schema_type)
    if (
        expected is None
        or not isinstance(value, expected)
        or (schema_type in {"number", "integer"} and isinstance(value, bool))
    ):
        return ["type"]
    if schema_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        if not isinstance(properties, dict) or not isinstance(required, list):
            return ["schema"]
        for key in required:
            if key not in value:
                errors.append(f"missing:{key}")
        if schema.get("additionalProperties") is False:
            errors.extend(f"unknown:{key}" for key in value if key not in properties)
        for key, nested in value.items():
            if key in properties and isinstance(properties[key], dict):
                errors.extend(
                    f"{key}.{item}" for item in validate_against_definition(nested, properties[key])
                )
    elif schema_type == "array":
        if len(value) > int(schema.get("maxItems", 100)):
            errors.append("maxItems")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                errors.extend(
                    f"{index}.{nested}" for nested in validate_against_definition(item, item_schema)
                )
    elif schema_type == "string" and len(value) > int(schema.get("maxLength", 4000)):
        errors.append("maxLength")
    elif schema_type in {"number", "integer"}:
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("maximum")
    if "enum" in schema and value not in schema["enum"]:
        errors.append("enum")
    return errors
