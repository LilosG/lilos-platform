# ruff: noqa: E501
"""Metric-governance, aggregation, comparison, and report-snapshot policies."""

import hashlib
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Literal

DataState = Literal[
    "valid",
    "zero",
    "missing",
    "unavailable",
    "unsupported",
    "stale",
    "partial",
    "delayed",
    "invalid",
    "suppressed",
]


def observation(value: Decimal | None, state: DataState) -> dict[str, object]:
    if value is None and state in {"valid", "zero"}:
        raise ValueError("numeric state requires a value")
    if value is not None and state in {"missing", "unavailable", "unsupported", "suppressed"}:
        raise ValueError("missing-data state cannot carry a value")
    return {"value": str(value) if value is not None else None, "state": state}


def aggregate(
    values: list[Decimal], behavior: str, *, weights: list[Decimal] | None = None
) -> Decimal:
    if not values:
        raise ValueError("missing observations cannot aggregate to zero")
    if behavior == "sum":
        return sum(values, Decimal(0))
    if behavior == "minimum":
        return min(values)
    if behavior == "maximum":
        return max(values)
    if behavior == "weighted_average":
        if not weights or len(weights) != len(values) or sum(weights) == 0:
            raise ValueError("valid weights required")
        return sum(
            (value * weight for value, weight in zip(values, weights, strict=True)), Decimal(0)
        ) / sum(weights)
    raise ValueError("metric is not aggregatable by the requested method")


def percent_change(current: Decimal, previous: Decimal) -> Decimal | None:
    return None if previous == 0 else ((current - previous) / abs(previous)) * 100


def snapshot_hash(payload: Mapping[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def anomaly(
    values: list[Decimal], candidate: Decimal, minimum_points: int = 7
) -> dict[str, object]:
    if len(values) < minimum_points:
        return {"detected": False, "reason": "insufficient_data"}
    mean = sum(values, Decimal(0)) / len(values)
    deviation = sum((abs(value - mean) for value in values), Decimal(0)) / len(values)
    detected = deviation > 0 and abs(candidate - mean) > deviation * 3
    return {
        "detected": detected,
        "baseline": str(mean),
        "threshold": str(deviation * 3),
        "method": "mean_absolute_deviation_v1",
    }
