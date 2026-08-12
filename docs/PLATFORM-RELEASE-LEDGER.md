# LILOs Platform Release Ledger

This ledger is updated by the principal release integrator from repository and live evidence.

## Status vocabulary

- `NOT_STARTED`
- `IMPLEMENTED_NOT_ACCEPTED`
- `LIVE_READ_ACCEPTED`
- `LIVE_WRITE_ACCEPTED`
- `PILOT_READY`
- `BLOCKED_EXTERNAL`
- `DEFERRED_POST_PILOT`

Do not mark a capability more complete than the available evidence.

## Baseline

Starting repository baseline to verify at Round 0:
`65c51f4dfd0a3d9a7642a68814a58c21679038eb`

Round 0 must replace this if current main has advanced.

## Capability ledger

| Layer / capability | Implementation | Live acceptance | UX / productization | Automation | Reporting | Current blocker / evidence |
|---|---|---|---|---|---|---|
| Agency operating layer | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Reconcile current shell/navigation against V1 |
| Client workspace | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Verify real client-role scoping |
| Entitlement-aware navigation | IMPLEMENTED_NOT_ACCEPTED | n/a | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | Verify actual role/product behavior |
| Unified onboarding | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | readiness partial | Needs consolidated Managed/Co-Managed/Self-Service flow |
| Google connection lifecycle | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync partial | health partial | Reconcile current scopes/health; no unnecessary OAuth |
| Google provider resource mapping | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | n/a | Broad discovery must be privileged and tenant-safe |
| GBP operational product | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync/media/post workflows partial | partial | Reconcile current live/read/write evidence |
| Reviews | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | ingestion/reply workflow partial | partial | Reconcile current live/read/write evidence |
| Search Console | IMPLEMENTED_NOT_ACCEPTED | unknown | IMPLEMENTED_NOT_ACCEPTED | sync unknown | partial | Round 0 prove mapping/sync/freshness |
| GA4 | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | sync unknown | IMPLEMENTED_NOT_ACCEPTED | Period/comparison/freshness UX incomplete |
| SEO | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Reconcile crawl/GSC/recommendation lifecycle |
| Content | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Reconcile business facts/GitHub publication/verification |
| Leads | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | partial | partial | Provider dispatch/status semantics require proof |
| Integrations control plane | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | n/a | health partial | Needs central directory/detail/mapping convergence |
| Automation & Agents control plane | IMPLEMENTED_NOT_ACCEPTED | n/a | NOT_STARTED | IMPLEMENTED_NOT_ACCEPTED | NOT_STARTED | Existing engine must be surfaced/productized |
| Insights / reporting | IMPLEMENTED_NOT_ACCEPTED | partial | IMPLEMENTED_NOT_ACCEPTED | scheduled reporting partial/unknown | IMPLEMENTED_NOT_ACCEPTED | Governed metric and executive reporting convergence required |
| Release/production acceptance | IMPLEMENTED_NOT_ACCEPTED | partial | n/a | n/a | n/a | Round 0 reconcile deployment parity, migrations, Vercel/Render, backup/restore and pilot evidence |

## Known baseline questions Round 0 must answer

- Exact current main SHA and clean/dirty state.
- Exact frontend/API/worker/scheduler deployed SHAs.
- Current migration head and deployed DB migration state.
- Real agency-role and real client-role navigation/scoping.
- Whether client users can see unrelated Google provider resources.
- Source and semantics of any "17 locations" or similar cross-product metric.
- Source of contradictory product readiness states such as "Create the location profile" when provider data already exists.
- Current Google granted capabilities and whether any reauthorization is genuinely required.
- Current GSC and GA4 confirmed mappings, sync timestamps, periods, and data quality.
- Current workflow/schedule catalog and which handlers are actually scheduled/running.
- Lead email/SMS actual provider-dispatch and delivery semantics.
- Current reporting read models and period/comparison/freshness support.
- Current release-gate failures and genuine external blockers.

## Packet acceptance log

Append one entry per packet:

### Packet N — name
- Branch / commit:
- Auditor result:
- Principal result:
- Focused checks:
- Live checks:
- Ledger rows changed:
- Remaining blockers:
- Accepted: yes/no
