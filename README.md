# LILOs Platform

LILOs is being built as a modular monolith with a shared frontend, backend, and
background-process foundation. This repository is currently in Roadmap Phase 0:
repository and development-tooling baseline.

The governing documents are:

- `docs/LILOS-MASTER-SPEC.md`
- `docs/LILOS-BUILD-ROADMAP.md`
- `docs/LILOS-MASTER-BUILD-PROMPT.md`

## Repository layout

- `apps/web` — Astro and TypeScript frontend
- `apps/api` — FastAPI application
- `apps/worker` — background-worker process entrypoint
- `apps/scheduler` — scheduler process entrypoint
- `packages` — shared contracts, configuration, and frontend UI boundaries
- `docs` — governing documents, decisions, runbooks, and development guidance
- `infrastructure` — reserved for approved infrastructure definitions
- `scripts` — repository maintenance scripts
- `tests` — cross-application Python tests and future integration suites

## Prerequisites

- Node.js 22
- npm 10 or newer
- Python 3.12 through 3.14
- uv 0.9 or newer

## Setup

```sh
npm ci
uv sync --locked
```

See `docs/LOCAL-DEVELOPMENT.md` for startup, validation, and environment
instructions.

## Development commands

```sh
npm run dev:web
npm run dev:api
npm run dev:worker
npm run dev:scheduler
```

Run the complete local validation baseline with:

```sh
npm run check
```

Phase 0 does not include product behavior, persistence, authentication,
integrations, or production deployment configuration.
