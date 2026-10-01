"""Transport generation and drift rejection with isolated output paths."""

from pathlib import Path

import pytest

from scripts import check_contracts
from scripts.export_openapi import export


def test_public_schema_is_deterministic_and_contains_typed_projection(tmp_path: Path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    export(a)
    export(b)
    assert a.read_bytes() == b.read_bytes()
    import json

    schema = json.loads(a.read_text())
    assert "OpportunityDetail" in schema["components"]["schemas"]
    assert "AttentionView" in schema["components"]["schemas"]
    assert not any(path.startswith(("/internal", "/api/internal")) for path in schema["paths"])


def test_drift_rejects_missing_or_changed_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Use the real exporter/generator in a disposable contract root.
    (tmp_path / "node_modules").symlink_to(
        check_contracts.ROOT / "node_modules", target_is_directory=True
    )
    monkeypatch.setattr(check_contracts, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="Transport artifact drift"):
        check_contracts.check()
