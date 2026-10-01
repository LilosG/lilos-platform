# Command Center

Separate Astro SSR/Vercel application; `apps/web` remains operational.

The approved tracked UI baseline is preserved under `reference/` from
`LilosG/lilos-command-center-astro@d097c5255995b010f45b67a8ace90a80d00f090b`.
Its components, navigation and styles are the product reference; its fixtures and
sample mutations are isolated from the executable console. `src/` adapts the approved
shell, panels and Opportunity experience to request-scoped authoritative sources.
Future product routes retain their hierarchy and show unavailable states.
No prototype scripts or fixtures enter a production entry point.

Run workspace scripts from the repository root. For local SSR, copy `.env.example`
into `.env` and supply isolated local Auth/API configuration and a random CSRF secret.
No authentication or data fixtures are enabled by console environment variables.
Playwright's isolated upstream simulator lives only in `tests/browser/`.

Preview/stable staging invokes the merged Phase 0.5 prerequisite validator from the
Astro composition root and checks trusted deployment identity again at request time.
Use `CONSOLE_ORIGIN=https://<exact expected host>` plus the staging environment
example in `infrastructure/staging/console.env.example`; supply server-only
`CONSOLE_SUPABASE_KEY` and `CONSOLE_CSRF_SECRET` via protected configuration.
`CONSOLE_ENV=staging` is required for stable staging and `VERCEL_ENV=preview` invokes
preview validation regardless of that setting. No wildcard preview hosts.

All tenant routes are SSR, with private/no-store responses including errors and
redirects. Browser code sees a signed, session-bound CSRF nonce, never session tokens.
A request-local Supabase SSR client verifies the user, refreshes before loading,
buffers response cookies, and suppresses all failed-refresh cookie writes. This
allows a stale response to finish after another instance rotated without clearing
that session. Only explicit sign-out clears session chunks; invalid sessions require
sign-in without emitting destructive stale-response deletes. Chunk shrink is handled
by the SDK after successful identity validation. No process-local distributed lock.

BFF routes are a closed method/path registry. Canonical backend approval/revision
routes recheck tenancy, AAL, immutable revision state and exact fingerprints. Mutations
are never automatically replayed after timeout; reload canonical state before retry.
The DTO detail read makes one context request and one detail request. Extra SQL reads
inside the projection are tenant-scoped; staging performance remains pending.

`npm run contracts:generate` exports deterministic FastAPI OpenAPI and generated TS.
`npm run contracts:check` regenerates in isolation and detects drift by byte comparison.
