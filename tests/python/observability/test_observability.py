import json
import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.api.app.config import EnvironmentName, Settings
from apps.api.app.logging_config import JsonFormatter
from apps.api.app.observability.operations import AlertRule, Incident, IncidentStatus, SLODefinition
from apps.api.app.observability.telemetry import MetricPoint, TraceContext, redact


def test_nested_redaction_and_bounds() -> None:
    result = redact(
        {
            "authorization": "Bearer forbidden",
            "nested": {"refresh_token": "forbidden", "safe": "x" * 1000},
        }
    )
    assert result == {
        "authorization": "[REDACTED]",
        "nested": {"refresh_token": "[REDACTED]", "safe": "x" * 512},
    }


def test_json_formatter_redacts_sensitive_extra() -> None:
    record = logging.LogRecord("lilos", logging.INFO, "", 0, "ok", (), None)
    record.authorization = "Bearer forbidden"
    payload = json.loads(JsonFormatter(Settings()).format(record))
    assert "forbidden" not in json.dumps(payload)
    assert "correlation_id" in payload


def test_metric_labels_are_bounded_and_low_cardinality() -> None:
    point = MetricPoint.create("api.requests", 1, {"service": "api", "outcome": "success"})
    assert point.labels == (("outcome", "success"), ("service", "api"))
    with pytest.raises(ValueError):
        MetricPoint.create("api.requests", 1, {"organization_id": "tenant"})


def test_trace_context_propagates_only_identifiers() -> None:
    assert TraceContext("correlation", "trace", "span").job_headers() == {
        "correlation_id": "correlation",
        "trace_id": "trace",
        "parent_span_id": "span",
    }


def test_alert_fires_recovers_and_suppresses_for_maintenance() -> None:
    rule = AlertRule("api.error", "critical", Decimal("5"), 300, "operations", "api", Decimal("2"))
    assert rule.evaluate(Decimal("6")) == "firing"
    assert rule.evaluate(Decimal("1")) == "resolved"
    assert rule.evaluate(Decimal("6"), maintenance=True) == "suppressed"


def test_incident_lifecycle_is_versioned() -> None:
    incident = Incident("inc-1", "test", "sev2", IncidentStatus.DETECTED, "Test", "Safe")
    investigating = incident.transition(IncidentStatus.INVESTIGATING, 1)
    assert investigating.version == 2
    with pytest.raises(ValueError, match="INCIDENT_VERSION_CONFLICT"):
        investigating.transition(IncidentStatus.IDENTIFIED, 1)


def test_slo_missing_and_error_budget_are_explicit() -> None:
    slo = SLODefinition("api", Decimal("0.99"), 28, 1, datetime.now(UTC))
    assert slo.error_budget(0, 0)["state"] == "missing"
    assert slo.error_budget(995, 1000)["remaining"] == Decimal("0.5")


def test_production_configuration_fails_closed_without_telemetry() -> None:
    with pytest.raises(ValueError, match="telemetry"):
        Settings(environment=EnvironmentName.PRODUCTION, release="release-1")
