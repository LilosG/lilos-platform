"""Deterministic LILOs policy checks for the Render Blueprint."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT = ROOT / "render.yaml"
STAGING_BLUEPRINT = ROOT / "render.staging.yaml"
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
        "LILOS_GITHUB_APP_ID",
        "LILOS_GITHUB_APP_CLIENT_ID",
        "LILOS_GITHUB_APP_PRIVATE_KEY",
        "LILOS_GITHUB_APP_INSTALLATION_REDIRECT_URI",
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
STAGING_BRANCH = "worker/backend-closure-2026-08-10"
STAGING_REPOSITORY = "https://github.com/LilosG/lilos-platform.git"
STAGING_PROJECT = "lilos-platform-staging"
STAGING_ENVIRONMENT = "staging"
STAGING_GROUP = "lilos-staging-runtime"
STAGING_DATABASE = "lilos-staging-postgres"
STAGING_SERVICE_POLICY = {
    "lilos-staging-api": ("web", "/health/ready", "/app/scripts/render_start_api.sh", 30),
    "lilos-staging-worker": ("worker", None, "/app/scripts/render_start_worker.sh", 300),
}
STAGING_SECRET_POLICY = {
    "lilos-staging-api": set(),
    "lilos-staging-worker": set(),
}


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
    groups = {
        group.get("name"): group
        for group in blueprint.get("envVarGroups", [])
        if isinstance(group, dict)
    }
    production_group = groups.get(SHARED_GROUP, {})
    production_values = {
        item.get("key"): item.get("value")
        for item in production_group.get("envVars", [])
        if isinstance(item, dict)
    }
    if production_values.get("LILOS_PROVIDER_WRITES_ENABLED") != "true":
        errors.append("production:provider-writes-not-explicitly-enabled")
    return tuple(sorted(errors))


def validate_staging_blueprint(path: Path = STAGING_BLUEPRINT) -> tuple[str, ...]:
    """Validate the isolated, manual-deploy staging projection."""
    blueprint = load_blueprint(path)
    errors: list[str] = []
    if blueprint.get("previews") != {"generation": "off"}:
        errors.append("staging:previews")

    projects = blueprint.get("projects")
    if not isinstance(projects, list) or len(projects) != 1:
        return ("staging:project-exact-set",)
    project = projects[0]
    if not isinstance(project, dict) or project.get("name") != STAGING_PROJECT:
        errors.append("staging:project")
    environments = project.get("environments", []) if isinstance(project, dict) else []
    if not isinstance(environments, list) or len(environments) != 1:
        return tuple(sorted({*errors, "staging:environment-exact-set"}))
    environment = environments[0]
    if not isinstance(environment, dict) or environment.get("name") != STAGING_ENVIRONMENT:
        errors.append("staging:environment")
    if environment.get("networking") != {"isolation": "enabled"}:
        errors.append("staging:network-isolation")
    if environment.get("permissions") != {"protection": "enabled"}:
        errors.append("staging:protection")

    databases = environment.get("databases", [])
    if not isinstance(databases, list) or len(databases) != 1:
        errors.append("staging:database-exact-set")
        database: dict[str, Any] = {}
    else:
        database = databases[0] if isinstance(databases[0], dict) else {}
    database_policy = {
        "name": STAGING_DATABASE,
        "plan": "basic-256mb",
        "region": "oregon",
        "postgresMajorVersion": "17",
        "databaseName": "lilos_staging",
        "user": "lilos_staging",
        "diskSizeGB": 15,
        "storageAutoscalingEnabled": False,
        "ipAllowList": [],
    }
    if database != database_policy:
        errors.append("staging:database-policy")

    groups = environment.get("envVarGroups", [])
    if not isinstance(groups, list) or len(groups) != 1:
        errors.append("staging:environment-group-exact-set")
        group: dict[str, Any] = {}
    else:
        group = groups[0] if isinstance(groups[0], dict) else {}
    if group.get("name") != STAGING_GROUP:
        errors.append("staging:environment-group")
    shared_values = {
        item.get("key"): item.get("value")
        for item in group.get("envVars", [])
        if isinstance(item, dict)
    }
    if shared_values.get("LILOS_ENV") != "staging":
        errors.append("staging:runtime-environment")
    if shared_values.get("LILOS_INTERNAL_ADMIN_ROUTES_ENABLED") != "false":
        errors.append("staging:internal-routes")
    if shared_values.get("LILOS_PROVIDER_WRITES_ENABLED") != "false":
        errors.append("staging:provider-writes")
    shared_items = {
        item.get("key"): item
        for item in group.get("envVars", [])
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
    if shared_items.get("LILOS_SECRET_ENCRYPTION_KEY") != {
        "key": "LILOS_SECRET_ENCRYPTION_KEY",
        "generateValue": True,
    }:
        errors.append("staging:generated-encryption-key")
    if any("sync" in item for item in group.get("envVars", []) if isinstance(item, dict)):
        errors.append("staging:group-placeholder")

    services = environment.get("services", [])
    if not isinstance(services, list):
        return tuple(sorted({*errors, "staging:services-missing"}))
    by_name = {
        service.get("name"): service
        for service in services
        if isinstance(service, dict) and isinstance(service.get("name"), str)
    }
    if set(by_name) != set(STAGING_SERVICE_POLICY):
        errors.append("staging:services-exact-set")

    database_reference = {"name": STAGING_DATABASE, "property": "connectionString"}
    for name, (
        service_type,
        health_path,
        command_fragment,
        shutdown_delay,
    ) in STAGING_SERVICE_POLICY.items():
        service = by_name.get(name, {})
        if service.get("type") != service_type:
            errors.append(f"{name}:type")
        if service.get("runtime") != "docker" or service.get("region") != "oregon":
            errors.append(f"{name}:runtime-region")
        if service.get("plan") != "starter" or service.get("numInstances") != 1:
            errors.append(f"{name}:capacity")
        if service.get("repo") != STAGING_REPOSITORY:
            errors.append(f"{name}:repository")
        if service.get("branch") != STAGING_BRANCH or service.get("autoDeployTrigger") != "off":
            errors.append(f"{name}:deploy-governance")
        if service.get("dockerContext") != "." or service.get("dockerfilePath") != DOCKERFILE:
            errors.append(f"{name}:docker-paths")
        if command_fragment not in str(service.get("dockerCommand", "")):
            errors.append(f"{name}:command")
        if service.get("maxShutdownDelaySeconds") != shutdown_delay:
            errors.append(f"{name}:shutdown-delay")
        if health_path is not None and service.get("healthCheckPath") != health_path:
            errors.append(f"{name}:health")

        env_vars = service.get("envVars", [])
        if {"fromGroup": STAGING_GROUP} not in env_vars:
            errors.append(f"{name}:shared-environment")
        by_key = {
            item.get("key"): item
            for item in env_vars
            if isinstance(item, dict) and isinstance(item.get("key"), str)
        }
        if by_key.get("LILOS_DATABASE_URL", {}).get("fromDatabase") != database_reference:
            errors.append(f"{name}:application-database")
        migration = by_key.get("LILOS_MIGRATION_DATABASE_URL")
        if name == "lilos-staging-api":
            if migration is None or migration.get("fromDatabase") != database_reference:
                errors.append(f"{name}:migration-database")
            if service.get("preDeployCommand") != "sh /app/scripts/render_predeploy.sh":
                errors.append(f"{name}:predeploy")
        elif migration is not None or "preDeployCommand" in service:
            errors.append(f"{name}:worker-migration")

        secret_keys = {key for key, item in by_key.items() if item.get("sync") is False}
        if secret_keys != STAGING_SECRET_POLICY[name]:
            errors.append(f"{name}:secret-policy")
        for item in by_key.values():
            if item.get("sync") is False and "value" in item:
                errors.append(f"{name}:secret-value")

    return tuple(sorted(errors))


def main() -> int:
    errors = (*validate_blueprint(), *validate_staging_blueprint())
    if errors:
        print("Render Blueprint policy validation failed: " + ", ".join(errors))
        return 1
    print("Render Blueprint policy validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
