"""Explicit resource identity checks; environment names alone grant no access."""

from urllib.parse import unquote, urlsplit


def require_supabase_database(url: str, project: str) -> None:
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    user = unquote(parsed.username or "")
    direct = host == f"db.{project}.supabase.co" and user == "postgres"
    pooler = host.endswith(".pooler.supabase.com") and user == f"postgres.{project}"
    if not (direct or pooler) or parsed.path != "/postgres" or parsed.fragment:
        raise ValueError("Database must belong to the approved staging Supabase project")


def require_preview_environment(
    *,
    api_url: str,
    supabase_url: str,
    approved_api: str,
    project: str,
    production_project: str,
    expected_host: str,
    deployment_host: str,
    protected: bool,
) -> None:
    if not project or project == production_project or not production_project:
        raise ValueError("Distinct approved staging and production project identities required")
    api = urlsplit(api_url)
    approved = urlsplit(approved_api)
    if (
        api.scheme != "https"
        or not api.hostname
        or api.username
        or api.query
        or api.fragment
        or api.path not in ("", "/")
        or api.port not in (None, 443)
        or api_url.rstrip("/") != approved_api.rstrip("/")
        or approved.scheme != "https"
        or approved.hostname in {"api.lilosgrowth.com"}
    ):
        raise ValueError("Preview requires the exact approved staging API origin")
    if supabase_url.rstrip("/") != f"https://{project}.supabase.co":
        raise ValueError("Preview requires staging Supabase")
    if not protected or not expected_host or expected_host != deployment_host:
        raise ValueError("Protected deployment and exact expected hostname required")
    if any(value in expected_host for value in ("/", "*", ":", "@")):
        raise ValueError("Expected hostname must be exact")
