from pathlib import Path

from scripts.validate_render_blueprint import (
    STAGING_BLUEPRINT,
    load_blueprint,
    validate_blueprint,
    validate_staging_blueprint,
)


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


def test_render_blueprint_requires_provider_writes_enabled(tmp_path: Path) -> None:
    candidate = tmp_path / "render.yaml"
    source = Path("render.yaml").read_text(encoding="utf-8")
    candidate.write_text(
        source.replace(
            '      - key: LILOS_PROVIDER_WRITES_ENABLED\n        value: "true"',
            '      - key: LILOS_PROVIDER_WRITES_ENABLED\n        value: "false"',
        ),
        encoding="utf-8",
    )

    assert "production:provider-writes-disabled" in validate_blueprint(candidate)


def test_staging_blueprint_is_isolated_manual_and_write_disabled() -> None:
    assert validate_staging_blueprint() == ()
    blueprint = load_blueprint(STAGING_BLUEPRINT)
    environment = blueprint["projects"][0]["environments"][0]

    assert environment["networking"] == {"isolation": "enabled"}
    assert environment["permissions"] == {"protection": "enabled"}
    assert environment["databases"][0]["ipAllowList"] == []
    assert {service["branch"] for service in environment["services"]} == {
        "worker/backend-closure-2026-08-10"
    }
    assert {service["autoDeployTrigger"] for service in environment["services"]} == {"off"}
    assert {service["repo"] for service in environment["services"]} == {
        "https://github.com/LilosG/lilos-platform.git"
    }
    group_items = {item["key"]: item for item in environment["envVarGroups"][0]["envVars"]}
    assert group_items["LILOS_SECRET_ENCRYPTION_KEY"] == {
        "key": "LILOS_SECRET_ENCRYPTION_KEY",
        "generateValue": True,
    }
    assert all(
        item.get("sync") is not False
        for service in environment["services"]
        for item in service["envVars"]
    )


def test_staging_blueprint_rejects_provider_writes_enabled(tmp_path: Path) -> None:
    candidate = tmp_path / "render.staging.yaml"
    source = STAGING_BLUEPRINT.read_text(encoding="utf-8")
    candidate.write_text(
        source.replace(
            'LILOS_PROVIDER_WRITES_ENABLED\n                value: "false"',
            'LILOS_PROVIDER_WRITES_ENABLED\n                value: "true"',
        ),
        encoding="utf-8",
    )

    assert "staging:provider-writes" in validate_staging_blueprint(candidate)


def test_backend_image_is_portable_nonroot_and_signal_aware() -> None:
    dockerfile = Path("infrastructure/docker/backend.Dockerfile").read_text(encoding="utf-8")
    assert "USER lilos" in dockerfile
    assert 'ENTRYPOINT ["/usr/bin/tini", "--"]' in dockerfile
    assert "render" not in dockerfile.lower()
