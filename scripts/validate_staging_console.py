"""Fail-closed prerequisite validation for the future Vercel console build.

Run before configuring a protected Preview/stable-staging deployment. Phase 1
must invoke this same check from its build/startup composition root.
"""

import os

from apps.api.app.staging.isolation import require_preview_environment


def validate(environment: dict[str, str]) -> None:
    required = (
        "CONSOLE_API_ORIGIN",
        "CONSOLE_APPROVED_STAGING_API_ORIGIN",
        "CONSOLE_PRODUCTION_API_ORIGIN",
        "CONSOLE_SUPABASE_URL",
        "CONSOLE_STAGING_SUPABASE_PROJECT_REF",
        "CONSOLE_PRODUCTION_SUPABASE_PROJECT_REF",
        "CONSOLE_EXPECTED_HOST",
        "CONSOLE_DEPLOYMENT_PROTECTED",
    )
    if any(not environment.get(key) for key in required):
        raise ValueError("Missing console staging prerequisite configuration")
    if environment["CONSOLE_APPROVED_STAGING_API_ORIGIN"].rstrip("/") == environment[
        "CONSOLE_PRODUCTION_API_ORIGIN"
    ].rstrip("/"):
        raise ValueError("Approved staging API must differ from production")
    if environment.get("VERCEL_ENV") not in {"preview", "production"}:
        raise ValueError("Console staging configuration requires a Vercel deployment environment")
    expected = environment["CONSOLE_EXPECTED_HOST"]
    host = (
        environment.get("VERCEL_URL", "")
        if environment["VERCEL_ENV"] == "preview"
        else "console-staging.lilosgrowth.com"
    )
    require_preview_environment(
        api_url=environment["CONSOLE_API_ORIGIN"],
        supabase_url=environment["CONSOLE_SUPABASE_URL"],
        approved_api=environment["CONSOLE_APPROVED_STAGING_API_ORIGIN"],
        project=environment["CONSOLE_STAGING_SUPABASE_PROJECT_REF"],
        production_project=environment["CONSOLE_PRODUCTION_SUPABASE_PROJECT_REF"],
        expected_host=expected,
        deployment_host=host,
        protected=environment["CONSOLE_DEPLOYMENT_PROTECTED"] == "true",
    )
    if any(
        key.startswith("PUBLIC_")
        and any(part in key for part in ("TOKEN", "SECRET", "SERVICE_ROLE", "PRIVATE_KEY"))
        for key in environment
    ):
        raise ValueError("Console refuses public secret configuration")


if __name__ == "__main__":
    validate(dict(os.environ))
    print("Console staging prerequisite configuration valid")
