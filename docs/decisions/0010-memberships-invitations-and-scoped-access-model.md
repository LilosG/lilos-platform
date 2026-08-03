# ADR 0010: Memberships, invitations, and scoped access model

- Status: Accepted
- Date: 2026-08-02
- Packet: PHASE-03-TASK-02

## Context

Authentication proves only a Supabase-authenticated human mapped to an active `user_profiles`
record. It does not prove organization membership or permission. Phase 3 therefore needs a durable,
organization-scoped access domain before request authorization can be enforced.

## Decision

An organization/user pair has one permanently reserved `organization_memberships` row. Membership
types are `internal`, `client`, `partner`, and `support`; they classify but never grant access.
States are `invited`, `active`, `suspended`, `revoked`, and `expired`. Only invited membership may
activate/expire; active may suspend; suspended may restore; invited, active, or suspended may
revoke. Revoked and expired are terminal. Every transition is compare-and-swap versioned and
audited.

Invitation creation creates its membership in `invited`. Acceptance by an authenticated active
platform user atomically accepts the invitation and activates that same membership. Cancellation
revokes it; expiry expires it. Invitations store normalized email and only a globally unique SHA-256
digest of a 32-byte random URL-safe token. The guarded creation response returns plaintext once
with no-store/no-cache; logs and audit metadata never contain plaintext, digest, or full email.
Acceptance requires the stored user-profile email snapshot to match and uses generic failures.
Default lifetime is seven days and maximum lifetime is thirty days. Delivery and resend are deferred.

The immutable global role catalog is `organization_owner`, `organization_admin`,
`organization_manager`, `organization_member`, and `organization_viewer`. The immutable permission
catalog and mappings are exactly those in `docs/AUTHORIZATION-MODEL.md`. Although most keys are
`resource.action`, the approved catalog includes segmented resources such as
`organization.members.manage`; validation therefore permits two or more lowercase identifier
segments separated by dots while API creation remains prohibited. Explicit idempotent seeding uses
deterministic UUIDs, rejects mismatches, is atomic, and creates global audit events only when records
are created.

A membership may hold multiple global roles at organization or individual-location scope.
Organization scope covers current and future locations; location scope covers only that same-
organization location. Allows are additive. There are no global, all-locations, location-group, or
nested scopes. Direct permission allows are prohibited.

Membership-specific permission denies use the same organization/location scopes. Any applicable
deny overrides every applicable allow; no narrower allow, broader allow, role, or administrator
bypasses it. Assignment and deny rows may be physically removed, with immutable audit events
preserving evidence. Effective enforcement is deferred to PHASE-03-TASK-03.

Only an active organization can yield effective runtime access, and an active user plus active
membership are also required. Organization lifecycle controls administration exactly as follows:

| Organization | Create/invite | Suspend | Restore | Revoke | Assign role | Remove role | Add deny | Remove deny | Runtime |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| prospect | yes | yes | yes | yes | yes | yes | yes | yes | no |
| onboarding | yes | yes | yes | yes | yes | yes | yes | yes | no |
| active | yes | yes | yes | yes | yes | yes | yes | yes | yes |
| paused | no | yes | no | yes | no | yes | yes | yes | no |
| suspended | no | yes | no | yes | no | yes | yes | no | no |
| offboarding | no | yes | no | yes | no | yes | yes | no | no |
| archived | no | no | no | no | no | no | no | no | no |

Organization and user states suppress access without rewriting memberships or assignments. User
reactivation cannot restore a suspended, revoked, or expired membership. JWT organization or role
claims remain untrusted.

The fixed catalog seed creates no membership or owner. A separate guarded local/test first-owner
operation may atomically create an active membership for an existing active user and assign owner
at organization scope. It is unregistered by default and rejected in development, staging, and
production. Production invitation delivery and first-owner provisioning remain deferred.

## Consequences

Database composite foreign keys prevent cross-organization membership/location scope. Repositories
and routes remain organization-scoped and return ordinary not-found results across ownership
boundaries. Mutation and audit append share a caller-owned transaction and neither service commits.
No RLS or broad route authorization is introduced, so these records describe access but do not yet
protect existing Phase 2 routes.
