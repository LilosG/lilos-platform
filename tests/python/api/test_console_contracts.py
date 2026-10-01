"""Transport generation and drift rejection with isolated output paths."""

import subprocess
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


@pytest.mark.parametrize("artifact", ["openapi.json", "src/generated/api.ts"])
@pytest.mark.parametrize("failure", ["missing", "changed"])
def test_drift_rejects_missing_or_changed_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, artifact: str, failure: str
) -> None:
    # Isolate unit-level drift rejection from the Node generator exercised by console CI.
    contracts = tmp_path / "packages/contracts"
    export(contracts / "openapi.json")
    types = contracts / "src/generated/api.ts"
    types.parent.mkdir(parents=True)
    types.write_text("export type Synthetic = string;\n")

    def generate(command: list[str], *, check: bool) -> None:
        assert check is True
        Path(command[-1]).write_text("export type Synthetic = string;\n")

    monkeypatch.setattr(subprocess, "run", generate)
    monkeypatch.setattr(check_contracts, "ROOT", tmp_path)
    target = contracts / artifact
    if failure == "missing":
        target.unlink()
    else:
        target.write_text("changed artifact\n")
    with pytest.raises(SystemExit, match="Transport artifact drift"):
        check_contracts.check()
