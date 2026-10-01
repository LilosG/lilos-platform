# Command Center staging setup

Repository configuration is implemented; external provisioning is OWNER ACTION
REQUIRED. Do not import production environment groups or credentials.

1. Approve the four-service Render/Supabase/Vercel budget. Create the separate
   `lilos-command-center-staging` Supabase project. Record its project reference
   and the production project reference independently. Use direct PostgreSQL
   (`db.<staging-ref>.supabase.co`, user `postgres`) or Supabase pooler
   (user `postgres.<staging-ref>`) with database `postgres`. All URLs must identify
   this same approved project. Apply migrations only through the API predeploy.
2. Deploy `render.staging.yaml` manually from reviewed `main`. It has API, worker,
   scheduler and pinned private Hermes in isolated Oregon staging, no Render DB.
   Set the `sync: false` values independently: DB/migration URL, Auth issuer/JWKS,
   telemetry, web origins, Fernet key, OAuth and GitHub App settings. Generate a new
   Fernet key with `Fernet.generate_key()`; Render random strings are not Fernet keys.
   Set `LILOS_STAGING_FORBIDDEN_SECRET_SHA256` to comma-separated SHA256 fingerprints
   of production encryption/OAuth/App/Hermes/inference secrets and provider tokens. Supply fingerprints
   through protected deployment configuration; never copy the secrets. Owner must
   attest the list is complete. Startup rejects any configured matching secret.
   Hermes API/tool keys are independently generated and shared only inside staging.
3. Create a separate Vercel console project with deployment protection on Preview
   and the stable staging deployment. Reserve `console-staging.lilosgrowth.com` and
   configure DNS/TLS, Supabase site URL and exact authorized redirect hosts. Use
   the server-only variables in `console.env.example`. `CONSOLE_EXPECTED_HOST` must
   be the exact `VERCEL_URL` on previews, or the stable hostname on staging; no
   wildcard. Validate with `python -m scripts.validate_staging_console` before
   deploy. Phase 1 must wire this check into its console composition/build root;
   this phase creates no console application or auth implementation. Protection
   remains an owner-controlled setting and requires actual deployment verification.
4. Run `python -m scripts.seed_staging` with the staging-only configuration after
   the API predeploy catalogs/migrations. Nine synthetic organizations and their
   locations/websites/provider scenarios are created idempotently. They remain
   setup-required/prospect rather than claiming activation, ownership, live health
   or successful sync. Use canonical onboarding/entitlements/membership actions
   to grant the designated staging operators access; no fake Supabase user IDs.
5. Provide exactly one dedicated GitHub repository and independent App installation.
   Set `LILOS_STAGING_GITHUB_REPOSITORY`, `LILOS_STAGING_GITHUB_INSTALLATION_ID`,
   `LILOS_STAGING_GITHUB_PATH_PREFIX` (normalized directory ending `/`) and optional
   `LILOS_STAGING_GITHUB_BASE_BRANCH` (default `main`). Independently install/connect
   the App to the synthetic publishing org through canonical Integrations. Rerun
   seed to create its canonical target. The production LILOs Growth repo is refused.
   Configure its normal publishing contract/page map through canonical tooling.
   Enable `LILOS_PROVIDER_WRITES_ENABLED` only after scoped configuration and
   connection validation. Branches remain canonical `lilos-content-<UUID>` and
   `lilos-site-change-<UUID>`; every file and pre-merge changed file is checked.
   Google/GBP writes remain denied even when this global switch is enabled.
6. Independently authorize a staging Google OAuth client and LILOs-owned GSC/GA4
   properties on a separate staging smoke organization; confirm GBP scope separately.
   Do not reuse synthetic org connections. Map exactly one property per provider.
   Put its UUID in `LILOS_STAGING_LIVE_GOOGLE_ORGANIZATION_IDS` on API/worker/scheduler.
   Run `python -m scripts.configure_staging_smoke` to install daily 09:17 UTC
   existing `seo.sync_search_console` and `insights.sync_analytics` schedules.
   Worker construction uses real read adapters only for those explicit scopes.
   Missing mappings, fixture credentials and unrelated orgs fail closed. Failed
   refresh/scope/sync uses existing job outcomes, audit and operational attention.
   No live reads have been accepted yet; verify first success/refresh and alerts.
7. Verify staging restore/backup, protection/auth, TLS and actual resource regions
   before live staging acceptance. UI baseline tag and the dedicated fixed canary
   source/reset harness require separately approved repository actions. No production
   canary or ordinary LILOs Growth pages are changed in this phase.

Default fixture adapters never call live HTTP. Tokens beginning `fixture:` are
non-secret scenario references and are rejected by live/production configuration.
Synthetic `.invalid` sites are never live provider targets. Partial GSC payloads
fail incomplete, GA4 rejects incomplete metric headers/values, and sparse GBP profile fields
remain absent; there is no invented completeness/zero fallback.
