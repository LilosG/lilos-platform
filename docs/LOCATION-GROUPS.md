# Organization-scoped location groups

## Purpose and boundaries

Location groups organize selected locations inside one organization. They support administrative
organization and a future reporting scope. They do not own locations, create another tenant or
authorization boundary, or influence configuration, profiles, entitlements, integrations,
workflows, business identity, billing, or AI behavior.

Nested groups, automatic membership, bulk reassignment, primary groups, membership ordering, and
frontend administration are not implemented.

The Phase 2 business-identity resolver does not query or return group membership. Any future
inclusion requires an explicit revision to ADR 0007 and the identity contract.

## Group schema and keys

`location_groups` contains exactly `id`, `organization_id`, `name`, `key`, `description`, `status`,
`created_at`, `updated_at`, `archived_at`, and `version`.

Name is trimmed and required at 1–120 characters. Description is nullable and trimmed at 1–1,000
characters; blank input normalizes to null. There is no metadata field.

Key input is trimmed and lowercased. A key must be 3–63 lowercase ASCII characters, begin with a
letter, contain only letters, numbers, and single hyphens, and have no consecutive or trailing
hyphen. Punctuation is not replaced. `admin`, `api`, `internal`, `platform`, `public`, `system`,
`support`, and `www` are reserved. Keys are unique within one organization, may repeat in another
organization, cannot change, and remain reserved after archival. PostgreSQL enforces the key shape
and an immutable-key trigger rejects later changes.

## Membership schema and cardinality

`location_group_memberships` contains exactly `id`, `organization_id`, `location_group_id`,
`location_id`, and `created_at`.

A location may belong to zero, one, or many groups; a group may contain zero or more locations.
The scoped group/location combination is unique. Duplicate add returns a conflict. Removal is
explicit; missing removal returns not found. Membership has no state, order, priority, primary
flag, metadata, or update operation.

Direct and composite restrictive foreign keys prove that the membership, group, and location
share one organization. Repository access always includes organization scope. Cross-organization
identifiers are indistinguishable from missing records.

## Lifecycle and parent policy

Groups are `active` or `archived`. The only transition is active to archived. Archived is terminal,
readable, immutable, and rejects new membership. Archival retains all memberships, fills
`archived_at`, requires `expected_version`, and increments version once. Active name/description
replacement follows the same compare-and-swap convention. No group delete or unarchive exists.

Parent permissions follow [ADR 0007](decisions/0007-location-group-domain-policies.md). Prospect,
onboarding, and active organizations allow every operation. Paused organizations allow group
create/update/archive and membership removal but not membership add. Suspended and archived
organizations are read-only. Offboarding organizations allow only membership removal and group
archive. Reads remain allowed in every parent state.

New membership accepts setup-required, active, paused, or temporarily closed locations. It rejects
permanently closed or archived locations. Existing membership persists when a location later
pauses, closes, or archives. Removal remains explicit and does not require an operational location.

## Transactions, audit, and routes

Services lock and validate the current organization, group, and location rows as applicable.
Group creation, replacement, archive, membership add, membership removal, and their audit records
share one caller-owned `AsyncSession`; no domain service commits. Owning transaction failure rolls
back both mutation and evidence.

Audit metadata contains only organization, group, and optional location identifiers, operation,
group version where applicable, and changed field names. It excludes profile/configuration content,
contacts, customer data, credentials, and secrets.

Temporary routes are under `/internal/organizations/{organization_id}/location-groups`. They are
unregistered by default, may be enabled only in local/test, and are rejected in development,
staging, and production. They are unauthenticated bootstrap surfaces and are not production-safe.
Always-mounted application routes require `locations.read` for reads and
`locations.groups.manage` for mutations. Reporting execution and RLS remain future work.

Location groups have no authorization effect in the initial access model. No group-scoped
assignment or deny exists, and membership changes alter no permission. Group authorization scope is
explicitly deferred.
