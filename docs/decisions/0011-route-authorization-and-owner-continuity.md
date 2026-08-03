# ADR 0011: Route authorization and active-owner continuity

- Status: Accepted
- Date: 2026-08-03
- Packet: PHASE-03-TASK-04

## Context

Phase 3 already separates verified identity, organization membership, fixed role permissions,
organization/location scope, and membership-specific denies. Application routes still need fixed
server policies, and privilege administration must not accidentally leave an active organization
without an accountable active owner.

## Decision

Always-mounted routes live below `/api/v1`. Every route authenticates first, derives the platform
user only from the verified principal, and uses a fixed permission, scope, and minimum AAL. Reads
and ordinary domain writes require AAL1. Membership suspension/restoration/revocation, role and
deny mutation, and invitation cancellation or local/test issuance require AAL2. Permission checks
do not replace domain lifecycle validation. Wrong-owner child identifiers retain the established
not-found behavior.

An active organization must retain at least one active owner after it has one. An active owner is
an active `user_profiles` record with an active membership and an `organization_owner` assignment
at organization scope. Location-scoped assignments, inactive users, and invited, suspended,
revoked, or expired memberships do not count. Removal of an owner assignment, suspension or
revocation of an owner membership, and deactivation of an owner user are rejected with
`LAST_ACTIVE_OWNER_CONFLICT` if they would remove the final active owner.

The owning organization row and all qualifying owner membership, assignment, and user rows are
locked in the caller-owned transaction before the protected mutation. Organization locking
serializes concurrent owner-removal attempts, so two removals cannot both observe the other owner
as remaining. The rule applies only while the organization is active; prospect/onboarding
bootstrap may be ownerless, and no owner is silently created.

The proof-only authorization routes are removed. Deterministic catalog seeds and guarded local/test
bootstrap routes remain disabled by default and cannot be enabled in development, staging, or
production. Production invitation delivery, production first-owner provisioning, and global
platform-user lifecycle administration remain deferred because the current permission catalog has
no safe platform-superadministrator authority.

## Consequences

- Authentication remains insufficient for organization access.
- Owners have no evaluation bypass and explicit denies still override owner permissions.
- User lifecycle administration remains local/test-only, but its service still enforces owner
  continuity.
- No migration, decision persistence, cache, custom role, custom permission, group scope, direct
  allow, entitlement, or RLS policy is added.
