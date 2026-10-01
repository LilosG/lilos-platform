# Follow-on Phase Prompts

Use these only after the preceding phase is merged.

For every phase:

1. start from current merged `main`
2. read `MASTER_PLAN.md`
3. read all completed prior phase acceptance artifacts
4. inspect current code/contracts/tests
5. preserve the approved architecture
6. complete one coherent scope
7. run all relevant gates
8. open one PR
9. do not merge automatically

---

## Phase 2 — Integrations + Local Search

```text
Start from current merged main.

Read MASTER_PLAN.md, all completed Phase 0/0.5/1 artifacts, the acceptance matrix, and the current implementation.

Execute Phase 2: Integrations + Local Search.

Preserve the Phase 1 runtime/auth/BFF/adapter patterns.

Integrate authoritative contracts for:
- Integration status
- reconnect state
- provider mapping
- freshness/last sync
- Search Console
- GA4 where relevant to Local Search
- GBP
- rankings/local visibility
- Pages
- Technical
- crawl/page intelligence

Do not duplicate provider logic in Astro.
Do not flatten stale/partial/reconnect/error states.
Do not use fixtures in production paths.
Add purpose-built read models only where needed to prevent excessive fan-out or frontend inference.

Complete the vertical product area, tests, staging acceptance, and one coherent PR.

Do not begin Phase 3.
Do not merge automatically.
```

---

## Phase 3 — Reviews

```text
Start from current merged main.

Read MASTER_PLAN.md and all completed prior phase artifacts.

Execute Phase 3: Reviews.

Use canonical reviews/provider/workflow contracts.

Integrate:
- review inventory
- ratings/review metrics
- response state
- response drafting where supported
- policy/client-specific approval behavior
- publish state
- reconnect/provider errors
- audit/history

Do not impose a blanket approval gate.
Do not publish directly from browser code.
Do not hide unsupported provider states.

Complete staging acceptance, all required gates, and one coherent PR.

Do not begin Phase 4.
Do not merge automatically.
```

---

## Phase 4 — Website & Content

```text
Start from current merged main.

Read MASTER_PLAN.md and all completed prior phase artifacts.

Execute Phase 4: Website & Content.

Integrate authoritative:
- page inventory
- content
- technical website issues
- site-change opportunities
- content/publication workflows
- page mapping
- GitHub publishing
- build gates
- deployment verification
- website conversion-path data where it belongs in Website & Content

Reuse the Phase 1 governed change pattern.
Do not create a second publishing engine.
Do not edit repositories from Astro.
Do not build one-off templates.

Complete staging acceptance, all gates, and one coherent PR.

Do not begin Phase 5.
Do not merge automatically.
```

---

## Phase 5 — Leads / Conversion Outcomes

```text
Start from current merged main.

Read MASTER_PLAN.md and all completed prior phase artifacts.

Execute Phase 5: Leads / Conversion Outcomes.

Preserve the product boundary:
- Website & Content / Conversions = site journey/friction/CTA behavior
- Leads = measured business outcomes

Integrate authoritative lead/outcome data only.
Preserve unavailable vs zero semantics.
Preserve source attribution limitations.
Do not fabricate completed outcomes when no provider/source exists.

Complete staging acceptance, tests, and one coherent PR.

Do not begin Phase 6.
Do not merge automatically.
```

---

## Phase 6 — Automations

```text
Start from current merged main.

Read MASTER_PLAN.md and all completed prior phase artifacts.

Execute Phase 6: Automations.

Use canonical workflow/schedule/job records.

Build the approved exception-first UX:
- Requires Attention
- Upcoming Important Runs
- Recent Meaningful Outcomes
- Operational Health
- All Automations

Preserve durable workflow state.
Do not create a frontend scheduler.
Do not infer success before reconciliation.
Expose retry/recovery only through canonical backend actions.

Complete staging acceptance, tests, and one coherent PR.

Do not begin Phase 7.
Do not merge automatically.
```

---

## Phase 7 — Reports

```text
Start from current merged main.

Read MASTER_PLAN.md and all completed prior phase artifacts.

Execute Phase 7: Reports.

Integrate authoritative:
- report readiness
- data readiness
- scheduled/upcoming
- sent/history
- generation state
- typed blockers

Do not infer readiness in browser code.
Add canonical backend read models if required.
Preserve missing/stale/partial source semantics.

Complete staging acceptance, tests, and one coherent PR.

Do not begin Phase 8.
Do not merge automatically.
```

---

## Phase 8 — Client Overview + Portfolio

```text
Start from current merged main.

Read MASTER_PLAN.md and all completed prior phase artifacts.

Execute Phase 8: Client Overview + Portfolio.

Only now build aggregate dashboards from already-integrated domains.

Client Overview hierarchy:
- current growth focus
- attention/opportunities
- performance snapshot
- drivers
- guest/customer journeys where relevant
- recent work
- coming next
- operational health

Portfolio hierarchy:
- attention
- opportunities
- KPIs
- client portfolio
- upcoming/activity/health

Use purpose-built read models where aggregation is needed.
Do not duplicate domain calculations in Astro.

Complete staging acceptance, performance validation, all gates, and one coherent PR.

Do not begin Phase 9.
Do not merge automatically.
```

---

## Phase 9 — Administration / Settings / Onboarding

```text
Start from current merged main.

Read MASTER_PLAN.md and all completed prior phase artifacts.

Execute Phase 9: Administration / Settings / Onboarding.

Migrate the remaining valid operational capabilities from the old frontend, including only those confirmed by the Phase 0 non-regression inventory.

Preserve:
- server-side route protection
- backend permission authority
- onboarding invariants
- integration mapping
- reconnect behavior
- admin-only diagnostics
- organization/location management where supported

Do not expose test-harness material to normal users.
Do not duplicate admin authorization in Astro.

Complete staging acceptance, all gates, and one coherent PR.

Do not begin production rollout automatically.
Do not merge automatically.
```

---

## Production Acceptance / Canary

```text
Start from current merged main.

Read MASTER_PLAN.md and all completed phase acceptance artifacts.

Do not make unrelated product changes.

Execute the approved production acceptance sequence only:

1. verify staging sign-off remains green
2. verify production-canary readiness
3. use the approved LILOs Growth canary reset harness to create the controlled defect
4. allow normal production crawl/analyze flow to detect it
5. confirm the canonical Issue Opportunity
6. run normal Hermes recommendation flow
7. revise if required
8. approve exact revision
9. confirm workflow execution
10. confirm GitHub PR
11. confirm build gate
12. confirm merge/deploy
13. confirm live verification
14. record correlation/causation evidence
15. confirm canary returns to good state
16. run capacity/health acceptance

Do not touch a client asset.
Do not perform Google/GBP writes unless explicitly approved.
Do not broaden scope.

Produce a production acceptance report.
Do not start wider rollout without explicit owner approval.
```

---

## Gradual Rollout

```text
Start from the exact production-accepted main SHA.

Read MASTER_PLAN.md and the production acceptance report.

Execute only the approved gradual rollout:

1. operator-only
2. internal LILOs users
3. selected client cohort
4. wider client cohort
5. console becomes canonical

At every stage verify:
- auth/MFA
- tenant isolation
- errors
- latency/capacity
- workflows
- integrations
- no elevated 5xx
- no data leakage
- rollback remains available

Do not remove apps/web.

Stop immediately if acceptance thresholds fail.
Use the rollback path defined in MASTER_PLAN.md.

After sustained success, produce the final retirement-readiness report.
```

---

## apps/web Cleanup

```text
Start only after the new console has been canonical for the approved stability period and the retirement-readiness report is accepted.

Read MASTER_PLAN.md and all acceptance reports.

Create a dedicated cleanup branch/PR.

Remove only:
- apps/web
- obsolete compatibility code proven unused
- obsolete old-frontend deployment configuration
- obsolete transitional API/schema compatibility after verification

Do not remove canonical backend capabilities.
Do not remove audit/history.
Do not remove compatibility still used by any external caller.

Run the full repository suite and migration checks.

Produce a cleanup inventory and rollback note.

Do not merge automatically.
```
