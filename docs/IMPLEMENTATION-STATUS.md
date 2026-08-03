# LILOs implementation status

## Current task

- Roadmap phase: Phase 3 — Authentication, Memberships and Authorization
- Implementation packet: `PHASE-03-TASK-02`
- Deliverable: Organization memberships, invitations, fixed roles/permissions, scoped assignments,
  and explicit denies
- Status: Complete locally; commit, push, and hosted CI pending
- Date: 2026-08-02
- Commit or pull request: Pending

## Implemented requirements

- Added organization-scoped permanent memberships and secure hash-only invitations with controlled,
  versioned lifecycles and atomic minimized audit events.
- Added fixed immutable global system-role and permission catalogs, explicit idempotent audited seed,
  multi-role organization/location assignments, and membership-specific denies where every
  applicable deny overrides allow.
- Added composite database ownership constraints, guarded local/test administration routes,
  migration `20260802_0007`, ADR 0010, and focused membership/invitation/authorization docs.

Authorization enforcement across existing routes remains deliberately deferred to
`PHASE-03-TASK-03`; a valid authenticated principal alone still grants no organization access.

## Phase 3 task 02 validation evidence

- Focused access-domain suite: 9 passed against PostgreSQL 17. All prior suites were also run in
  bounded isolated databases; together all 297 Python tests passed.
- `npm run check` passed formatting, ESLint, Ruff, Astro Check (0 errors/warnings/hints), strict
  mypy over 184 source files, Vitest, non-database pytest, frontend production build, and secret
  scanning. The production build generated one static page.
- Clean base-to-head reached `20260802_0007`; two Alembic checks reported no drift. Catalog review
  verified exact column counts, named checks, restrictive foreign keys, composite ownership,
  partial duplicate-prevention indexes, immutable type/key triggers, and the audit append-only
  trigger.
- Explicit catalog seed created 5 roles, 15 permissions, 49 mappings, and 3 audit events; the
  second run created none. Unit/integration tests prove mismatch rollback.
- Downgrade to `20260802_0006` removed only Task 02 tables while retaining `user_profiles`, all
  Phase 2 tables, three immutable catalog audit events, and append-only audit protection;
  re-upgrade restored head and no drift.
- Existing upstream Starlette/httpx deprecation warning remains unchanged and unsuppressed.

## Phase 3 task 01 validation evidence

- Focused authentication and configuration suite: 45 passed against isolated PostgreSQL 17.
- Full repository validation: formatting, ESLint, Ruff, Astro type checking, strict mypy over 167
  source files, Vitest, all 288 Python tests, Astro production build, and secret scan passed.
- Clean base-to-head migration reached `20260802_0006`; Alembic reported no drift. Catalog review
  confirmed the exact nine columns, five validated constraints, unique subject mapping, immutable
  subject trigger, and retained append-only audit trigger.
- Downgrade to `20260802_0005` removed only `user_profiles` and its trigger function while every
  Phase 2 table and immutable/audit control remained; re-upgrade restored head.
- The existing upstream Starlette/httpx deprecation warning remains unchanged and unsuppressed.

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
- Added the global `industries` registry with immutable normalized keys, controlled lifecycle,
  bounded JSONB policy documents, optimistic concurrency, and migration `20260802_0003`.
- Added nullable primary-industry ownership to organizations without backfill, while requiring an
  active industry for new client, partner, and demo organizations.
- Added the narrow organization industry-assignment operation and atomic audit orchestration for
  industry creation, lifecycle changes, and assignments.
- Added explicit, idempotent, audited initial-industry seeding and temporary local/test-only
  industry administration routes.
- Added focused contracts, repository, service, API, seed, migration, rollback, and compatibility
  tests plus industry operational documentation.
- Validation: focused industry suite `25 passed`; organization/location/audit/database regressions
  `92 passed`; full Python suite `149 passed`; Ruff, mypy, frontend ESLint/Astro/Vitest/build,
  Alembic clean upgrade/check/downgrade/re-upgrade, PostgreSQL catalog inspection, explicit seed
  idempotency, and secret scan passed. The existing upstream Starlette/httpx deprecation warning
  remains unchanged.
- Added one optional controlled organization profile per organization and one optional,
  organization-owned controlled location profile per location.
- Added bounded scalar context and PostgreSQL bounded string arrays without generic JSON metadata,
  automatic population, AI write behavior, or effective-profile composition.
- Added normalized claim conflict validation, defensive collection copying, one-to-one ownership,
  composite organization/location integrity, optimistic replacement, and stable errors.
- Added ADR 0006 and enforced the approved profile parent-state matrices through transaction-local
  parent row locks; the strictest organization/location permission wins.
- Added atomic profile audit events that record identity, operation, version, and changed field
  names without profile content.
- Added temporary local/test-only profile routes, migration `20260802_0004`, focused profile tests,
  and profile architecture and operations documentation.
- Added organization-scoped location groups and many-to-many memberships with the exact approved
  bounded schema, immutable scoped keys, terminal archival, optimistic concurrency, and no nested
  groups or downstream configuration/authorization behavior.
- Added direct and composite restrictive ownership constraints that prevent cross-organization
  membership, plus deterministic bounded group/member listing and narrow repositories.
- Added the full parent-organization permission matrix, location eligibility rules, explicit
  membership persistence/removal, row-locked mutation validation, and atomic bounded audit events.
- Added guarded temporary group and membership routes, migration `20260802_0005`, ADR 0007,
  location-group documentation, and focused lifecycle/isolation/migration tests.
- Added a computed, immutable, read-only business-identity service that resolves current
  organization, location, industry, and optional controlled profile context without a table,
  snapshot, cache, mutation, or audit event.
- Added explicit missing-data indicators, separately attributable cross-level lists and claims, and
  the one authorized traceable scalar resolution for `call_to_action_override`.
- Added organization-scoped negative access, all-state read preservation, read-only transaction,
  no-fabricated-default, no-group-inclusion, contract, and guarded-route tests.
- Added ADR 0008, business-identity documentation, and the Phase 2 acceptance evidence package.

## Test evidence

- No dependency or migration was added or changed for `PHASE-02-TASK-06`.
- `uv run pytest tests/python/business_identity -q` against PostgreSQL 17 — all 32 focused
  business-identity tests passed with the existing Starlette/httpx warning.
- `npm run check` and `uv run pytest tests/python -q` against PostgreSQL 17 passed: Ruff formatting
  checked 152 Python files, ESLint and Ruff passed, Astro Check reported 0 diagnostics, strict mypy
  passed 149 source files, Vitest passed 1 test, pytest passed all 250 tests, Astro built 1 page,
  and the environment/secret scan passed.
- Clean migration upgrade reached unchanged head `20260802_0005`; Alembic reported no drift.
  Catalog inspection confirmed every Phase 2 table and ownership constraint, immutable-key/slug
  triggers, append-only audit protection, and the absence of a business-identity table. Downgrade
  to base and re-upgrade to head completed successfully with no drift.
- `docs/PHASE-02-ACCEPTANCE.md` records every completed packet, migration, boundary, guarantee,
  deferral, and exit criterion. Phase 2 is complete.

- No dependency was added or changed for `PHASE-02-TASK-05`.
- `uv run pytest tests/python/location_groups -q` against PostgreSQL 17 — all 30 focused
  location-group tests passed with the existing Starlette/httpx warning.
- Organization, location, profile, industry, audit, and database regression suites — all 156
  tests passed.
- `npm run check` against PostgreSQL 17 passed: formatting checks passed for 142 Python files,
  ESLint and Ruff passed, Astro Check reported 0 diagnostics, strict mypy passed 139 source files,
  Vitest passed 1 test, pytest passed all 218 tests, Astro built 1 page, and the environment/secret
  scan passed.
- Clean upgrade reached `20260802_0005`; `uv run alembic check` reported no drift. Catalog
  inspection verified the exact ten group columns and five membership columns, scoped unique
  constraints, four validated `ON DELETE RESTRICT` ownership foreign keys, deterministic-list
  indexes, the immutable-key trigger, and the existing audit append-only trigger.
- Downgrade to `20260802_0004` removed both location-group tables and their trigger function while
  retaining organizations, industries, locations, both profile tables, audit events, and prior
  controls; re-upgrade restored head successfully.

- No dependency was added or changed for `PHASE-02-TASK-04`.
- `uv run pytest tests/python/profiles -q` against PostgreSQL 17 — all 39 focused profile tests
  passed with the existing Starlette/httpx warning.
- Organization, industry, location, audit, and database regression suites — all 117 tests passed.
- `npm run check` against PostgreSQL 17 passed: formatting checks passed for 126 Python files,
  ESLint and Ruff passed, Astro Check reported 0 diagnostics, strict mypy passed 123 source files,
  Vitest passed 1 test, pytest passed all 188 tests, Astro built 1 page, and the environment/secret
  scan passed.
- Clean upgrade reached `20260802_0004`; `uv run alembic check` reported no drift. Catalog
  inspection verified 16 organization-profile columns, 15 location-profile columns, all bounded
  array checks, the three validated `ON DELETE RESTRICT` foreign keys, one-to-one constraints, and
  composite organization/location ownership.
- Downgrade to `20260802_0003` removed both profile tables and their supporting location ownership
  constraint while retaining organizations, industries, locations, audit events, and the audit
  append-only and location-slug protections; re-upgrade restored head successfully.

- No dependency was added or changed for `PHASE-02-TASK-03`.
- `uv run pytest tests/python/industries -q` against PostgreSQL 17 — all 25 focused industry tests
  passed with the existing Starlette/httpx warning.
- Organization, location, audit, and database regression suites — all 92 tests passed.
- `npm run check` against PostgreSQL 17 passed: 110 Python files were formatted, Ruff passed,
  strict mypy passed 107 source files, Astro Check reported 0 diagnostics, Vitest passed 1 test,
  pytest passed all 149 tests, Astro built 1 page, and the secret scan passed.
- Clean upgrade reached `20260802_0003`; `uv run alembic check` reported no drift. Catalog
  inspection verified 12 industry columns, 15 named constraints, three indexes, the immutable-key
  trigger, and the validated `ON DELETE RESTRICT` organization foreign key.
- The explicit seed created the five controlled records and five audit events on its first run,
  then reported all five as existing on its second run. Every policy document remained `{}` and no
  full policy document appeared in audit metadata.
- Downgrade to `20260802_0002` removed `organizations.industry_id` and `industries` while retaining
  organizations, locations, audit events, and all five industry-creation audit records; re-upgrade
  restored head successfully.

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
- Cross-level list/claim composition beyond separately attributable business-identity context.
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

- Phase 3 — Authentication, Memberships and Authorization, only when separately authorized.
- Do not begin Phase 3 as part of this packet.
