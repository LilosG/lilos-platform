from apps.api.app.notifications.models import (
    NotificationDelivery,
    NotificationEvent,
    NotificationTemplate,
)


def test_notification_schema_is_durable_and_deduplicated() -> None:
    assert {"organization_id", "idempotency_key", "context"} <= set(
        NotificationEvent.__table__.columns.keys()
    )
    assert {"recipient_reference", "status", "job_id"} <= set(
        NotificationDelivery.__table__.columns.keys()
    )
    assert "body_template" in NotificationTemplate.__table__.columns
