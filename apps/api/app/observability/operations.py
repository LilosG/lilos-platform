"""Deterministic alerts, incidents, SLOs, and error budgets."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum


class IncidentStatus(StrEnum):
    DETECTED = "detected"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MITIGATING = "mitigating"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"


TRANSITIONS = {
    IncidentStatus.DETECTED: {IncidentStatus.INVESTIGATING},
    IncidentStatus.INVESTIGATING: {IncidentStatus.IDENTIFIED, IncidentStatus.MITIGATING},
    IncidentStatus.IDENTIFIED: {IncidentStatus.MITIGATING},
    IncidentStatus.MITIGATING: {IncidentStatus.MONITORING},
    IncidentStatus.MONITORING: {IncidentStatus.RESOLVED, IncidentStatus.MITIGATING},
    IncidentStatus.RESOLVED: {IncidentStatus.CLOSED, IncidentStatus.MONITORING},
    IncidentStatus.CLOSED: set(),
}


@dataclass(frozen=True, slots=True)
class Incident:
    incident_id: str
    environment: str
    severity: str
    status: IncidentStatus
    title: str
    summary: str
    owner: str | None = None
    version: int = 1

    def transition(self, status: IncidentStatus, expected_version: int) -> "Incident":
        if expected_version != self.version:
            raise ValueError("INCIDENT_VERSION_CONFLICT")
        if status not in TRANSITIONS[self.status]:
            raise ValueError("INCIDENT_TRANSITION_INVALID")
        return replace(self, status=status, version=self.version + 1)


@dataclass(frozen=True, slots=True)
class AlertRule:
    key: str
    severity: str
    threshold: Decimal
    duration_seconds: int
    owner: str
    runbook: str
    recovery_threshold: Decimal

    def evaluate(self, value: Decimal, *, maintenance: bool = False) -> str:
        if maintenance:
            return "suppressed"
        if value >= self.threshold:
            return "firing"
        if value <= self.recovery_threshold:
            return "resolved"
        return "pending"


@dataclass(frozen=True, slots=True)
class SLODefinition:
    key: str
    target: Decimal
    window_days: int
    version: int
    effective_at: datetime

    def error_budget(self, good_events: int, total_events: int) -> dict[str, Decimal | str]:
        if total_events <= 0:
            return {"state": "missing", "remaining": Decimal("0")}
        achieved = Decimal(good_events) / Decimal(total_events)
        allowed_bad = Decimal("1") - self.target
        consumed = max(Decimal("0"), (Decimal("1") - achieved) / allowed_bad)
        return {"state": "valid", "remaining": max(Decimal("0"), Decimal("1") - consumed)}


def utc_now() -> datetime:
    return datetime.now(UTC)
