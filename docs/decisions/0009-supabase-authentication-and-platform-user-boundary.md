# ADR 0009: Supabase authentication and platform-user identity boundary

- Status: Accepted
- Date: 2026-08-02
- Decision owners: LILOs platform architecture
- Related roadmap phase: Phase 3

## Context

Supabase Auth authenticates human identity, while LILOs must retain a separate platform lifecycle
record without treating authentication as organization membership or authorization. The boundary
must validate provider tokens without storing credentials, fail closed during unverifiable key
states, and allow local deactivation to take effect on the next LILOs request.

## Decision

`user_profiles` maps one application UUID to one immutable, unique Supabase `auth.users.id` UUID.
It stores only optional non-authoritative email/display snapshots, `active|deactivated` status,
deactivation timestamp, UTC timestamps, and optimistic version. There is no separate users table,
Supabase foreign key, physical deletion, session table, token storage, organization scope, role, or
permission. Provisioning is explicit through a local/test-only bootstrap service and never occurs
on first login.

The API accepts only a bearer access token. A provider-neutral verifier validates configured ES256
or RS256 signatures against bounded HTTPS JWKS, exact issuer/audience, expiry and applicable time
claims, UUID subject/session, authenticated provider role, non-anonymous state, and `aal1|aal2`.
Unsupported algorithms, embedded key material, malformed claims, and algorithm/key mismatches fail
closed. JWKS is fresh for 900 seconds, usable during failure for at most 3600 seconds after its last
successful retrieval, and forcibly refreshed once for an unknown key ID. With no usable key,
authentication is unavailable rather than bypassed.

The authenticated principal contains only platform/auth user IDs, active status, provider session
ID, assurance level, and token issue/expiry times. It proves no organization access, membership,
application permission, entitlement, or approval authority. Both AAL values authenticate; later
authorization policy decides where AAL2 is mandatory.

Supabase owns login, email verification, refresh, MFA operations, and provider session sign-out.
LILOs stores no session identifier and calls no Management/Auth Admin API. Local deactivation
rejects the next LILOs request but does not claim immediate provider-wide token invalidation.

Provision, deactivate, and reactivate mutations append minimized immutable audit events in the
caller transaction. Authentication attempts produce redacted structured security logs, not audit
rows. Externally observable authentication failures collapse to a generic no-store 401; exhausted
JWKS/provider availability returns a generic no-store 503.

## Consequences

- Authentication and authorization remain independent roadmap capabilities.
- Email cannot substitute for the verified subject and duplicate email snapshots are valid.
- An unknown subject and a deactivated user are externally indistinguishable.
- Test verification uses injected fakes and local asymmetric keys without production fallback.
- Individual-session revocation, provider administrative synchronization, memberships,
  invitations, roles, permissions, and organization authorization remain later work.

## Validation and review

Validate both algorithms, all required claims, confusion/rejection cases, key rotation and bounded
outage behavior, redaction, generic errors, lifecycle concurrency, atomic audit, database
immutability, guarded routes, migration downgrade preservation, and all earlier regressions.
