# ROUND 0 — Principal Reconciliation Prompt

You are the `release-integrator`.

Do not begin broad product implementation.

Read and obey:
- `AGENTS.md`
- `docs/governing/LILOS-MASTER-SPEC.md`
- `docs/PLATFORM-CONSOLIDATION-RELEASE.md`
- `docs/governing/LILOS-BUILD-ROADMAP.md`
- `docs/governing/LILOS-MASTER-BUILD-PROMPT.md`
- `docs/governing/LILOS-FINISH-LINE-HANDOFF.md`
- `docs/PLATFORM-RELEASE-LEDGER.md`
- `docs/VISUAL-UX-REFERENCE-NOTES.md`

Current repository truth supersedes historical status descriptions.

## Objective

Establish a factual release baseline and the exact shared-contract/ownership map needed to execute Platform Consolidation without architectural drift.

## Round 0 permissions

Do not modify product/backend/frontend/migration/infrastructure code.

You may update only:
- `docs/PLATFORM-RELEASE-LEDGER.md`
- `docs/PLATFORM-CONSOLIDATION-RELEASE.md` if a repository fact requires a clarification that does not contradict the Master Spec
- a new `docs/PLATFORM-OWNERSHIP-MAP.md`
- a new `docs/PLATFORM-PACKET-PLAN.md`

Do not change external provider configuration, Google Cloud, Render, Vercel, Supabase data, or production state.

## Required investigation

1. Confirm current branch/SHA/working tree and compare to ledger baseline.
2. Map repo structure for frontend, API, services, integrations, workflows, worker, scheduler, reporting, tests, migrations, infrastructure.
3. Identify canonical models/services/read models for:
   - org/location/entitlements;
   - onboarding/readiness;
   - provider connections/accounts/resources/mappings;
   - GBP;
   - Reviews;
   - SEO/GSC/GA4;
   - Content/GitHub publishing;
   - Leads/notifications;
   - Insights/reporting;
   - workflow/job/schedule/approval/retry/reconciliation/audit.
4. Trace current agency/client navigation and authorization boundaries.
5. Trace how product readiness is computed and identify any duplicated/contradictory source of truth.
6. Trace Google connection state/granted capabilities and product consumption contracts. Do not initiate OAuth.
7. Trace provider discovery/mapping and whether normal client workspace data can include unrelated provider resources.
8. Trace current automation schedule registrations/handlers and which V1 product operations already have durable workflows.
9. Trace lead communication status semantics from planned → queued/provider accepted/delivered/failed if those states exist.
10. Trace Insights metric definitions, periods/comparisons/freshness/source/data-quality support.
11. Identify shared files/contracts that specialist workstreams must not modify concurrently.
12. Define branch/file ownership boundaries for Integrations, Automation, Product UX, and Insights/Reporting.
13. Build exact packet dependency graph and acceptance scenarios.
14. Update the release ledger from evidence. If live evidence is unavailable, mark it unknown/not accepted rather than guessing.

## Deliverables

Create:
- `docs/PLATFORM-OWNERSHIP-MAP.md`
- `docs/PLATFORM-PACKET-PLAN.md`

Update:
- `docs/PLATFORM-RELEASE-LEDGER.md`

Return a concise report:
- exact baseline;
- architecture already present;
- confirmed consolidation gaps;
- highest-risk cross-cutting issues;
- packet dependency graph;
- files/contracts reserved to principal;
- which work may safely parallelize after Packet 1;
- Round 0 PASS/FAIL.

Do not start Packet 1 until Round 0 artifacts are complete and internally consistent.
