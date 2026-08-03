from pathlib import Path

from scripts.validate_render_blueprint import load_blueprint, validate_blueprint


def test_render_blueprint_matches_approved_runtime() -> None:
    assert validate_blueprint() == ()
    blueprint = load_blueprint()
    assert [service["name"] for service in blueprint["services"]] == [
        "lilos-api",
        "lilos-worker",
        "lilos-scheduler",
    ]


def test_render_blueprint_rejects_managed_database(tmp_path: Path) -> None:
    candidate = tmp_path / "render.yaml"
    candidate.write_text("services: []\ndatabases:\n  - name: forbidden\n", encoding="utf-8")
    assert "prohibited-root:databases" in validate_blueprint(candidate)


def test_backend_image_is_portable_nonroot_and_signal_aware() -> None:
    dockerfile = Path("infrastructure/docker/backend.Dockerfile").read_text(encoding="utf-8")
    assert "USER lilos" in dockerfile
    assert 'ENTRYPOINT ["/usr/bin/tini", "--"]' in dockerfile
    assert "render" not in dockerfile.lower()
