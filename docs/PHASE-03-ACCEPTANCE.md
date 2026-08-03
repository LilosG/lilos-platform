# Phase 3 acceptance

## Objective and completed packets

Phase 3 establishes secure platform identity and organization-scoped access while keeping
authentication, membership, authorization, domain lifecycle, and product entitlement separate.

- `PHASE-03-TASK-01` — authentication and user identity (`884a3ab`)
- `PHASE-03-TASK-02` — memberships, invitations, roles, permissions, scopes, denies (`9495bb8`)
- `PHASE-03-TASK-03` — deterministic authorization evaluator (`61b799f`)
- `PHASE-03-TASK-04` — route enforcement and closure (this commit)

## Completed capabilities

- Supabase-compatible ES256/RS256 bearer verification maps an immutable provider subject to one
  active `user_profiles` record without granting organization access.
- Permanent organization memberships, secure hash-only invitations, immutable global role and
  permission catalogs, organization/location assignments, and membership-specific denies are
  organization-isolated and audited.
- The evaluator requires an active user, active organization, active membership, applicable allow,
  absence of any applicable deny, correct scope, and sufficient server-fixed AAL.
- Always-mounted `/api/v1` organization, location, profile, group, business-identity, and approved
  access-administration routes enforce fixed authentication and authorization policies.
- Location-group membership is never authorization scope. Domain services retain all lifecycle and
  optimistic-concurrency authority after authorization succeeds.
- An active organization cannot lose its final active organization-scoped owner through assignment
  removal, membership suspension/revocation, or user deactivation. Locked caller-owned
  transactions serialize concurrent attempts.
- Authorization evaluations are read-only, unpersisted security-log events. Domain mutations and
  immutable audit appends remain atomic.

## Security and isolation checklist

- [x] Authentication alone grants no organization access.
- [x] JWT organization, role, permission, and AAL-policy claims are not authorization inputs.
- [x] Membership type grants no permission.
- [x] Multiple role allows are additive and scope-bounded.
- [x] Every applicable deny overrides owner, administrator, and all other allows.
- [x] AAL2 is fixed for privilege-changing access operations; clients cannot lower it.
- [x] Cross-organization child identifiers use ordinary not-found behavior.
- [x] No hidden superuser, owner bypass, deny bypass, direct allow, or global scope exists.
- [x] No authorization decision, token, session, or invitation plaintext is persisted.
- [x] Local/test bootstrap routes are unregistered by default and impossible to enable in unsafe
  environments.
- [x] Proof-only authorization routes are removed after real route coverage.
- [x] PostgreSQL head remains `20260802_0007`; no Phase 3 closure migration is required.
- [x] Audit append-only and immutable subject/key/type triggers remain intact.

## Migrations and tests

The Phase 3 migration sequence is `20260802_0006` (`user_profiles`) followed by `20260802_0007`
(access domain). Route enforcement and active-owner continuity require no schema change. Final
acceptance validates base-to-head upgrade, Alembic drift, all constraints/triggers, downgrade to
base, and re-upgrade. The complete PostgreSQL-backed suite passes 312 tests; focused Phase 3
identity/access suites pass 56 tests and focused Phase 2/domain regressions pass 193. Suites cover
authentication bypass, organization/user/membership
state, scoped privilege escalation, deny precedence, MFA, invitation secrecy and replay,
cross-tenant isolation, owner continuity including concurrency, domain-policy separation, route
guarding, audit atomicity, and all Phase 1/2 regressions.

## Bootstrap limitations and deferred work

Production invitation email delivery and first-owner provisioning remain deferred. Global platform
user lifecycle operations remain local/test-only because the catalog intentionally has no hidden
platform-superadministrator permission. Also deferred: PostgreSQL RLS, custom roles/permissions,
location-group authorization scope, direct permission allows, provider-side session revocation,
frontend authentication/administration, product entitlements, Phase 4 configuration inheritance,
workflows, integrations, AI, and production deployment.

## Known warning and status

The locked Starlette test client emits its existing upstream `httpx` deprecation warning. It is not
suppressed or modified. With local, PostgreSQL, migration, and hosted CI validation passing, Phase
3 is complete. Do not begin Phase 4 without a separately authorized packet.
