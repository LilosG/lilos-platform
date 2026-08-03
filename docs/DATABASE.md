# PostgreSQL and migrations

## Phase 4 shared administration

Revision `20260803_0001` adds 14 shared-administration tables with restrictive ownership,
controlled scope/state checks, positive revisions, effective-period checks, and governed
immutability triggers. JSONB is limited to bounded facts, catalog requirements, registered
configuration, and declarative policies; secrets and executable content fail validation.

Run `npm run db:seed:administration` after access seeding. Downgrade to `20260802_0007` removes
Phase 4 while retaining Phase 1–3 data, access catalogs, audit history, and append-only protection.

## Supported database

PostgreSQL is the only supported persistence engine. The FastAPI application uses SQLAlchemy 2.x
with `asyncpg`; Alembic uses the same async dialect. SQLite is not a supported runtime or
integration-test substitute.

Revision `20260801_0001` is the persistence baseline and manages only Alembic's version marker.
Revision `20260801_0002` adds the shared append-only `audit_events` table. It does not add an
organization, location, user, product, workflow, integration, or other business-domain table. See
`docs/AUDIT.md` for the schema, write contract, metadata policy, and immutability controls.

Revision `20260802_0001` adds `organizations` as the primary tenant boundary and adds the nullable
restrictive audit-event organization foreign key. Revision `20260802_0002` adds organization-owned
`locations` and the nullable restrictive audit location foreign key. Revision `20260802_0003` adds
the global `industries` registry and a nullable, restrictive `organizations.industry_id`. It does
not backfill existing organizations or insert seed records.

Revision `20260802_0004` adds optional one-to-one `organization_profiles` and `location_profiles`,
plus a supporting uniqueness constraint for composite location ownership. It adds no profile data,
composition behavior, AI path, or audit foreign key.

Revision `20260802_0005` adds organization-scoped `location_groups` and
`location_group_memberships`, restrictive direct/composite ownership constraints, scoped
uniqueness, deliberate deterministic-list indexes, and an immutable group-key trigger. It adds no
configuration, permission, product, workflow, profile, hierarchy, or business-identity behavior.

Revision `20260802_0006` adds the exact platform `user_profiles` identity mapping described below.
Revision `20260802_0007` adds organization memberships, hash-only invitations, immutable system
role/permission catalogs, scoped role assignments, and membership-specific denies. Phase 3 route
enforcement and active-owner continuity require no additional table or migration.

## Configuration

The database settings are:

- `LILOS_DATABASE_URL` — application connections;
- `LILOS_MIGRATION_DATABASE_URL` — optional migration-specific credentials, falling back to the
  application URL; and
- `LILOS_TEST_DATABASE_URL` — isolated integration-test database.

`LILOS_DATABASE_CONNECT_TIMEOUT_SECONDS` bounds connection attempts to more than 0 and at most 30
seconds, defaulting to 5 seconds. It applies to application readiness and migration connections.

Use an async SQLAlchemy URL:

```text
postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DATABASE
```

Plain `postgresql://` and `postgres://` schemes are normalized to the asyncpg dialect. URLs must
remain in ignored local environment configuration or an approved secret facility. They must not be
committed or printed in logs.

The API can import and start without database configuration. Liveness remains healthy, while
readiness returns HTTP 503 and reports only that PostgreSQL is unavailable. Invoking a database
session or migration without its required configuration fails explicitly.

## Local PostgreSQL

Install PostgreSQL 17 using the package manager appropriate to the workstation. On macOS with
Homebrew:

```sh
brew install postgresql@17
brew services start postgresql@17
```

Create a dedicated local application database and a separate database whose name contains `test`.
Never point integration tests at staging, production, an existing Supabase project, or client data.

Store local URLs in the ignored `.env` file:

```text
LILOS_DATABASE_URL=postgresql+asyncpg://LOCAL_USER:LOCAL_PASSWORD@127.0.0.1:5432/lilos_local
LILOS_MIGRATION_DATABASE_URL=postgresql+asyncpg://LOCAL_MIGRATOR:LOCAL_PASSWORD@127.0.0.1:5432/lilos_local
LILOS_TEST_DATABASE_URL=postgresql+asyncpg://LOCAL_USER:LOCAL_PASSWORD@127.0.0.1:5432/lilos_test
```

These examples are placeholders, not credentials.

## Migration commands

Apply all migrations:

```sh
npm run db:upgrade
```

Confirm the database is at every current head:

```sh
npm run db:current
```

Downgrade to the base revision in a disposable local or test database:

```sh
npm run db:downgrade
```

Revision identifiers follow `YYYYMMDD_NNNN`. The deterministic initial revision is
`20260801_0001`; the audit revision is `20260801_0002`; the organization revision is
`20260802_0001`; the location revision is `20260802_0002`; and the industry revision is
`20260802_0003`; the profile revision is `20260802_0004`; and the location-group revision is
`20260802_0005`; the platform-user revision is `20260802_0006`; and the access-domain revision is
`20260802_0007`. Every future migration must
document affected tables, constraints, indexes, data movement, compatibility, and rollback or
forward-fix behavior.

Downgrading from `20260801_0002` to `20260801_0001` drops `audit_events` and is destructive to
recorded audit evidence. That downgrade is intended for disposable validation databases before
production use or an explicitly approved recovery procedure.

Downgrading `20260802_0001` to `20260801_0002` removes the audit organization foreign key before
dropping `organizations`. It preserves `audit_events` and its append-only trigger. Organization
records must never be removed through this downgrade outside a disposable validation database or
an explicitly approved recovery procedure.

Downgrading `20260802_0002` to `20260802_0001` removes the audit location index and foreign key,
then the location table and immutable-slug function. Organizations, audit events, and audit
append-only controls remain intact. Re-upgrade does not rewrite immutable audit evidence: it
validates the restored audit location foreign key when all preserved references resolve, or leaves
the constraint `NOT VALID` for historical rows while still enforcing it for every new write.

This destructive downgrade is not a routine production rollback mechanism when immutable audit
records retain location UUIDs. It is intended only for disposable local or test databases,
controlled pre-production validation, or an explicitly approved recovery procedure with operator
review. Production rollback should normally use forward remediation or an approved compensating
migration instead of dropping location ownership while immutable audit evidence remains.

### Unvalidated audit location foreign key

An approved destructive downgrade and re-upgrade can preserve legitimate historical
`audit_events.location_id` values whose location rows no longer exist. PostgreSQL then installs the
foreign key as `NOT VALID`: it continues rejecting invalid new writes, but its historical rows have
not all been validated. Operators must handle this state explicitly.

#### Detection

Identify the constraint and inspect its validation state:

```sql
SELECT conname, convalidated, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE conrelid = 'public.audit_events'::regclass
  AND conname = 'fk_audit_events_location_id_locations';
```

`convalidated = false` identifies the exceptional unvalidated state. An absent constraint is a
separate schema incident and must not be treated as equivalent.

#### Investigation

Identify retained references that do not resolve to a current location:

```sql
SELECT audit.id AS audit_event_id,
       audit.location_id,
       audit.occurred_at,
       audit.event_type
FROM audit_events AS audit
LEFT JOIN locations AS location ON location.id = audit.location_id
WHERE audit.location_id IS NOT NULL
  AND location.id IS NULL
ORDER BY audit.occurred_at ASC, audit.id ASC;
```

Confirm through the approved incident, change, and recovery records whether each row is legitimate
immutable historical evidence retained from an authorized destructive downgrade. Do not delete,
null, or rewrite audit events merely to satisfy the constraint.

#### Remediation

When recovery policy requires the references to resolve, restore or reconcile the referenced
location records through an explicitly reviewed migration or recovery procedure. The procedure
must preserve organization ownership, approved field validation, and audit meaning. Use forward
remediation or a compensating migration in normal production operation; do not perform ad hoc data
changes or silently discard historical evidence.

#### Validation

Only after the investigation query returns no unresolved references may an operator validate the
constraint:

```sql
ALTER TABLE audit_events
VALIDATE CONSTRAINT fk_audit_events_location_id_locations;
```

Repeat the detection query and require `convalidated = true`. A failed validation must leave the
constraint unvalidated while the remaining references are investigated; it is not authorization to
modify immutable audit rows.

#### Audit and change recording

Record detection results, the approved disposition of every unresolved reference, migration or
recovery identifiers, validation output, operator/reviewer identities, and completion time in the
applicable incident, change, or recovery log.

Downgrading `20260802_0003` to `20260802_0002` first removes the organization industry foreign key
and nullable column, then removes the industry table and immutable-key function. Organizations,
locations, and immutable audit history otherwise remain intact. The downgrade is destructive to
industry records and is appropriate only for a disposable database or an explicitly approved
recovery procedure. The migration never inserts, backfills, or silently assigns an industry.

## Controlled industry seed

Apply migrations before explicitly creating the initial industry registry:

```sh
npm run db:seed:industries
```

The command uses the application database transaction and audited industry service. It is
idempotent for matching key/name pairs, does not overwrite policy JSON, and fails on a name
mismatch. See `docs/INDUSTRIES.md` for the full contract.

Downgrading `20260802_0004` to `20260802_0003` removes both profile tables before removing the
supporting location ownership constraint. Organizations, industries, locations, audit events, and
their existing controls remain intact. Immutable audit events retain profile IDs as ordinary
resource references; the downgrade does not delete or rewrite audit evidence. This destructive
profile-data downgrade is for disposable validation databases or an explicitly approved recovery
procedure, not routine production rollback.

Downgrading `20260802_0005` to `20260802_0004` removes memberships before groups and then removes
the immutable-key function. Organizations, industries, locations, profiles, audit events, and
their prior controls remain intact. Immutable audit rows retain group and membership UUIDs as
ordinary resource references and are neither deleted nor rewritten. The destructive group-data
downgrade is intended for disposable validation or an explicitly approved recovery procedure.

Business identity introduces no database object or migration. It is computed from the current
organization, location, industry, and optional profile records inside the caller's read
transaction. It introduced no Phase 2 migration, and a table or snapshot named for business
identity would be an unexpected duplicate source of truth.

Revision `20260802_0006` adds only `user_profiles`. It stores the immutable unique Supabase Auth
UUID mapping, optional bounded administrative display/contact snapshots, controlled lifecycle,
UTC timestamps, and optimistic version. A PostgreSQL trigger rejects `auth_user_id` changes. There
are no password, token, session, organization, membership, role, or permission columns and no
foreign key to the Supabase-owned auth schema.

Downgrade to `20260802_0005` removes the table and its trigger function while preserving every
Phase 2 table, constraint, immutable-key trigger, and audit append-only control. Audit records keep
ordinary resource UUID evidence and are not rewritten or deleted.

## Test validation

With `LILOS_TEST_DATABASE_URL` and `LILOS_MIGRATION_DATABASE_URL` pointing to an isolated test
database:

```sh
uv run pytest tests/python/database -q
uv run alembic upgrade head
uv run alembic downgrade base
uv run alembic upgrade head
```

The integration suite rejects a test URL whose database name does not contain `test`. Its temporary
transaction-probe table is removed after the rollback test. CI runs the suite against an ephemeral
PostgreSQL 17 service with fixed test-only credentials.

## Model conventions

Future models inherit from the shared declarative base and opt into:

- application-generated UUIDv4 primary keys using PostgreSQL `UUID`;
- timezone-aware `TIMESTAMP WITH TIME ZONE` creation and update fields;
- UTC Python defaults and database `now()` defaults; and
- deterministic names for primary keys, foreign keys, unique constraints, checks, and indexes.

These conventions do not replace tenant ownership, organization scope, authorization, retention,
or domain-specific integrity requirements in later implementation packets.

## Access-domain revision

Revision `20260802_0007` adds memberships, hash-only invitations, immutable global role/permission
catalogs and mappings, plus organization/location-scoped role assignments and permission denies.
All tenant ownership uses restrictive direct/composite foreign keys. Membership type and catalog
keys have immutable-key triggers. No custom catalogs, sessions, JWTs, secrets, RLS, or route
enforcement are stored.

Run `npm run db:seed:access` explicitly after migrations. The deterministic audited seed is
idempotent for exact matches and fails instead of rewriting mismatches. Downgrade to
`20260802_0006` removes the seven access tables in dependency order while preserving
`user_profiles`, every Phase 2 structure, and immutable audit evidence. This destructive downgrade
is for disposable validation or approved recovery, not routine production rollback.
