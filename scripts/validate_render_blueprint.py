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
    },
    "lilos-worker": WORKER_SECRETS,
    "lilos-scheduler": WORKER_SCHEDULER_SECRETS,
}
PROHIBITED_ROOT_KEYS = {"databases", "projects"}
PROHIBITED_SERVICE_TYPES = {"cron", "keyvalue", "redis"}
STAGING_BRANCH = "main"
STAGING_REPOSITORY = "https://github.com/LilosG/lilos-platform.git"
STAGING_PROJECT = "lilos-command-center-staging"
STAGING_ENVIRONMENT = "staging"
STAGING_GROUP = "lilos-staging-runtime"
STAGING_HERMES = "lilos-command-center-staging-hermes"
STAGING_SERVICE_POLICY = {
    name.replace("lilos-", "lilos-command-center-staging-", 1): policy
    for name, policy in SERVICE_POLICY.items()
}
STAGING_IDENTITY_KEYS = {
    "LILOS_STAGING_SUPABASE_PROJECT_REF",
    "LILOS_PRODUCTION_SUPABASE_PROJECT_REF",
    "LILOS_STAGING_FORBIDDEN_SECRET_SHA256",
    "LILOS_STAGING_GITHUB_REPOSITORY",
    "LILOS_STAGING_GITHUB_INSTALLATION_ID",
    "LILOS_STAGING_GITHUB_PATH_PREFIX",
    "LILOS_STAGING_LIVE_GOOGLE_ORGANIZATION_IDS",
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
        "HERMES_AUXILIARY_MODEL": "nvidia/nemotron-3-ultra-550b-a55b:free",
        "HERMES_AUXILIARY_VISION_MODEL": "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
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
            'platform_toolsets["api_server"] = ["lilos", "no_mcp"]',
            "agent.disabled_toolsets",
            "sessions.auto_prune",
            "sessions.retention_days 30",
            # Config-schema rotation and explicit auxiliary routing are
            # load-bearing production policy. The checks below prove that
            # fixed free-only routes are applied instead of paid fallback.
            "below the v12 support floor",
            "auxiliary.free_only true",
            'auxiliary.openrouter_model "$HERMES_AUXILIARY_MODEL"',
            "auxiliary.vision.provider openrouter",
            'auxiliary.vision.model "$HERMES_AUXILIARY_VISION_MODEL"',
            "auxiliary.compression.provider openrouter",
            'auxiliary.compression.model "$HERMES_AUXILIARY_MODEL"',
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
    expected_openrouter_key = {
        "key": "LILOS_OPENROUTER_API_KEY",
        "fromService": {
            "name": HERMES_SERVICE,
            "type": "pserv",
            "envVarKey": "OPENROUTER_API_KEY",
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
        if consumer_env.get("LILOS_OPENROUTER_API_KEY") != expected_openrouter_key:
            errors.append(f"{consumer}:openrouter-shared-secret")
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
        "LILOS_OPENROUTER_API_KEY",
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
    """Four-service manual staging, separate Supabase, and no production references."""
    blueprint = load_blueprint(path)
    errors: list[str] = []
    if blueprint.get("previews") != {"generation": "off"}:
        errors.append("staging:previews")
    projects = blueprint.get("projects", [])
    if len(projects) != 1 or projects[0].get("name") != STAGING_PROJECT:
        return ("staging:project",)
    environments = projects[0].get("environments", [])
    if len(environments) != 1 or environments[0].get("name") != STAGING_ENVIRONMENT:
        return ("staging:environment",)
    environment = environments[0]
    if environment.get("networking") != {"isolation": "enabled"}:
        errors.append("staging:network-isolation")
    if environment.get("permissions") != {"protection": "enabled"}:
        errors.append("staging:protection")
    if "databases" in blueprint or "databases" in environment or "services" in blueprint:
        errors.append("staging:prohibited-resource")
    groups = environment.get("envVarGroups", [])
    if len(groups) != 1 or groups[0].get("name") != STAGING_GROUP:
        return (*errors, "staging:environment-group")
    group = {item.get("key"): item for item in groups[0].get("envVars", [])}
    for key, value in {
        "LILOS_ENV": "staging",
        "LILOS_GOOGLE_PROVIDER_MODE": "fixture",
        "LILOS_INTERNAL_ADMIN_ROUTES_ENABLED": "false",
        "LILOS_PROVIDER_WRITES_ENABLED": "false",
        "LILOS_AI_PROVIDER": "hermes",
    }.items():
        if group.get(key) != {"key": key, "value": value}:
            errors.append(
                "staging:provider-writes"
                if key == "LILOS_PROVIDER_WRITES_ENABLED"
                else f"staging:{key}"
            )
    if any("sync" in item or "generateValue" in item for item in group.values()):
        errors.append("staging:group-secrets")
    services = environment.get("services", [])
    by_name = {item.get("name"): item for item in services}
    if len(services) != 4 or set(by_name) != {*STAGING_SERVICE_POLICY, STAGING_HERMES}:
        errors.append("staging:services-exact-set")
    for name, service in by_name.items():
        if service.get("branch") != "main" or service.get("autoDeployTrigger") != "off":
            errors.append(f"{name}:deploy-governance")
        if (
            service.get("repo") != STAGING_REPOSITORY
            or service.get("region") != "oregon"
            or service.get("runtime") != "docker"
        ):
            errors.append(f"{name}:runtime-repository-region")
        env_items = service.get("envVars", [])
        env = {item.get("key"): item for item in env_items if "key" in item}
        for item in env_items:
            if "fromDatabase" in item or (item.get("sync") is False and "value" in item):
                errors.append(f"{name}:unsafe-resource-or-secret")
            reference = item.get("fromService", {}).get("name")
            if reference and reference not in {*STAGING_SERVICE_POLICY, STAGING_HERMES}:
                errors.append(f"{name}:production-reference")
        if name in STAGING_SERVICE_POLICY:
            kind, health, command, shutdown = STAGING_SERVICE_POLICY[name]
            if (
                service.get("type") != kind
                or service.get("dockerCommand") != f"sh {command}"
                or service.get("maxShutdownDelaySeconds") != shutdown
            ):
                errors.append(f"{name}:process-contract")
            if service.get("dockerfilePath") != DOCKERFILE or service.get("dockerContext") != ".":
                errors.append(f"{name}:docker-paths")
            if (
                {"fromGroup": STAGING_GROUP} not in env_items
                or service.get("plan") != "starter"
                or service.get("numInstances") != 1
            ):
                errors.append(f"{name}:group-capacity")
            required = {
                "LILOS_DATABASE_URL",
                "LILOS_SUPABASE_AUTH_ISSUER",
                "LILOS_SUPABASE_AUTH_JWKS_URL",
                *STAGING_IDENTITY_KEYS,
            }
            if name.endswith("-api"):
                required |= {"LILOS_MIGRATION_DATABASE_URL", "LILOS_SECRET_ENCRYPTION_KEY"}
                if (
                    service.get("healthCheckPath") != health
                    or service.get("preDeployCommand") != "sh /app/scripts/render_predeploy.sh"
                ):
                    errors.append(f"{name}:api-health-predeploy")
            elif "preDeployCommand" in service or "LILOS_MIGRATION_DATABASE_URL" in env:
                errors.append(f"{name}:worker-migration")
            for key in required:
                if env.get(key) != {"key": key, "sync": False}:
                    errors.append(f"{name}:independent:{key}")
            if name.endswith("-scheduler") and any(
                key in env
                for key in (
                    "LILOS_HERMES_API_KEY",
                    "LILOS_HERMES_TOOL_API_KEY",
                    "LILOS_OPENROUTER_API_KEY",
                )
            ):
                errors.append(f"{name}:least-privilege")
        elif name == STAGING_HERMES:
            if (
                service.get("type") != "pserv"
                or service.get("dockerfilePath") != HERMES_DOCKERFILE
                or service.get("plan") != "standard"
            ):
                errors.append("staging:hermes-runtime")
            if service.get("disk") != {
                "name": "staging-hermes-data",
                "mountPath": "/opt/data",
                "sizeGB": 5,
            }:
                errors.append("staging:hermes-disk")
            for key in ("API_SERVER_KEY", "LILOS_TOOL_API_KEY"):
                if env.get(key) != {"key": key, "generateValue": True}:
                    errors.append(f"staging:hermes:{key}")
            if (
                env.get("HERMES_RUNTIME_VERSION", {}).get("value") != "v2026.8.19"
                or env.get("HERMES_MAX_ITERATIONS", {}).get("value") != "25"
                or env.get("HERMES_YOLO_MODE", {}).get("value") != "0"
            ):
                errors.append("staging:hermes-bounds")
            if env.get("LILOS_TOOL_BASE_URL") != {
                "key": "LILOS_TOOL_BASE_URL",
                "fromService": {
                    "name": "lilos-command-center-staging-api",
                    "type": "web",
                    "property": "hostport",
                },
            }:
                errors.append("staging:hermes-tools")
    return tuple(sorted(errors))
