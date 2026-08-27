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
HERMES_SERVICE = "lilos-hermes"
HERMES_DOCKERFILE = "./infrastructure/docker/hermes-render.Dockerfile"
DOCKERFILE = "./infrastructure/docker/backend.Dockerfile"
SHARED_GROUP = "lilos-production-runtime"
WORKER_SCHEDULER_SECRETS = {
    "LILOS_DATABASE_URL",
    "LILOS_SUPABASE_AUTH_ISSUER",
    "LILOS_SUPABASE_AUTH_JWKS_URL",
    "LILOS_TELEMETRY_EXPORT_ENDPOINT",
    "LILOS_SECRET_ENCRYPTION_KEY",
    "LILOS_GOOGLE_OAUTH_CLIENT_ID",
    "LILOS_GOOGLE_OAUTH_CLIENT_SECRET",
    "LILOS_GOOGLE_OAUTH_REDIRECT_URI",
    "LILOS_GITHUB_APP_ID",
    "LILOS_GITHUB_APP_CLIENT_ID",
    "LILOS_GITHUB_APP_PRIVATE_KEY",
    "LILOS_GITHUB_APP_INSTALLATION_REDIRECT_URI",
    "LILOS_OPENROUTER_API_KEY",
}
WORKER_SECRETS = WORKER_SCHEDULER_SECRETS | {
    "LILOS_GOOGLE_PAGESPEED_API_KEY",
    "LILOS_GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON",
    "LILOS_DATAFORSEO_LOGIN",
    "LILOS_DATAFORSEO_PASSWORD",
}

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
        "LILOS_GOOGLE_PAGESPEED_API_KEY",
        "LILOS_GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON",
        "LILOS_DATAFORSEO_LOGIN",
        "LILOS_DATAFORSEO_PASSWORD",
        "LILOS_SECRET_ENCRYPTION_KEY",
        "LILOS_GITHUB_APP_ID",
        "LILOS_GITHUB_APP_CLIENT_ID",
        "LILOS_GITHUB_APP_PRIVATE_KEY",
        "LILOS_GITHUB_APP_INSTALLATION_REDIRECT_URI",
        "LILOS_OPENROUTER_API_KEY",
    },
    "lilos-worker": WORKER_SECRETS,
    "lilos-scheduler": WORKER_SCHEDULER_SECRETS,
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
STAGING_SECRET_POLICY: dict[str, set[str]] = {
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
    if set(by_name) != {*SERVICE_POLICY, HERMES_SERVICE}:
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

    hermes = by_name.get(HERMES_SERVICE, {})
    if (
        hermes.get("type") != "pserv"
        or hermes.get("runtime") != "docker"
        or hermes.get("region") != "oregon"
        or hermes.get("plan") != "standard"
    ):
        errors.append("lilos-hermes:runtime-policy")
    if hermes.get("branch") != "main" or hermes.get("autoDeployTrigger") != "checksPass":
        errors.append("lilos-hermes:deploy-governance")
    if hermes.get("dockerContext") != "." or hermes.get("dockerfilePath") != HERMES_DOCKERFILE:
        errors.append("lilos-hermes:docker-paths")
    if "image" in hermes or "dockerCommand" in hermes:
        errors.append("lilos-hermes:upstream-entrypoint-bypass")
    if hermes.get("disk") != {
        "name": "hermes-data",
        "mountPath": "/opt/data",
        "sizeGB": 5,
    }:
        errors.append("lilos-hermes:persistent-disk")
    hermes_env = {
        item.get("key"): item
        for item in hermes.get("envVars", [])
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
    hermes_values = {
        "PORT": "8642",
        "API_SERVER_ENABLED": "true",
        "API_SERVER_HOST": "0.0.0.0",
        "API_SERVER_PORT": "8642",
        "API_SERVER_MODEL_NAME": "hermes-agent",
        "HERMES_RUNTIME_VERSION": "v2026.8.19",
        "HERMES_INFERENCE_PROVIDER": "openrouter",
        "HERMES_INFERENCE_MODEL": "deepseek/deepseek-v4-flash-0731",
        # Spend bound: Hermes loops outside the AI Gateway and accepts no token
        # budget, so iteration count is the only enforceable cap on a runaway run.
        "HERMES_MAX_ITERATIONS": "25",
        "HERMES_YOLO_MODE": "0",
    }
    if set(hermes_env) != {
        *hermes_values,
        "API_SERVER_KEY",
        "OPENROUTER_API_KEY",
        "LILOS_TOOL_BASE_URL",
        "LILOS_TOOL_API_KEY",
    }:
        errors.append("lilos-hermes:env-exact-set")
    for key, value in hermes_values.items():
        if hermes_env.get(key) != {"key": key, "value": value}:
            errors.append(f"lilos-hermes:env:{key}")
    if hermes_env.get("API_SERVER_KEY") != {
        "key": "API_SERVER_KEY",
        "generateValue": True,
    }:
        errors.append("lilos-hermes:generated-api-key")
    if hermes_env.get("OPENROUTER_API_KEY") != {
        "key": "OPENROUTER_API_KEY",
        "sync": False,
    }:
        errors.append("lilos-hermes:openrouter-secret")
    if hermes_env.get("LILOS_TOOL_BASE_URL") != {
        "key": "LILOS_TOOL_BASE_URL",
        "fromService": {
            "name": "lilos-api",
            "type": "web",
            "property": "hostport",
        },
    }:
        errors.append("lilos-hermes:tool-private-url")
    if hermes_env.get("LILOS_TOOL_API_KEY") != {
        "key": "LILOS_TOOL_API_KEY",
        "generateValue": True,
    }:
        errors.append("lilos-hermes:generated-tool-key")

    hermes_dockerfile = ROOT / HERMES_DOCKERFILE.removeprefix("./")
    hermes_start_script = ROOT / "scripts" / "render_start_hermes.sh"
    if not hermes_dockerfile.is_file():
        errors.append("lilos-hermes:dockerfile-missing")
    else:
        dockerfile_text = hermes_dockerfile.read_text(encoding="utf-8")
        for fragment in (
            "nousresearch/hermes-agent:v2026.8.19@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09",
            "infrastructure/hermes/plugins/lilos",
            "ENTRYPOINT",
            "lilos-render-start-hermes",
            "--no-supervise",
            "--external-supervisor",
        ):
            if fragment not in dockerfile_text:
                errors.append(f"lilos-hermes:dockerfile:{fragment}")
    if not hermes_start_script.is_file():
        errors.append("lilos-hermes:start-script-missing")
    else:
        start_text = hermes_start_script.read_text(encoding="utf-8")
        for fragment in (
            "/opt/hermes/docker/stage2-hook.sh",
            "/opt/hermes/docker/main-wrapper.sh",
            "platform_toolsets.api_server",
            "agent.disabled_toolsets",
            "sessions.auto_prune",
            "sessions.retention_days 30",
            "LILOS_TOOL_API_KEY",
            "Bootstrap complete; starting foreground gateway",
        ):
            if fragment not in start_text:
                errors.append(f"lilos-hermes:start-script:{fragment}")

    expected_base_url = {
        "key": "LILOS_HERMES_BASE_URL",
        "fromService": {
            "name": HERMES_SERVICE,
            "type": "pserv",
            "property": "hostport",
        },
    }
    expected_api_key = {
        "key": "LILOS_HERMES_API_KEY",
        "fromService": {
            "name": HERMES_SERVICE,
            "type": "pserv",
            "envVarKey": "API_SERVER_KEY",
        },
    }
    expected_tool_key = {
        "key": "LILOS_HERMES_TOOL_API_KEY",
        "fromService": {
            "name": HERMES_SERVICE,
            "type": "pserv",
            "envVarKey": "LILOS_TOOL_API_KEY",
        },
    }
    expected_runtime_release = {
        "key": "LILOS_HERMES_RUNTIME_RELEASE",
        "fromService": {
            "name": HERMES_SERVICE,
            "type": "pserv",
            "envVarKey": "HERMES_RUNTIME_VERSION",
        },
    }
    for consumer in ("lilos-api", "lilos-worker"):
        consumer_env = {
            item.get("key"): item
            for item in by_name.get(consumer, {}).get("envVars", [])
            if isinstance(item, dict) and isinstance(item.get("key"), str)
        }
        if consumer_env.get("LILOS_HERMES_BASE_URL") != expected_base_url:
            errors.append(f"{consumer}:hermes-private-url")
        if consumer_env.get("LILOS_HERMES_API_KEY") != expected_api_key:
            errors.append(f"{consumer}:hermes-api-key")
        if consumer_env.get("LILOS_HERMES_RUNTIME_RELEASE") != expected_runtime_release:
            errors.append(f"{consumer}:hermes-runtime-release")
        if consumer == "lilos-api":
            if consumer_env.get("LILOS_HERMES_TOOL_API_KEY") != expected_tool_key:
                errors.append("lilos-api:hermes-tool-key")
        elif "LILOS_HERMES_TOOL_API_KEY" in consumer_env:
            errors.append("lilos-worker:hermes-tool-key-least-privilege")

    scheduler_env = {
        item.get("key")
        for item in by_name.get("lilos-scheduler", {}).get("envVars", [])
        if isinstance(item, dict) and isinstance(item.get("key"), str)
    }
    if scheduler_env & {
        "LILOS_HERMES_BASE_URL",
        "LILOS_HERMES_API_KEY",
        "LILOS_HERMES_TOOL_API_KEY",
    }:
        errors.append("lilos-scheduler:hermes-least-privilege")

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
        errors.append("production:provider-writes-disabled")
    if production_values.get("LILOS_AI_PROVIDER") != "hermes":
        errors.append("production:hermes-not-primary")
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
    if not isinstance(projects[0], dict) or project.get("name") != STAGING_PROJECT:
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
