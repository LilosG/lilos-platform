# Authorization domain model

The access domain supplies authorization inputs to the enforced `/api/v1` route surface.
Authentication alone still grants no organization access.

## Fixed catalogs

System roles are owner, admin, manager, member, and viewer using keys prefixed
`organization_`. The permission catalog is:

- `organization.read`, `organization.update`, `organization.members.manage`,
  `organization.invitations.manage`, `organization.roles.manage`,
  `organization.settings.manage`
- `locations.read`, `locations.create`, `locations.update`, `locations.lifecycle.manage`,
  `locations.groups.manage`
- `profiles.read`, `profiles.update`, `business_identity.read`, `audit.read`

Owner has all permissions. Admin has all except role management. Manager has organization read,
member/invitation administration, all initial location permissions, profile read/update, business
identity read, and audit read. Member and viewer both have organization/location/profile/business-
identity read. Their distinct stable taxonomy is reserved for later expansion.

Run `npm run db:seed:access` after migrations. Seeding uses deterministic UUIDs, creates exact
catalog records/mappings and global audit events atomically, is idempotent, and rejects any mismatch
without silently rewriting data. There are no catalog mutation routes.

## Assignments and denies

Memberships may have multiple role assignments at organization or location scope. Composite
foreign keys prove membership and location ownership in SQL. Organization allows cover all current
and future organization locations; location allows cover exactly one location. Allows are additive.
Location groups have no authorization effect.

There are no direct allow grants. Membership-specific organization/location denies override every
applicable allow, with no role or administrator bypass. Deny and assignment removals delete only the
association row and append immutable audit evidence. Closed/archived resources remain readable
where their domain policy permits, while permissions never bypass lifecycle restrictions.

PHASE-03-TASK-03 adds the read-only evaluator described in
`docs/AUTHORIZATION-ENFORCEMENT.md`. It requires an active authenticated principal, active
organization, active scoped membership, applicable catalog allow, absence of an applicable deny,
and the server-fixed AAL. It persists no decisions and emits minimized security logs rather than
business audit events.

The Phase 2 and approved access-administration operations listed in the Phase 3 route matrix use the
evaluator. Proof-only routes are removed. No JWT claim, membership type, internal route, or catalog
record is an enforcement bypass. Custom roles, custom permissions, group scope, all-locations
scope, RLS, and product entitlements remain deferred.

An active organization must retain one active organization-scoped owner after ownership is
established. The service locks the organization and qualifying owner rows before owner assignment
removal, owner membership suspension/revocation, or owner user deactivation. This continuity
invariant creates no owner permission or deny bypass.
