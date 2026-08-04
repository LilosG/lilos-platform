# Phase 19 Acceptance

Phase 19 production preparation is complete. Repository-side infrastructure-as-code, deployment
pipelines, and application code are live; a real pilot sign-in and a direct database-level
heartbeat verification have both succeeded in production. Full production launch remains
**BLOCKED** on the exact remaining external access, values, and approvals recorded in the
consolidated decision block at the end of this document. No production-launch claim is made and
Phase 20 remains prohibited.

## Runtime heartbeat verification (2026-08-04 ~21:17 UTC, release `1ef2066edb26c2c68855262410d65ed16b65b5ad`)

`scripts/verify_runtime_heartbeats.py` (added this phase) was run as a read-only Render one-off Job
against the production database. Reported result:

- `lilos-worker`: `ok=True status=running`, heartbeat fresh, single active instance identity.
- `lilos-scheduler`: `ok=True status=running`, heartbeat fresh, single active instance identity.
- Both heartbeats persisted `release=1ef2066edb26c2c68855262410d65ed16b65b5ad`, matching the
  commit whose deploy was live at verification time.
- "Runtime heartbeat verification passed for all services."

This resolves blocker 1 from the prior acceptance pass (worker/scheduler sustained heartbeat
verification): sustained heartbeat renewal in the database is now directly confirmed, not merely
inferred from the absence of error logs. No database credentials, DSNs, or raw row data were
exposed to reach this result — the script prints only service name, instance key (already
documented as a bounded non-secret identity), release, status, and heartbeat age.

## Rollback evidence

`render deploys list` for `lilos-api` (`srv-d9oi90ad0e5s73bldhng`) shows 20 tracked historical
deploys, each tied to a specific commit, with the current live deploy at
`1ef2066edb26c2c68855262410d65ed16b65b5ad` and prior deploys (`dac8ee2`, `449dc39`, ...) retained
as `deactivated` rather than discarded. This is concrete, mechanical rollback capability: any
retained prior deploy can be redeployed. No rollback was exercised against production this pass
(that would be a destructive/disruptive action requiring separate approval); this only confirms
the capability and history exist. `docs/PRODUCTION-MIGRATION-RUNBOOK.md` and
`docs/DISASTER-RECOVERY.md` document the intended procedure; CI's synthetic backup/restore gate
(`scripts/verify_restored_database.py`) continues to pass on every run as repository-side evidence.

## Monitoring, telemetry, and backups — investigated, still blocked

- **Telemetry destination**: `LILOS_TELEMETRY_EXPORT_ENDPOINT` is configured (production requires
  it to boot) but its value is a raw connection value this session will not read, and the
  destination itself was not identified: no GitHub webhook or GitHub App integration exists on
  this repository (`gh api repos/.../hooks` returns empty; no monitoring app is installed
  alongside the Render/GitHub Actions apps already visible in Deployments). Still blocked —
  requires the operator to identify the destination and grant access to confirm dashboards, alert
  rules, and that data is arriving.
- **Production database provider / backup / PITR**: no Render Postgres or Key Value datastore
  exists in this Render workspace (`render services` lists only the three application services),
  confirming the database is externally hosted, consistent with the Blueprint's intentional
  exclusion of Render-managed Postgres. Which provider hosts it cannot be determined without
  reading `LILOS_DATABASE_URL`, a raw connection value this session will not expose. Given
  Supabase Auth is configured for this deployment, Supabase-hosted Postgres is the most likely
  candidate, but this is an inference, not a confirmed fact, and is not acted on. Still blocked.
- **Restore-verification capability**: CI's synthetic restore (PostgreSQL 17, current schema head)
  passes on every run — this is real, current, repository-side evidence, but it is synthetic data
  restored to a disposable local database, not a production-backup restore. Still blocked pending
  identification of the production backup destination above.

## Operational ownership and canonical domain — recorded per operator decision

The operator has designated the following, to be treated as recorded operational fact going
forward (not independently verifiable by this session, and none of these required an unsafe or
destructive action to record):

- Pilot organization: **LILOs Growth** (`36beb4d7-a1db-40b4-81bb-d98380f87dbf`)
- Pilot business owner: **Mike Prickett**
- Operational / on-call contact: **mike@lilosgrowth.com**
- Target canonical frontend domain: **app.lilosgrowth.com** — recorded as the intended target
  only. **Not configured.** No DNS record, Vercel domain assignment, or TLS issuance was
  performed; that requires a separate explicit production approval per instruction. The
  platform-issued hosts (`lilos-api.onrender.com`, `lilos-platform-web.vercel.app`) remain the
  live, canonical addresses until that cutover is explicitly approved and executed.

Named approvers for the remaining Section 27 rows (security, data governance, migration/DBA,
accessibility, provider/AI, live infrastructure launch) are not yet designated beyond the pilot
business owner above — see the consolidated decision block.

## Exact remaining external blockers, in priority order

1. **Monitoring/telemetry destination access**: identify and grant access to confirm dashboards,
   alert rules, and live data arrival; on-call contact is now named (see above).
2. **Production database provider identification and backup/PITR confirmation**: identify the
   host behind `LILOS_DATABASE_URL` and confirm/verify its backup, PITR, and restore-environment
   configuration, or provision an explicit backup destination.
3. **Canonical domain cutover approval**: `app.lilosgrowth.com` is recorded as the target; explicit
   approval is required before assigning it in Vercel/DNS.
4. **Section 27 sign-off**: security, data governance, migration/DBA, accessibility, and
   provider/AI approver rows remain pending named individuals beyond the pilot business owner.

Blockers resolved this pass: worker/scheduler sustained heartbeat verification (directly confirmed
via the database), operational on-call/ownership naming, and rollback-capability evidence.

Therefore: one authenticated pilot sign-in path and direct worker/scheduler heartbeat health are
both verified in production; monitoring/alert-data-arrival and backup/PITR remain unverified; the
canonical domain is decided but not cut over; Section 27 remains unsigned pending named approvers;
and no production-launch claim is made. Phase 20 remains prohibited.

## Consolidated decision block (external, cannot be derived safely)

1. **Telemetry destination access** — grant this session (or a named operator) access to whatever
   service `LILOS_TELEMETRY_EXPORT_ENDPOINT` points to, so dashboards/alerts/data-arrival can be
   confirmed.
2. **Database host identification** — confirm which provider hosts production Postgres (Supabase
   is the working assumption pending confirmation) and grant access to verify its backup/PITR
   configuration.
3. **Domain cutover approval** — explicit go-ahead to assign `app.lilosgrowth.com` in Vercel and
   configure DNS/TLS, per the recorded target above.
4. **Section 27 approver names** — confirm whether Mike Prickett serves as sole approver across all
   remaining rows, or name additional individuals for security/data/DBA/accessibility/provider
   sign-off.

Repository preparation includes a current-schema Render Blueprint and portable backend Dockerfile.
The Blueprint intentionally excludes Render Postgres, Render Key Value, Render Workflows, cron
services, and persistent disks. This resolves the runtime-vendor decision only.

The worker and scheduler consume the Phase 5 PostgreSQL claim/attempt/lease/retry contract
continuously, renew active leases, maintain Phase 17 heartbeats, and drain cooperatively within the
approved Render shutdown window; both fail closed on invalid configuration or sustained database
failure. Sustained heartbeat renewal in the database is now directly confirmed (see above).
