# Organization tenant foundation

## Ownership boundary

`organizations` is the highest-level technical tenant boundary. There is no separate `tenants`
table or tenant entity. In platform code and architecture, “tenant-aware” means explicitly
organization-scoped. Future location-owned records must also retain direct `organization_id`
ownership rather than relying only on an indirect location relationship.

This packet does not create industries, locations, organization profiles, users, memberships,
products, workflows, integrations, or billing data. `industry_id` will be added only when the
industries table and its ownership contract are implemented.

## Schema and classifications

The organization record contains:

- application-generated UUIDv4 `id`;
- immutable unique `slug`, bounded `name`, `organization_type`, and `status`;
- IANA `timezone` and uppercase three-letter `default_currency`;
- bounded optional legal, website, contact, billing, external-reference, and onboarding fields;
- nullable `archived_at`;
- timezone-aware UTC `created_at` and `updated_at`; and
- integer optimistic-concurrency `version`, beginning at 1.

Organization types are `client`, `internal`, `partner`, `demo`, and `test`. Lifecycle statuses are
`prospect`, `onboarding`, `active`, `paused`, `suspended`, `offboarding`, and `archived`. PostgreSQL
named CHECK constraints enforce both sets and the essential slug, currency, version, and archival
timestamp invariants.

`onboarding_status` is separate from the primary lifecycle `status`. It is an optional
informational label: when supplied through the typed creation contract, surrounding whitespace is
trimmed and the value must contain 1–64 characters. It has no enumerated values, state machine, or
automatic transition behavior in this packet. A later onboarding packet may replace or constrain
this informational field through an explicit migration and contract revision.

## Slug contract

Creation strips surrounding whitespace and lowercases uppercase input before validation. It does
not generate a slug from a name or replace punctuation. A valid slug:

- has 3–63 lowercase ASCII characters;
- begins with a letter;
- contains only letters, numbers, and single hyphens;
- has no consecutive or trailing hyphen; and
- is not `admin`, `api`, `internal`, `platform`, `public`, `system`, `support`, or `www`.

PostgreSQL reinforces normalized form, shape, length, reserved values, and uniqueness. A database
trigger rejects any later slug change. Archived slugs remain stored and therefore cannot be reused.

## Lifecycle and concurrency

The permitted transitions are:

| Action | From | To |
| --- | --- | --- |
| Start onboarding | `prospect` | `onboarding` |
| Activate | `onboarding`, `suspended` | `active` |
| Pause | `active` | `paused` |
| Resume | `paused` | `active` |
| Suspend | `active`, `paused` | `suspended` |
| Start offboarding | any non-archived operational state | `offboarding` |
| Archive | `offboarding` | `archived` |

Archived organizations have no normal outbound transition. Every action requires the version last
read by the caller. The repository uses one compare-and-swap update matching ID, current status,
and version; success increments the version. Stale requests and invalid transitions return distinct
conflict errors. `updated_at` changes on each transition, while `archived_at` is populated only when
the record becomes archived.

The repository exposes no physical delete, general update, or slug-update method. Every normal
creation produces an audit row, whose restrictive foreign key also prevents deleting that
organization while its audit evidence exists. Production database roles that explicitly revoke
organization deletion and schema/trigger management remain deployment work.

## Transactional audit

Creation and lifecycle service methods use the caller-owned SQLAlchemy `AsyncSession`. They flush
organization changes and append audit evidence but never commit. A failed owning transaction rolls
back both the organization operation and its audit event.

Audit records include organization/resource IDs, lifecycle state and version, and request
correlation ID. They do not copy contact fields, credentials, or unrestricted personal data. The
nullable `audit_events.organization_id` now has an `ON DELETE RESTRICT` foreign key to
`organizations.id`.

## Temporary internal administration routes

The routes under `/internal/organizations` are temporary bootstrap administration surfaces. They
are not authenticated, authorized, rate-limited administration APIs and are not production-safe.

They are absent by default. `LILOS_INTERNAL_ADMIN_ROUTES_ENABLED=true` registers them only when
`LILOS_ENV` is `local` or `test`. Enabling them in `development`, `staging`, or `production` fails
settings validation before application startup. The flag is not a bypass token and must not be
treated as a future authentication or authorization mechanism.

Collection reads use bounded offset pagination for this small administrative list, ordered by
`created_at ASC, id ASC` with a maximum limit of 100.

## Deferred isolation enforcement

Current organization-only tests prove record-specific lookup and deterministic separation among
fabricated organizations. Authentication, membership, permissions, organization-bound request
context, cross-organization authorization, and PostgreSQL Row Level Security belong to later Phase
2 and Phase 3 packets. Until those controls exist, these routes must remain disabled outside local
and test use.
