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
        "lilos-hermes",
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


def test_render_blueprint_requires_hermes_persistent_storage(tmp_path: Path) -> None:
    candidate = tmp_path / "render.yaml"
    source = Path("render.yaml").read_text(encoding="utf-8")
    candidate.write_text(
        source.replace("      sizeGB: 5", "      sizeGB: 1"),
        encoding="utf-8",
    )

    assert "lilos-hermes:persistent-disk" in validate_blueprint(candidate)


def test_render_blueprint_requires_private_hermes_service_binding(tmp_path: Path) -> None:
    candidate = tmp_path / "render.yaml"
    source = Path("render.yaml").read_text(encoding="utf-8")
    private_binding = """      - key: LILOS_HERMES_BASE_URL
        fromService:
          name: lilos-hermes
          type: pserv
          property: hostport"""
    candidate.write_text(
        source.replace(
            private_binding,
            private_binding.replace("property: hostport", "property: host"),
            1,
        ),
        encoding="utf-8",
    )

    assert "lilos-api:hermes-private-url" in validate_blueprint(candidate)


def test_staging_blueprint_is_isolated_manual_and_write_disabled() -> None:
    assert validate_staging_blueprint() == ()
    blueprint = load_blueprint(STAGING_BLUEPRINT)
    environment = blueprint["projects"][0]["environments"][0]

    assert environment["networking"] == {"isolation": "enabled"}
    assert environment["permissions"] == {"protection": "enabled"}
    assert "databases" not in environment
    assert {service["branch"] for service in environment["services"]} == {"main"}
    assert {service["autoDeployTrigger"] for service in environment["services"]} == {"off"}
    assert len(environment["services"]) == 4
    api = next(service for service in environment["services"] if service["type"] == "web")
    assert {"key": "LILOS_SECRET_ENCRYPTION_KEY", "sync": False} in api["envVars"]


def test_staging_blueprint_rejects_provider_writes_enabled(tmp_path: Path) -> None:
    candidate = tmp_path / "render.staging.yaml"
    import yaml

    document = load_blueprint(STAGING_BLUEPRINT)
    items = document["projects"][0]["environments"][0]["envVarGroups"][0]["envVars"]
    next(item for item in items if item.get("key") == "LILOS_PROVIDER_WRITES_ENABLED")["value"] = (
        "true"
    )
    candidate.write_text(yaml.safe_dump(document), encoding="utf-8")

    assert "staging:provider-writes" in validate_staging_blueprint(candidate)


def test_backend_image_is_portable_nonroot_and_signal_aware() -> None:
    dockerfile = Path("infrastructure/docker/backend.Dockerfile").read_text(encoding="utf-8")
    assert "USER lilos" in dockerfile
    assert 'ENTRYPOINT ["/usr/bin/tini", "--"]' in dockerfile
    assert "render" not in dockerfile.lower()


def test_hermes_bootstrap_repairs_config_before_stage2_and_pins_api_tools() -> None:
    source = Path("scripts/render_start_hermes.sh").read_text(encoding="utf-8")

    assert source.index('HERMES_CONFIG_FILE="${HERMES_HOME}/config.yaml"') < source.index(
        "/opt/hermes/docker/stage2-hook.sh"
    )
    assert "config set platform_toolsets.api_server" not in source
    assert 'platform_toolsets["api_server"] = ["lilos", "no_mcp"]' in source
