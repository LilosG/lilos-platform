"""Cryptographic verification, key rotation, and fail-closed cache tests."""

import asyncio
import base64
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from apps.api.app.authentication.enums import AssuranceLevel
from apps.api.app.authentication.errors import (
    TokenVerificationError,
    TokenVerificationUnavailableError,
)
from apps.api.app.authentication.verifier import SupabaseJwksVerifier
from apps.api.app.config import EnvironmentName, Settings

ISSUER = "https://fabricated-test.supabase.co/auth/v1"
JWKS_URL = "https://fabricated-test.supabase.co/auth/v1/.well-known/jwks.json"
AUTH_USER_ID = UUID("10000000-0000-4000-8000-000000000001")
SESSION_ID = UUID("20000000-0000-4000-8000-000000000001")


def encoded(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def keys() -> tuple[Any, Any, dict[str, Any], dict[str, Any]]:
    # A fixed scalar makes the EC fixture deterministic without embedding deployable key material.
    ec_private = ec.derive_private_key(8675309, ec.SECP256R1())
    ec_public = ec_private.public_key().public_numbers()
    ec_jwk = {
        "kty": "EC",
        "crv": "P-256",
        "x": encoded(ec_public.x),
        "y": encoded(ec_public.y),
        "use": "sig",
        "alg": "ES256",
        "kid": "test-ec-key",
    }
    rsa_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    rsa_public = rsa_private.public_key().public_numbers()
    rsa_jwk = {
        "kty": "RSA",
        "n": encoded(rsa_public.n),
        "e": encoded(rsa_public.e),
        "use": "sig",
        "alg": "RS256",
        "kid": "test-rsa-key",
    }
    return ec_private, rsa_private, ec_jwk, rsa_jwk


def settings(**overrides: Any) -> Settings:
    values = {
        "environment": EnvironmentName.TEST,
        "supabase_auth_issuer": ISSUER,
        "supabase_auth_jwks_url": JWKS_URL,
    }
    values.update(overrides)
    return Settings.model_validate(values)


def claims(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(UTC)
    values: dict[str, Any] = {
        "iss": ISSUER,
        "aud": "authenticated",
        "sub": str(AUTH_USER_ID),
        "session_id": str(SESSION_ID),
        "role": "authenticated",
        "aal": "aal1",
        "is_anonymous": False,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
    }
    values.update(overrides)
    return values


def token(private_key: Any, algorithm: str, kid: str, **overrides: Any) -> str:
    return jwt.encode(claims(**overrides), private_key, algorithm=algorithm, headers={"kid": kid})


def verifier_with(document: dict[str, Any]) -> SupabaseJwksVerifier:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=document, request=request)

    return SupabaseJwksVerifier(
        settings(), client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )


@pytest.mark.parametrize(
    "algorithm,index,kid", [("ES256", 0, "test-ec-key"), ("RS256", 1, "test-rsa-key")]
)
def test_valid_asymmetric_tokens(algorithm: str, index: int, kid: str) -> None:
    ec_key, rsa_key, ec_jwk, rsa_jwk = keys()
    verified = asyncio.run(
        verifier_with({"keys": [ec_jwk, rsa_jwk]}).verify(
            token((ec_key, rsa_key)[index], algorithm, kid, aal="aal2")
        )
    )
    assert verified.auth_user_id == AUTH_USER_ID
    assert verified.session_id == SESSION_ID
    assert verified.assurance_level is AssuranceLevel.AAL2


@pytest.mark.parametrize(
    ("override", "value"),
    [
        ("iss", "https://wrong.invalid/auth/v1"),
        ("aud", "anon"),
        ("exp", 1),
        ("nbf", int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())),
        ("iat", int((datetime.now(UTC) + timedelta(minutes=5)).timestamp())),
        ("sub", "not-a-uuid"),
        ("session_id", "not-a-uuid"),
        ("role", "anon"),
        ("role", "service_role"),
        ("aal", "aal3"),
        ("is_anonymous", True),
    ],
)
def test_invalid_claims_fail_closed(override: str, value: Any) -> None:
    ec_key, _, ec_jwk, _ = keys()
    with pytest.raises(TokenVerificationError):
        asyncio.run(
            verifier_with({"keys": [ec_jwk]}).verify(
                token(ec_key, "ES256", "test-ec-key", **{override: value})
            )
        )


@pytest.mark.parametrize("missing", ["sub", "session_id", "role", "aal", "is_anonymous"])
def test_required_claims_are_enforced(missing: str) -> None:
    ec_key, _, ec_jwk, _ = keys()
    payload = claims()
    del payload[missing]
    encoded_token = jwt.encode(payload, ec_key, algorithm="ES256", headers={"kid": "test-ec-key"})
    with pytest.raises(TokenVerificationError):
        asyncio.run(verifier_with({"keys": [ec_jwk]}).verify(encoded_token))


def test_invalid_signature_unknown_kid_and_embedded_jwk_fail() -> None:
    ec_key, _, ec_jwk, _ = keys()
    other_key = ec.derive_private_key(42, ec.SECP256R1())
    cases = [
        token(other_key, "ES256", "test-ec-key"),
        token(ec_key, "ES256", "unknown-key"),
        jwt.encode(
            claims(),
            ec_key,
            algorithm="ES256",
            headers={"kid": "test-ec-key", "jku": "https://attacker.invalid/jwks"},
        ),
    ]
    for candidate in cases:
        with pytest.raises(TokenVerificationError):
            asyncio.run(verifier_with({"keys": [ec_jwk]}).verify(candidate))


def test_hs256_and_none_are_rejected_before_key_selection() -> None:
    hs_token = jwt.encode(
        claims(), "fabricated-test-key-material-only-32", algorithm="HS256", headers={"kid": "x"}
    )
    none_token = jwt.encode(claims(), key="", algorithm="none", headers={"kid": "x"})
    verifier = verifier_with({"keys": []})
    for candidate in (hs_token, none_token):
        with pytest.raises(TokenVerificationError):
            asyncio.run(verifier.verify(candidate))


def test_unknown_kid_forces_one_refresh_and_rotated_key_succeeds() -> None:
    first_key, _, first_jwk, _ = keys()
    rotated_key = ec.derive_private_key(10101, ec.SECP256R1())
    public = rotated_key.public_key().public_numbers()
    rotated_jwk = {**first_jwk, "kid": "rotated", "x": encoded(public.x), "y": encoded(public.y)}
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        document = {"keys": [first_jwk]} if calls == 1 else {"keys": [first_jwk, rotated_jwk]}
        return httpx.Response(200, json=document, request=request)

    verifier = SupabaseJwksVerifier(
        settings(), client=httpx.AsyncClient(transport=httpx.MockTransport(handler))
    )
    asyncio.run(verifier.verify(token(first_key, "ES256", "test-ec-key")))
    asyncio.run(verifier.verify(token(rotated_key, "ES256", "rotated")))
    assert calls == 2


def test_cached_key_survives_bounded_outage_then_fails_closed() -> None:
    ec_key, _, ec_jwk, _ = keys()
    now = [0.0]
    fail = [False]

    async def handler(request: httpx.Request) -> httpx.Response:
        if fail[0]:
            raise httpx.ConnectError("fabricated outage", request=request)
        return httpx.Response(200, json={"keys": [ec_jwk]}, request=request)

    verifier = SupabaseJwksVerifier(
        settings(supabase_auth_jwks_cache_seconds=60, supabase_auth_jwks_stale_seconds=120),
        client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        monotonic=lambda: now[0],
    )
    candidate = token(ec_key, "ES256", "test-ec-key")
    asyncio.run(verifier.verify(candidate))
    fail[0] = True
    now[0] = 61
    assert asyncio.run(verifier.verify(candidate)).auth_user_id == AUTH_USER_ID
    now[0] = 121
    with pytest.raises(TokenVerificationUnavailableError):
        asyncio.run(verifier.verify(candidate))


def test_malformed_jwks_and_first_load_outage_are_unavailable() -> None:
    ec_key, _, _, _ = keys()
    for document in ({"keys": "invalid"}, {"keys": [{"kty": "oct", "kid": "bad", "alg": "ES256"}]}):
        with pytest.raises(TokenVerificationUnavailableError):
            asyncio.run(verifier_with(document).verify(token(ec_key, "ES256", "test-ec-key")))

    async def outage(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("fabricated timeout", request=request)

    unavailable = SupabaseJwksVerifier(
        settings(), client=httpx.AsyncClient(transport=httpx.MockTransport(outage))
    )
    with pytest.raises(TokenVerificationUnavailableError):
        asyncio.run(unavailable.verify(token(ec_key, "ES256", "test-ec-key")))


def test_untrusted_organization_and_application_role_claims_are_ignored() -> None:
    ec_key, _, ec_jwk, _ = keys()
    verified = asyncio.run(
        verifier_with({"keys": [ec_jwk]}).verify(
            token(
                ec_key,
                "ES256",
                "test-ec-key",
                organization_id="attacker-controlled",
                application_role="platform_owner",
            )
        )
    )
    assert set(verified.model_dump()) == {
        "auth_user_id",
        "session_id",
        "assurance_level",
        "issued_at",
        "expires_at",
        "algorithm",
        "key_id",
    }
