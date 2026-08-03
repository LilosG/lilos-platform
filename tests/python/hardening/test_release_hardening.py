from pathlib import Path

import pytest

from apps.api.app.observability.telemetry import MetricPoint, redact
from scripts.release_gate import missing_release_documents


def test_release_gate_reports_missing_documents(tmp_path: Path) -> None:
    assert "docs/PHASE-17-ACCEPTANCE.md" in missing_release_documents(tmp_path)


@pytest.mark.parametrize(
    "payload",
    [
        {"access_token": "forbidden"},
        {"nested": {"password": "forbidden"}},
        {"authorization": "Bearer forbidden"},
        {"lead_message": "private"},
    ],
)
def test_sensitive_failure_payloads_are_redacted(payload: dict[str, object]) -> None:
    assert "forbidden" not in str(redact(payload)) and "private" not in str(redact(payload))


def test_tenant_identifier_cannot_become_metric_cardinality() -> None:
    with pytest.raises(ValueError):
        MetricPoint.create("jobs.running", 1, {"organization_id": "tenant-a"})
