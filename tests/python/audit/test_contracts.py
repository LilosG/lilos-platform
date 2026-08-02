"""Audit creation-contract and metadata-policy tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from apps.api.app.audit.contracts import AuditEventCreate
from apps.api.app.audit.enums import AuditActorType, AuditResult
from apps.api.app.audit.metadata import JsonValue


def valid_command(**overrides: object) -> AuditEventCreate:
    values: dict[str, object] = {
        "event_type": "platform.audit_test",
        "action": "record",
        "result": AuditResult.SUCCEEDED,
        "occurred_at": datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        "actor_type": AuditActorType.SYSTEM,
        "summary": "Recorded a fabricated audit test event.",
    }
    values.update(overrides)
    return AuditEventCreate.model_validate(values)


def test_contract_normalizes_timezone_and_copies_metadata() -> None:
    supplied_metadata: dict[str, JsonValue] = {
        "context": {"attempt": 1},
        "token_count": 10,
    }
    command = valid_command(metadata=supplied_metadata)

    supplied_context = supplied_metadata["context"]
    assert isinstance(supplied_context, dict)
    supplied_context["attempt"] = 2

    assert command.occurred_at.tzinfo is UTC
    assert command.metadata == {"context": {"attempt": 1}, "token_count": 10}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("actor_type", "operator"),
        ("result", "complete"),
        ("event_type", "Not Valid"),
        ("action", "x" * 129),
        ("summary", "x" * 501),
        ("correlation_id", "invalid correlation"),
    ],
)
def test_contract_rejects_invalid_fields(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        valid_command(**{field: value})


def test_contract_rejects_naive_occurred_at() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        valid_command(occurred_at=datetime(2026, 8, 1, 12, 0))


@pytest.mark.parametrize(
    "metadata",
    [
        {"access_token": "not-allowed"},
        {"nested": {"password": "not-allowed"}},
        {"value": float("nan")},
        {"too.deep": {"a": {"b": {"c": {"d": {"e": "value"}}}}}},
        {"oversized": "x" * 16_384},
    ],
)
def test_contract_rejects_prohibited_or_oversized_metadata(
    metadata: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        valid_command(metadata=metadata)
