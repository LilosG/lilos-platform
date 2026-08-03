from datetime import UTC, datetime
from uuid import uuid4

from apps.api.app.products.leads.contracts import LeadIntake
from apps.api.app.products.leads.models import Lead, LeadCommunication, LeadConsent
from apps.api.app.products.leads.service import normalize_email, normalize_phone, submission_hash


def test_contact_normalization_and_submission_idempotency() -> None:
    assert normalize_email(" Person@Example.COM ") == "person@example.com"
    assert normalize_phone("+1 (555) 010-0000") == "+15550100000"
    source_id = uuid4()
    received_at = datetime.now(UTC)
    assert submission_hash(
        LeadIntake(
            source_id=source_id,
            external_submission_id="one",
            location_id=None,
            first_name="Test",
            received_at=received_at,
        )
    ) == submission_hash(
        LeadIntake(
            source_id=source_id,
            external_submission_id="two",
            location_id=None,
            first_name="Test",
            received_at=received_at,
        )
    )


def test_consent_and_communication_are_separate_and_explicit() -> None:
    assert {"channel", "consent_type", "status", "evidence_reference", "withdrawn_at"} <= set(
        LeadConsent.__table__.columns.keys()
    )
    assert {"status", "notification_delivery_id", "workflow_run_id", "idempotency_key"} <= set(
        LeadCommunication.__table__.columns.keys()
    )
    assert (
        "consent_email" not in Lead.__table__.columns
        and "consent_sms" not in Lead.__table__.columns
    )


def test_speed_to_lead_events_are_not_conflated() -> None:
    assert {
        "received_at",
        "acknowledged_at",
        "first_outbound_attempt_at",
        "first_delivered_at",
        "first_human_contact_at",
        "converted_at",
    } <= set(Lead.__table__.columns.keys())
