# Local development

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

## Run the worker and scheduler

```sh
npm run dev:worker
npm run dev:scheduler
```

Both processes report that they are intentionally idle and exit successfully. Durable jobs and
schedules belong to a later roadmap phase.

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
