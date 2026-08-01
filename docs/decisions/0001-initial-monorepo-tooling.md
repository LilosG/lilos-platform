# ADR 0001: Initial monorepo and development tooling

- Status: Accepted
- Date: 2026-08-01
- Owners: Platform Engineering
- Related roadmap phase: Phase 0

## Context

The master specification requires a simple monorepo, an Astro frontend, a FastAPI backend, and
external worker processes. Phase 0 must provide repeatable local validation without introducing
production infrastructure or a repository orchestration framework.

## Decision

Use npm workspaces for TypeScript packages and one root uv project for Python applications. Use
Astro, TypeScript, and Tailwind CSS for the web baseline; FastAPI and Uvicorn for the API process;
Prettier, ESLint, Astro Check, and Vitest for frontend validation; and Ruff, mypy, and pytest for
Python validation. Root npm scripts provide a single command surface without Turborepo, Nx,
Docker, or another orchestrator.

The modular-monolith boundary is represented by deployable applications under `apps` and shared
package boundaries under `packages`. No product module, persistence layer, integration, or
external provider is introduced by this decision.

## Consequences

- Dependency state is reproducible through `package-lock.json` and `uv.lock`.
- Frontend and Python tooling remain independently runnable and independently validated in CI.
- The worker and scheduler are separate process entrypoints while sharing the Python codebase.
- Package boundaries are documentary until approved shared contracts or UI primitives exist.
- A future architecture decision is required before introducing a repository orchestrator.

## Alternatives considered

- Turborepo or Nx: rejected because the current repository does not need orchestration complexity.
- Multiple Python projects: deferred until independent packaging or dependency lifecycles are
  demonstrated.
- Docker-based local development: excluded from the assigned Phase 0 scope.

## Validation and review

Validate through local and CI formatting, linting, type checking, tests, builds, and startup smoke
tests. Review this decision if package count, build time, or independent deployment requirements
create a measured limitation.
