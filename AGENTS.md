# LILOs Platform — Agent Constitution

This file applies to every OpenCode agent working in this repository.

## Authority and precedence

Use this order when instructions conflict:

1. `docs/governing/LILOS-MASTER-SPEC.md` — architecture, product, security, data, workflow, integration, release requirements.
2. `docs/PLATFORM-CONSOLIDATION-RELEASE.md` — the current commercial V1 target and platform consolidation contract.
3. `docs/governing/LILOS-BUILD-ROADMAP.md` — build sequencing where still relevant.
4. `docs/governing/LILOS-MASTER-BUILD-PROMPT.md` — implementation discipline.
5. `docs/PLATFORM-RELEASE-LEDGER.md` — current acceptance status, not architecture authority.
6. Current repository truth — authoritative for what actually exists now.
7. Historical chats/handoffs — evidence and context only; never implementation authority.

If a governing document is missing, report it. Do not silently replace it with assumptions.

## Release goal

Deliver one coherent commercial V1 of the complete LILOs platform, not a collection of isolated modules.

Required platform layers:

- Agency operating layer.
- Client workspace.
- Modular product entitlements.
- Managed by LILOs, Co-Managed, and Self-Service onboarding modes using one underlying onboarding engine.
- Centralized Integrations control plane.
- Operational products: GBP, Reviews, SEO, Content, Leads, Insights.
- Automation & Agents control plane powered by the existing workflow/worker/scheduler runtime.
- Governed AI tasks embedded in product workflows.
- Cross-product Insights and Reporting.
- Approvals, work queues, failures, activity, audit, and settings.
- Production-safe tenant isolation, authorization, idempotency, reconciliation, observability, and release controls.

## Platform boundaries

### Integrations owns external systems

Connections, credentials, OAuth, provider accounts, provider resource discovery, mappings, webhooks, capability health, and sync health belong to Integrations.

Operational products consume confirmed integration state.

Do not duplicate provider configuration inside GBP, Reviews, SEO, Content, Leads, or Insights.

### Operational products own business work

GBP, Reviews, SEO, Content, Leads, and Insights must primarily answer what the operator can do, what changed, what needs attention, and what work is next.

A product may show concise integration health and a link to Manage Integration. It must not expose broad provider discovery/mapping machinery during normal operation.

### Automation & Agents is a first-class product layer

Use the existing workflow registry, worker, scheduler, job, approval, retry, reconciliation, audit, and notification architecture.

Do not install or introduce a parallel agent orchestration framework unless the Master Spec is formally amended.

An LILOs "agent" is a governed workflow containing deterministic and/or AI-assisted tasks, with schemas, validation, permissions, approvals, limits, observability, and recovery.

### Insights and Reporting use governed metrics

Never manufacture a metric to fill a dashboard.

Never treat missing data as zero.

Metrics require meaningful period/context, source/freshness, and data-quality state where applicable.

## Non-negotiable engineering rules

- Inspect repository truth before proposing or implementing changes.
- Diagnose evidence first. Do not code from a hypothesized root cause.
- Reuse canonical services, repositories, contracts, and workflow infrastructure.
- No duplicate architecture.
- No direct production SQL repairs or bypasses.
- No invented provider IDs, mappings, credentials, or provider state.
- No front-end-only authorization or tenancy fixes; backend remains authoritative.
- Preserve tenant isolation and least privilege.
- Preserve immutable/auditable state transitions.
- Preserve idempotency and provider reconciliation for writes.
- Do not declare live provider acceptance based on unit tests.
- Do not declare a platform layer complete because one module inside it works.
- Do not broaden a packet when adjacent work is discovered. Record adjacent work in the release ledger.
- Do not silently change deployment, hosting, authentication, database, or integration architecture.
- Do not edit Google Cloud/provider configuration without concrete provider evidence requiring it.
- Do not weaken security, approvals, migrations, CI, tests, backup/recovery, accessibility, or release gates to move faster.
- Do not add unrelated products/integrations during platform consolidation.

## User experience contract

The interface must hide implementation complexity unless the user is in a privileged diagnostic/admin surface.

Agency users need portfolio health, requires-attention queues, today's work, approvals, automation state, reporting readiness, and recent activity.

Client users need account status, results, what changed, required actions, completed work, upcoming work, and freshness.

Navigation must respect role, scope, entitlement, and readiness.

A client workspace must never expose unrelated provider resources, organizations, locations, or administrative capabilities.

## Onboarding contract

One resumable onboarding engine supports:

- Managed by LILOs.
- Co-Managed.
- Self-Service.

Underlying sequence:

Business → Locations → Products → Integrations → Resource Mapping → Configuration → Automation Defaults → Readiness Review → Activate.

The operating mode determines who performs each step; it does not create separate onboarding architecture.

## Verification discipline

During implementation use focused tests for the changed behavior.

At packet acceptance, run the relevant focused integration/regression checks.

Run the expensive full repository/release gate once the integrated release candidate is stable.

Canonical repository commands include:

- `npm run format:check`
- `npm run lint`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run check:secrets`
- `npm run check:browser`
- `npm run check:release`
- `npm run check:production-preflight`
- `npm run db:current`

Use narrower workspace/Python commands during development when appropriate.

## Completion vocabulary

Use only evidence-backed states:

- `NOT_STARTED`
- `IMPLEMENTED_NOT_ACCEPTED`
- `LIVE_READ_ACCEPTED`
- `LIVE_WRITE_ACCEPTED`
- `PILOT_READY`
- `BLOCKED_EXTERNAL`
- `DEFERRED_POST_PILOT`

"Implemented" is not synonymous with "live accepted."

## Git / collaboration rules

- Never push directly unless the user explicitly requests it.
- Never force-push.
- Never reset or clean away work you did not create.
- Specialists do not merge themselves.
- Parallel coding happens only in isolated worktrees after shared contracts/ownership are frozen.
- Principal release integrator owns cross-cutting contracts and integration of specialist work.

## Required completion report for every execution packet

Return:

1. Repository state inspected.
2. Existing implementation discovered and reused.
3. Evidence-backed gaps.
4. Changes implemented.
5. Files changed.
6. Focused tests and results.
7. Acceptance scenarios and PASS/FAIL.
8. Remaining blockers/risks.
9. Exact release-ledger updates.
10. Adjacent work discovered but intentionally not implemented.
