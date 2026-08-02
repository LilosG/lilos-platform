"""Provider-neutral verifier contract and bounded Supabase JWKS implementation."""

import asyncio
import json
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID

import httpx
import jwt
from jwt import InvalidTokenError, PyJWK

from apps.api.app.authentication.contracts import VerifiedProviderClaims
from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authentication.errors import (
    TokenVerificationError,
    TokenVerificationUnavailableError,
)
from apps.api.app.config import Settings

MAX_JWKS_BYTES = 256_000
MAX_JWKS_KEYS = 32


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> VerifiedProviderClaims: ...


@dataclass(frozen=True, slots=True)
class CachedJwks:
    keys: Mapping[str, PyJWK]
    retrieved_at: float


class SupabaseJwksVerifier:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        monotonic: Any = time.monotonic,
    ) -> None:
        issuer, jwks_url = settings.require_authentication_urls()
        self.issuer = issuer
        self.audience = settings.supabase_auth_audience
        self.jwks_url = jwks_url
        self.allowed_algorithms = settings.authentication_algorithms()
        self.cache_seconds = settings.supabase_auth_jwks_cache_seconds
        self.stale_seconds = settings.supabase_auth_jwks_stale_seconds
        self.clock_skew = settings.supabase_auth_clock_skew_seconds
        self._client = client
        self._monotonic = monotonic
        self._cache: CachedJwks | None = None
        self._lock = asyncio.Lock()

    async def verify(self, token: str) -> VerifiedProviderClaims:
        header = self._safe_header(token)
        algorithm = header.get("alg")
        kid = header.get("kid")
        if (
            algorithm not in self.allowed_algorithms
            or not isinstance(kid, str)
            or not 1 <= len(kid) <= 128
        ):
            raise TokenVerificationError
        if any(name in header for name in ("jwk", "jku", "x5c", "x5u")):
            raise TokenVerificationError

        key = await self._select_key(kid, algorithm, force_refresh=False)
        if key is None:
            key = await self._select_key(kid, algorithm, force_refresh=True)
        if key is None:
            raise TokenVerificationError
        try:
            claims = jwt.decode(
                token,
                key=key.key,
                algorithms=[algorithm],
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.clock_skew,
                options={"require": ["exp", "sub", "role", "session_id", "aal", "is_anonymous"]},
            )
        except InvalidTokenError as exc:
            raise TokenVerificationError from exc
        return self._validated_claims(claims, algorithm=algorithm, kid=kid)

    def _safe_header(self, token: str) -> dict[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise TokenVerificationError from exc
        return header

    async def _select_key(self, kid: str, algorithm: str, *, force_refresh: bool) -> PyJWK | None:
        cache = self._cache
        age = self._monotonic() - cache.retrieved_at if cache is not None else float("inf")
        if not force_refresh and cache is not None and age <= self.cache_seconds:
            return self._compatible_key(cache.keys.get(kid), algorithm)
        try:
            cache = await self._refresh(force=force_refresh)
        except TokenVerificationUnavailableError:
            cache = self._cache
            if cache is None or self._monotonic() - cache.retrieved_at > self.stale_seconds:
                raise
        return self._compatible_key(cache.keys.get(kid), algorithm)

    async def _refresh(self, *, force: bool) -> CachedJwks:
        async with self._lock:
            current = self._cache
            if (
                not force
                and current is not None
                and self._monotonic() - current.retrieved_at <= self.cache_seconds
            ):
                return current
            try:
                client = self._client or httpx.AsyncClient(
                    timeout=httpx.Timeout(5.0), follow_redirects=False
                )
                owns_client = self._client is None
                try:
                    response = await client.get(
                        self.jwks_url, headers={"Accept": "application/json"}
                    )
                finally:
                    if owns_client:
                        await client.aclose()
                if response.is_redirect or str(response.url) != self.jwks_url:
                    raise ValueError("unexpected JWKS response URL")
                response.raise_for_status()
                if len(response.content) > MAX_JWKS_BYTES:
                    raise ValueError("JWKS response is too large")
                document = json.loads(response.content)
                keys = self._parse_jwks(document)
            except (httpx.HTTPError, ValueError, json.JSONDecodeError, TypeError) as exc:
                raise TokenVerificationUnavailableError from exc
            refreshed = CachedJwks(keys=keys, retrieved_at=self._monotonic())
            self._cache = refreshed
            return refreshed

    def _parse_jwks(self, document: Any) -> dict[str, PyJWK]:
        if not isinstance(document, dict) or not isinstance(document.get("keys"), list):
            raise ValueError("invalid JWKS")
        raw_keys = document["keys"]
        if not 1 <= len(raw_keys) <= MAX_JWKS_KEYS:
            raise ValueError("invalid JWKS key count")
        parsed: dict[str, PyJWK] = {}
        for value in raw_keys:
            if not isinstance(value, dict):
                raise ValueError("invalid JWK")
            kid = value.get("kid")
            if not isinstance(kid, str) or not 1 <= len(kid) <= 128 or kid in parsed:
                raise ValueError("invalid JWK kid")
            algorithm = value.get("alg")
            key_type = value.get("kty")
            if algorithm not in self.allowed_algorithms:
                continue
            if (algorithm == "ES256" and key_type != "EC") or (
                algorithm == "RS256" and key_type != "RSA"
            ):
                raise ValueError("JWK algorithm and key type mismatch")
            parsed[kid] = PyJWK.from_dict(value, algorithm=algorithm)
        if not parsed:
            raise ValueError("JWKS has no supported keys")
        return parsed

    @staticmethod
    def _compatible_key(key: PyJWK | None, algorithm: str) -> PyJWK | None:
        if key is None or key.algorithm_name != algorithm:
            return None
        if (algorithm == "ES256" and key.key_type != "EC") or (
            algorithm == "RS256" and key.key_type != "RSA"
        ):
            return None
        return key

    def _validated_claims(
        self, claims: dict[str, Any], *, algorithm: str, kid: str
    ) -> VerifiedProviderClaims:
        try:
            if claims["role"] != "authenticated" or claims["is_anonymous"] is not False:
                raise ValueError
            subject = UUID(claims["sub"])
            session_id = UUID(claims["session_id"])
            assurance = AssuranceLevel(claims["aal"])
            expires_at = datetime.fromtimestamp(claims["exp"], tz=UTC)
            issued_at = datetime.fromtimestamp(claims["iat"], tz=UTC) if "iat" in claims else None
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise TokenVerificationError from exc
        return VerifiedProviderClaims(
            auth_user_id=subject,
            session_id=session_id,
            assurance_level=assurance,
            issued_at=issued_at,
            expires_at=expires_at,
            algorithm=algorithm,
            key_id=kid,
        )
