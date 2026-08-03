from scripts.production_preflight import production_preflight


def valid_environment() -> dict[str, str]:
    return {
        "LILOS_ENV": "production",
        "LILOS_DATABASE_URL": "postgresql+asyncpg://db.invalid/lilos",
        "LILOS_RELEASE": "release-2026-08-03",
        "LILOS_SUPABASE_AUTH_ISSUER": "https://auth.invalid",
        "LILOS_SUPABASE_AUTH_JWKS_URL": "https://auth.invalid/.well-known/jwks.json",
        "LILOS_TELEMETRY_EXPORT_ENDPOINT": "https://telemetry.invalid/v1/traces",
        "LILOS_INTERNAL_ADMIN_ROUTES_ENABLED": "false",
    }


def test_preflight_accepts_complete_fail_closed_contract() -> None:
    assert production_preflight(valid_environment()) == ()


def test_preflight_reports_names_without_values() -> None:
    environment = valid_environment()
    secret_value = environment.pop("LILOS_DATABASE_URL")
    errors = production_preflight(environment)
    assert errors == ("missing:LILOS_DATABASE_URL",)
    assert secret_value not in " ".join(errors)


def test_preflight_rejects_internal_routes() -> None:
    environment = valid_environment()
    environment["LILOS_INTERNAL_ADMIN_ROUTES_ENABLED"] = "true"
    assert production_preflight(environment) == ("unsafe:LILOS_INTERNAL_ADMIN_ROUTES_ENABLED",)
