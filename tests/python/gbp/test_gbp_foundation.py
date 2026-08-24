from datetime import UTC, datetime, timedelta

from apps.api.app.products.gbp.adapter import BUSINESS_MANAGE_SCOPE, SUPPORTED_WRITE_FIELDS
from apps.api.app.products.gbp.freshness import (
    PROFILE_SYNC_FRESHNESS,
    profile_sync_is_stale,
)
from apps.api.app.products.gbp.service import canonical_hash, normalize_profile, profile_health


def test_google_contract_is_narrow_and_current() -> None:
    assert BUSINESS_MANAGE_SCOPE == "https://www.googleapis.com/auth/business.manage"
    assert {"profile.description", "regularHours"} == SUPPORTED_WRITE_FIELDS


def test_profile_normalization_preserves_unknown_absent_and_is_deterministic() -> None:
    source = {
        "name": "locations/1",
        "title": "Example",
        "regularHours": {},
        "unknownProviderField": True,
    }
    normalized = normalize_profile(source)
    assert normalized == {"name": "locations/1", "title": "Example", "regularHours": {}}
    assert canonical_hash(normalized) == canonical_hash(dict(reversed(list(normalized.items()))))


def test_profile_health_is_evidence_based() -> None:
    result = profile_health({"title": "Example"}, datetime.now(UTC) - timedelta(days=8))
    assert result["healthy"] is True and result["ranking_claim"] is None
    assert {
        "address_unavailable",
        "hours_missing",
        "description_missing",
        "provider_snapshot_stale",
    } <= set(result["warnings"])


def test_unsupported_provider_write_field_is_rejected() -> None:
    assert "categories" not in SUPPORTED_WRITE_FIELDS


def test_profile_sync_freshness_contract() -> None:
    now = datetime(2026, 8, 23, 12, tzinfo=UTC)

    assert timedelta(hours=24) == PROFILE_SYNC_FRESHNESS
    assert profile_sync_is_stale(None, now=now)
    assert profile_sync_is_stale(now - PROFILE_SYNC_FRESHNESS - timedelta(seconds=1), now=now)
    assert not profile_sync_is_stale(now - PROFILE_SYNC_FRESHNESS, now=now)
    assert not profile_sync_is_stale(now - PROFILE_SYNC_FRESHNESS + timedelta(seconds=1), now=now)
