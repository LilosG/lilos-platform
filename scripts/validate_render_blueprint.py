"""Deterministic LILOs policy checks for the Render Blueprint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "render.yaml"
SERVICE_POLICY = {
    "lilos-api": ("web", "/health/ready", "/app/scripts/render_start_api.sh", 30),
    "lilos-worker": ("worker", None, "/app/scripts/render_start_worker.sh", 300),
    "lilos-scheduler": ("worker", None, "/app/scripts/render_start_scheduler.sh", 60),
}
DOCKERFILE = "./infrastructure/docker/backend.Dockerfile"
SHARED_GROUP = "lilos-production-runtime"
SECRET_POLICY = {
    "lilos-api": {
        "LILOS_DATABASE_URL",
        "LILOS_MIGRATION_DATABASE_URL",
        "LILOS_SUPABASE_AUTH_ISSUER",
        "LILOS_SUPABASE_AUTH_JWKS_URL",
        "LILOS_TELEMETRY_EXPORT_ENDPOINT",
        "LILOS_WEB_ORIGINS",
        "LILOS_GOOGLE_OAUTH_CLIENT_ID",
        "LILOS_GOOGLE_OAUTH_CLIENT_SECRET",
        "LILOS_GOOGLE_OAUTH_REDIRECT_URI",
        "LILOS_SECRET_ENCRYPTION_KEY",
    },
    "lilos-worker": {
        "LILOS_DATABASE_URL",
        "LILOS_SUPABASE_AUTH_ISSUER",
        "LILOS_SUPABASE_AUTH_JWKS_URL",
        "LILOS_TELEMETRY_EXPORT_ENDPOINT",
    },
    "lilos-scheduler": {
        "LILOS_DATABASE_URL",
        "LILOS_SUPABASE_AUTH_ISSUER",
        "LILOS_SUPABASE_AUTH_JWKS_URL",
        "LILOS_TELEMETRY_EXPORT_ENDPOINT",
    },
}
PROHIBITED_ROOT_KEYS = {"databases", "projects"}
PROHIBITED_SERVICE_TYPES = {"cron", "keyvalue", "redis"}


def load_blueprint(path: Path = BLUEPRINT) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("Render Blueprint must be an object")
    return document


def validate_blueprint(path: Path = BLUEPRINT) -> tuple[str, ...]:
    blueprint = load_blueprint(path)
    errors: list[str] = []
    errors.extend(f"prohibited-root:{key}" for key in PROHIBITED_ROOT_KEYS & blueprint.keys())

    services = blueprint.get("services")
    if not isinstance(services, list):
        return ("services:missing",)
    by_name = {
        service.get("name"): service
        for service in services
        if isinstance(service, dict) and isinstance(service.get("name"), str)
    }
    if set(by_name) != set(SERVICE_POLICY):
        errors.append("services:exact-set")

    for name, (
        service_type,
        health_path,
        command_fragment,
        shutdown_delay,
    ) in SERVICE_POLICY.items():
        service = by_name.get(name, {})
        if service.get("type") != service_type:
            errors.append(f"{name}:type")
        if service.get("runtime") != "docker" or service.get("region") != "oregon":
            errors.append(f"{name}:runtime-region")
        if service.get("dockerContext") != "." or service.get("dockerfilePath") != DOCKERFILE:
            errors.append(f"{name}:docker-paths")
        if command_fragment not in str(service.get("dockerCommand", "")):
            errors.append(f"{name}:command")
        if service.get("maxShutdownDelaySeconds") != shutdown_delay:
            errors.append(f"{name}:shutdown-delay")
        if health_path is not None and service.get("healthCheckPath") != health_path:
            errors.append(f"{name}:health")
        if service.get("type") in PROHIBITED_SERVICE_TYPES or "disk" in service:
            errors.append(f"{name}:prohibited-resource")
        env_vars = service.get("envVars", [])
        if {"fromGroup": SHARED_GROUP} not in env_vars:
            errors.append(f"{name}:shared-environment")
        secret_keys = {
            item.get("key")
            for item in env_vars
            if isinstance(item, dict) and item.get("sync") is False
        }
        if secret_keys != SECRET_POLICY[name]:
            errors.append(f"{name}:secret-policy")
        for item in env_vars:
            if isinstance(item, dict) and item.get("sync") is False and "value" in item:
                errors.append(f"{name}:secret-value")

        if name != "lilos-api" and "preDeployCommand" in service:
            errors.append(f"{name}:predeploy")

    api = by_name.get("lilos-api", {})
    api_start_script = ROOT / "scripts" / "render_start_api.sh"
    if not api_start_script.is_file():
        errors.append("lilos-api:start-script-missing")
    else:
        api_start_text = api_start_script.read_text(encoding="utf-8")
        if (
            "0.0.0.0" not in api_start_text
            or "${PORT:-10000}" not in api_start_text
            or "python -m uvicorn" not in api_start_text
        ):
            errors.append("lilos-api:bind")
    predeploy = str(api.get("preDeployCommand", ""))
    predeploy_policy_text = predeploy

    if predeploy == "sh /app/scripts/render_predeploy.sh":
        predeploy_script = ROOT / "scripts" / "render_predeploy.sh"
        if not predeploy_script.is_file():
            errors.append("lilos-api:predeploy-script-missing")
        else:
            predeploy_policy_text = predeploy_script.read_text(encoding="utf-8")

    for command in (
        "alembic upgrade head",
        "scripts.seed_industries",
        "scripts.seed_access_catalog",
        "scripts.seed_administration_catalog",
        "scripts.seed_integration_providers",
    ):
        if command not in predeploy_policy_text:
            errors.append(f"lilos-api:predeploy:{command}")

    serialized = path.read_text(encoding="utf-8").lower()
    for prohibited in ("render postgres", "key value", "render workflow", "type: cron"):
        if prohibited in serialized:
            errors.append(f"prohibited-text:{prohibited}")
    return tuple(sorted(errors))


def main() -> int:
    errors = validate_blueprint()
    if errors:
        print("Render Blueprint policy validation failed: " + ", ".join(errors))
        return 1
    print("Render Blueprint policy validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
