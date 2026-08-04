# Phase 19 Acceptance

Phase 19 production preparation is complete. Repository-side infrastructure-as-code, deployment
pipelines, and application code are live, and a real pilot sign-in has now succeeded end-to-end in
production. Deployment and launch remain **BLOCKED** on the exact remaining external access,
values, and approvals recorded at the end of this document. No production-launch claim is made and
Phase 20 remains prohibited.

## Verified live infrastructure and pilot sign-in (2026-08-04, commit `449dc399f2f0cb66bed1bc3ef752e144b392a9bd`)

This pass re-verified live state using CLI/account access now available: Vercel CLI, GitHub CLI,
and — newly, since the previous acceptance pass — an authenticated Render CLI session
(`render whoami` succeeds). It supersedes the prior version of this document, which listed several
of the items below as blocked; those are now resolved with direct evidence.

### Newly resolved since the last acceptance pass

- **Render interactive access** — resolved. `render whoami`, `render services`, and `render logs`
  now work from this session. This was blocker 1 in the prior version of this document.
- **`LILOS_WEB_ORIGINS` configuration** — resolved. A live CORS preflight
  (`OPTIONS /api/v1/me`) with `Origin: https://lilos-platform-web.vercel.app` now returns `200`
  with `access-control-allow-origin: https://lilos-platform-web.vercel.app`. The same preflight
  with an unrelated origin (`https://not-allowed.invalid`) returns `400 Disallowed CORS origin`
  with no `access-control-allow-origin` header — confirming the allow-list is origin-specific, not
  a wildcard.
- **Vercel Supabase configuration** — resolved. `vercel env ls production` (via the Vercel CLI)
  confirms `PUBLIC_LILOS_SUPABASE_URL` and `PUBLIC_LILOS_SUPABASE_ANON_KEY` are now set for
  Production and Preview, alongside the previously-set `PUBLIC_LILOS_API_BASE_URL`. Values were
  not read or displayed — only their presence was confirmed.
- **Supabase issuer/JWKS configuration** — resolved. The production Supabase issuer and JWKS URL
  were corrected on the `lilos-api` Render service (external action, not performed by this
  session). `lilos-api` was redeployed at 2026-08-04T18:39–18:40Z for the current commit; live
  behavior is consistent with a working verifier (malformed-token requests still return
  `401 AUTHENTICATION_REQUIRED`, not `503`, i.e. the verifier constructs and evaluates tokens
  rather than failing to initialize).
- **Successful production sign-in and `GET /api/v1/me`** — reported by the operator and consistent
  with the infrastructure evidence above (correct CORS, correct Supabase config, correct API
  deployment). This session has no pilot credentials and did not itself perform the sign-in; it
  independently verified every prerequisite that would be required for it to work (CORS,
  Supabase config presence, API auth verifier behavior, current deployment).
- **Pilot organization and owner provisioning** — reported by the operator with concrete
  identifiers, consistent with the `provision_pilot_owner` script and the access-control
  contracts added in this phase:
  - Supabase auth UUID: `a44081bb-95c8-4463-be31-a83291b5239d`
  - Backend user profile ID: `a79e82aa-4c9e-4bb0-a13a-5cd873663fa0`
  - Organization ID: `36beb4d7-a1db-40b4-81bb-d98380f87dbf` ("LILOs Growth", type `internal`)
  - Owner email: `mike@lilosgrowth.com`
  - This session did not run the provisioning script and has no database access to independently
    query these rows; this entry records the operator's report, not an independent database check.

### Previously verified, re-confirmed this pass

- **Render deployment pipeline**: GitHub's Deployments API confirms all three services
  (`lilos-api`, `lilos-worker`, `lilos-scheduler`) deployed successfully for the current commit
  `449dc39` (`lilos-api` 18:39–18:40Z; `lilos-worker`/`lilos-scheduler` 18:00–18:01Z). `render
  services` confirms none are suspended.
- **Production PostgreSQL**: `GET https://lilos-api.onrender.com/health/ready` returns
  `{"status":"ready","dependencies":[{"name":"postgresql","status":"healthy"}]}`.
- **Worker and scheduler process stability (partial)**: `render logs` for both services shows
  exactly one `process.started` event since the current deploy, at the current commit's release
  identifier, with zero `ERROR`-level log lines since. No crash-loop or restart pattern is present
  in roughly 45 minutes of observed uptime. This confirms the processes started cleanly on the
  current release and have not crashed or logged an error since. It does **not** confirm sustained
  heartbeat renewal in the database (heartbeats are written directly to a database table, not
  logged to stdout, and this session has no database access to query that table) — see blocker 1
  below.
- **Vercel frontend**: `https://lilos-platform-web.vercel.app/` and `/login` both return `200`.
  Static `curl` output always contains the "not configured" markup regardless of actual
  configuration, because that state toggling happens client-side in JavaScript after the page
  loads (`curl` does not execute it) — so `curl` alone cannot verify the signed-in experience.
  What `curl`/CLI evidence *can* and does confirm: the current corrected Phase 16 build is live,
  correct Vercel environment variables are present, and the API it targets is healthy and
  CORS-reachable. The signed-in experience itself is confirmed by the operator's report above.
- **TLS**: both live hosts present valid, current platform-issued certificates. No custom domain
  is assigned to either service — see blocker 4.
- **GitHub Actions CI**: the `main` CI run for commit `449dc39` passed both jobs in full.
- **Render Blueprint validation**: `check-jsonschema` against Render's schema and
  `scripts/validate_render_blueprint.py` both pass against the current `render.yaml`.

## Exact remaining external blockers, in priority order

1. **Worker/scheduler sustained heartbeat verification**: process-level stability is confirmed
   (see above), but heartbeat renewal in the database, lease claim/attempt activity, and dead-letter
   handling are not independently confirmed. Requires either direct database read access or a
   diagnostics/heartbeat-status API surface this session can call.
2. **Monitoring/telemetry destination verification**: `LILOS_TELEMETRY_EXPORT_ENDPOINT` is
   configured (the process requires it to boot in production), but this session does not know
   which destination it points to and has no access to confirm dashboards, alert rules, or that
   data is actually arriving. No on-call contacts are named.
3. **Encrypted backup/PITR destination and restore environment**: unverifiable without knowing
   which provider hosts the production Postgres instance behind `LILOS_DATABASE_URL` (Render's own
   Postgres is explicitly excluded from the Blueprint) and without dashboard/credential access to
   that host.
4. **Canonical production domain**: no domain has been assigned to either live service. The
   pilot organization's name ("LILOs Growth") and owner email domain (`lilosgrowth.com`) suggest a
   candidate, and that domain is already present in the same Vercel account (a separate existing
   project), but assigning it to this platform without an explicit decision would be an
   unauthorized guess. The current live hosts remain the platform-issued
   `lilos-api.onrender.com` and `lilos-platform-web.vercel.app` addresses.
5. **Named approvers and launch authorization**: no architecture, engineering, product,
   security/privacy, operations, data, DBA, or business approvers are named; Section 27 remains
   unsigned.

Blockers resolved this pass (Render interactive access, `LILOS_WEB_ORIGINS`, Vercel Supabase
configuration, Supabase issuer/JWKS configuration, Supabase project access for the frontend, and
pilot organization/owner existence) are removed from this list. Production PostgreSQL and Render
deployment-pipeline access, previously listed as blockers, are also resolved — see above.

Therefore: one authenticated pilot sign-in path is verified end-to-end by report and consistent
infrastructure evidence; worker/scheduler heartbeat activity, monitoring/alerting, and backups
remain unverified; no canonical domain and no named approvers exist; Section 27 remains unsigned;
and no production-launch claim is made. Phase 20 remains prohibited.

## Immediate next actions (require the exact access listed in the blockers above)

- Provide read access to the worker/scheduler heartbeat/lease tables (or a diagnostics API) so
  sustained runtime health can be confirmed independently of log absence (blocker 1).
- Identify the telemetry destination and grant access to confirm data is arriving and alerts are
  configured, and name on-call contacts (blocker 2).
- Identify the Postgres host behind `LILOS_DATABASE_URL` and confirm/verify its backup and PITR
  configuration, or provision an explicit backup destination (blocker 3).
- Decide whether `lilosgrowth.com` (or another domain) becomes the platform's canonical production
  domain, or confirm the platform-issued hosts are acceptable for continued pilot use (blocker 4).
- Name the required approvers and complete Section 27 sign-off (blocker 5).

Repository preparation includes a current-schema Render Blueprint and portable backend Dockerfile.
The Blueprint intentionally excludes Render Postgres, Render Key Value, Render Workflows, cron
services, and persistent disks. This resolves the runtime-vendor decision only.

The worker and scheduler consume the Phase 5 PostgreSQL claim/attempt/lease/retry contract
continuously, renew active leases, maintain Phase 17 heartbeats, and drain cooperatively within the
approved Render shutdown window; both fail closed on invalid configuration or sustained database
failure. Their Render deploys succeeded for the current commit with a stable single-instance
process (no restarts, no errors) over the observed window; sustained heartbeat renewal in the
database itself remains unconfirmed pending database access (blocker 1).
