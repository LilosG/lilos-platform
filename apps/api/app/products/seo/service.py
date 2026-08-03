"""Deterministic URL, crawl-safety, score, and missing-data policies."""

import ipaddress
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit, urlunsplit


@dataclass(frozen=True, slots=True)
class NormalizedURL:
    value: str
    reasons: tuple[str, ...]


def normalize_url(value: str) -> NormalizedURL:
    parsed = urlsplit(value.strip())
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise ValueError("unsupported URL")
    scheme = parsed.scheme.lower()
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    port = parsed.port
    netloc = (
        host
        if port is None or (scheme, port) in {("http", 80), ("https", 443)}
        else f"{host}:{port}"
    )
    path = quote(unquote(parsed.path or "/"), safe="/%:@-._~!$&'()*+,;=")
    reasons = ["fragment_removed"] if parsed.fragment else []
    if parsed.hostname != host:
        reasons.append("host_normalized")
    if netloc != parsed.netloc:
        reasons.append("default_port_or_authority_normalized")
    return NormalizedURL(urlunsplit((scheme, netloc, path, parsed.query, "")), tuple(reasons))


def validate_crawl_target(value: str, allowed_hosts: frozenset[str]) -> NormalizedURL:
    normalized = normalize_url(value)
    host = urlsplit(normalized.value).hostname
    if host not in allowed_hosts:
        raise ValueError("crawl host is outside the confirmed website scope")
    try:
        address = ipaddress.ip_address(host or "")
    except ValueError:
        return normalized
    if not address.is_global:
        raise ValueError("private and special network targets are prohibited")
    return normalized


def opportunity_score(
    *,
    search_potential: int,
    business_value: int,
    relevance: int,
    confidence: int,
    urgency: int,
    effort: int,
) -> tuple[int, dict[str, int]]:
    inputs = {
        "search_potential": search_potential,
        "business_value": business_value,
        "relevance": relevance,
        "confidence": confidence,
        "urgency": urgency,
        "effort": effort,
    }
    if any(value < 0 or value > 100 for value in inputs.values()):
        raise ValueError("score inputs must be between 0 and 100")
    score = round(
        (
            search_potential * 2
            + business_value * 3
            + relevance * 2
            + confidence * 2
            + urgency
            - effort
        )
        / 9
    )
    return max(0, min(100, score)), inputs


def metric_value(value: int | float | None, quality: str) -> dict[str, object]:
    return {"value": value, "state": "missing" if value is None else quality}
