# Phase 0.5 acceptance

State: `IMPLEMENTED_NOT_ACCEPTED` for repository implementation; external live
staging acceptance remains pending. Phase 1 readiness:
`READY WITH OWNER ACTIONS BEFORE LIVE STAGING`.

## Implementation

- Replaced stale staging branch/Render DB/API-worker topology with a manual `main`
  Blueprint: isolated Oregon API, worker, scheduler and pinned private Hermes,
  independent staging Supabase Auth/Postgres, 5 GB Hermes disk. Global writes default
  disabled; no paid resource was created. Existing production Blueprint is unchanged.
- Settings reject staging DB/Auth project mismatch, production project identity,
  missing isolation configuration and known production secret reuse. Production
  rejects fixture provider configuration. Fixture credentials cannot reach live
  adapters. Independent staging secret/token fingerprints must be owner supplied.
- Central service/handler factories select GSC, GA4 and GBP fixtures through existing
  protocols and HTTP seams. Healthy, expired, 429, unavailable, timeout, partial and
  missing-mapping scenarios are deterministic. No live HTTP fallback. Expired
  credentials use canonical reconnect errors. Partial GSC/GA4 reports fail incomplete
  instead of entering zero-valued aggregation; GBP sparse fields remain absent.
- Shared contract tests exercise fixtures and real adapters with committed sanitized
  provider-shaped HTTP response snapshots (synthetic identifiers). These are parser
  evidence, not current Google OAuth acceptance or newly collected live recordings.
- Google/GBP/review writes are denied in staging even with global writes enabled.
  GitHub requires the fixed repo/installation, canonical branch and normalized path;
  App token minting is limited to that repository. Paths are checked before branch
  creation and changed files are rechecked before the governed merge. Production
  approval, audit, idempotency, reconciliation and global kill-switch behavior remain.
- Explicit seed command uses canonical organization, industry, location, website,
  integration and publishing services. It creates nine synthetic scenario shapes,
  11 locations and stable re-runnable mappings, serializes concurrent seeds and
  refuses production/live-connection overwrite. Publishing target creation waits
  for an actual independently connected test App installation; none is fabricated.
- Daily 09:17 UTC read-smoke setup uses existing GSC/GA4 workflow keys, schedules,
  jobs and worker handlers. It requires explicit staging org UUIDs, one confirmed
  mapping per provider and independent live credentials. Fixture-only orgs cannot
  enable live smoke. GBP scope/acceptance remains an owner decision.
- Console environment examples and fail-closed prerequisite validation cover exact
  staging API/Auth identity, exact deployment host and protection. Phase 1 must invoke
  the check in its console composition/build root; no console app is created here.

## Validation

Development evidence: 125 focused adapter/config/security checks passed before the
final parser hardening; 75 focused publishing, provider-sync, worker, review and
GitHub App regressions passed. Final gate results are recorded below after execution.
PostgreSQL checks use only disposable local `lilos_phase05_test` on port 55440.
No migration or dependency was added; no browser or production-preflight suite run.

- `npm run format:check`, `npm run lint`, `npm run typecheck`: PASS; Python
  formatting covered 675 files and mypy covered 671 source files.
- Final targeted backend command: `LILOS_ENV=test
LILOS_TEST_DATABASE_URL=postgresql+asyncpg://lilos_test@127.0.0.1:55440/lilos_phase05_test
.venv/bin/python -m pytest tests/python/staging tests/python/api/test_config.py
tests/python/database/test_config.py tests/python/hardening/test_render_blueprint.py
tests/python/gbp/test_adapter.py tests/python/content/test_github_adapter.py
tests/python/workflows/test_workflow_handlers.py tests/python/workflows/test_process_runtime.py
tests/python/content/test_content_publish_lifecycle.py tests/python/seo/test_sync_transactions.py
tests/python/reviews/test_review_publish_handler.py tests/python/integrations/test_github_app.py
-q --tb=short`: PASS, 204 tests; one existing Starlette deprecation warning.
- `npm run check:render`: PASS official Render schema. Explicit Python invocation
  of `validate_blueprint()` and `validate_staging_blueprint()` returned `((), ())`;
  focused policy tests PASS. The existing module CLI has no entry point, so the
  explicit invocation supplies policy evidence without changing unrelated tooling.
- `npm run check:secrets`: PASS; example values empty, no high-confidence secrets.
- `npm run test:web`: PASS, 450 tests in 48 files. `npm run build`: PASS, 15 pages.
- Final diff review added the direct GBP media-delete guard and preserved its HTTP
  timeout/redirect policy. Focused GBP adapter/write-boundary tests: PASS, 40 tests;
  changed-file Ruff checks and mypy: PASS. Broad final gates were not repeated.
- Full implementation diff reviewed; `git diff --check`: PASS.

## External resources and owner actions

Actually created/connected externally: none. A disposable local test database was
created for validation. No Supabase/Render/Vercel project, GitHub test repo/App,
DNS record or live Google authorization was created or connected. No production
or client asset was mutated. No canary defect/reset was executed.

One remaining owner checklist (configuration details in `infrastructure/staging/README.md`):

- Approve staging costs and confirm Render workspace, Supabase admin access,
  Vercel protection entitlement, actual regions and restore/backup evidence.
- Create separate staging Supabase Auth/Postgres; supply exact staging/production
  project refs, staging DB/migration URLs, issuer/JWKS/publishable key, independent
  Fernet/CSRF/OAuth/App/Hermes/inference secrets, telemetry and production secret/token
  fingerprints through protected configuration. Do not copy production credentials.
- Provision the four-service staging Blueprint; create the separate protected Vercel
  console project, DNS/TLS for `console-staging.lilosgrowth.com`, exact callback/preview
  hosts and staging Auth redirect configuration. Verify protection and auth live.
- Run seed and canonical operator membership/entitlement/onboarding setup. Provide
  one dedicated GitHub test repo/App installation/private key, owner/repo/path/base
  scope and publishing contract/page map; connect it to the synthetic publishing org,
  rerun seed, then enable scoped writes and verify the governed test publication.
- Independently authorize staging Google OAuth and LILOs-owned GSC/GA4 properties;
  confirm GBP scope. Provide a separate smoke org and confirmed mappings, enable
  its explicit UUID, install schedules and capture actual refresh/read/failure alerts.
- Publish the approved immutable UI baseline tag before Phase 1 import. Separately
  authorize the dedicated LILOs Growth canary source/reset-harness repository PR and
  supply a scoped production read session for later readiness evidence. Neither is
  permission to alter normal business pages or run the canary now.

Actual incremental recurring cost: **$0**. Inherited Phase 0 planning estimate:
**$57.25–$72.25/month** base before variable usage; expanded scenario up to
**$171.25/month**, plus optional protection/inference/bandwidth. These are the dated
Phase 0 estimates, not purchased plans or measured capacity. Owner confirms billing.

Repository-side acceptance: negative isolation/write cases, fixture contracts,
seed rerun/refusal, schedule setup/dispatch and affected regressions must PASS.
Live isolation/protection/restore, Google reads and GitHub publication:
**OWNER ACTION REQUIRED**, no live acceptance claimed. No true blocker was introduced
by this phase. Baseline UI and later canary qualification remain the Phase 0 items;
no adjacent product work, Phase 1 implementation or unrelated debugging was performed.

## Exact files changed

- `.env.example`
- `apps/api/app/config.py`
- `apps/api/app/execution/handlers.py`
- `apps/api/app/execution/provider_sync_handlers.py`
- `apps/api/app/execution/runtime.py`
- `apps/api/app/integrations/adapter_factory.py`
- `apps/api/app/integrations/connection_service.py`
- `apps/api/app/products/analytics/adapter.py`
- `apps/api/app/products/analytics/service.py`
- `apps/api/app/products/content/github_adapter.py`
- `apps/api/app/products/content/github_app_service.py`
- `apps/api/app/products/content/publish_handler.py`
- `apps/api/app/products/gbp/adapter.py`
- `apps/api/app/products/gbp/discovery_service.py`
- `apps/api/app/products/reviews/ingestion_service.py`
- `apps/api/app/products/reviews/publish_handler.py`
- `apps/api/app/products/seo/search_console_adapter.py`
- `apps/api/app/products/seo/search_console_service.py`
- `apps/api/app/staging/__init__.py`
- `apps/api/app/staging/isolation.py`
- `apps/api/app/staging/provider_fixtures.py`
- `apps/api/app/staging/seed.py`
- `apps/api/app/staging/write_boundary.py`
- `docs/implementation/command-center/DECISION_LOG.md`
- `docs/implementation/command-center/PHASE_00_5_ACCEPTANCE.md`
- `docs/implementation/command-center/PHASE_00_5_PROMPT.md`
- `infrastructure/staging/README.md`
- `infrastructure/staging/console.env.example`
- `render.staging.yaml`
- `scripts/configure_staging_smoke.py`
- `scripts/seed_staging.py`
- `scripts/validate_render_blueprint.py`
- `scripts/validate_staging_console.py`
- `tests/fixtures/providers/recorded_responses.json`
- `tests/python/api/test_config.py`
- `tests/python/database/test_config.py`
- `tests/python/hardening/test_render_blueprint.py`
- `tests/python/staging/__init__.py`
- `tests/python/staging/conftest.py`
- `tests/python/staging/test_isolation.py`
- `tests/python/staging/test_provider_contracts.py`
- `tests/python/staging/test_seed.py`
- `tests/python/staging/test_smoke.py`
- `tests/python/staging/test_write_boundary.py`
