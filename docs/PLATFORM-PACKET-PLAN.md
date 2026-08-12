# LILOs Platform Packet Plan

**Created:** 2026-08-11
**Purpose:** Exact packet dependency graph, acceptance scenarios, and exit criteria for the Platform Consolidation release.

## Packet dependency graph

```
Packet 0 (Baseline) ─── THIS ROUND
    │
    ▼
Packet 1 (Platform IA) ─── establishes frozen shared contracts
    │
    ├──► Packet 2 (Unified Onboarding) ─── depends on Packet 1 contracts
    │
    ├──► Packet 3 (Integration Control Plane) ─── isolated worktree after Packet 1
    │         │
    │         ▼
    ├──► Packet 4 (Product UX Convergence) ─── isolated worktree after Packet 1;
    │         │                                  consumes Packet 3 contracts
    │         ▼
    ├──► Packet 5 (Automation & Agents) ─── isolated worktree after Packet 1
    │
    └──► Packet 6 (Insights & Reporting) ─── after product/integration data contracts stabilize
              │
              ▼
         Packet 7 (Productization & Release Acceptance) ─── integrated release branch only
```

## Packet 0 — Baseline and Contract Map

**Status:** IN PROGRESS (this round)
**Owner:** Principal Release Integrator
**Permissions:** Read-only for product code; may update release/control documentation only

### Acceptance scenarios

1. **SC0-BASELINE:** Current branch, SHA, and working tree are confirmed and recorded.
   - **Evidence:** `git rev-parse HEAD`, `git status --porcelain`, `git log --oneline -10`
   - **Expected:** Branch `release/platform-consolidation`, SHA `35cf577`, clean tree

2. **SC0-STRUCTURE:** Repository structure is mapped for frontend, API, services, integrations, workflows, worker, scheduler, reporting, tests, migrations, infrastructure.
   - **Evidence:** Complete directory tree with file listings
   - **Expected:** All modules identified and documented in ownership map

3. **SC0-MODELS:** Canonical models/services/read models are identified for all domains.
   - **Evidence:** Domain trace covering org/location/entitlements, onboarding, integrations, GBP, Reviews, SEO, Content, Leads, Insights, workflow infrastructure
   - **Expected:** Every domain has identified owning files

4. **SC0-NAV:** Agency/client navigation and authorization boundaries are traced.
   - **Evidence:** `platform.ts` navigation groups, `AppShell.astro` rendering, `authorization/dependencies.py` guards
   - **Expected:** Navigation structure and auth boundaries documented

5. **SC0-READINESS:** Product readiness computation is traced and contradictory sources identified.
   - **Evidence:** `administration/service.py` readiness engine, `dashboard-logic.ts` summarization
   - **Expected:** Readiness chain documented; contradictory states identified

6. **SC0-GOOGLE:** Google connection state and product consumption contracts are traced.
   - **Evidence:** `connection_service.py` lifecycle, `granted_services()`, scope management
   - **Expected:** Connection lifecycle documented; no unnecessary OAuth triggers identified

7. **SC0-DISCOVERY:** Provider discovery/mapping and client workspace data leakage are traced.
   - **Evidence:** `gbp.astro` unmapped location rendering, `aggregation_service.py` counting
   - **Expected:** Leakage paths identified; P0 issues documented

8. **SC0-AUTOMATION:** Automation schedule registrations and handlers are traced.
   - **Evidence:** `workflow_catalog.py` WORKFLOW_TYPES, `handlers.py` _REGISTRY
   - **Expected:** 9 registered handlers documented; schedule activation state noted

9. **SC0-LEADS:** Lead communication status semantics are traced.
   - **Evidence:** `LeadCommunication` model status constraint, `_handle_leads_send_communication`
   - **Expected:** Status lifecycle documented; sent-vs-delivered gap noted

10. **SC0-INSIGHTS:** Insights metric definitions, periods, freshness, and data-quality support are traced.
    - **Evidence:** `aggregation_service.py`, `MetricObservation.quality_state`, GA4 adapter
    - **Expected:** Metric governance documented; period/comparison gap noted

11. **SC0-SHARED:** Shared files/contracts that specialist workstreams must not modify concurrently are identified.
    - **Evidence:** Ownership map collision matrix
    - **Expected:** All shared contracts listed with owner

12. **SC0-OWNERSHIP:** Branch/file ownership boundaries are defined for all specialists.
    - **Evidence:** `PLATFORM-OWNERSHIP-MAP.md`
    - **Expected:** Every file assigned to an owner

13. **SC0-LEDGER:** Release ledger is updated from evidence.
    - **Evidence:** `PLATFORM-RELEASE-LEDGER.md` updated
    - **Expected:** All capabilities classified with evidence-backed states

### Exit criteria
- `PLATFORM-OWNERSHIP-MAP.md` created and internally consistent
- `PLATFORM-PACKET-PLAN.md` created (this file)
- `PLATFORM-RELEASE-LEDGER.md` updated with evidence-backed states
- All 13 acceptance scenarios PASS
- No product code modified

---

## Packet 1 — Platform Information Architecture

**Depends on:** Packet 0
**Owner:** Principal Release Integrator
**Specialists may assist:** Product UX (for page-level changes within frozen contracts)

### Objective
Establish agency/client boundaries, role/scope/entitlement-aware navigation, settings/integrations/automation placement, and removal of provider/setup leakage from normal product IA.

### Acceptance scenarios

1. **SC1-CLIENT-NAV:** Client-role user sees only Workspace, Operations (entitled products), Manage (Settings, Integrations if authorized), and no Admin group.
   - **Test:** Log in with real client-role account; inspect navigation DOM
   - **Expected:** Admin group not rendered (not just hidden); `/administration` and `/onboarding` return 403 with clear error

2. **SC1-AGENCY-NAV:** Agency-role user sees full navigation including Admin group.
   - **Test:** Log in with agency-role account; inspect navigation DOM
   - **Expected:** All groups visible; Admin group accessible

3. **SC1-GBP-SCOPE:** Client GBP page shows only confirmed mapped locations for that client's organization.
   - **Test:** Log in with Wheyland client role; navigate to `/gbp`
   - **Expected:** Only Wheyland managed locations visible; no unrelated business names

4. **SC1-DISCOVERY-ISOLATION:** Broad provider resource discovery is accessible only through privileged Integrations workflow.
   - **Test:** Agency operator navigates to Integrations → Google → Unmapped Resources
   - **Expected:** Discovery queue available; mapping controls functional

5. **SC1-READINESS-TRUTH:** Product readiness reflects actual managed state without contradictions.
   - **Test:** Verify GBP readiness for Wheyland (has synced location, 90 reviews)
   - **Expected:** GBP readiness shows "ready" or truthful blocker; not "Create the location profile" when location exists

6. **SC1-INSIGHTS-LOCATIONS:** Insights "Locations" count reflects only confirmed mapped locations, not all provider-discovered resources.
   - **Test:** Verify Insights summary for Wheyland
   - **Expected:** Location count matches confirmed managed locations only

7. **SC1-NAV-LABELS:** Navigation labels use operational language, not implementation vocabulary.
   - **Test:** Inspect all navigation item labels
   - **Expected:** No raw provider IDs, internal codes, or implementation terms

8. **SC1-EMPTY-STATES:** Every product page has intentional empty/loading/error/unauthorized states.
   - **Test:** Navigate to each product page as client with no data, as unauthenticated user, as unauthorized user
   - **Expected:** Appropriate states rendered; no blank pages or raw errors

9. **SC1-SHARED-CONTRACTS:** All shared contracts are frozen and documented.
   - **Test:** Verify ownership map freeze list matches current file state
   - **Expected:** No drift between documented and actual contracts

### Exit criteria
- All 9 acceptance scenarios PASS
- Client role cannot see unrelated provider resources (P0 release blocker resolved)
- Navigation communicates one coherent platform
- Shared contracts frozen for parallel work

---

## Packet 2 — Unified Onboarding

**Depends on:** Packet 1
**Owner:** Principal Release Integrator (may delegate to specialist with frozen contracts)

### Objective
Managed, Co-Managed, Self-Service responsibility modes over one resumable engine. Shared business/location/product/integration/mapping/config/readiness path.

### Acceptance scenarios

1. **SC2-MANAGED:** Agency operator can complete full onboarding for a new client through the UI.
   - **Test:** Create organization → add location → assign products → connect Google → map resources → configure → review readiness → activate
   - **Expected:** All steps completable without direct DB manipulation

2. **SC2-CO-MANAGED:** Client can complete bounded setup steps assigned by agency.
   - **Test:** Agency preconfigures; client completes remaining steps
   - **Expected:** Client sees only their assigned steps; agency sees full state

3. **SC2-SELF-SERVICE:** Client can complete full self-service onboarding.
   - **Test:** Client creates account → adds business → selects products → connects integrations → configures → activates
   - **Expected:** Full flow completable; appropriate guidance at each step

4. **SC2-RESUMABLE:** Onboarding can be paused and resumed without data loss.
   - **Test:** Start onboarding, close browser, reopen, continue
   - **Expected:** State preserved; no duplicate steps required

5. **SC2-READINESS-DERIVED:** Readiness is derived from authoritative domain/integration state, not duplicated UI flags.
   - **Test:** Verify readiness computation uses `AdministrationService.readiness()` only
   - **Expected:** No separate readiness flags; single source of truth

6. **SC2-ACTIVATION:** Product activation requires validated readiness.
   - **Test:** Attempt to activate product with missing integration
   - **Expected:** Activation blocked with clear remediation

### Exit criteria
- New account can reach activation without direct DB manipulation
- All three operating modes functional
- Readiness is single source of truth

---

## Packet 3 — Integration Control Plane

**Depends on:** Packet 1
**Owner:** Integrations Specialist
**Isolated worktree:** Yes

### Objective
Provider directory/detail workspaces, Google/GitHub/email/SMS configuration and health, privileged provider-resource mapping, confirmed product dependencies.

### Acceptance scenarios

1. **SC3-DIRECTORY:** Integrations page shows provider directory with connection status per provider.
   - **Test:** Navigate to `/integrations`
   - **Expected:** Google, GitHub, email, SMS cards with connected/degraded/action-required status

2. **SC3-GOOGLE-WORKSPACE:** Google provider detail shows credential health, granted capabilities, account, mappings, sync freshness.
   - **Test:** Click Google from directory
   - **Expected:** GBP/GSC/GA4 capability status; last sync timestamps; mapped resources

3. **SC3-MAPPING-QUEUE:** Unmapped resources queue is admin-only, searchable, collapsible.
   - **Test:** Agency operator views Google workspace; client role attempts same
   - **Expected:** Agency sees mapping queue; client does not

4. **SC3-CONNECT-ONCE:** Google connection established once serves GBP, GSC, and GA4.
   - **Test:** Connect Google with all scopes; verify all three products show connected
   - **Expected:** Single connection row; all capabilities granted

5. **SC3-NO-UNNECESSARY-OAUTH:** Healthy fully-scoped connection does not prompt OAuth on normal navigation.
   - **Test:** Navigate between pages with healthy connection
   - **Expected:** No OAuth redirect; no consent screen

6. **SC3-INCREMENTAL-SCOPE:** Adding a new product scope performs incremental authorization only.
   - **Test:** Connect with GBP only; later enable GSC
   - **Expected:** Single incremental consent for new scope; existing scopes preserved

7. **SC3-HEALTH-DEGRADED:** Expired or revoked credentials show degraded state with clear remediation.
   - **Test:** Simulate expired token
   - **Expected:** "Reconnect required" status; clear action button

8. **SC3-GITHUB:** GitHub App installation and repository discovery functional.
   - **Test:** Install GitHub App; discover repositories
   - **Expected:** Repositories listed; publishing target configurable

### Exit criteria
- Connect once, map once, consume everywhere
- Provider health visible and actionable
- No unnecessary OAuth prompts

---

## Packet 4 — Operational Product Convergence

**Depends on:** Packet 1 (contracts), Packet 3 (integration state)
**Owner:** Product UX Specialist
**Isolated worktree:** Yes (against frozen contracts)

### Objective
GBP, Reviews, SEO, Content, Leads become focused operating workspaces consuming centralized integrations.

### Acceptance scenarios

1. **SC4-GBP-OPERATIONAL:** GBP page is an operational workspace, not a discovery dump.
   - **Test:** Navigate to `/gbp` with confirmed mapped location
   - **Expected:** Profile overview, posts, media, performance, recommendations; no unmapped discovery list

2. **SC4-REVIEWS-WORKFLOW:** Review inbox shows status, response workflow, approvals.
   - **Test:** View reviews for mapped location
   - **Expected:** Review list with status; draft/approve/publish flow

3. **SC4-SEO-RECOMMENDATIONS:** SEO page shows opportunities, recommendations, implementation state.
   - **Test:** View SEO with synced GSC data
   - **Expected:** Prioritized opportunities; recommendation lifecycle

4. **SC4-CONTENT-PUBLISHING:** Content page supports opportunity → brief → draft → approve → publish flow.
   - **Test:** Create content item through full lifecycle
   - **Expected:** Each state transition functional; GitHub PR created on publish

5. **SC4-LEADS-PIPELINE:** Leads page shows intake, routing, assignment, status.
   - **Test:** View leads with test data
   - **Expected:** Lead list with status; assignment controls; communication history

6. **SC4-PRODUCT-HEALTH:** Each product shows concise integration health and link to Manage Integration.
   - **Test:** View each product page
   - **Expected:** Small health indicator; link to `/integrations`; no broad provider configuration

7. **SC4-SETUP-BLOCKER:** Incomplete setup shows one bounded blocking banner, not a full-page setup dump.
   - **Test:** View product with missing integration
   - **Expected:** Single banner with direct action; product UI still partially visible

### Exit criteria
- Normal product pages primarily answer what can be done and what requires attention
- No provider discovery leakage in product workspaces
- Setup blockers are bounded and actionable

---

## Packet 5 — Automation & Agents

**Depends on:** Packet 1 (contracts), Packet 3 (integration state)
**Owner:** Automation & Agents Specialist
**Isolated worktree:** Yes

### Objective
Productize existing workflow/worker/scheduler runtime and complete required V1 automation visibility/execution paths.

### Acceptance scenarios

1. **SC5-CATALOG:** Automation catalog shows all registered workflow types with status.
   - **Test:** Navigate to Automation surface
   - **Expected:** GBP sync, review ingestion, content publish, SEO crawl, etc. listed with active/paused/attention state

2. **SC5-SCHEDULES:** Scheduled workflows show cron expression, last run, next run, status.
   - **Test:** View schedule for `gbp.sync`
   - **Expected:** Schedule details visible; last/next run timestamps

3. **SC5-RUN-HISTORY:** Workflow run history shows status, duration, result per run.
   - **Test:** View run history for a workflow type
   - **Expected:** List of runs with timestamps, status, step details

4. **SC5-APPROVALS:** Approval-required workflows pause and await human decision.
   - **Test:** Trigger approval-requiring workflow
   - **Expected:** Workflow pauses at approval step; approval action advances workflow

5. **SC5-FAILURES:** Failed workflows show error details, retry count, and manual recovery path.
   - **Test:** Trigger workflow failure
   - **Expected:** Failure visible with error category; retry/recovery options

6. **SC5-SCHEDULED-EXECUTION:** Scheduled workflows execute without dashboard open.
   - **Test:** Set schedule; close dashboard; verify execution after scheduled time
   - **Expected:** Workflow runs on schedule; results visible on next dashboard load

7. **SC5-CLIENT-VISIBILITY:** Client surface shows understandable automation status without internal diagnostics.
   - **Test:** Log in as client; view automation
   - **Expected:** "Last synced 2 hours ago" not "Worker PID 1234 lease expired"

### Exit criteria
- LILOs visibly performs durable scheduled/background work when no dashboard is open
- Automation status understandable by both agency and client users
- All 9 registered handlers have observable execution paths

---

## Packet 6 — Insights & Reporting

**Depends on:** Packet 1 (contracts), Packet 3 (integration data), Packet 4 (product data)
**Owner:** Insights & Reporting Specialist
**Isolated worktree:** Yes (after product data contracts stabilize)

### Objective
Governed cross-product metrics, periods/comparisons/freshness, agency/client dashboards, completed work, automation activity, report workflow.

### Acceptance scenarios

1. **SC6-GOVERNED-METRICS:** Every displayed metric has a defined source, period, freshness, and data-quality state.
   - **Test:** Inspect each KPI on dashboard
   - **Expected:** Source label, period, last sync timestamp, quality indicator

2. **SC6-NO-FABRICATED:** No metric is manufactured to fill a dashboard; missing data is not treated as zero.
   - **Test:** Disconnect GA4; view dashboard
   - **Expected:** GA4 metrics show "unavailable" not "0"

3. **SC6-PERIOD-COMPARISON:** Metrics support period selection and comparison where data supports it.
   - **Test:** Select different periods; view comparison
   - **Expected:** Current period vs prior period shown; trend direction indicated

4. **SC6-CROSS-PRODUCT:** Dashboard aggregates data across entitled products.
   - **Test:** Enable GBP + Reviews + SEO; view dashboard
   - **Expected:** Metrics from all three products visible; no cross-contamination

5. **SC6-AGENCY-DASHBOARD:** Agency dashboard shows portfolio-level KPIs, requires attention, today's work.
   - **Test:** Agency operator views dashboard
   - **Expected:** Outcome KPIs, attention queue, work queue in first viewport

6. **SC6-CLIENT-DASHBOARD:** Client dashboard shows simplified outcome view.
   - **Test:** Client user views dashboard
   - **Expected:** Account status, 3-5 KPIs, what changed, requires attention, completed work

7. **SC6-REPORTS:** Scheduled reports can be defined, generated, and delivered.
   - **Test:** Create report definition; trigger generation; verify delivery
   - **Expected:** Report generated with immutable snapshot; delivery tracked

8. **SC6-DATA-QUALITY:** Data-quality issues are surfaced, not hidden.
   - **Test:** Introduce stale sync; view dashboard
   - **Expected:** Stale data indicator; last successful sync shown

### Exit criteria
- A client can understand outcomes and LILOs work from the platform
- No fabricated metrics
- Period/comparison/freshness semantics clear

---

## Packet 7 — Productization and Release Acceptance

**Depends on:** Packets 1-6
**Owner:** Principal Release Integrator
**Worktree:** Integrated release branch only

### Objective
Consistent UX, terminology, empty/error states, accessibility/responsive/browser acceptance, tenant-role acceptance, real integration acceptance, focused live writes where authorized, full release gate.

### Acceptance scenarios

1. **SC7-UX-CONSISTENCY:** Cards, tabs, tables, spacing, type scale, button hierarchy consistent across all pages.
   - **Test:** Visual review of all pages
   - **Expected:** Consistent patterns; no visual drift between products

2. **SC7-TERMINOLOGY:** Operational language used throughout; no implementation vocabulary.
   - **Test:** Text review of all pages
   - **Expected:** No raw provider IDs, internal codes, database column names

3. **SC7-STATES:** Every interactive element has loading, empty, error, success, and unauthorized states.
   - **Test:** Exercise each state per page
   - **Expected:** Appropriate state rendered; no blank pages

4. **SC7-ACCESSIBILITY:** Critical workflows pass keyboard navigation and screen reader checks.
   - **Test:** Run Playwright accessibility tests
   - **Expected:** No critical violations

5. **SC7-RESPONSIVE:** Critical workflows functional on mobile viewport.
   - **Test:** Run Playwright mobile tests
   - **Expected:** Navigation, forms, tables usable on mobile

6. **SC7-BROWSER:** Critical workflows functional in Chromium.
   - **Test:** Run Playwright browser tests
   - **Expected:** All browser tests pass

7. **SC7-TENANT-ROLE:** Cross-tenant and cross-role access attempts fail correctly.
   - **Test:** Attempt cross-org access; attempt unauthorized action
   - **Expected:** 403 with clear error; no data leakage

8. **SC7-LIVE-WRITES:** Controlled provider writes complete with full verification chain.
   - **Test:** Execute bounded write window for GitHub PR, GBP post, review reply
   - **Expected:** Approval → idempotency → write → re-read → verification → reconciliation → audit

9. **SC7-RELEASE-GATE:** Full release gate passes.
   - **Test:** Run `npm run check:release`, `npm run check:production-preflight`
   - **Expected:** All checks pass

### Exit criteria
- Coherent controlled-pilot commercial V1
- All release gate checks pass
- Known pilot-disabled capabilities explicitly labeled

---

## Packet dependency constraints

| Packet | Must complete before | May parallelize with |
|--------|---------------------|---------------------|
| 0 | 1 | — |
| 1 | 2, 3, 4, 5 | — |
| 2 | 7 | 3, 4, 5 (with frozen contracts) |
| 3 | 4, 6, 7 | 2, 5 (isolated worktrees) |
| 4 | 6, 7 | 2, 3, 5 (isolated worktree, frozen contracts) |
| 5 | 7 | 2, 3, 4 (isolated worktree) |
| 6 | 7 | — (requires stable product data) |
| 7 | — | — (integrated branch only) |

## Risk register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Client scope leakage (P0) | Release blocker | Packet 1 must resolve before any client login |
| Contradictory readiness states | High | Packet 1 must trace and repair owning service |
| Vercel deployment rate-limited | Medium | Operational resolution; not a code fix |
| Lead communication sent-vs-delivered semantics | Medium | Packet 5/6 must verify; pilot-disable if unproven |
| GA4 period/comparison missing | Medium | Packet 6 must implement or truthfully document gap |
| No active automation schedules in DB | Medium | Packet 5 must create and activate schedules |
| Live write acceptance unproven | Medium | Packet 7 controlled write window |
| Migration head not deployed to production | High | Packet 0 must verify deployment parity |