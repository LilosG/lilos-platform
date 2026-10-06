# ruff: noqa: E501
"""Explicit GBP capability, hours, completeness, and conflict policies."""

from dataclasses import dataclass
from datetime import date, time


@dataclass(frozen=True, slots=True)
class Capability:
    key: str
    readable: bool
    writable: bool
    reason: str | None = None


def require_capability(capabilities: dict[str, Capability], key: str, *, write: bool) -> Capability:
    capability = capabilities.get(key)
    if capability is None or not capability.readable or (write and not capability.writable):
        raise ValueError("provider capability unavailable")
    return capability


def validate_hours(periods: list[tuple[date, time, time]]) -> None:
    by_date: dict[date, list[tuple[time, time]]] = {}
    for day, opens, closes in periods:
        if opens >= closes:
            raise ValueError("hours interval must close after it opens")
        by_date.setdefault(day, []).append((opens, closes))
    for values in by_date.values():
        ordered = sorted(values)
        if any(
            current[0] < previous[1]
            for previous, current in zip(ordered, ordered[1:], strict=False)
        ):
            raise ValueError("hours intervals overlap")


def special_hour_periods(
    service_date: date, periods: list[tuple[time, time]], *, closed: bool
) -> list[dict[str, object]]:
    """Google's ``specialHours.specialHourPeriods`` entries for one date.

    A closed day is a single entry with ``closed: true`` and no times; otherwise one entry per
    opening interval.
    """
    start = {"year": service_date.year, "month": service_date.month, "day": service_date.day}
    if closed:
        return [{"startDate": start, "closed": True}]
    return [
        {
            "startDate": start,
            "openTime": {"hours": opens.hour, "minutes": opens.minute},
            "closeTime": {"hours": closes.hour, "minutes": closes.minute},
            "closed": False,
        }
        for opens, closes in periods
    ]


def completeness(supported: set[str], observed: dict[str, object]) -> dict[str, object]:
    known = sorted(key for key in supported if key in observed)
    unknown = sorted(key for key in supported if key not in observed)
    return {
        "complete": not unknown,
        "known": known,
        "unknown": unknown,
        "unsupported_excluded": True,
        "ranking_score": None,
    }


def conflicts(
    approved: dict[str, object], desired: dict[str, object], observed: dict[str, object]
) -> list[dict[str, object]]:
    result = []
    for field in sorted(set(approved) | set(desired) | set(observed)):
        values = {
            repr(source[field]) for source in (approved, desired, observed) if field in source
        }
        if len(values) > 1:
            result.append(
                {
                    "field": field,
                    "approved": approved.get(field),
                    "desired": desired.get(field),
                    "observed": observed.get(field),
                }
            )
    return result
