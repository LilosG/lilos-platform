# Authorization domain model

This packet stores authorization inputs but does not enforce them across application routes.
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

Only the five guarded authorization-test routes use the evaluator in this packet. Existing Phase 2
and access-administration routes are not broadly converted yet. No current JWT claim, membership
type, internal route, or catalog record is an enforcement bypass. Custom roles, custom permissions,
group scope, all-locations scope, RLS, product entitlements, and broad route enforcement remain
deferred.
