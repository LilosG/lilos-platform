import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid4

from apps.api.app.products.gbp import capability_backfill


def test_capability_document_never_expands_adapter_write_surface() -> None:
    document = capability_backfill.capability_document_from_profile(
        {
            "name": "locations/123",
            "profile": {"description": "Current description"},
            "regularHours": {"periods": []},
            "categories": {"primaryCategory": {"name": "categories/gcid:restaurant"}},
            "websiteUri": "https://example.com/",
        }
    )

    assert "name" not in document
    assert cast(dict[str, object], document["profile"])["writable"] is True
    assert cast(dict[str, object], document["regularHours"])["writable"] is True
    assert cast(dict[str, object], document["categories"])["writable"] is False
    assert cast(dict[str, object], document["websiteUri"])["writable"] is False


def test_legacy_profile_snapshot_is_backfilled_without_google_io(monkeypatch: Any) -> None:
    organization_id = uuid4()
    location_id = uuid4()
    gbp_location_id = uuid4()
    observed_at = datetime.now(UTC)
    recorded: dict[str, object] = {}

    class FakeSession:
        def __init__(self) -> None:
            self.scalar_calls = 0

        async def scalars(self, _statement: object) -> list[object]:
            return [SimpleNamespace(id=gbp_location_id)]

        async def scalar(self, _statement: object) -> object | None:
            self.scalar_calls += 1
            if self.scalar_calls == 1:
                return None
            return SimpleNamespace(
                normalized_profile={
                    "profile": {"description": "Synced provider description"},
                    "categories": {"primaryCategory": {"name": "categories/gcid:restaurant"}},
                },
                observed_at=observed_at,
            )

    class FakeOperations:
        async def record_capability_snapshot(
            self,
            _session: object,
            org: object,
            gbp_location: object,
            capabilities: object,
            snapshot_observed_at: object,
            *,
            actor_id: object,
            correlation_id: object,
        ) -> object:
            recorded.update(
                {
                    "organization_id": org,
                    "gbp_location_id": gbp_location,
                    "capabilities": capabilities,
                    "observed_at": snapshot_observed_at,
                    "actor_id": actor_id,
                    "correlation_id": correlation_id,
                }
            )
            return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(capability_backfill, "GBPOperationsService", FakeOperations)

    async def scenario() -> None:
        repaired = await capability_backfill.ensure_capability_snapshot_from_profile(
            cast(Any, FakeSession()),
            organization_id=organization_id,
            location_id=location_id,
            correlation_id="hermes-gbp-regression",
        )
        assert repaired is True

    asyncio.run(scenario())

    assert recorded["organization_id"] == organization_id
    assert recorded["gbp_location_id"] == gbp_location_id
    assert recorded["observed_at"] == observed_at
    assert recorded["correlation_id"] == "hermes-gbp-regression"
    capabilities = cast(dict[str, dict[str, object]], recorded["capabilities"])
    assert capabilities["profile"]["writable"] is True
    assert capabilities["categories"]["writable"] is False
