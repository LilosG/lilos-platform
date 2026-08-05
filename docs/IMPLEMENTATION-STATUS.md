# LILOs implementation status

## Google Business Profile OAuth connection foundation (2026-08-05)

This packet completes the code-level work behind `PHASE-09-ACCEPTANCE.md`'s remaining
blockers (2) and (3) for the pilot GBP connection — a single-provider implementation
using the currently-approved Google Cloud project as a temporary pilot OAuth client. It
does not create Google Cloud credentials, configure Render/Vercel/Supabase, perform a
real pilot authorization, or begin Search Console/Analytics/Places integration, GBP
account/location discovery, or GBP provider writes — all explicitly out of scope for
this pass. Dual-client migration to a future dedicated LILOs Google Cloud project
remains a deliberate, separate, later reconnect workflow, not attempted here.

**Reconciled from the prior uncommitted state:**

- `cryptography` was pinned to `>=44.0,<45`, silently downgrading the already-resolved
  transitive version (`pyjwt[crypto]` resolves `50.0.0`) by several major versions.
  Widened to `>=44.0,<51`; `uv.lock` now resolves `50.0.0` again.
- `apps/api/app/integrations/secrets.py`'s `ProviderSecret` model had no migration.
  Added `migrations/versions/20260805_0001_provider_secrets.py`.
- Added `key_version` to `ProviderSecret` and `Settings.secret_encryption_key_version`
  (default `1`). `FernetSecretStore` stamps the active version on every write and
  refuses to decrypt a row stamped with a different version. Rotation itself (a keyring
  supporting simultaneous retired/active keys, plus a re-encryption script) is not
  implemented this pass — see `docs/OAUTH-AND-SECRETS.md` for the documented procedure
  a future packet must follow.
- `apps/api/app/integrations/connection_service.py` had a duplicate/unused `hashlib`
  import (ruff `F401`/`F811`), a nonsensical no-op expression in
  `recover_organization_id` (`self.intents.__class__ and _state_hash(state)`, always
  evaluating the right-hand side), and lazily created the `google_business_profile`
  `Provider` row inside request handling instead of through this codebase's explicit,
  idempotent, audited seed convention. All three fixed: state-hash lookup was
  consolidated into `OAuthIntentService.find_by_state`/`fail` (removing the need for a
  private hash helper in `connection_service.py` entirely), and provider registration
  now happens only via `apps/api/app/integrations/provider_seed.py`
  (`scripts/seed_integration_providers.py` / `npm run db:seed:integration-providers`);
  an unseeded provider now fails closed with the same `IntegrationNotConfiguredError` an
  unconfigured OAuth client produces.
- Google token revocation on disconnect, and a `gbp.connection.failed` audit event on
  token-exchange failure, were both missing; both added.

**New this pass, reusing the existing Phase 7/8 Integration Framework without
duplicating it (`OAuthAuthorizationIntent`, `IntegrationConnection`, `Provider`,
`ProviderResourceMapping`, `OAuthIntentService`, the `SecretStore` Protocol all
already existed on `main`):**

- Always-mounted routes: `POST /api/v1/organizations/{organization_id}/integrations/google/connect`,
  `GET .../status`, `POST .../disconnect` (all gated by the existing `gbp.connect`
  fixed permission at organization scope, AAL1, plus an effective-`gbp`-entitlement
  check reusing `AdministrationService`'s existing entitlement repository — deliberately
  narrower than the full product readiness engine, which also evaluates business
  facts, configuration, approval policy, runtime controls, and onboarding, none of
  which bear on whether an OAuth authorization can begin), and the fixed,
  unauthenticated, organization-agnostic `GET /api/v1/integrations/google/callback` —
  the exact URL that must be registered with Google. Tenant identity is recovered
  entirely from the already-validated, hashed, one-time `state` parameter, never from
  the callback URL.
- The callback redirects the browser back to `/gbp?connected=1` or
  `/gbp?connected=0&reason=...`, using the first configured `LILOS_WEB_ORIGINS` entry as
  the frontend origin (no dedicated frontend-base-URL setting was added, consistent
  with the exact four-variable environment contract below).
- Google token revocation (`POST https://oauth2.googleapis.com/revoke`) on disconnect,
  best-effort and non-blocking; `reconnect_required` on a failed refresh; audit events
  for started/connected/failed/reconnect-required/disconnected, all via the existing
  `AuditEventService` — no duplicate audit infrastructure.
- A real, protected "Google connection" panel on the existing `/gbp` frontend route:
  Connect/Reconnect/Disconnect (with an inline two-step confirmation, no native
  dialog), a truthful connected/pending/degraded/reconnect-required/disconnected status
  display, a post-callback success/failure banner, a permission-denied state, and a
  missing-configuration state (`INTEGRATION_NOT_CONFIGURED`) — no fixture data, no dead
  buttons.
- `apps/api/app/integrations/connection_service.py`'s Google HTTP calls (token
  exchange, refresh, revoke) go through an injectable `http_client_factory`, exactly
  mirroring the existing SEO crawler's pattern — tests exercise the real code path
  against `httpx.MockTransport`, never the network.

**Deferred, explicitly out of scope for this packet:** GBP account/location discovery
(the existing, committed `GoogleBusinessProfileAdapter` is real but nothing yet calls it
to populate `GBPAccount`/`GBPLocation`), GBP provider writes/dispatch (no workflow step
handler exists for `gbp.publish_change`/`gbp.publish_post` — this is a cross-product gap
predating this packet, not introduced by it), Search Console/Analytics/Places
integration, and migration to a future dedicated LILOs Google Cloud OAuth client. The
shared product-readiness `INTEGRATION_FOUNDATION_DEFERRED` finding for `gbp` is
deliberately left unchanged: it reflects that GBP still cannot do discovery or writes
regardless of OAuth connection state, which remains true after this packet.

**Environment contract (values not entered, per instruction):** `LILOS_GOOGLE_OAUTH_CLIENT_ID`,
`LILOS_GOOGLE_OAUTH_CLIENT_SECRET`, `LILOS_GOOGLE_OAUTH_REDIRECT_URI`,
`LILOS_SECRET_ENCRYPTION_KEY` — added to `render.yaml` as `sync: false` on `lilos-api`
only (no code path today performs refresh or dispatch from the worker or scheduler);
`scripts/validate_render_blueprint.py`'s `SECRET_POLICY` allow-list and
`docs/SECRETS-INVENTORY.md` updated to match. Nothing was added to Vercel, Supabase,
GitHub Actions, or any frontend-public variable.

**Validation:** `ruff format --check`, `ruff check`, and `mypy` all pass with zero
findings on every file touched this pass. 25 new deterministic backend tests (no real
Google credentials) — provider-seed idempotency/conflict, `FernetSecretStore`
round-trip/key-version-mismatch/missing-key/malformed-reference, the full
begin→complete→refresh→disconnect connection lifecycle against `httpx.MockTransport`,
provider-denial and reused-state failure paths, and route-level authorization/
entitlement/status/callback-redirect behavior against a real PostgreSQL-backed test
app — all pass. `uv run pytest` (full suite), `alembic upgrade head`/`check`, Prettier,
ESLint, `astro check`, Vitest, the production build, and `scripts/check_secrets.py`
were all re-run; see the accompanying report for exact totals. No commit was made as
part of this packet; the operator must create the Google Cloud OAuth client and
configure the four environment variables above before any real connection can be
attempted.

## Platform administration, reconciliation and correction (2026-08-05)

This pass resolved the "no hidden platform administrator exists" limitation recorded
below under Phase 1 (`Known limitations`). Migration `20260804_0002` adds an additive
`platform_administrators` table — a revocable, cross-organization grant with no
relationship to `organization_memberships`, `roles`, or role assignments; a partial
unique index enforces at most one active grant per user. `require_platform_administrator`
(`apps/api/app/platform_admin/dependencies.py`) is a narrow, fail-closed authorization
primitive independent of the existing per-organization RBAC engine. Always-mounted
routes under `/api/v1/platform` (`apps/api/app/routes/platform_administration.py`) let a
platform administrator create/list/get organizations, drive their lifecycle transitions,
list active industries, create/list/activate locations, and idempotently bootstrap an
organization's first owner — the same sequence `scripts/provision_pilot_owner.py` already
performed by hand, now available from the UI. Every write reuses the existing
organization/location/access-control services verbatim, so audit events and invariants
are unchanged. A new protected `administration.astro` "Client organizations" panel
(`apps/web/src/lib/platform-admin.ts`) probes the real API and only reveals
platform-admin controls on a genuine 200 — never a client-inferred permission. AppShell
gained real active-nav-item indication, and a design-token/CSS polish pass (error alert
and empty-state patterns, expanded color/shadow/radius tokens) was applied consistently
across all six product pages.

Three defects were found and fixed during reconciliation, all now covered by green
tests: `Settings.validate_secret_encryption_key` crashed the entire application on
startup whenever `LILOS_SECRET_ENCRYPTION_KEY` was unset (its own default) — now
short-circuits on `None`; `tests/python/database/test_migrations.py` and
`tests/python/audit/test_migration.py` had exhaustive table-list assertions that were
never updated for the new table; and the frontend's `BootstrapOwnerResult` type/read
(`owner_assignment_created`) didn't match the backend contract's actual field
(`owner_role_assignment_created`). A fourth issue — a new `validate_production_google_oauth`
model validator that unconditionally required Google OAuth credentials in every
production deployment — was removed rather than fixed, because nothing in this release
consumes those settings (see below); it was breaking pre-existing, unrelated production
configuration tests.

**Deferred, not part of this packet:** `apps/api/app/integrations/connection_service.py`,
`secrets.py`, `errors.py`, `contracts.py`, and the `google_oauth_*`/
`secret_encryption_key` fields on `Settings` are real, typed, in-progress work toward
resolving the Phase 9/14 "blocked on Google OAuth credentials" item (a full GBP OAuth
connect/callback/refresh/disconnect service backed by Fernet-encrypted secret storage).
They were found already present in the working tree, untouched by this packet, and left
that way: the new `ProviderSecret` model has no migration, `connection_service.py` fails
`ruff format`/`ruff check` (unused/redefined `hashlib` import), and none of it is mounted
in `main.py` or exercised by any test. It is not currently live — Alembic autogenerate
detects no drift only because nothing imports the module, so `provider_secrets` is not
yet registered against `Base.metadata`. Finishing it (route, migration, tests, lint
cleanup) is separate, explicitly-scoped follow-up work, not resumed here.

**Validation:** `uv run ruff format --check`, `uv run ruff check`, and `uv run mypy`
(354 source files) all pass with zero findings outside the deferred integrations files
noted above. `uv run pytest` — 445 passed against an ephemeral PostgreSQL 17 instance,
including the fixed platform-administration and migration-table-list suites.
`uv run alembic upgrade head` / `alembic check` — clean, no drift. Frontend: `prettier
--check`, `eslint`, `astro check` (0/0/0), `vitest run` (19 passed), `astro build` (9
static pages), and `playwright test` (42 passed) all pass. `uv run python
scripts/check_secrets.py` and `git diff --check` both pass. No commit was made as part
of this reconciliation pass.

## Phase 14 — Remaining Business Profile capabilities, reconciliation and correction (2026-08-05)

The prior "Phase 14 status: complete" claim covered only the domain model
and pure deterministic functions — there was no service layer, API, or
frontend for categories, hours, media, posts, capability snapshots,
completeness/conflicts reporting, or suspension cases. This pass built the
full application surface: a new `GBPOperationsService` adds capability
snapshot recording, governed per-field change-set proposal/approval
(failing closed on unavailable capabilities), special-hours proposal/
approval (rejecting overlapping periods), media proposal, post drafting/
approval/publication-reservation (requiring a confirmed write-enabled
location), suspension-case reporting, and completeness/conflicts
reporting. Every action writes a real audit event and, where relevant, a
real notification. Bare exceptions from the pure capability/hours
functions are now caught and re-raised as typed API errors. Tenant-scoped
routes were added under `.../gbp/operations`; the existing `/gbp` frontend
route gained a real Operations panel for confirmed locations — no fixture
data, no dead buttons. Live provider capability discovery, change
dispatch, media upload, post publication, and suspension detection remain
blocked on the same external Google OAuth credentials recorded in
`PHASE-09-ACCEPTANCE.md`, not requested again this pass.

## Phase 13 — SEO vertical slice, reconciliation and correction (2026-08-05)

The prior "Phase 13 status: complete" claim covered only the domain model
and pure deterministic functions — there was no service layer, API, or
frontend at all. This pass built the full application surface: a new
`SEOService` adds website confirmation, Search Console property mapping
(gated on a real connected integration), a real bounded same-host crawler
using `httpx` with SSRF-safe host allowlisting that extracts technical/
on-page signals and deterministically generates opportunities, local
landing-page gap detection, recommendation approval, implementation-task
tracking with verification, and outcome recording. Every action writes a
real audit event and, where relevant, a real notification. Tenant-scoped
read routes were added for the full domain; a typed errors module replaced
bare exceptions; a real protected `/seo` frontend route was added with
truthful readiness, website confirmation, crawl triggering, an opportunity
queue, and recommendation/implementation controls — no fixture data, no
dead buttons. Live Search Console query/page metric sync remains blocked on
real OAuth credentials, not configured this pass; crawling and on-page
analysis need no such credentials and are fully real.

## Phase 12 — Content vertical slice, reconciliation and correction (2026-08-05)

The prior "Phase 12 status: complete" claim covered the domain model and a
publish-reservation stub only — see `docs/PHASE-12-ACCEPTANCE.md` for the
full reconciliation. Corrected this pass: every opportunity, item, brief,
revision, and publication action now writes a real audit event; revisions
entering review raise real notifications; a new AI-assisted drafting path
drives content generation through the existing AI Gateway, always requiring
editorial and client review; publication reservation now verifies the
target's connection is actually connected; tenant-scoped read routes for
opportunities, items, briefs, revisions, publications, targets, summary,
and audit history were added; a typed errors module replaced bare
exceptions; and a real protected `/content` frontend route was added with
truthful readiness, an opportunity queue, a content pipeline, and a detail
view with brief creation, manual/AI drafting, approval, and publication
reservation — no fixture data, no dead buttons. Live GitHub branch/PR/build/
deploy dispatch remains blocked on a real per-organization repository
connection, not configured this pass.

## Phase 11 — Leads vertical slice, reconciliation and correction (2026-08-04)

The prior "Phase 11 status: complete" claim was inaccurate — see
`docs/PHASE-11-ACCEPTANCE.md` for the full reconciliation. Corrected this
pass: migration `20260804_0001` adds lead notes and follow-up tasks (forced
tenant RLS) plus conversion-value and loss-reason fields on leads; every
intake, consent, communication, assignment, status change, note, and task
now writes a real audit event; assignment and conversion raise real
notifications; a status-transition guard rejects invalid moves out of
terminal states; list/detail/summary/source-performance read routes and
assignment/status/conversion/loss/note/task write routes were added, with
list responses kept free of contact identity and the detail route carrying
full contact identity under the same permission and tenant scope; a typed
errors module replaced bare exceptions that previously fell through to
unhandled 500s; and a real protected `/leads` frontend route was added with
truthful readiness, inbox, detail/lifecycle controls, notes, tasks, and
audit history — no fabricated leads or CRM state, no dead buttons. All new
capability reuses existing shared services (audit, notifications, workflow,
entitlements, authorization); live email/SMS dispatch and CRM sync remain
blocked on external provider credentials not configured this pass.

## Phase 10 — Reviews vertical slice, reconciliation and correction (2026-08-04)

The prior "Phase 10 status: complete" claim was inaccurate — see `docs/PHASE-10-ACCEPTANCE.md` for
the full reconciliation. Corrected this pass: every review ingestion, draft, approval, and
publication reservation now writes a real audit event; restricted-case creation and response
publication raise real notifications; a new AI-assisted drafting path was added through the
existing `AIGateway`/`DeterministicAIProvider`, always requiring human review; list, detail,
summary, response-history, and audit-history read routes were added with tenant-scoped pagination,
filtering, search, and permission checks; a typed errors module replaced bare exceptions that
previously fell through to unhandled 500s; and a real protected `/reviews` frontend route was added
with truthful readiness, inbox, detail/response composer, and audit history — no fixture data, no
dead buttons. All new capability reuses existing shared services (audit, notifications, AI routing,
entitlements, authorization); no new migration was required. Live provider dispatch of a published
response remains genuinely blocked on the same external Google credentials recorded in
`PHASE-09-ACCEPTANCE.md`. Phase 11 (Leads) was not started this pass.

## Phase 9 — Google Business Profile vertical slice, reconciliation and correction (2026-08-04)

The prior "Phase 9 status: complete" claim was inaccurate — see `docs/PHASE-09-ACCEPTANCE.md` for
the full reconciliation. Corrected this pass: every GBP mutation now writes a real audit event
(previously none did); added tenant-scoped, permission-checked read routes for account discovery,
location discovery, change detail, publication history, and audit history — all reusing existing
shared services, no new migration; added a real protected `/gbp` frontend route showing truthful
readiness (including the platform's own existing `INTEGRATION_FOUNDATION_DEFERRED` blocked state),
real (currently empty) discovery data, and an explicit "not available in this release" panel for
Phase 14-scoped capabilities (categories/hours/attributes/services/products/media/posts — those
belong to roadmap Phase 14, not Phase 9). 11 new backend integration tests plus a new Playwright
case were added; full repository validation was run. "Connect Google" and any live provider write
remain genuinely blocked on external Google OAuth client credentials, a secret-encryption key for
a real `SecretStore`, and a registered workflow job handler — see `PHASE-09-ACCEPTANCE.md` for the
exact blocker record. Phases 10 (Reviews) and 11 (Leads) were not started this pass.

## Phase 19 production preparation

The vendor-neutral deployment contract, production preflight, inventories, release and recovery
runbooks, smoke/pilot plans, support plan, and Section 27 package are implemented. Production
deployment and launch remain blocked on the exact external access, environment, domain, monitoring,
backup, pilot, contact, and approval dependencies recorded in `PHASE-19-ACCEPTANCE.md`. No
production deployment or launch is claimed.

## Phase 19 verified infrastructure state (2026-08-04, superseded — see next section)

A re-verification of actual account/CLI access (rather than the prior recorded blocker list) found
Render, Vercel, and production PostgreSQL are live and already connected to this repository:

- Render's GitHub App integration auto-deploys `lilos-api`, `lilos-worker`, and `lilos-scheduler`
  on push; all three deployed successfully for commit `16ff8ba` (verified via the GitHub
  Deployments API — `state: success` for each). `https://lilos-api.onrender.com/health/ready`
  reports PostgreSQL healthy, and the API's `preDeployCommand` runs `alembic upgrade head` (fail-fast)
  and the explicit catalog seeds before every deploy, so the production database is migrated to
  head and seeded.
- The `lilos-platform-web` Vercel project was found serving the pre-Phase-16 fabricated demo shell
  in production (`https://lilos-platform-web.vercel.app`) — a live, client-visible defect. This
  session redeployed the corrected Phase 16 build via `vercel deploy --prod`; the live site now
  correctly shows the truthful "not configured" state. `PUBLIC_LILOS_API_BASE_URL` was set on
  Vercel to the live Render API URL; `PUBLIC_LILOS_SUPABASE_URL`/`PUBLIC_LILOS_SUPABASE_ANON_KEY`
  remain unset (no Supabase access available).
- CORS is not yet enabled on the live API (`LILOS_WEB_ORIGINS` was not previously part of the
  Render Blueprint). `render.yaml` and `scripts/validate_render_blueprint.py` were updated in the
  working tree (not committed) to declare it; the actual origin value still needs to be set in the
  Render dashboard, which this session cannot reach.
- Render interactive CLI/dashboard access, direct PostgreSQL credentials, Supabase project access,
  a designated canonical domain, a monitoring/backup destination, a pilot organization, and named
  approvers remain unavailable to this session. See `PHASE-19-ACCEPTANCE.md` for the exact,
  re-verified blocker list and the immediate next actions each one gates.

No production-launch claim is made; Phase 20 remains prohibited.

## Phase 19 production pilot verification (2026-08-04, commit `449dc399f2f0cb66bed1bc3ef752e144b392a9bd`)

This pass resolves several items the prior section above listed as blocked. Full detail and
evidence are in `PHASE-19-ACCEPTANCE.md`; summary:

- **Resolved this pass**: Render interactive CLI access (`render whoami`, `render services`,
  `render logs` now work); `LILOS_WEB_ORIGINS` CORS configuration (live preflight confirms the
  Vercel origin is allowed and an unrelated origin is rejected); Vercel's
  `PUBLIC_LILOS_SUPABASE_URL`/`PUBLIC_LILOS_SUPABASE_ANON_KEY` (confirmed present, values not
  read); the production Supabase issuer/JWKS configuration; and a successful pilot sign-in and
  `GET /api/v1/me` call (reported by the operator, consistent with all independently-verified
  prerequisites).
- **Pilot organization and owner provisioned**: organization "LILOs Growth"
  (`36beb4d7-a1db-40b4-81bb-d98380f87dbf`, type `internal`), owner user profile
  (`a79e82aa-4c9e-4bb0-a13a-5cd873663fa0`) mapped to Supabase auth user
  `a44081bb-95c8-4463-be31-a83291b5239d`, reported by the operator. This session did not run the
  provisioning script and has no database access to independently confirm these rows.
- **Worker/scheduler**: confirmed stable (single clean start on the current release, zero error
  logs, no restarts over the observed window) via `render logs`, but sustained heartbeat renewal
  in the database is not independently confirmed — heartbeats write to a database table, not
  stdout, and this session has no database read access.
- **Still blocked, in priority order**: (1) worker/scheduler database-level heartbeat
  verification, (2) monitoring/telemetry destination verification and on-call contacts, (3)
  backup/PITR destination and restore verification, (4) canonical production domain decision, (5)
  named launch approvers and Section 27 sign-off.

No production-launch claim is made; Phase 20 remains prohibited.

## Phase 19 closure pass (2026-08-04 ~21:17 UTC, release `1ef2066edb26c2c68855262410d65ed16b65b5ad`)

`scripts/verify_runtime_heartbeats.py` was run as a read-only Render Job against production:
`lilos-worker` and `lilos-scheduler` both report `ok=True status=running` with fresh heartbeats at
release `1ef2066`. This directly confirms sustained runtime health at the database level — the
previously-open item from the prior pass. `render deploys list` for `lilos-api` shows 20 retained
historical deploys, giving concrete rollback capability/evidence. Operational ownership was
recorded per operator decision: pilot business owner Mike Prickett, on-call contact
`mike@lilosgrowth.com`, target canonical domain `app.lilosgrowth.com` (recorded only — not
configured; platform-issued hosts remain live pending a separate cutover approval). Monitoring/
telemetry-destination access, the production database provider/backup identity, and full Section 27
named-approver sign-off remain blocked pending external access this session cannot safely derive.
See `PHASE-19-ACCEPTANCE.md` for full evidence and the consolidated decision block.

## Current task

- Roadmap phase: Phase 16 — Administrative and Client User Interfaces
- Implementation packet: `PHASE-16-CORRECTION`
- Deliverable: Replace the static demo shell with a real operational application
  foundation (authentication, organization/location context, API integration,
  protected routes, truthful states)
- Status: Implementation and local validation complete
- Date: 2026-08-04
- Commit or pull request: This phase packet

The "Phase 4" entry previously recorded in this position was stale: Phases 5–18 are
recorded as implemented elsewhere in this document (through migration
`20260803_0013`), so this document's own history shows Phase 4 closure is no longer
the active task. This packet does not resume Phase 4 or Phase 5 work.

## Phase 16 correction packet (`PHASE-16-CORRECTION`)

Verification against the Phase 16 roadmap deliverables and exit criteria found the
existing frontend (`apps/web/src/pages/index.astro`) was a fully static demo: a
hardcoded organization, permission set, entitlements, readiness, metrics, and
activity feed, with no authentication, no API calls, and no protected routes. The
navigation-visibility logic also fabricated authorization state client-side rather
than deferring to the server. This violated the Master Build Prompt's prohibition
on placeholder implementations presented as finished and on hiding/inventing
authorization outcomes in the frontend.

### Implemented

- **Backend (minimal, self-scoped, no migration; classified as a blocking existing
  defect required to complete this task):**
  - `MembershipRepository.list_by_user` (`apps/api/app/access_control/repository.py`)
    and `AccessControlService.list_my_organizations`
    (`apps/api/app/access_control/service.py`) resolve every organization a caller
    belongs to, scoped strictly by the verified principal's `platform_user_id`.
  - Always-mounted `GET /api/v1/me` and `GET /api/v1/me/organizations`
    (`apps/api/app/routes/api_v1.py`) give a signed-in user a production-safe way
    to discover their own identity and organization memberships — previously the
    only such endpoint (`/internal/auth/me`) was gated behind
    `internal_admin_routes_enabled` (local/test only).
  - `Settings.web_origins` / `allowed_web_origins()` (`apps/api/app/config.py`) and
    conditional `CORSMiddleware` mounting (`apps/api/app/main.py`) let a
    browser-hosted frontend call the API cross-origin; disabled by default, HTTPS
    required in production, validated as bare origins (no path/query/fragment).
- **Frontend (`apps/web/src`):**
  - `lib/config.ts`, `lib/supabase-client.ts`, `lib/session.ts`, `lib/api-client.ts`,
    `lib/workspace.ts`, `lib/dashboard-logic.ts` — real Supabase email/password
    session handling and a typed API client whose every outcome
    (`not-configured` / `unauthenticated` / `forbidden` / `not-found` /
    `disconnected` / `error` / `ok`) is rendered as a distinct, truthful UI state.
  - `pages/login.astro` — real sign-in form; redirects to the workspace once
    signed in; shows an explicit "not configured" state instead of a broken form
    when deployment configuration is absent.
  - `pages/index.astro` — client-side boot sequence: redirects unauthenticated
    visitors to `/login`, fetches the real principal, real organization
    memberships (explicit empty state if none), real locations, and real
    per-product readiness (`GET .../products/{key}/readiness`) for all six
    product keys. An organization switcher is populated from real data when a
    caller belongs to more than one organization.
  - `components/AppShell.astro` — navigation is now a static, always-rendered
    list; the previous permission-Set-based filtering (which fabricated
    authorization state in the client) is removed. Org name, user identity,
    assurance level, and sign-out are populated from real data at runtime.
  - Metrics, activity history, and SEO recommendations have no backing read API
    in this release (Insights/audit routes are not mounted) and are shown as an
    explicit "not available in this release" panel — no simulated data.

### Architecture and decisions

- The frontend remains a static Astro build (no SSR adapter added); all
  authentication and data gating is client-side JavaScript. The backend remains
  the sole authorization authority — every real data render is the direct
  result of a real, separately-authorized API response, never a client-inferred
  permission.
- Email/password sign-in was used rather than magic-link/OAuth to avoid adding a
  callback-route flow out of scope for this correction.
- No SSR, no new database migration, no per-product detail screens, and no
  Insights/activity/SEO panels were added — each is either genuinely out of
  Phase 16's roadmap scope or has no backing API yet; deferred rather than
  simulated.

### Tests and validation

- Backend: `uv run ruff format --check`, `uv run ruff check`, `uv run mypy` all
  passed with zero findings introduced by this change (one pre-existing,
  unrelated `ruff` finding in `scripts/validate_render_blueprint.py` was left
  untouched, out of scope). `uv run pytest` — 396 passed against an ephemeral
  PostgreSQL 17 instance, including new focused self-scope isolation tests
  (`tests/python/access_control/test_self_scope_api.py`) and CORS configuration
  tests (`tests/python/api/test_config.py`).
- Frontend: `npx prettier --check .`, `npx eslint .`, `npx astro check` (0
  errors/warnings/hints), `npx vitest run` (18 passed, including new
  `config.test.ts`, `api-client.test.ts`, `dashboard-logic.test.ts`), `npx astro
  build` (2 static pages), and `npx playwright test` (10 passed across desktop
  and mobile viewports) all passed. The Playwright suite and a manual
  `astro preview` fetch confirmed the unconfigured build renders the truthful
  "This deployment is not configured" state rather than any fabricated content.
- Live Supabase/API click-through (real sign-in, real organization switch) was
  not exercised — no Supabase project or reachable API deployment exists for
  this repository yet, consistent with the Phase 19 external blockers already
  recorded in `PHASE-19-ACCEPTANCE.md`. This is a known limitation, not a claim
  of full end-to-end verification.

### Deferred / excluded scope

- OAuth/magic-link sign-in, SSR adapter, per-product detail screens, and any
  Insights/activity/SEO backing API remain out of scope for this packet.
- Production CORS origins, Supabase project provisioning, and API deployment
  remain external Phase 19 blockers.

## Phase 4 implementation

- Added governed service catalog/assignments, immutable-revision facts, product/configuration
  catalogs, organization/location entitlements, and computed readiness.
- Added effective-dated configuration with explicit merge/source trace, policy categories, feature
  flags, restrictive runtime controls, evidence-based onboarding, and non-destructive offboarding.
- Added 19 fixed permissions with conservative role mappings, sensitive-action AAL2, and protected
  production routes. Entitlement, readiness, authorization, flags, and controls remain separate.
- Added migration `20260803_0001`, explicit product/configuration seed, focused security/domain
  tests, route matrix, domain documentation, and Phase 4 acceptance evidence.

## Phase 4 validation evidence

- `npm run check` passed Prettier, ESLint, Ruff formatting/linting over 218 Python files, Astro
  Check with 0 diagnostics, strict mypy over 215 source files, Vitest (1 passed), the Python suite
  (208 passed, 119 expected integration skips), the one-page production build, and secret scanning.
- The complete PostgreSQL-backed Python suite passed all 327 tests after the final CI-regression
  fixture and migration-expectation corrections.
- The focused PostgreSQL-backed Phase 4 suite passed all 15 tests. The focused authentication,
  authorization, and access-control regression suites passed all 57 tests.
- PostgreSQL 17 upgraded cleanly from base through `20260803_0001`; both Alembic checks reported no
  drift. Catalog inspection confirmed 14 Phase 4 tables, 134 named constraints, 44 indexes, 22
  governance triggers, restrictive foreign keys, and intact append-only audit protection.
- The explicit seed created 7 products and 7 configuration definitions, then created none on its
  second run. A controlled mismatch failed closed and rolled back without partial catalog or audit
  writes. A direct cross-organization service assignment was rejected by the composite foreign key.
- Downgrade to `20260802_0007` removed all 14 Phase 4 tables while preserving all 16 Phase 1–3
  domain tables and their immutable/append-only triggers; re-upgrade restored head without drift.
- The existing upstream Starlette/httpx deprecation warning remains unchanged and unsuppressed.

## Implemented requirements

- Added always-mounted bearer-authenticated `/api/v1` routes for supported organization, location,
  profile, location-group, business-identity, membership, invitation, role-assignment, deny, and
  catalog operations. Every route uses a fixed permission, scope, and AAL policy.
- Added transaction-safe final-active-owner protection for assignment removal, membership
  suspension/revocation, and user deactivation, including concurrent removal coverage.
- Removed the proof-only authorization-test routes and reduced access-control bootstrap operations
  to deterministic membership, first-owner, and local/test invitation setup.
- Added the Phase 3 route matrix, acceptance record, ADR 0011, production-route security tests, and
  closure documentation. No migration or dependency was added; head remains `20260802_0007`.
- Added an immutable read-only authorization request and decision contract combining the verified
  principal, active organization/user/membership state, fixed permission catalog, organization or
  location scope, explicit deny precedence, and server-selected minimum AAL.
- Added a deterministic fail-closed authorization service with narrow organization-scoped reads,
  additive role allows, no role/membership/JWT bypass, ordinary wrong-owner location not-found
  behavior, and minimized security logging without audit or decision persistence.
- The earlier five fixed-policy proof routes were replaced by the production-capable route surface.
- Added focused contracts, state, role, scope, deny, MFA, isolation, failure, logging, and HTTP tests
  plus `docs/AUTHORIZATION-ENFORCEMENT.md`. No migration or dependency was added; head remains
  `20260802_0007`.

## Phase 3 task 04 validation evidence

- `npm run check` passed formatting across 201 files, ESLint, Ruff, Astro Check with no diagnostics,
  strict mypy over 198 source files, Vitest, 194 non-database Python tests with 118 expected skips,
  the frontend production build, and secret scanning.
- The complete PostgreSQL-backed Python suite passed all 312 tests. Focused authentication,
  authorization, and access-control suites passed 56 tests; focused organization, location,
  profile, location-group, business-identity, audit, and database suites passed 193 tests.
- PostgreSQL 17 upgraded cleanly from base to `20260802_0007`; both Alembic checks reported no
  drift. Catalog inspection confirmed all Phase 2/3 tables, 55 grouped constraint categories, 18
  access/user indexes, immutable subject/key/type triggers, append-only audit protection, and no
  authorization-decision table.
- A destructive disposable-database downgrade reached base with only `alembic_version` remaining;
  re-upgrade restored head and a second no-drift result.
- The existing upstream Starlette/httpx deprecation warning remains unchanged and unsuppressed.

## Phase 3 task 03 validation evidence

- `uv run pytest tests/python/authorization -q` passed all 11 focused tests against PostgreSQL 17.
- Authentication and Task 02 access-control regressions passed all 42 tests. The complete
  PostgreSQL-backed Python suite passed all 308 tests with only the unchanged upstream
  Starlette/httpx deprecation warning.
- `npm run check` passed Prettier, Ruff formatting/linting over 199 files, ESLint, Astro Check with
  no diagnostics, strict mypy over 196 source files, Vitest, non-database pytest (193 passed/115
  skipped), the one-page Astro production build, and secret scanning.
- A clean PostgreSQL 17 base-to-head upgrade reached `20260802_0007`; Alembic check reported no
  drift. Catalog inspection found no authorization/decision table and retained all nine immutable
  and append-only triggers. A full downgrade to base, re-upgrade, and second Alembic check passed.

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
- PostgreSQL RLS and billing-provider synchronization.
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
- Production first-owner provisioning, invitation email delivery, and global platform-user
  administration remain deferred; no hidden platform administrator exists.
- The audit repository has no production API and no speculative cross-tenant behavior. Future
  tenant and authorization packets must scope audit reads before exposure.
- Database trigger enforcement is active now. Least-privilege production database roles that also
  revoke update, delete, truncate, trigger-management, and schema-owner privileges remain deployment
  work.
- Organization isolation is enforced in the always-mounted application routes through verified
  identity, active membership, fixed permissions, scope, and denies. PostgreSQL RLS remains later.

## Next eligible task

- Phase 5 only when separately authorized. Phase 4 is complete locally pending recorded CI evidence.
# Phase 5 completion
# Phase 13 completion
# Phase 14 completion
# Phase 15 completion
# Phase 16 completion

Phase 16 replaces the Phase 0 placeholder with the responsive accessible operational shell, authorization-aware navigation policy, readiness/degradation states, validated metric presentation, and reusable workspace components. Browser and component validation are documented; server authorization remains authoritative.


Phase 15 establishes definition-driven observations, goals, annotations, immutable report snapshots, tracked delivery, and evidence-bearing insights at migration `20260803_0012`. Missing data and partial periods remain explicit.


Phase 14 completes the capability-governed GBP model at migration `20260803_0011`, including categories, special hours, grouped changes, media rights, posts, scheduling state, and suspension cases. Unsupported provider surfaces remain unavailable.


Phase 13 adds the evidence-driven SEO persistence and policy foundation at migration `20260803_0010`: confirmed website/property scope, deterministic URLs, bounded crawl intent, quality-labelled observations, deduplicated opportunities, immutable recommendations, implementation verification, and measurement outcomes. Live Search Console validation is deferred to approved credentials.


Phase 12 is complete at migration `20260803_0009`: evidence-backed content planning, structured briefs, shared-AI/manual immutable revisions, grounding and claim validation, editorial/client approval, allowlisted GitHub/Astro publication intent, build/deployment verification states, reconciliation, and rollback lineage are established. Phases 9–12 milestone is complete; Phase 13 has not begun.

Phase 11 is complete at migration `20260803_0008`: verified lead sources, deduplicated evidence, tenant-RLS-protected lead data, explicit channel/purpose consent, withdrawal suppression, routing state, durable communications, speed-to-lead events, and CRM conflict mappings are established.

Phase 10 is complete at migration `20260803_0007`: shared AI task/execution governance and review ingestion, immutable revisions, deterministic risk triage, grounded drafting, approval, restricted escalation, publication intent, and verification/reconciliation are established.

Phase 9 is complete at migration `20260803_0006`: the first GBP vertical slice provides secure Google adapter contracts, discovery identities, explicit location mapping, normalized snapshots, evidence-based health, grounded immutable changes, approval state, durable publication intent, verification, and reconciliation boundaries. Live Google validation awaits approved credentials.

Phase 8 is complete at migration `20260803_0005`: shared synchronization definitions, durable runs/checkpoints, observed-state snapshots, proposed change intents, verification, conflicts, and deterministic normalization/diffing are established. Phases 5–8 foundation milestone is complete; Phase 9 has not begun.

Phase 7 is complete at migration `20260803_0004`: provider registry, organization-owned connections, hash-only OAuth state, secret-store references, capability/health metadata, and external resource mappings are established.

Phase 6 is complete at migration `20260803_0003`: governed templates, notification events, recipient deliveries, preferences, attempts, deduplication, and Phase 5 job integration are established without a production provider.

Phase 5 is complete at migration `20260803_0002`: shared workflow definitions and versions, durable runs/steps/jobs/attempts, scheduling, leases, retry, cancellation, dead-letter handling, and organization-scoped idempotency are established. Provider actions remain deferred.
# Phase 17 — Observability and Operational Hardening

Implemented at migration `20260803_0013`: bounded/redacted telemetry, safe metric labels, trace propagation, deterministic alerts, incident/SLO/heartbeat persistence, dashboards, alert catalog, diagnostics policy, and production incident runbooks. External telemetry activation is a Phase 19 dependency.
# Phase 18 — Testing, Security, and Reliability Hardening

Implemented release-blocking dependency, browser/accessibility, synthetic restore, migration, secret, acceptance-package, redaction, and regression gates. Production load/soak, live monitoring, manual accessibility, provider sandbox, and geographic recovery evidence remain external launch dependencies.
