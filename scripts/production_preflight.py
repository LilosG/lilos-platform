"""Fail-closed, value-redacting production configuration preflight."""

from __future__ import annotations

import os
from collections.abc import Mapping

from pydantic import ValidationError

from apps.api.app.config import Settings

REQUIRED_ENVIRONMENT_KEYS = (
    "LILOS_DATABASE_URL",
    "LILOS_RELEASE",
    "LILOS_SUPABASE_AUTH_ISSUER",
    "LILOS_SUPABASE_AUTH_JWKS_URL",
    "LILOS_TELEMETRY_EXPORT_ENDPOINT",
)


def production_preflight(environment: Mapping[str, str]) -> tuple[str, ...]:
    """Return stable error categories without returning configuration values."""
    errors = [f"missing:{key}" for key in REQUIRED_ENVIRONMENT_KEYS if not environment.get(key)]
    if environment.get("LILOS_ENV") != "production":
        errors.append("invalid:LILOS_ENV")
    if environment.get("LILOS_INTERNAL_ADMIN_ROUTES_ENABLED", "false").lower() not in {
        "false",
        "0",
        "no",
        "off",
    }:
        errors.append("unsafe:LILOS_INTERNAL_ADMIN_ROUTES_ENABLED")
    if errors:
        return tuple(sorted(errors))

    try:
        Settings.model_validate(
            {
                "environment": environment["LILOS_ENV"],
                "database_url": environment["LILOS_DATABASE_URL"],
                "release": environment["LILOS_RELEASE"],
                "supabase_auth_issuer": environment["LILOS_SUPABASE_AUTH_ISSUER"],
                "supabase_auth_jwks_url": environment["LILOS_SUPABASE_AUTH_JWKS_URL"],
                "telemetry_export_endpoint": environment["LILOS_TELEMETRY_EXPORT_ENDPOINT"],
                "internal_admin_routes_enabled": False,
            }
        )
    except ValidationError:
        return ("invalid:production_configuration",)
    return ()


def main() -> int:
    errors = production_preflight(os.environ)
    if errors:
        print("production preflight blocked: " + ", ".join(errors))
        return 1
    print("production preflight passed; configuration values were not displayed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
