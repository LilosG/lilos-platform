# ADR 0002: PostgreSQL persistence foundation

- Status: Accepted
- Date: 2026-08-01
- Owners: Platform Engineering
- Related roadmap phase: Phase 1

## Context

The platform specification makes PostgreSQL authoritative and requires an asynchronous FastAPI
persistence layer, migration-controlled schema changes, stable identifier and timestamp
conventions, truthful readiness, and PostgreSQL integration tests. This packet must establish those
contracts without introducing tenant or product tables.

## Decision

Use SQLAlchemy 2.x with `asyncpg` for application database access and Alembic's asynchronous engine
pattern for migrations. The FastAPI lifespan owns an optional lazy engine and session factory. Each
request dependency owns one session and one transaction. PostgreSQL is an explicit readiness
dependency but not a liveness dependency.

Use a separately configurable migration URL with application-URL fallback. Require a PostgreSQL
test database for integration and migration tests; do not substitute SQLite. CI supplies an
ephemeral PostgreSQL 17 service.

Future models use application-generated UUIDv4 primary keys, timezone-aware UTC timestamps, and
shared SQLAlchemy naming conventions. The deterministic baseline revision `20260801_0001` performs
no domain DDL.

## Consequences

- The API process can start and serve liveness without database configuration.
- Database-backed work fails explicitly until configuration and connectivity are available.
- Readiness returns a sanitized unavailable state when PostgreSQL cannot be used.
- Successful request transactions commit; exceptions roll back before session closure.
- Application and migration credentials can follow separate least-privilege policies.
- Database integration validation requires a real isolated PostgreSQL instance.
- Domain tables, tenant scope, RLS, authentication, audit records, and product persistence remain
  later roadmap work.

## Alternatives considered

- SQLite tests: rejected because they do not validate PostgreSQL types, transaction behavior, or
  migration semantics.
- Synchronous application sessions: rejected because the approved FastAPI runtime prefers async
  dependency access.
- Eager database connection during import: rejected because it would break liveness-only startup
  and make configuration absence indistinguishable from process health.
- A baseline business table: rejected because domain schema is explicitly out of scope.

## Validation and review

Validate engine connectivity, sanitized readiness, transaction commit and rollback, model metadata,
and Alembic head/base/head movement against PostgreSQL. Review the decision if a future deployment
uses a transaction pooler requiring different engine pooling behavior.
