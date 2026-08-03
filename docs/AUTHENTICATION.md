# Authentication and platform user identity

Supabase Auth owns human login, password reset, provider-side email verification, MFA enrollment
and challenge, access-token refresh, and provider sign-out. LILOs verifies Supabase access tokens
and maps their cryptographically verified UUID `sub` to exactly one local `user_profiles` record.
A mapped active user proves identity only; it grants no organization membership, permission,
entitlement, or approval authority.

## Platform user record

`user_profiles` contains `id`, immutable unique `auth_user_id`, optional normalized `email`, optional
`display_name`, `active|deactivated` status, `deactivated_at`, UTC timestamps, and optimistic
`version`. Email is a non-unique contact snapshot and is never an authentication lookup. Profiles
are explicitly provisioned; valid tokens do not auto-provision unknown subjects.

Deactivation and reactivation require the expected version and atomically record minimized audit
evidence. A deactivated user fails their next authenticated LILOs request even if their Supabase
token is otherwise valid. LILOs does not revoke that token at Supabase, store sessions, or guarantee
invalidation in unrelated systems.

## Token verification

Only `Authorization: Bearer <access-token>` is accepted, capped at 16,384 bytes. The verifier
accepts configured ES256 and RS256 keys and requires exact issuer, configured audience
(`authenticated` by default), expiration, UUID subject, UUID `session_id`, `authenticated` role,
`is_anonymous=false`, and `aal1|aal2`. `nbf` and `iat`, when present, receive at most 60 seconds of
clock skew. Missing AAL is rejected; it is not inferred. Custom organization, membership, role,
permission, or entitlement claims are ignored.

Configure these values locally in the ignored `.env` file:

```text
LILOS_SUPABASE_AUTH_ISSUER=
LILOS_SUPABASE_AUTH_AUDIENCE=
LILOS_SUPABASE_AUTH_JWKS_URL=
LILOS_SUPABASE_AUTH_ALLOWED_ALGORITHMS=
LILOS_SUPABASE_AUTH_JWKS_CACHE_SECONDS=
LILOS_SUPABASE_AUTH_JWKS_STALE_SECONDS=
LILOS_SUPABASE_AUTH_CLOCK_SKEW_SECONDS=
LILOS_SUPABASE_AUTH_MAX_TOKEN_BYTES=
```

Issuer and JWKS URL are explicit HTTPS values; no project reference or production key is inferred.
No service-role key is required.

## JWKS rotation and outages

JWKS responses are HTTPS-only, redirect-rejecting, size/key-count bounded, and cached for 900
seconds. An unknown `kid` triggers one forced refresh. During retrieval failure, a cached matching
key remains usable only through 3600 seconds after the last successful retrieval, while every token
claim is still validated. First-load failure or stale-cache expiry fails closed with
`AUTHENTICATION_UNAVAILABLE`; process startup and liveness remain available.

## HTTP and logging contracts

All ordinary failures—including unknown or deactivated users—return the same `401
AUTHENTICATION_REQUIRED`, `WWW-Authenticate: Bearer`, `Cache-Control: no-store`, and correlation
ID. Exhausted verifier availability returns generic retryable `503 AUTHENTICATION_UNAVAILABLE`.
Responses never echo tokens, subjects, or user existence.

Security logs contain stable result/reason codes, correlation ID, and only bounded operational
context. They exclude authorization headers, tokens, claims, email, provider payloads, signing
material, OTPs, MFA secrets, and recovery data. Operational log retention is not implemented here.

## Local and test use

When the existing internal-route guard is explicitly enabled in local/test, bootstrap routes can
create/read/deactivate/reactivate mappings and `/internal/auth/me` verifies a bearer token. These
temporary unauthenticated administration routes are not production-safe and cannot be enabled in
development, staging, or production. Tests use injected verifiers and local asymmetric fixtures;
production never falls back to either.

Authentication remains separate from ADR 0010 access records. A principal must map to an active
user before invitation acceptance, but gains no organization scope, membership, role, permission,
or entitlement. Stored profile email is used only for invitation matching; JWT email and
organization/role claims remain untrusted. Deactivation suppresses access without rewriting
memberships.

The authorization evaluator and always-mounted `/api/v1` routes consume only this verified
immutable principal. They compare the
principal's platform-user ID to the server-constructed policy request and preserves the verified
`aal1|aal2` value. JWT organization, role, permission, entitlement, and client-supplied assurance
claims remain ignored. An
authenticated principal without an effective active organization membership and applicable
permission receives generic authorization denial, not organization access.

User deactivation remains a guarded local/test administrative operation because no global
platform-administrator permission exists. Its service nevertheless locks current active-owner
relationships and rejects deactivation that would leave an active organization without an active
organization-scoped owner.
