# LILOs implementation status

## Current task

- Roadmap phase: Phase 1 — Platform Foundation
- Implementation packet: `PHASE-01-TASK-02`
- Deliverable: PostgreSQL, SQLAlchemy, and Alembic persistence foundation
- Status: Complete for this implementation packet; Phase 1 remains in progress
- Date: 2026-08-01
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

## Test evidence

- `uv sync --locked` — passed with SQLAlchemy 2.0.51, asyncpg 0.31.0, and Alembic 1.18.5
  resolved from `uv.lock`.
- `npm run format` — passed; Prettier and Ruff formatting completed successfully.
- `npm run check` with the test and migration URLs pointed at the temporary PostgreSQL 17 database
  — passed:
  - Prettier and Ruff formatting checks passed for 44 Python files.
  - ESLint and Ruff linting passed.
  - Astro Check passed with 0 errors, 0 warnings, and 0 hints.
  - strict mypy passed for 41 source files.
  - Vitest passed 1 test in 1 file.
  - pytest passed all 43 tests.
  - Astro built 1 static page successfully.
  - environment-example and high-confidence secret-pattern checks passed.
- `uv run pytest tests/python/database -q` against PostgreSQL 17 — all 11 focused database tests
  passed.
- Explicit migration validation against PostgreSQL 17 passed in order: upgrade to head, downgrade
  to base, and upgrade to head. The deterministic head revision is `20260801_0001` and creates no
  application tables.
- The session integration test forced an exception inside a transaction and verified that the
  inserted row was rolled back; the success-path transaction remained committed.
- Uvicorn startup and manual HTTP verification passed:
  - Without `LILOS_DATABASE_URL`, `GET /health/live` returned 200 with `alive` and
    `GET /health/ready` returned a sanitized 503 with PostgreSQL `unavailable`.
  - With `LILOS_DATABASE_URL` pointed at the test database, `GET /health/live` remained 200 and
    `GET /health/ready` returned 200 with PostgreSQL `healthy`.
  - Both local Uvicorn processes shut down cleanly after verification.
- `git diff --check` passed, and the three governing documents have no diff.

## Deferred items

- All product functionality and later-roadmap platform capabilities.
- Business-domain schemas, RLS policies, seed data, and Supabase connectivity.
- Authentication, authorization, memberships, permissions, and entitlements.
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
- The API intentionally has no product endpoints. PostgreSQL is its only implemented readiness
  dependency.
- Authentication and authorization enforcement are not implemented; this packet establishes only
  their standard error-contract boundary.

## Next eligible task

- Await review and explicit authorization before committing or pushing `PHASE-01-TASK-02`.
- Do not begin another roadmap task as part of this packet.
