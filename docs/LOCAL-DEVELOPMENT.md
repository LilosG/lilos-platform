# Local development

## Phase 4 catalogs

After upgrade and access seeding, run `npm run db:seed:administration`. It needs no provider
credentials or network, is a no-op for exact catalogs, and fails on mismatch.

## Scope

This guide covers the local development baseline, FastAPI runtime contract, and PostgreSQL
persistence foundation. It does not connect to Supabase, Vercel, Google, AI providers, Stripe, or
another external service.

## Prerequisites

- Node.js 22
- npm 10 or newer
- Python 3.12, 3.13, or 3.14
- uv 0.9 or newer

## Install dependencies

From the repository root:

```sh
npm ci
uv sync --locked
```

Both lockfiles are committed so local development and CI resolve the same dependency versions.

## Environment convention

Copy `.env.example` to `.env` only when local overrides are needed. The committed example contains
variable names with empty values and no credentials. Local `.env` files are ignored by Git.

The API validates `LILOS_ENV`, `LILOS_LOG_LEVEL`, `LILOS_API_TITLE`, `LILOS_API_VERSION`, and the
three database URL settings documented in `docs/DATABASE.md`.
Supported environments are `local`, `test`, `development`, `staging`, and `production`. Safe local
defaults are used when values are absent. These variables configure only the local process and do
not connect any service.

## Start the frontend

```sh
npm run dev:web
```

Astro listens on `http://127.0.0.1:4321` by default.

## Start the API

```sh
npm run dev:api
```

Uvicorn listens on `http://127.0.0.1:8000`. The application exposes only its health and OpenAPI
surfaces; it has no product routes.

Verify the runtime from another terminal:

```sh
curl -i http://127.0.0.1:8000/health/live
curl -i http://127.0.0.1:8000/health/ready
curl -i -H 'X-Correlation-ID: local-check-001' http://127.0.0.1:8000/health/live
```

Each response returns `X-Correlation-ID`. Without `LILOS_DATABASE_URL`, liveness returns HTTP 200
and readiness returns HTTP 503 with PostgreSQL unavailable. See `docs/API.md` for the accepted
format, response schemas, error contract, and structured logging fields.

## Run PostgreSQL migrations

Configure a local PostgreSQL database as described in `docs/DATABASE.md`, then run:

```sh
npm run db:upgrade
npm run db:current
```

Create the five controlled initial industries explicitly after upgrading:

```sh
npm run db:seed:industries
```

The command is transactional, idempotent for matching records, and creates audit evidence through
the application service. It does not run automatically. See `docs/INDUSTRIES.md`.

## Test authentication locally

Authentication requires explicit HTTPS issuer/JWKS configuration listed in `.env.example`; no
Supabase secret or Management API key is used. Temporary user bootstrap and `/internal/auth/me`
routes register only when `LILOS_INTERNAL_ADMIN_ROUTES_ENABLED=true` in local/test. Do not expose
that unauthenticated bootstrap surface on a shared network.

Run focused tests without external provider access:

```sh
uv run pytest tests/python/authentication -q
```

The suite uses an injected verifier and local asymmetric JWKS fixtures. See
`docs/AUTHENTICATION.md` for token validation, outage, deactivation, MFA, and revocation limits.

## Run the worker and scheduler

```sh
npm run dev:worker
npm run dev:scheduler
```

Durable jobs and schedules use the configured PostgreSQL database. Both processes validate
configuration and connectivity, write service heartbeats, poll continuously with bounded idle
backoff, and stop on SIGINT/SIGTERM.
Without `LILOS_DATABASE_URL` they fail closed with a non-zero exit instead of remaining alive.

## Validation

Run every baseline validation:

```sh
npm run check
```

Individual commands are available when narrowing a failure:

```sh
npm run format:check
npm run lint
npm run typecheck
npm run test
npm run build
npm run check:secrets
```

Run only the focused API runtime tests with:

```sh
uv run pytest tests/python/api tests/python/test_api.py
```

Run PostgreSQL integration and migration tests with an isolated test database configured:

```sh
uv run pytest tests/python/database -q
```

Apply repository formatting with:

```sh
npm run format
```

## Troubleshooting

- Run commands from the repository root.
- If dependencies changed, run `npm ci` and `uv sync --locked` again.
- Do not add credentials to `.env.example`; keep local values in the ignored `.env` file.
- Do not use production data or production provider credentials for local development.

After upgrading, run `npm run db:seed:access` to establish the fixed role/permission catalog. It
creates no membership or owner. Temporary access bootstrap routes require
`LILOS_INTERNAL_ADMIN_ROUTES_ENABLED=true` with `LILOS_ENV=local` or `test`. Treat one-time
invitation plaintext as a secret: never log or commit it.

Run the authorization evaluator security suite against an isolated PostgreSQL test database with:

```sh
uv run pytest tests/python/authorization -q
```

The proof-only authorization-test routes were removed after the always-mounted `/api/v1` routes
adopted the evaluator. Use the real application routes for authorization testing. Internal
membership and first-owner operations remain guarded setup tools; local/test invitation issuance
also requires a valid AAL2 bearer principal with the fixed invitation-management permission.
Never expose the internal guard on a shared network.
