# Local development

## Scope

This guide covers the Roadmap Phase 0 development baseline. It does not connect to Supabase,
Vercel, Google, AI providers, Stripe, or another external service.

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

Phase 0 commands use safe local defaults directly. The listed variable names reserve the `LILOS_`
namespace for later validated environment configuration; they do not connect any service.

## Start the frontend

```sh
npm run dev:web
```

Astro listens on `http://127.0.0.1:4321` by default.

## Start the API

```sh
npm run dev:api
```

Uvicorn listens on `http://127.0.0.1:8000`. The Phase 0 application intentionally exposes no
product routes.

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

Apply repository formatting with:

```sh
npm run format
```

## Troubleshooting

- Run commands from the repository root.
- If dependencies changed, run `npm ci` and `uv sync --locked` again.
- Do not add credentials to `.env.example`; keep local values in the ignored `.env` file.
- Do not use production data or production provider credentials for local development.
