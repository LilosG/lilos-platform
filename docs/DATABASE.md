# PostgreSQL and migrations

## Supported database

PostgreSQL is the only supported persistence engine. The FastAPI application uses SQLAlchemy 2.x
with `asyncpg`; Alembic uses the same async dialect. SQLite is not a supported runtime or
integration-test substitute.

Revision `20260801_0001` is the persistence baseline and manages only Alembic's version marker.
Revision `20260801_0002` adds the shared append-only `audit_events` table. It does not add an
organization, location, user, product, workflow, integration, or other business-domain table. See
`docs/AUDIT.md` for the schema, write contract, metadata policy, and immutability controls.

Revision `20260802_0001` adds `organizations` as the primary tenant boundary and adds the nullable
restrictive audit-event organization foreign key. No separate tenant, industry, location, profile,
identity, membership, product, or other future-domain table is created. Industry ownership is
deferred until the industries table is implemented.

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
`20260802_0001`; and the location revision is `20260802_0002`. Every future migration must document affected tables, constraints, indexes, data
movement, compatibility, and rollback or forward-fix behavior.

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
