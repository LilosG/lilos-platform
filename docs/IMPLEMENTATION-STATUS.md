# LILOs implementation status

## Current task

- Roadmap phase: Phase 2 — Tenant, Organization and Location Model
- Implementation packet: `PHASE-02-TASK-02`
- Deliverable: Organization-owned location and isolation foundation
- Status: Complete for this implementation packet; Phase 2 remains in progress
- Date: 2026-08-02
- Commit or pull request: Uncommitted; commit and push explicitly prohibited for this task

## Implemented requirements

- Created the requested `apps`, `packages`, `docs`, `infrastructure`, `scripts`, and `tests`
  structure with explicit modular-monolith boundaries.
- Initialized the Astro, TypeScript, and Tailwind CSS frontend under `apps/web`.
- Initialized the FastAPI application under `apps/api` without product routes or external
  dependencies.
- Added safe, intentionally idle Python entrypoints for `apps/worker` and `apps/scheduler`.
- Added npm workspace and uv dependency management with committed lockfiles.
- Added Prettier, ESLint, Astro Check, Vitest, Ruff, mypy, and pytest foundations.
- Added root development and validation commands plus local-development documentation.
- Added a two-job GitHub Actions workflow that mirrors the frontend and Python validation.
- Added an ADR template and ADR 0001 for the initial monorepo and tooling decision.
- Added `.gitignore`, `.editorconfig`, `.nvmrc`, and a values-empty `.env.example`.
- Added repository secret-pattern and environment-example validation.
- Reviewed the final repository delta and confirmed the three governing documents are unchanged.
- Added typed API settings for all five explicit environment names, log level, title, and version.
- Added request correlation-ID validation, generation, response propagation, handler context, and
  structured-log context.
- Added typed liveness and readiness responses. Liveness remains process-only; readiness reports
  PostgreSQL as the only implemented infrastructure dependency.
- Added a standard error envelope and handlers for validation, not found, authentication and
  authorization-style failures, conflicts, and unexpected internal failures.
- Added structured JSON application and request-completion logging without request or response
  bodies.
- Added focused tests for configuration, metadata, correlation, errors, security redaction, logging,
  and health contracts.
- Added organization-owned locations with approved type/address rules, lifecycle and parent-state
  policy, scoped immutable slugs, optimistic concurrency, and one-primary enforcement.
- Added strictly organization-scoped location persistence and temporary local/test-only bootstrap
  routes; location mutations and audit records share the owning transaction.
- Added audit location ownership, migration `20260802_0002`, ADR 0005, and location documentation.
- Validation: focused location suite `17 passed`; full Python suite `124 passed`; Ruff, mypy,
  frontend ESLint/Astro/Vitest/build, Alembic upgrade/check/downgrade/re-upgrade, PostgreSQL catalog
  inspection, and secret scan passed. The existing upstream Starlette/httpx deprecation warning
  remains unchanged.
- Added `docs/API.md` and updated local API development guidance.
- Added SQLAlchemy 2.x, asyncpg, and Alembic with locked dependency versions.
- Added optional typed application, migration, and test PostgreSQL URLs.
- Added lazy async engine and session-factory ownership with explicit shutdown disposal.
- Added a transaction-bound FastAPI session dependency with commit, rollback, and sanitized database
  failure handling.
- Added a declarative base, UUIDv4 primary-key mixin, timezone-aware UTC timestamp mixin, and
  deterministic constraint/index naming conventions.
- Added PostgreSQL to readiness without making liveness database-dependent.
- Added deterministic Alembic baseline revision `20260801_0001` with no business-domain DDL.
- Added a PostgreSQL-only integration suite and ephemeral PostgreSQL 17 CI service.
- Added database documentation and ADR 0002.
- Added the append-only `audit_events` model and deterministic revision `20260801_0002` without
  creating organization, location, user, product, workflow, integration, or approval tables.
- Added typed audit actor and result enums plus a bounded audit creation contract.
- Added a defensive JSON metadata policy that rejects secret-bearing keys, non-JSON values,
  excessive nesting, and oversized content.
- Added a transactional audit service and controlled repository with no update or delete methods.
- Added deterministic chronological retrieval using `occurred_at DESC, id DESC`.
- Added PostgreSQL enforcement that rejects update, delete, and truncate operations on audit events.
- Added focused unit, database, migration, rollback, ordering, immutability, and privacy tests.
- Added audit schema and usage documentation plus ADR 0003.
- Clarified through ADR 0004 that organization is the technical tenant boundary and no separate
  tenant table exists.
- Added the `organizations` model and deterministic revision `20260802_0001` without creating
  industries, locations, profiles, identities, memberships, products, or other future tables.
- Added stable organization type/status classifications, immutable normalized slugs, IANA timezone
  validation, currency validation, bounded fields, archival consistency, and optimistic versioning.
- Added a controlled repository with no delete, general update, or slug-update method and a
  database trigger that rejects slug changes.
- Added organization lifecycle rules, atomic compare-and-swap transitions, archived-state
  irreversibility, and stable not-found/conflict errors.
- Added atomic organization and audit writes using the caller-owned transaction. The audit
  organization reference now has a nullable restrictive foreign key.
- Added temporary organization bootstrap routes that are absent by default, permitted only through
  explicit local/test configuration, and rejected in development, staging, and production.
- Added organization contract, repository, service, API, lifecycle, concurrency, isolation,
  migration, rollback, audit, and route-safety tests.
- Added organization architecture, schema, lifecycle, API, privacy, and operational documentation.

## Test evidence

- No dependency was added or changed for `PHASE-02-TASK-01-REVISED`.
- `uv run pytest tests/python/organizations -q` against PostgreSQL 17 — all 42 focused
  organization tests passed with the existing Starlette/httpx warning.
- `npm run check` with test and migration URLs pointed at temporary PostgreSQL 17 — passed:
  - Prettier and Ruff formatting checks passed for 75 Python files.
  - ESLint and Ruff linting passed.
  - Astro Check passed with 0 errors, 0 warnings, and 0 hints.
  - strict mypy passed for 72 source files.
  - Vitest passed 1 test in 1 file.
  - pytest passed all 107 tests.
  - Astro built 1 static page successfully.
  - environment-example and high-confidence secret-pattern checks passed.
- PostgreSQL catalog inspection verified 19 organization columns, 12 named constraints, the
  deliberate listing/unique/primary indexes, the immutable-slug trigger, and the restrictive audit
  organization foreign key.
- `uv run alembic check` passed with no new upgrade operations detected.
- Explicit downgrade to `20260801_0002` removed organizations, its foreign key, and slug function
  while preserving `audit_events` and its append-only trigger/function; re-upgrade restored
  `20260802_0001`.
- Live Uvicorn verification confirmed routes return 404 by default, operate only when explicitly
  enabled in test, propagate correlation IDs, normalize slugs, and return a stable stale-version
  conflict. Production unsafe enablement failed settings validation before startup.

- No dependency was added or changed for `PHASE-01-TASK-03`.
- `npm run format` — passed; Prettier made no frontend changes and Ruff reported all 59 Python
  files formatted.
- `npm run check` with the test and migration URLs pointed at the temporary PostgreSQL 17 database
  — passed:
  - Prettier and Ruff formatting checks passed for 59 Python files.
  - ESLint and Ruff linting passed.
  - Astro Check passed with 0 errors, 0 warnings, and 0 hints.
  - strict mypy passed for 56 source files.
  - Vitest passed 1 test in 1 file.
  - pytest passed all 65 tests.
  - Astro built 1 static page successfully.
  - environment-example and high-confidence secret-pattern checks passed.
- `uv run pytest tests/python/audit -q` against PostgreSQL 17 — all 22 focused audit tests passed.
- `uv run pytest tests/python/database -q` against PostgreSQL 17 — all 11 persistence tests passed.
- The focused suite created and retrieved succeeded, failed, and denied audit events; verified
  nullable scope references, correlation IDs, copied metadata, event chaining, and deterministic
  ordering; and proved that a failed owning transaction rolls back its audit event.
- PostgreSQL rejected direct update, delete, and truncate attempts while preserving the audit row.
- Explicit migration validation passed: upgrade to head, catalog inspection, downgrade to
  `20260801_0001`, and upgrade to head. At the prior revision, both the audit table and trigger
  function were absent; the restored head is `20260801_0002`.
- Catalog inspection verified 24 columns, eight named constraints, five deliberate secondary
  indexes, timezone-aware timestamps, JSONB metadata, nullable UUID references, and the append-only
  trigger.
- `uv run alembic check` passed with no new upgrade operations detected.

## Deferred items

- All product functionality and later-roadmap platform capabilities.
- Business-domain schemas, RLS policies, seed data, and Supabase connectivity.
- Authentication, authorization, memberships, permissions, and entitlements.
- Industries, locations, organization/location profiles, location groups, and business identity.
- Durable job execution, queues, schedule dispatch, retries, and workflow state.
- Vercel, Hetzner, or other production infrastructure configuration.
- Google, AI-provider, Stripe, email, SMS, and other external integrations.
- Product API routes and versioned product contracts.
- Metrics, distributed tracing, centralized log collection, and production deployment wiring.

## Known limitations

- The CI workflow is locally reviewed and mirrors passing local commands, but it cannot produce a
  hosted run until repository changes are committed and pushed with explicit authorization.
- Starlette emits one deprecation warning for its current `httpx`-backed test client. The intended
  and locked dependency remains `httpx`; all tests pass.
- The API intentionally has no product endpoints. Temporary organization bootstrap routes are
  absent unless explicitly enabled in local/test. PostgreSQL is its only readiness dependency.
- Authentication and authorization enforcement are not implemented; this packet establishes only
  their standard error-contract boundary.
- The audit repository has no production API and no speculative cross-tenant behavior. Future
  tenant and authorization packets must scope audit reads before exposure.
- Database trigger enforcement is active now. Least-privilege production database roles that also
  revoke update, delete, truncate, trigger-management, and schema-owner privileges remain deployment
  work.
- Organization isolation currently establishes the ownership record and record-specific data
  access only. Authentication, membership, authorization, scoped request context, and PostgreSQL
  RLS remain later packets; the temporary routes are not production-safe.

## Next eligible task

- Await review and explicit authorization before committing or pushing
  `PHASE-02-TASK-01-REVISED`.
- Do not begin another roadmap task as part of this packet.
