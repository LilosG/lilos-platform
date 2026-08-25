"""Canonical Hermes private-runtime endpoint normalization."""

from urllib.parse import urlsplit


def normalize_hermes_base_url(base_url: str) -> str:
    """Return a validated HTTP(S) Hermes origin, accepting Render-style bare hostport values."""
    normalized = base_url.strip().rstrip("/")
    if not normalized:
        raise ValueError("Hermes base URL is required")

    lowered = normalized.lower()
    if not lowered.startswith(("http://", "https://")):
        if "://" in normalized:
            raise ValueError("Hermes base URL must use HTTP or HTTPS")
        normalized = f"http://{normalized}"

    parsed = urlsplit(normalized)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Hermes base URL must be an HTTP(S) origin")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Hermes base URL must not contain credentials")
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ValueError("Hermes base URL must not contain a path, query, or fragment")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("Hermes base URL contains an invalid port") from exc

    return normalized.rstrip("/")
