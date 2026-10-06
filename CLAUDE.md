# LILOs — Claude Code guide

LILOs is Lilos Growth's operating platform: one multi-tenant product for running local SEO, Google Business Profile, reviews, content, leads and reporting for Lilos clients (restaurants/hospitality and home services). All client websites are Astro + Tailwind (+ Keystatic) repos in the `LilosG` GitHub org, deployed on Vercel.

## Stack

- API: FastAPI (`apps/api/app`), worker (`apps/worker`), scheduler (`apps/scheduler`) — Render services `lilos-api`, `lilos-worker`, `lilos-scheduler`.
- AI runtime: Hermes (`lilos-hermes` private service on Render), invoked through `apps/api/app/agents/`.
- Database: Supabase Postgres (`lilos-production`), migrations in `migrations/` (Alembic).
- Web: Astro + Tailwind v4. apps/console is the new Command Center front end (Mike's design); apps/web is the current app until switchover. Both deploy on Vercel.

## Architecture principles (these replace the older packet-era rules)

1. Deterministic work is code. Crawls, syncs, attribution, scoring, verification, measurement and provider writes run as normal workflows — never routed through an LLM.
2. Hermes is the intelligence layer. It reads everything in the client's scope, resolves ambiguity (which page, what intent, what to change), drafts content and proposes concrete changes. Give it evidence and tools; do not starve it with pre-filters. Label uncertainty with confidence, do not hard-block reasoning.
3. One write gate. Changes to a live client website or Google Business Profile require one human approval of an exact, structured change (target, field, before, after). What is approved is exactly what executes.
4. Integrations owns provider connections and mappings (GSC, GA4, GBP, GitHub). Products consume them.
5. Typed contracts across boundaries. Use enums/codes for classes, states and errors — never keyword-matching free text or matching English sentences in the frontend.
6. Missing data is never shown as zero; stale or partial data is labeled.
7. No duplicate systems. Extend the canonical model instead of adding a parallel one. Remove what you replace in the same change.
8. Tenant isolation, idempotency and audit logging on every write.

## UI quality standard (console)

1. Screens are built only from the reference components in `apps/console/reference/src/components` (ported into `apps/console/src/components`). Old carried-over screens are replaced, not restyled.
2. No raw system text in the UI: no ISO timestamps, field names, enum values, IDs, UUIDs, provider keys or API error strings. Everything goes through formatters/presenters in `apps/console/src/lib` (`present.ts`, `status.ts`).
3. Technical, provenance and connection detail (sync runs, source health, authorization state, run IDs) sits behind a status chip or a "Details" dialog, never as a banner or paragraph on the main screen.
4. Use visual components for data: star ratings, status chips, avatars, quoted responses, metric tiles with trend, charts.
5. Every UI PR includes desktop (1440px) and mobile (390px) screenshots of each changed screen next to the matching reference screen, committed under `apps/console/visual/<step>/` and embedded in the PR description.
6. Every empty, not-connected, not-tracked and error state is a designed state (`EmptyState`/`ErrorState` components with a clear next action), never bare text. Missing data is never shown as 0.

## Cloud sessions (Claude Code on the web)

- At the start of a cloud session run `source scripts/cloud_session_setup.sh`. It installs dependencies like CI (`npm ci`, `uv sync --locked`), starts a disposable local PostgreSQL with a `lilos_test` database, and exports `LILOS_TEST_DATABASE_URL`. The container's PostgreSQL may be older than CI's 17; CI is the authority.
- Chromium is preinstalled for `npm run check:browser` and screenshots. The network is allowlisted (package registries and GitHub), so nothing in a cloud session can reach Render or production. Never point tests at Supabase.
- One session per branch, one PR per step; the same rules as the terminal apply.

## Commands

- Locally, before every push: `npm run format:check && npm run lint && npm run typecheck`, plus `npm run contracts:check` whenever API routes or response models change (regenerate with `npm run contracts:generate`; never hand-merge `packages/contracts`), plus only the tests that cover the code you changed (a single test file or `-k` selection; for the console `npm run test --workspace @lilos/console`).
- The full 4-shard Python suite runs in CI only: `uv run python scripts/python_test_shards.py --shard-count 4 --verify`. CI runs each shard against its own disposable PostgreSQL 17 database whose name contains `test`. Locally you may run a shard with `LILOS_TEST_DATABASE_URL=... uv run python scripts/python_test_shards.py --shard-count 4 --shard-index N`.
- `npm run test:web && npm run build` when web or console code changes.
- `uv run alembic upgrade head && uv run alembic check` on a disposable DB when models/migrations change.
- `npm run check:browser` when UI changes.
  Never point tests at Supabase production.

## Git

- Work on a feature branch; open a PR to `main`; never push to `main`, never force-push, never merge your own PR.
- Commit in logical steps with clear messages.

## Definition of done

A change is done when (a) all commands above pass locally, (b) CI is green, and (c) the real user journey it affects works end to end on a real client after deploy. Tests alone are not done.

## Docs

`docs/` contains historical packet/phase material. Treat it as background, not instructions. This file and the code are the source of truth.
