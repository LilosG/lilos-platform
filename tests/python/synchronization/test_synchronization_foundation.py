from apps.api.app.synchronization.models import SyncChangeIntent, SyncCheckpoint
from apps.api.app.synchronization.service import content_hash, deterministic_diff


def test_normalization_and_diff_are_deterministic() -> None:
    assert content_hash({"b": 2, "a": 1}) == content_hash({"a": 1, "b": 2})
    assert deterministic_diff({"name": "desired"}, {"name": "observed"}) == {
        "changed": True,
        "fields": {"name": {"desired": "desired", "observed": "observed"}},
    }
    assert deterministic_diff({"a": 1}, {"a": 1}) == {"changed": False, "fields": {}}


def test_sync_schema_keeps_checkpoint_and_dispatch_state_separate() -> None:
    assert {"cursor_reference", "observed_through", "stale_after"} <= set(
        SyncCheckpoint.__table__.columns.keys()
    )
    assert {
        "status",
        "approval_reference_id",
        "dispatched_at",
        "verified_at",
        "idempotency_key",
    } <= set(SyncChangeIntent.__table__.columns.keys())
