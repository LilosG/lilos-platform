# Phase 19 Acceptance

Phase 19 production preparation is complete. Repository-side infrastructure-as-code, deployment
pipelines, and application code are now live and independently verified as described below.
Deployment and launch remain **BLOCKED** on the exact remaining external access, values, and
approvals recorded at the end of this document. No production-launch claim is made and Phase 20
remains prohibited.

## Verified live infrastructure (2026-08-04, commit `16ff8ba4acdfe3b74a46cce887d36f9af3e7e2c4`)

This verification was performed from the current working environment using CLI/account access
that is now available (Vercel CLI authenticated; GitHub CLI authenticated; Render CLI is not
interactively authenticated — see blockers). It supersedes the prior version of this document,
which stated Render/Vercel/PostgreSQL access did not exist; that was not re-verified before this
pass and turned out to be materially stale.

- **Render**: connected to this GitHub repository via the official Render GitHub App
  (`performed_via_github_app: renderinc`), with `autoDeployTrigger: checksPass` driving automatic
  deploys on push. GitHub's Deployments API confirms all three declared services
  (`lilos-api`, `lilos-worker`, `lilos-scheduler`) deployed successfully for commit `16ff8ba`
  (`state: "success"` for all three, deployment IDs 5741388263 / 5741388250 / 5741388277,
  completed 2026-08-04T09:34–09:35Z). This resolves the prior "no Render workspace/account access"
  blocker for the deployment pipeline itself. Interactive Render CLI/dashboard access is still not
  available to this session (`render login` requires a human to complete a browser device-code
  approval) — see blockers.
- **Production PostgreSQL**: `GET https://lilos-api.onrender.com/health/ready` returns
  `{"status":"ready","dependencies":[{"name":"postgresql","status":"healthy"}]}`. The API's
  `preDeployCommand` (`scripts/render_predeploy.sh`) runs `alembic upgrade head` under `set -eu`
  before every deploy; a failed migration would fail the deploy. Since the `lilos-api` deploy for
  `16ff8ba` is `success`, the production database is migrated to head and the explicit
  industries/access-catalog/administration-catalog seeds ran. No direct database credentials are
  available to this session, so migration head was confirmed by this inference from deploy
  success and live readiness, not by a direct `alembic current` query against production.
- **Production environment values**: `LILOS_DATABASE_URL`, `LILOS_MIGRATION_DATABASE_URL`,
  `LILOS_SUPABASE_AUTH_ISSUER`, `LILOS_SUPABASE_AUTH_JWKS_URL`, and
  `LILOS_TELEMETRY_EXPORT_ENDPOINT` are confirmed present and valid on the live `lilos-api`
  service: the process booted under `LILOS_ENV=production`, whose settings validator
  (`Settings.validate_production_observability`) requires a non-default release and a telemetry
  endpoint or the process fails to start; `/health/ready` reports the database reachable; and an
  unauthenticated request with a malformed bearer token returns `401 AUTHENTICATION_REQUIRED`
  rather than `503 AUTHENTICATION_UNAVAILABLE`, which only happens if the Supabase JWKS verifier
  constructed successfully from a configured issuer/JWKS URL. No secret value was read, requested,
  or displayed to reach this conclusion.
- **CORS is not yet configured on the live service**: `LILOS_WEB_ORIGINS` was not part of the
  Render Blueprint before this pass, so it is unset on the live `lilos-api` service. A live
  preflight check (`OPTIONS /api/v1/me` with `Origin: https://lilos-platform-web.vercel.app`)
  returns `405` with no `access-control-allow-origin` header, confirming the deployed Vercel
  frontend cannot yet call the API from a browser. `render.yaml` now declares
  `LILOS_WEB_ORIGINS` (`sync: false`) on `lilos-api`; `scripts/validate_render_blueprint.py` was
  updated to require it. This is a repository-only change (not yet committed, per instruction) —
  see next actions.
- **Vercel frontend**: `lilos-platform-web` is a real, authenticated Vercel project
  (`mikes-projects-d07cfe4a/lilos-platform-web`) aliased to
  `https://lilos-platform-web.vercel.app`. Its prior production deployment (9h before this pass)
  was serving the fabricated Phase-0 demo shell that Phase 16 replaced — a real, live, incorrect
  state was found and fixed. This session redeployed the current corrected build
  (`vercel deploy --prod`); the live site now correctly serves the truthful "This deployment is
  not configured" state at `/` and `/login`, verified by direct `curl`. `PUBLIC_LILOS_API_BASE_URL`
  was set to `https://lilos-api.onrender.com` in the Vercel project's Production environment
  (value not displayed; confirmed present via `vercel env ls`). `PUBLIC_LILOS_SUPABASE_URL` and
  `PUBLIC_LILOS_SUPABASE_ANON_KEY` remain unset — no Supabase project access is available to this
  session — so the deployed frontend correctly continues to show the not-configured state rather
  than a broken or fabricated one.
- **TLS**: both live hosts (`lilos-api.onrender.com`, `lilos-platform-web.vercel.app`) present
  valid, current platform-issued certificates (verified via direct TLS handshake). No custom
  domain is assigned to either service yet — see blockers.
- **GitHub Actions CI**: the `main` branch CI run for commit `16ff8ba` passed both jobs (Frontend
  validation, Python validation) in full, including format/lint/typecheck/test/build/dependency
  audit/Render Blueprint validation/migration validation/synthetic backup restore/environment
  example/release acceptance package checks.

## Exact remaining external blockers

1. **Render interactive access**: automated GitHub-triggered deploys work, but this session has no
   interactive Render CLI/dashboard session (`render login` requires a human to approve a
   browser device-code grant) and no Render API key. Setting the new `LILOS_WEB_ORIGINS` value,
   reading deploy logs directly, or inspecting worker/scheduler process health beyond "deploy
   succeeded" all require this.
2. **Production PostgreSQL direct access**: no database credentials are available to this session
   to query migration head, table state, or run a direct backup/restore test; database health was
   inferred only from the API's own readiness endpoint and predeploy behavior.
3. **Supabase project access**: no Supabase URL, anon key, service key, or dashboard access is
   available. This blocks (a) completing the Vercel frontend's remaining two configuration values,
   (b) verifying Supabase Auth redirect/callback URLs include the live Vercel origin, and (c) any
   real sign-in click-through test.
4. **Canonical production domain**: no domain has been designated for the platform. Vercel account
   access includes several client-project domains (e.g. `lilosgrowth.com`) but none are the LILOs
   platform's own domain; assigning one without an explicit decision would be an unauthorized
   guess. The current live hosts are the platform-issued `lilos-api.onrender.com` and
   `lilos-platform-web.vercel.app` addresses only.
5. **Monitoring/alert destination and on-call contacts**: a telemetry export endpoint is
   configured and the process depends on it to boot, but this session has no access to that
   destination to confirm dashboards, alert rules, or that data is actually arriving; no on-call
   contacts are named.
6. **Encrypted backup/PITR destination and restore environment**: unverifiable without database
   host/dashboard access; ownership of backups depends on which provider actually hosts the
   production Postgres instance behind `LILOS_DATABASE_URL`, which this session cannot read.
7. **Approved pilot organization**: no pilot organization, users, provider test resources,
   notification destination, or lead source has been designated, so no authenticated smoke-test
   step beyond liveness/readiness/CORS could be run against production.
8. **Named approvers and launch authorization**: no architecture, engineering, product,
   security/privacy, operations, data, DBA, or business approvers are named; Section 27 remains
   unsigned.

Therefore migrations are believed current (evidenced, not directly queried), smoke/pilot/rollback
tests beyond liveness/readiness/CORS were not executed, monitoring/alerts/backups are not verified
active, Section 27 is unsigned, and no production-launch claim is made. Phase 20 remains
prohibited.

## Immediate next actions (require the exact access listed in the blockers above)

- Set `LILOS_WEB_ORIGINS=https://lilos-platform-web.vercel.app` on the live `lilos-api` Render
  service (requires Render dashboard/API access; blocker 1), then redeploy.
- Provide the Supabase project URL and anon key (or grant Supabase dashboard access) so
  `PUBLIC_LILOS_SUPABASE_URL` and `PUBLIC_LILOS_SUPABASE_ANON_KEY` can be set on Vercel and a real
  sign-in verified end-to-end (blocker 3).
- Decide and assign a canonical production domain, or confirm the platform-issued hosts are
  acceptable for initial pilot use (blocker 4).
- Name a pilot organization and monitoring/backup/on-call/approval owners (blockers 5–8).

Repository preparation includes a current-schema Render Blueprint and portable backend Dockerfile.
The Blueprint intentionally excludes Render Postgres, Render Key Value, Render Workflows, cron
services, and persistent disks. This resolves the runtime-vendor decision only.

The worker and scheduler consume the Phase 5 PostgreSQL claim/attempt/lease/retry contract
continuously, renew active leases, maintain Phase 17 heartbeats, and drain cooperatively within the
approved Render shutdown window; both fail closed on invalid configuration or sustained database
failure. Their Render deploys succeeded for commit `16ff8ba`, but continuous heartbeat activity
was not independently confirmed by this session (no database access) — deploy success confirms the
container started and passed its startup checks, not sustained runtime health.
