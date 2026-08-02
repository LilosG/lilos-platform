# Industry classification foundation

## Scope

`industries` is the global registry of reusable platform classification defaults. Each
organization may reference one primary industry. Multi-industry organizations, location
overrides, configuration schema registration, inheritance, and product-specific templates are
deferred. Industry policy documents must never contain client-specific configuration.

## Schema and keys

An industry stores UUIDv4 `id`, immutable `key`, bounded `name` and `description`, `status`, three
JSONB default-policy objects, UTC `created_at`, `updated_at`, nullable `archived_at`, and optimistic
`version`. Keys are globally unique and remain reserved while an archived record exists.

Creation trims surrounding whitespace and lowercases ASCII input. A key is 3–63 characters,
begins with a lowercase letter, contains only lowercase letters, numbers, and single underscores,
and has no consecutive or trailing underscore. Punctuation is rejected rather than replaced, and
keys are never generated from names. PostgreSQL enforces the normalized shape and a trigger rejects
later key changes.

## Lifecycle and concurrency

Statuses are `active`, `deprecated`, and `archived`. The only transitions are:

| From | To |
| --- | --- |
| `active` | `deprecated` |
| `deprecated` | `active` |
| `deprecated` | `archived` |

Active records cannot be archived directly and archived records are terminal. Every transition
requires `expected_version`; the repository performs one compare-and-swap update and increments
the version exactly once. It exposes no delete or key-update operation.

## Controlled policy documents

`default_configuration`, `default_risk_policy`, and `default_content_policy` are controlled
default-policy documents, not final configuration schemas. Each must be a JSON object; `{}` is
valid. Application validation defensively rebuilds every nested container and enforces, per
document:

- at most 16,384 compact serialized UTF-8 bytes;
- at most five nested levels, 50 entries per object or array, and 200 total values;
- keys of 1–64 bounded ASCII identifier characters;
- strings of at most 1,024 characters and finite numbers; and
- rejection of known secret-bearing keys at every depth, including passwords, credentials,
  authorization values, cookies, private keys, API keys, and access or refresh tokens.

PostgreSQL additionally requires JSON objects and bounds their stored serialized size. No route
provides unrestricted policy mutation. Schema registration, validation by registered product
schema, inheritance, merging, and explainability belong to Roadmap Phase 4.

## Organization compatibility and assignment

Migration `20260802_0003` adds nullable `organizations.industry_id` with `ON DELETE RESTRICT` and
does not backfill it. Organizations created before this migration may retain `NULL` until an
explicit assignment. This temporary compatibility rule avoids invalidating existing records;
onboarding-readiness reporting is deferred.

New `client`, `partner`, and `demo` organizations require an active industry. New `internal` and
`test` organizations may omit it. Existing assignments remain readable if an industry is later
deprecated. New creation and the narrow `set_industry` operation reject deprecated or archived
industries. Assignment requires `expected_version`, performs an atomic compare-and-swap, and
increments the organization version once. There is no general organization update or bulk
reassignment operation.

## Explicit initial seed

After migrating, run the controlled seed command with an application database URL configured:

```sh
npm run db:seed:industries
```

It creates `restaurant`, `bar`, `home_services`, `professional_services`, and
`general_local_business` through `IndustryService`. Every created record therefore receives an
audit event in the same transaction. Repeated runs skip matching key/name pairs, never alter
existing policy JSON, and report a key/name mismatch as an error. Seeding is never an import side
effect and is not embedded in the schema migration.

## Audit and transaction boundary

Industry creation and lifecycle events are global (`organization_id` is null). Organization
assignment events carry the organization ID. Audit metadata includes industry ID/key, prior and
resulting status or assignment, and resulting version where applicable, but never the full policy
documents. Services flush into the caller-owned `AsyncSession` and never commit independently, so
a failed owning transaction rolls back both the mutation and its audit evidence.

## Temporary internal routes

Industry create, get, list, lifecycle, and organization assignment routes are temporary,
unauthenticated bootstrap surfaces. They are unregistered by default, can be explicitly enabled
only in `local` or `test`, and are rejected by configuration in `development`, `staging`, and
`production`. The setting is not an authentication or authorization substitute.
