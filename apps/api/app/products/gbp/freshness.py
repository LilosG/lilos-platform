"""Canonical freshness semantics for GBP profile snapshots."""

from datetime import UTC, datetime, timedelta

PROFILE_SYNC_FRESHNESS = timedelta(hours=24)


def profile_sync_is_stale(last_synced_at: datetime | None, *, now: datetime | None = None) -> bool:
    """Return whether a GBP profile needs a successful provider refresh."""
    if last_synced_at is None:
        return True

    reference_time = now or datetime.now(UTC)
    if reference_time.tzinfo is None or reference_time.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    if last_synced_at.tzinfo is None or last_synced_at.utcoffset() is None:
        raise ValueError("last_synced_at must be timezone-aware")

    return last_synced_at.astimezone(UTC) < (
        reference_time.astimezone(UTC) - PROFILE_SYNC_FRESHNESS
    )
