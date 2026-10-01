# Phase 0 — Command Center integration contract

Recorded: 2026-09-30. Execution branch: `command-center/phase-0`.
Scope: discovery and design only. No console application, production data change,
provider setup, infrastructure provisioning, or Phase 0.5 implementation.

## Evidence and authority

Every statement in a table inherits its Evidence column or the explicit label
preceding the table. `VERIFIED CURRENT FACT` means inspected code, configuration,
test results, or a named read-only remote response; it does not imply live acceptance.
`NOT YET VERIFIED` means runtime evidence has not been obtained and does not prevent architecture definition. `VERIFIED BASELINE ISSUE` annotates an observed failure under `VERIFIED CURRENT FACT`.
`PROPOSED DESIGN` is a future implementation requirement. `BLOCKER` means evidence
is absent or a check failed. `OWNER ACTION REQUIRED` identifies external decisions
and account operations that the coding agent cannot complete in this phase.

VERIFIED CURRENT FACT: root `AGENTS.md`, `CLAUDE.md`, `MASTER_PLAN.md`, and
`PHASE_00_PROMPT.md` were read in full before changes. All four governing documents
exist under `docs/governing/`; the consolidation release contract and release ledger
were inspected. AGENTS authority precedence governs the older CLAUDE instruction
that treats historical docs as background. No runtime architecture was amended.

## A. Exact baselines and topology

| Evidence              | Item                                 | Recorded result                                                                                                                                                                                                                               |
| --------------------- | ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| VERIFIED CURRENT FACT | Platform merged main / starting HEAD | `0d505db70233f54f69729a85979a9c2d093fdee2`; remote `refs/heads/main` matched; clean initial tree; branch retained                                                                                                                             |
| VERIFIED CURRENT FACT | Approved UI main                     | `d097c5255995b010f45b67a8ace90a80d00f090b`, `LilosG/lilos-command-center-astro`; independent remote recheck matched                                                                                                                           |
| VERIFIED CURRENT FACT | Canary site source main              | `fc8f63c6faaa55b98908b644cbf8db4694f80a3d`, `LilosG/lilos-growth`; read-only checkout outside platform                                                                                                                                        |
| PROPOSED DESIGN       | Permanent UI tag                     | Annotated `command-center-ui-baseline-2026-09-30` at `d097c525`; never move it; tag annotation must retain the browser failure below                                                                                                          |
| OWNER ACTION REQUIRED | Remote UI tag                        | No such remote tag existed at inspection. Publish the permanent reference in the UI repository before importing into the platform; this packet pushes only the requested platform branch                                                      |
| VERIFIED CURRENT FACT | Platform lock versions               | Astro 7.3.2, Tailwind 4.3.3, TypeScript 6.0.3, Vitest 4.1.11, Playwright 1.63.0, Supabase JS dependency range ^2.112.0                                                                                                                        |
| VERIFIED CURRENT FACT | UI lock versions                     | Astro 7.3.5, Tailwind 4.3.3, TypeScript 6.0.3, Vitest 5.0.3, Playwright 1.63.0; static output, trailing slash always                                                                                                                          |
| VERIFIED CURRENT FACT | Python environment                   | FastAPI 0.141.1, Pydantic 2.13.4, SQLAlchemy 2.0.51, Alembic 1.18.5; local Python 3.13.11; backend Docker Python 3.12.12, uv 0.9.28                                                                                                           |
| VERIFIED CURRENT FACT | Node tooling                         | Repository npm 10.9.2 pin, Node >=22; sandbox Node 26.7.0/npm 11.19.0; escalated shell Node 22.17.1/npm 10.9.2. UI install warned its parser/undici require a newer Node patch                                                                |
| PROPOSED DESIGN       | Console runtime                      | Pin a supported Node 22 patch satisfying all locked engines (at least 22.22.3 for inspected UI parser), Astro SSR with Vercel Node adapter; validate rather than copy static config                                                           |
| VERIFIED CURRENT FACT | Existing web deployment              | Vercel `lilos-platform-web`; `dpl_3Hf2UGniCCBMsH68q1rGuw7MrECe` READY production at platform baseline, confirmed by `list_deployments`                                                                                                        |
| VERIFIED CURRENT FACT | Backend declared deployment          | `render.yaml`: API web, worker, scheduler worker, Hermes private Docker service, all Oregon, main, checks-pass deploy; Hermes disk 5 GB at `/opt/data`, pinned `v2026.8.19`                                                                   |
| VERIFIED CURRENT FACT | Current browser auth                 | `apps/web/astro.config.mjs` static; `supabase-client.ts` browser client with persisted session and auto-refresh; `api-client.ts` sends Bearer directly to API, refreshes once on 401                                                          |
| VERIFIED CURRENT FACT | Backend auth authority               | Supabase issuer/audience/JWKS verification in `authentication/verifier.py`; active platform UserProfile mapping; fixed authorization dependencies, membership/location/permission/entitlement/readiness and AAL checks                        |
| VERIFIED CURRENT FACT | Durable execution                    | `execution/{runtime,service,models,handler_resolver,workflow_catalog}.py`, `apps/worker`, `apps/scheduler`, `agents/{service,hermes_client,execution_handler}.py`; PostgreSQL jobs, attempts, schedules and governed agent runs               |
| NOT YET VERIFIED      | Live Render/Supabase state           | Render MCP returned no selected workspace and requires user selection; no live service/region/DB inventory verified. Vercel `get_project` failed connector argument validation (`idOrName`) on both attempts. No Supabase connector available |

VERIFIED CURRENT FACT: platform merged-main CI run
[36808002497](https://github.com/LilosG/lilos-platform/actions/runs/36808002497)
has successful frontend, Python static/policy, four Python shard, and DB integrity jobs.
Local checks and their limits are separately recorded in `ACCEPTANCE_MATRIX.md`.

VERIFIED CURRENT FACT — VERIFIED BASELINE ISSUE: the UI suite is `check`, `typecheck`, `lint`, `test`,
`test:browser`, `build` in its `package.json`. Check (136 files, no diagnostics),
TS, lint, 6 unit tests, and build (240 routes) passed. Locked install audited 416
packages with zero vulnerabilities. Full browser suite: **46 passed, 1 failed**;
focused rerun failed the same navigation test at line 131 (it also reported a browser session closure; root cause unproven). Full-run failure: dialog absent after
pointer click on Opportunity 13. Evidence: `tests/browser/navigation.spec.ts:121`,
`OpportunityRow.astro`, `interactions.ts`. This is a failed baseline journey,
not permission to redesign or alter the source repository in this packet.

## B. Existing frontend non-regression inventory

VERIFIED CURRENT FACT: these are implemented source capabilities, not a claim that
each is currently live accepted. Paths are relative to `apps/web/src`; backend
routes are in `apps/api/app/routes`. KEEP preserves behavior; REPLACE UX retains
capability in approved presentation; MOVE changes its product home.

| Capability                                                                                               | Disposition        | Existing evidence and required preservation                                                                                                                                   |
| -------------------------------------------------------------------------------------------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Password sign-in and sign-out                                                                            | REPLACE UX         | `pages/login.astro`, `lib/session.ts`: configured/unconfigured and signed-out states; revoke session through Supabase and clear all cookie chunks                             |
| Persisted session, token expiry/refresh and 401 recovery                                                 | REPLACE UX         | `lib/supabase-client.ts`, `session.ts`, `api-client.ts`, corresponding tests; server mediation replaces browser storage, preserves recoverability                             |
| MFA enrollment, verified factor reuse, abandoned enrollment cleanup, invalid codes and post-MFA return   | KEEP               | `pages/mfa.astro`, `session.ts`, `session.test.ts`: actual current AAL2, challenge/verify and refreshed elevated token; no redirect loop                                      |
| Organization/location context and entitlement navigation                                                 | REPLACE UX         | `lib/workspace.ts`, `platform.ts`, `product-entitlements.ts`, `ui/boot.ts`; retain UUID scope, pending readiness, no accidental global resource list                          |
| Admin/agency-only surfaces and owner continuity                                                          | KEEP               | `pages/administration.astro`, `pages/onboarding.astro`, `platform-admin-entitlements.test.ts`; backend `platform_admin/dependencies.py`, `access_control/owner_continuity.py` |
| Resumable onboarding, modes, assignment, activation                                                      | REPLACE UX         | `pages/onboarding.astro`, `lib/onboarding-blockers.ts`, backend `onboarding` and `client_onboarding.py`; one engine, three responsibility modes                               |
| Google connect, reconnect, incremental scopes, disconnect                                                | MOVE               | `pages/integrations.astro`, `lib/integrations.ts`; backend `integrations/connection_service.py`; centralized Integrations                                                     |
| GBP resource confirm/remove/archive and write access                                                     | MOVE               | `gbp_mapping.py`, `gbp_mapping` frontend functions; exact canonical provider Location IDs and AAL2 confirmation, never guessed IDs                                            |
| GSC property selection, website mapping and sync                                                         | MOVE               | `lib/search-console.ts`, backend `integrations.py`, `seo.py`; operational SEO shows readiness/link, setup in Integrations                                                     |
| GA4 discovery, website mapping and period comparison                                                     | MOVE               | `lib/analytics.ts`, backend `insights.py`, `integrations.py`, analytics services; confirmed website scope and real periods                                                    |
| GitHub App installation, repository, publishing contract/target                                          | MOVE               | `lib/content.ts`, `integrations.ts`, `github_app.py`, content target reconciler; token/server authority retained                                                              |
| Connection diagnostics and missing/expired/mapped states                                                 | KEEP               | `lib/integrations.ts`, `search-console.ts`, `analytics.ts`, `google-workspace-governance.test.ts`; privileged diagnostic scope only                                           |
| Durable workflow status and polling                                                                      | KEEP               | `lib/workflows.ts`, `agents.ts`, product pages; workflow IDs, job states, terminal outcomes; stop polling on navigation/terminal state                                        |
| Retries, reconciliation and recovery                                                                     | KEEP               | `gbp-operations.ts`, `content-operations.ts`, `seo.ts`; safe recovery routes and ambiguity, no browser blind retry of provider writes                                         |
| Exact revision approval and rejection                                                                    | KEEP               | `seo.ts`, `content-operations.ts`, `reviews.ts`, `gbp.ts`; AAL2, immutable revisions, single pending SEO revision, approved fingerprint                                       |
| Protected SEO signals, editing/supersession and implementation proof                                     | KEEP               | `seo.ts`, `ui/site-change-view.ts`, `ui/search-intelligence.ts`; backend `change_quality.py`, `decision.py`, `site_change_state.py`                                           |
| Typed failures and capability permissions                                                                | KEEP               | `api-client.ts`, `ui/errors.ts`, product contract modules, backend `errors.py`, `schemas.py`; retryable/category/code/correlation distinctions                                |
| Insights/reporting freshness and comparisons                                                             | REPLACE UX         | `pages/insights.astro`, `lib/reporting.ts`, `analytics.ts`, `reporting-chart.ts`; no absent-as-zero totals or inferred page conversion attribution                            |
| Automations, agent eligibility, stop/steer, schedules                                                    | REPLACE UX         | `pages/automations.astro`, `lib/agents.ts`, `automation-agent-ui.test.ts`; existing workflow registry only                                                                    |
| Reviews intake, risk flags, drafts, AI generation, approval, publish and audit                           | REPLACE UX         | `pages/reviews.astro`, `lib/reviews.ts`, `reviews.py`; no automatic publishing inferred from prototype preference                                                             |
| Leads source/secret, consent, assignment, status, notes, tasks and communication                         | REPLACE UX         | `pages/leads.astro`, `lib/leads.ts`, `leads.py`; queued notification is not delivered communication                                                                           |
| Content ideas, brief, draft, assets, revision, approval, PR/build/deploy/verification                    | REPLACE UX         | `pages/content.astro`, `content.ts`, `content-operations.ts`, content services/publishing state machine                                                                       |
| SEO websites, crawl inventory, technical issues, Page Intelligence, demand/gaps, recommendation, outcome | REPLACE UX         | `pages/seo.astro`, `lib/seo.ts`, backend `seo.py`; preserve query-only vs page-attributed evidence and limitations                                                            |
| GBP profile, completeness, change sets, special hours, media, posts, provider reconciliation/suspension  | REPLACE UX         | `pages/gbp.astro`, `gbp.ts`, `gbp-operations.ts`; retain provider capability/write governance                                                                                 |
| Old dashboard/settings layouts                                                                           | REPLACE UX         | `pages/index.astro`, `settings.astro`, `operating-dashboard.ts`; capability remains in portfolio, workspace and administration                                                |
| Prototype role toggle and sample success mutations                                                       | RETIRE WITH REASON | UI `sample-session.ts`, `workflows.ts`, `model-context.ts`: sample authority cannot authorize or mutate production; replace every mutation with domain action                 |

## C. Screen, value and action contract

PROPOSED DESIGN: all following mappings preserve the approved component hierarchy.
VERIFIED CURRENT FACT: route/screen inventory comes from the UI baseline
`src/config/routes.ts`, the two catch-all page modules, `src/types/domain.ts`,
`src/components/**` and `src/lib/workflows.ts`. All fixture paths below are in its
`src/data/fixtures/`. No fixture is an API contract.

Common contract applying to **every row**:

- Scope `O` is canonical organization UUID, `L` is confirmed location UUID, `W`
  is organization-owned website UUID; portfolio is only the actor's authorized
  organizations. Filter before aggregation, pagination, joins and counts.
- Reads display source ID, period, observed/synced time, freshness and quality.
  Missing is null with reason; stale/partial/unavailable/disconnected remain distinct.
  Never scale 30-day fixtures by a date multiplier or infer a numeric score.
- UI controls consume backend capabilities; permissions shown here are current
  route policies, not a copied frontend permission matrix. Backend rechecks action,
  scope, entitlement, readiness, AAL and approval.
- Mutations retain canonical audit actor/target/revision/correlation, domain
  idempotency field and durable run/job/publication references. Reads do not create
  substitute audit events. UI displays authoritative progress and safe error codes.
  For routes with no idempotency field, preserve state/version conflict semantics;
  do not claim that forwarding `Idempotency-Key` adds backend support.
- Async refresh reads canonical runs; no completed toast on enqueue. BFF routes are
  explicit per endpoint below, never arbitrary path forwarding. No-source values
  show `NO SOURCE — EXPLICIT EMPTY STATE`; related buttons are disabled with a reason.
- Every row's acceptance journey: authorized read -> exact scope/value/evidence ->
  eligible action (if sourced) -> canonical persisted status/audit -> reload;
  repeat with another tenant, missing source and insufficient permission.
  Specialized journeys are identified by acceptance matrix IDs.

Endpoint notation: `O=/api/v1/organizations/{organization_id}`;
`L=O/locations/{location_id}`; `S=O/seo`; `C=O/content`;
`G=O/integrations/google`; `H=O/integrations/github`; `F=O/workflows`.
Route suffixes below are literal existing routes unless explicitly called proposed.

| Screen / meaningful values                                                                                                                                          | Canonical read/model and scope                                                                                                                                                                    | Meaningful action / canonical mutation and policy                                                                                                                                                                            | Fixture replaced / representation / journey                                                                                             |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Portfolio `/`: client count, account status, attention, today's/upcoming work, recent activity                                                                      | `GET /api/v1/me/organizations`; authorized `Organization`, `Schedule`, `WorkflowRun`, approvals/audit; proposed portfolio read projection; portfolio                                              | Select client resolves UUID; attention links to domain actions; no mark-all-complete mutation                                                                                                                                | `clients`, `actions`, `activity`, `snapshots`; authorized totals and pending records, P01/P08                                           |
| `/clients/`: names, location/category, status, visibility/change/rank, traffic/leads/rating, next action                                                            | Same organizations plus profile/location, Insights/SEO/Reviews/Leads; proposed aggregate; portfolio                                                                                               | Search/sort/filter are presentation; open scoped workspace                                                                                                                                                                   | `clients`, `clientPerformance`; rank/visibility remain no-source unless sourced explicitly; P08                                         |
| `/attention/` and client attention dialog: severity, time, type, impact, next/button, resolution                                                                    | `AttentionView` section D; O/L                                                                                                                                                                    | Open source; reconnect/approve/recover via its route; never local `done=true`                                                                                                                                                | `actions`; persistent unresolved state until source resolves; P02/P03/P04                                                               |
| `/activity/`: client, event, time                                                                                                                                   | Canonical AuditEvent plus workflow/publication events; proposed authorized activity read endpoint; O/L                                                                                            | Navigate to first-class source; no write                                                                                                                                                                                     | `activity`; actor-safe timeline, not sample prose; P08                                                                                  |
| Portfolio/client Opportunities list, findings and detail: kind, title, priority, confidence, why, effort, expected gain, evidence/source/period/detected, next step | `SEOOpportunity`, `GrowthInitiative/Action`, `ContentOpportunity`; `GET S/opportunities`, `S/opportunities/{id}`, `O/growth`, `C/opportunities`; O/L/W                                            | Inspect domain detail; start recommendation/task through routes below, never generic Opportunity write                                                                                                                       | `opportunities`, `insights`, `growthWorkspaces`; gain nullable hypothesis, raw statuses retained; P01                                   |
| Opportunity detail: before/after, protected signals, proposal, revise/reject/approve, implementation, PR/build/deploy/live evidence                                 | `GET S/opportunities/{id}/recommendations`, `/hermes-run`, `S/recommendations/{id}/tasks`, `site_change_state`; O/W                                                                               | `POST S/opportunities/{id}/hermes-run` (seo.recommend), `/recommendations`; `POST S/recommendations/{id}/revise` (seo.recommend), `/decision` (seo.approve AAL2); exact approved change dispatches existing executor         | `opportunities`, `pageSignals`; immutable revision/fingerprint and typed blockers; P01/P04                                              |
| Growth detail: objective/actions/priority/confidence, decisions/measurement                                                                                         | `GET O/growth/{initiative_id}`, GrowthAction/Outcome; O/L                                                                                                                                         | `POST O/growth/{id}/decision`, `/dispatch`, `/reconcile` (workflows.execute); outcomes route (insights.manage); no extra publication approval                                                                                | `growthWorkspaces`; domain lifecycle/hypothesis not guaranteed gain; P01/P08                                                            |
| Client `/clients/{slug}/`: account, results/change, attention, completed/upcoming work, source freshness                                                            | Proposed ClientOverviewView combining org/profile, `GET O/insights/summary`, AttentionView/runs; O/L/W                                                                                            | Product navigation and source action only                                                                                                                                                                                    | `clients`, `snapshots`, `clientPerformance`, `insights`, `activity`; independent unavailable sources; P08                               |
| Local Search Overview and hospitality Search Performance/Momentum: sessions, demand/clicks/impressions/CTR/position/trends, opportunities                           | `GET S/workspace`, `S/websites/{W}/search-console/performance`, `O/insights/analytics/performance`; observations; O/W with seo.read/insights.read                                                 | Period selection reads persisted period; inspect query/page/Opportunity                                                                                                                                                      | `metrics`, `hospitalitySearchQueries`, `measurements`, `clientPerformance`, `pageSignals`; GSC position != local map rank; P02          |
| Local Search Rankings: visibility/chart, prior rank/top3/top10/not-found, distribution, scan time                                                                   | No persisted geographic local-ranking scan contract found; optional DataForSEO enrichment is not this grid model; O/L                                                                             | `runRankScan`: NO SOURCE — EXPLICIT EMPTY STATE; no invented workflow                                                                                                                                                        | `rankingDistribution`, `metrics`, `clientPerformance`; source unavailable with no percentages; P02                                      |
| Local Search GBP tab/profile dialog: mapped profile/name/category/address/hours, completeness and health                                                            | `GET O/gbp/locations`, `L/gbp/locations/{gbp_location_id}/profile`, `L/gbp/operations/locations/{id}/completeness`; confirmed GBPLocation + profile snapshots; O/L, gbp.read                      | Propose profile `/changes`, `/decision`, `/publish`; existing GBP permissions/AAL2; manage integration navigates to G                                                                                                        | `clients`, `systems`, `metrics`; profile data separate from connection health; P02                                                      |
| GBP performance calls/clicks/directions, post dialog/content                                                                                                        | No GBP performance observation source found; posts have `GET L/gbp/operations/locations/{id}/posts` and `/posts/provider`; O/L                                                                    | `savePost`: `POST .../locations/{id}/posts`, `.../posts/{revision_id}/decision`, `/publish`; never editing approved revision; governed provider write                                                                        | `metrics`, `clients.postCopy`; performance NO SOURCE — EXPLICIT EMPTY STATE; posts durable queued/provider-observed, P02                |
| Local Search Search Console tab/query table: query, clicks/impressions/position/CTR, prior/current period, landing page                                             | `GET S/websites/{W}/search-console/performance`, `/summary`, `S/workspace`; SEOSearchObservation, page attribution; O/W, seo.read                                                                 | Inspect observed page; refresh sync `POST S/websites/{W}/search-properties/{id}/sync` (seo.manage), mapping only Integrations                                                                                                | `hospitalitySearchQueries`, `metrics`, `measurements`; query-only demand never fabricated page match; P02                               |
| Local Search Pages / Website Pages / Page and landing-page dialogs: URL/name/content, status/indexing, clicks/sessions, health/check time                           | `GET S/crawl-runs/{id}/pages`, `S/websites/{W}/pages/{page_id}/intelligence`, SEOPage/observations, GSC/GA4 page evidence; O/W, seo.read                                                          | `updatePage` repairs through governed recommendation flow; `runWebsiteCheck` starts `POST F/seo.crawl_or_analysis/runs`, then `POST S/websites/{W}/crawl`; index status cannot be set locally                                | `pageRecords`, `pageSignals`; health number/index coverage NO SOURCE where not observed; P01/P04                                        |
| Local Search Technical / Website Technical: findings, affected page, severity, crawl status, check                                                                  | `GET S/workspace`, `S/crawl-runs`, opportunities/observations; O/W, seo.read                                                                                                                      | Crawl/inspect/recommend via SEO routes; deterministic software detects issue                                                                                                                                                 | `pageSignals`, `opportunities`, `metrics`; partial/error scan preserved; P01/P04                                                        |
| Website & Content Overview: organic sessions, lead/conversion totals, pages, health, insight                                                                        | SEO workspace + Insights analytics performance + Leads summary (no false page attribution); proposed small aggregate; O/W                                                                         | Navigate exact page/content/Opportunity                                                                                                                                                                                      | `metrics`, `clientPerformance`, `insights`, `pageRecords`; unsupported quality score empty; P04/P05                                     |
| Website Content tab / content editor: idea/brief/draft/status, target/slug, expected publication, assets                                                            | `GET O/content-operations`, `/{item_id}`, `/{item_id}/publishing-assets`; ContentItem/Brief/Revision/Publication; O/W, content.read                                                               | `saveContent`: `POST C/{item_id}/revisions` (content.edit), AI-draft; `POST O/content-operations/{item_id}/revisions/{id}/decision` (content.approve AAL2), `/{item_id}/publish` (content.publish AAL2), publication recover | `pageRecords`, `growthWorkspaces`; due date only real schedule; P04                                                                     |
| Website Conversions / conversion paths: tracked events/counts/outcomes, page path and tracking findings                                                             | GA4 observations provide totals and organic page keyEvents through canonical evidence; `GET O/insights/analytics/performance`, Page Intelligence; O/W, insights.read/seo.read                     | Inspect tracking Opportunity; cannot mark repaired locally                                                                                                                                                                   | `conversionEvents`, `pageSignals`; named event/path/funnel counts NO SOURCE — EXPLICIT EMPTY STATE until explicit transport source; P05 |
| Reviews list/response dialog: author/stars/text/date, risk/sentiment/status, existing response                                                                      | `GET L/reviews`, `/summary`, `/{review_id}/responses`; Review/RiskFlag/ResponseRevision; O/L, reviews.read                                                                                        | `POST L/reviews/{id}/responses`, `/ai-draft` (reviews.generate_response), `/{id}/responses/{response_id}/approve`, `/publish` (reviews.approve_response/publish_response AAL2); audit routes audit.read                      | `reviewRecords`, `metrics`; status changes only confirmed backend response; P03                                                         |
| Reviews requests / request dialog: request copy/count/eligible contacts, staged/sent                                                                                | No review-request campaign/delivery API identified; lead consent and communications are not review campaign records; O/L                                                                          | `stageReviewRequest`: NO SOURCE — EXPLICIT EMPTY STATE; no email sent claim or lead endpoint repurposing                                                                                                                     | `clients.requestCopy/requestCount`, `presentation`; disabled request action with reason; P03                                            |
| Review opportunities: unanswered/risk/reputation improvement                                                                                                        | Reviews/risk/escalation and eligible response revisions can feed Attention; Content/SEO/Growth source required for improvement Opportunity                                                        | Open exact review response action; no synthetic Opportunity ID                                                                                                                                                               | `opportunities`, `reviewRecords`; classify review reply attention separately; P03                                                       |
| Leads list/detail: contact/message/source/received/status, source sync, notes/tasks/assignee/consent, contact action                                                | `GET O/leads`, `/summary`, `/sources/performance`, `/{id}`, `/notes`, `/tasks`, `/communications`, `/consents`, `/assignees`; Lead and related records; O/L, leads.read                           | `markLead`: `POST O/leads/{id}/status` (leads.assign), `/assign`, `/convert`, `/loss`; `/notes`, `/tasks`, `/communications` (leads.respond), consent separately AAL2                                                        | `leads`, `metrics`; persisted contacted state does not prove sent message; P05                                                          |
| Leads Outcomes / event dialog: events, completed business outcomes, attribution, prior/current                                                                      | Lead conversions/loss and source performance; GrowthOutcome evidence; GA4 keyEvents are distinct; O/L/W                                                                                           | Navigate underlying outcome; no browser outcome increment                                                                                                                                                                    | `conversionEvents`, `measurements`, `clientPerformance`; event names/breakdown empty without source; P05                                |
| Portfolio/client Automations Overview/Inventory/run dialog: definition, frequency/status, last/next run, failures, detail/source                                    | `GET F`, `/runs`, `/runs/{id}`, `/schedules`; WorkflowDefinition/Run, Schedule, Job; AgentRun via `GET O/agents/runs`; O/L, workflows.read/schedules.read                                         | `runAutomation`: `POST F/{workflow_key}/runs` (workflows.execute); create/patch schedule (schedules.manage); agent stop/steer/approval through agent routes, recovery through publication domain                             | `automationDefs`, `automationRuns`; only registered keys, no invented rank-scan/monthly-report jobs; P06                                |
| Portfolio/client Reports / client report / monthly/historical dialogs: readiness, monthly measurements, report status/period/date/note, history/sent, download      | Insights + governed observations support metrics/readiness; no persisted monthly report artifact, delivery/history or rendering endpoint found; O/W, insights.read                                | `markReport`, `downloadReport`, `downloadMonthlyReport`: NO SOURCE — EXPLICIT EMPTY STATE until canonical reporting contracts; do not mark Sent or export sample summary                                                     | `reports`, `reportHistory`, `measurements`, `metrics`; real metrics may show, report readiness explicit unavailable; P07                |
| Portfolio/client Integrations / connections dialogs: provider/status/count/capability/last sync/auth, resource mapping                                              | `GET G/workspace`, `/status`, `/unmapped`, `H/workspace`, `/repositories`; IntegrationConnection/provider mappings/capabilities/sync runs; O/L/W, current GBPConnect policy uses gbp.connect AAL1 | `POST G/connect`, `/disconnect`, `/discover`, `/locations/{id}/sync`, `/analytics/properties/map`, `/search-console/properties/map`; H install/disconnect; GBP mapping confirm in gbp_mapping.py; re-fetch state after OAuth | `systems`, `clients.sourceSync`; `refreshConnection` starts provider-specific sync, no local Connected badge; P02                       |
| Settings: business name, primary location, category, reporting contact, response preference, timezone/status                                                        | Organization/Profile/Location, effective configuration/policy and business identity via O routes; O/L; backend organization/profile/config/policy permissions                                     | Save via distinct `PUT O/profile`, `PATCH O/locations/{L}`, configuration/policy proposal+approval; name/timezone only fields actually supported; NO SOURCE for reporting contact if no definition                           | `clients`, `presentation`; no blanket form submit or browser auto-publish grant; P09                                                    |
| Administration clients/organizations: name/type/status/industry/locations/entitlements                                                                              | `GET /api/v1/platform/organizations`, `/{O}`, `/industries`, `/{O}/locations`, `/{O}/product-entitlements`; platform admin, O                                                                     | Existing platform create/pause/resume/archive, location/profile/entitlement actions, owner continuity; no name-keyed action                                                                                                  | `clients`, `administration`, `presentation`; administrative backend authority, P09                                                      |
| Administration Onboarding: current step, responsibility/mode, readiness/action                                                                                      | `GET /api/v1/platform/organizations/{O}/onboarding-state`, `/onboarding-assign`, `GET O/onboarding`; same engine; platform admin or scoped client onboarding                                      | Platform start-onboarding/provision-website/onboarding-mode/onboarding-assign/activate; client `POST /api/v1/client/onboarding/organizations` and `/{O}/activate`                                                            | `administration`, `clients`; resumable mode-specific ownership, no sample Juniper assumption; P09                                       |
| Administration Users: role/access/status/invited                                                                                                                    | `GET O/memberships`, `/invitations`, `/access/roles`, `/access/permissions`; Membership/Invitation/RoleAssignment; O, organization.memberships/roles policies                                     | Existing invitation/membership/role-assignment/permission-deny routes, AAL2 where required; global user directory NO SOURCE                                                                                                  | `administration`; scope-owned list, hide absent account provisioning action; P09                                                        |
| Administration Platform/system: settings, integration/reporting/job health                                                                                          | Privileged operational metrics/health, platform products; no comprehensive system-settings UI endpoint found                                                                                      | No arbitrary setting mutation; exact known backend control/config action only                                                                                                                                                | `presentation`, `systems`; absent operational values empty, no false healthy label; P09                                                 |
| Global top bar/sidebar: context, dates/range, filters, role/navigation, connection badges                                                                           | `/api/v1/me`, `/me/organizations`, `/me/platform-administrator`, `O/products` and canonical selected scope                                                                                        | Navigate/filter/select only; retire `setDemoRole`; role cannot be set in sessionStorage                                                                                                                                      | `clients`, `presentation`; accessible focus/dialog/keyboard, backend route guards; P00/P09                                              |

PROPOSED DESIGN: opening commands `openOpp`, `openAction`, `openSystem`,
`showProfile`, `openPost`, `openPage`, `openContent`, `openLead`, `openReview`,
`openReviewRequest`, `openAutomation`, `openHistoricalReport`, `openReport`,
`openClientConnection`, `openOutcome`, `openClientAttention` load the corresponding
row above. `nav`, sort, search, period and filter controls change presentation only.
The UI `model-context.ts` sample tool interface must not expose a new write path.
No sample command remains unmapped: `startOpp`, `runRankScan`, `runWebsiteCheck`,
`savePost`, `saveContent`, `updatePage`, `markLead`, `generateReviewResponse`,
`saveReview`, `stageReviewRequest`, `refreshConnection`, `markReport`, all downloads,
`completeAction`, `runAutomation`, `setDemoRole`, and settings submit are covered.

## D. Opportunity and Attention read projections

PROPOSED DESIGN: introduce typed backend read contracts and tested UI adapters,
not a universal table/write lifecycle. Durable projection ID is
`{source_kind}:{source_uuid}`; source UUID never changes when text/status changes.
Include `organization_id`, nullable `location_id/website_id/page_id`, product area,
classification, raw source status, presentation status, evidence references,
observation period, source freshness/quality, nullable priority/confidence/effort,
allowed action descriptors, recommendation revision, workflow/run/job/publication
references and causation links. Offset/cursor sorting is deterministic and tenant
filtered; classification uses typed codes, never title keywords.

| Evidence              | Source -> classification                                                                                         | Identity/evidence/status/actions                                                                                                                                                                            |
| --------------------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| VERIFIED CURRENT FACT | SEOOpportunity                                                                                                   | `products/seo/models.py`, `seo.py`: UUID, opportunity type/priority, page attribution, evidence, recommendation revisions/tasks/outcomes, workspace and Page Intelligence                                   |
| PROPOSED DESIGN       | SEO technical detector finding -> Issue                                                                          | Preserve detector code and crawl/page observation. Recommend/revise/decide through S routes; raw lifecycle and site-change/publication state retained                                                       |
| PROPOSED DESIGN       | SEO demand/content gap and GrowthInitiative/Action -> Growth Opportunity                                         | Map explicit structured intent/source action type; no title parsing. Growth decisions/dispatch/reconcile stay Growth actions. References to same SEO/content source are linked, not double-counted          |
| PROPOSED DESIGN       | SEO optimization / accepted ContentOpportunity -> Optimization or Growth Opportunity by structured source intent | Source ContentOpportunity UUID; `C/opportunities/{id}/decision` creates canonical work; ContentItem/revision/publication retains own identity                                                               |
| PROPOSED DESIGN       | Tracking/configuration defect with persisted canonical evidence -> Data & Tracking                               | Use existing evidence/source codes; absence of a mapping is Attention, not a new fabricated defect. Unsupported event instrumentation source contributes no Opportunity                                     |
| BLOCKER               | Reviews/GBP/Leads generic improvement records                                                                    | No universal opportunity source exists in these modules. Their reviews, risks, profile changes and lead tasks feed domain work/Attention; future projection needs explicit governed source, otherwise empty |

VERIFIED CURRENT FACT: SEO revision statuses include superseded/withdrawn historical
revisions; publication states distinguish reserved, branch/PR, checks, merge,
deployment, verified, failed, reconciliation and rollback. Code evidence:
`seo/{decision,site_change_state,change_quality}.py`, content `models.py` and
`publish_handler.py`. A projection must not collapse them to Done.

PROPOSED DESIGN: Attention identity is `{source_kind}:{uuid}:{reason_code}` with
`resolved_at` derived from canonical state, not a frontend acknowledgement.

| Canonical source                                                                                   | Attention trigger/evidence                                                                                              | Allowed action and domain authority                                                                                             |
| -------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| IntegrationConnection/provider mapping/capability/sync records                                     | Expired/disconnected/reconnect, failed/partial sync, missing confirmed resource; connection UUID, observed time         | G/H connection/mapping/sync routes; backend capability policy, AAL2 where required; connection health never repaired by dismiss |
| SEORecommendationRevision, ContentRevision, ReviewResponseRevision, GBP change/post/media revision | Awaiting required decision; immutable revision UUID and exact proposed change                                           | Domain approve/reject/revise routes; approvals remain exact and audited                                                         |
| ContentPublication / GBP publication / review response                                             | Checks blocked, deploy failed, ambiguous provider result, reconciliation required; publication UUID and safe_error_code | Canonical recover/reconcile route where available; otherwise inspect with explicit manual action, no generic retry              |
| WorkflowRun / Job / AgentRun / Schedule                                                            | Failure, waiting_approval, retry_scheduled, overdue run with backend evidence; IDs and attempt timestamps               | F start/schedule actions or agent stop/steer/approval; preserve failed record, retry creates/reuses governed domain work        |
| ReviewRiskFlag / ReviewEscalation / unresponded Review; LeadTask                                   | Human response required; parent review/lead UUID and task/risk UUID                                                     | Reviews response and Leads tasks/communication; consent and risk gates remain backend                                           |
| OnboardingChecklistItem / readiness blockers                                                       | Required incomplete step or typed missing configuration                                                                 | Resume canonical onboarding/setup; no blanket gate for unrelated products                                                       |

PROPOSED DESIGN: backend aggregate read endpoints (names frozen during Phase 1)
`GET O/command-center/opportunities`, `/attention`, `/overview`, and agency portfolio
equivalents are additive and call canonical services/repositories with their read
policies. They return capabilities evaluated for the actor. They do not add mutation
routes. Generic source dictionaries in existing JSON responses require typed
Pydantic response DTOs before generated types provide useful guarantees.

## E. Auth, BFF and security

PROPOSED DESIGN: request-scoped `@supabase/ssr` server client in Astro middleware,
using getAll/setAll cookies, server-mediated password sign-in/sign-out/MFA and
Supabase verified user validation; never trust `getSession()` alone as identity.
No browser Supabase session client or serialized access/refresh token. Forward the
current user token, never service-role, to FastAPI. Supabase remains session authority;
FastAPI verifies JWT, active platform user, permissions and AAL on every request.
This all-server cookie design is deliberate; see the
[Supabase SSR guide](https://supabase.com/docs/guides/auth/server-side/advanced-guide).

PROPOSED DESIGN: host-only `__Host-` prefixed session-cookie base, no Domain,
Path=/, Secure, HttpOnly, SameSite=Lax; local HTTP has an explicit local-only
unprefixed cookie. MFA enrollment QR/secret is rendered once without HTML injection,
never retained in logs/caches. Server endpoints: POST `/auth/sign-in`, `/sign-out`,
`/mfa/enroll`, `/mfa/challenge`, `/mfa/verify`, `/mfa/unenroll`; read assurance/factors
server-side. Cleanup only the user's abandoned unverified enrollment. Return to a
validated relative path after confirmed AAL2, preserving original context, no loops.

PROPOSED DESIGN: refresh once in middleware before child loaders; updated cookies
and token propagated in request locals and response. No process-global Supabase
client. Use request-local refresh single-flight and SDK rotation semantics; do not
assume in-memory locking coordinates separate Vercel instances. Concurrent old
cookies may receive a stale failure after another response rotates: such failures
must not clear a newly rotated session. Recover once via a same-origin session read,
then require sign-in on definitive invalid session. Distributed refresh race tests
with opposite response completion order are a Phase 1 acceptance requirement.
No automatic replay of a mutation after uncertain dispatch.

PROPOSED DESIGN: preserve chunk suffixes and delete obsolete chunks on shrink,
logout or definitive invalidity. Maximum total Cookie header 16 KiB, maximum 8
session chunks; reject over-limit header as 431 and malformed/gapped session as
signed-out, without forwarding to API. SDK chunk size must fit browser per-cookie
limit. Test boundary valid sessions, malformed chunks, stale suffix and oversized
sessions; never disable MFA or drop security claims to fit cookies.

PROPOSED DESIGN: explicit BFF `/api/organizations/{uuid}/seo/...`, content,
content-operations, workflows, growth, reviews, leads, integrations and insights
routes correspond one-to-one to section C's selected method/route. `/api/me` and
organization context routes are fixed reads; `/api/platform/...` is separately
guarded. Only literal registered route templates, validated UUID path parameters,
known query keys and typed bodies accepted; unsupported methods 405, unknown routes 404. One configured HTTPS `LILOS_API_BASE_URL`; local-only loopback exception.
Follow no upstream redirects. Never accept user-provided upstream/URL/path headers.

PROPOSED DESIGN: default JSON body <=256 KiB; authentication <=16 KiB; no file
upload proxy until an explicit bounded media contract is selected. Fast read timeout
10 s, mutation timeout 30 s, auth 15 s; approved slower read max 30 s. Durable work
returns run references rather than holding SSR for Hermes/provider execution.
Preserve safe status/error/code/correlation and approved response headers;
strip Connection, Transfer-Encoding, Keep-Alive, proxy headers, Host, cookie,
upstream Set-Cookie and any response tokens. Attach server Bearer and sanitized
X-Correlation-ID; propagate idempotency into the actual domain body/header contract.
Log route template, timing, actor/scope IDs and correlation; redact passwords,
cookies, TOTP, QR secrets, access/refresh/OAuth tokens and provider raw bodies.

PROPOSED DESIGN: all unsafe requests (including auth) require exact expected Origin,
expected host from trusted deployment configuration and a session-bound CSRF nonce
(hidden form value or header). CSRF cookie is host-only Secure SameSite=Lax and
readable nonce only; server checks nonce binding, not merely equality of two
attacker-controlled values. Reject absent/foreign/null Origin and cross-site fetch
metadata; no trusted wildcard `*.vercel.app`. OAuth callbacks retain canonical
signed state/nonce and single-use validation, not an arbitrary Origin exception.
Trusted preview hostname is taken from Vercel deployment metadata and explicitly
registered; return paths reject schemes, `//`, encoded backslashes and external hosts.

PROPOSED DESIGN: SSR route guards handle signed-in, accessible org, entitlement
navigation and platform administration availability. FastAPI still decides actions.
Every authenticated page, redirect and BFF response (including errors and refresh)
uses `Cache-Control: private, no-store`; prevent CDN caching, prerendering, shared
module-level user data and token-bearing prefetch. Cross-tenant tests warm A's page,
request B and reuse source IDs; assert no values, counts, HTML or responses leak.

BLOCKER: existing Google OAuth return helper targets old `/integrations?org=...`
(`routes/integrations.py`). New console return behavior requires an additive,
validated application return contract; do not change old-web redirect globally.

## F. OpenAPI and generated transport types

VERIFIED CURRENT FACT: application OpenAPI inspected in memory without starting
API or connecting DB: 264 paths, 203 schemas with internal admin routes disabled.
Many product handlers return `dict[str, object]`; OpenAPI currently cannot fully
describe their nested serialized state. Source authority is FastAPI/Pydantic, not
handwritten web types or UI numeric sample IDs.

PROPOSED DESIGN: pinned `openapi-typescript` dev dependency; deterministic exporter
`scripts/export_openapi.py` constructs `create_app(Settings(_env_file=None,
internal_admin_routes_enabled=False))` with unconfigured DatabaseRuntime, no secrets
or live I/O. Sort JSON and exclude internal/provider tool surfaces from browser
transport consumption. Commit `packages/contracts/openapi.json` and
`packages/contracts/src/generated/api.ts`. Generation commands in Phase 1:

```sh
uv run python scripts/export_openapi.py --output packages/contracts/openapi.json
npx --no-install openapi-typescript packages/contracts/openapi.json -o packages/contracts/src/generated/api.ts
npm run contracts:check
```

PROPOSED DESIGN: `contracts:generate` wraps these commands;
`contracts:check` regenerates in CI and fails `git diff --exit-code` for both files.
Generation runs on API/schema changes even without console edits. No commands above
exist yet; they are a Phase 1 implementation contract. `apps/console/src/server/api`
uses transport types; `src/adapters` tests typed transformations to UI view models.
Cover enums/unknown codes, null vs zero, periods, status fidelity, permissions,
UUID ownership, revisions, source variants, malformed data and historical payloads.
Add response DTOs incrementally to the canonical routes; preserve JSON shape for web.

## G–H. Compatibility and routing

PROPOSED DESIGN: additive API evolution throughout dual-client operation, until
separate retirement PR. CI tests old web and console against the same generated
contract. Security/correctness exceptions document exact unsafe behavior, reason,
affected clients, deployment ordering, adapter and regression evidence; unsafe
authorization/data leakage is never preserved for compatibility. No blanket approval
ceremony. DB changes expand -> migrate/backfill via governed migrations -> contract
only after API/worker/scheduler/Hermes and both clients no longer use old fields.

VERIFIED CURRENT FACT: `organizations/models.py` globally unique slug constraint
`uq_organizations_slug` (stronger than active-only uniqueness), normalized lower
trimmed 3–63 characters, starts with letter, hyphen groups, reserved route names.
`contracts.py` normalizes; repository lookup calls slug immutable; update contract
does not expose a slug change. Archived orgs retain their slug reservation.

PROPOSED DESIGN: resolve slug using authenticated accessible organization list
or additive authorized backend lookup; require active organization, then only UUID
downstream. Unknown/inaccessible slug uses the same safe not-found behavior. Keep
immutable slugs for initial migration. If future slug changes are required, add
canonical audited aliases/redirects with unique reservations via DB migration,
not frontend name matching. Duplicate/dead organizations are separate hygiene;
do not rename, merge, delete or release their slugs in Phase 0.

BLOCKER: adapters needed for numeric UI IDs, label enums, role preview, sample
dates/period multipliers, product scope vs org scope, generic JSON responses,
pagination, publication state and nested source quality. Never assign sample client
IDs to real organizations or translate missing metrics into zero.

## I. Environment specification

PROPOSED DESIGN: exact logical resource names below are reservations, not claims
that they exist. Environment secrets must be verified independently before deploy.

| Environment       | Console/auth/data                                                                                                                                  | Backend/providers/writes                                                                                                                                                                     |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Local             | Local SSR; local Supabase Auth/Postgres or isolated test services; synthetic data                                                                  | Local API/worker/scheduler, fixture providers; no production credentials/network targets                                                                                                     |
| PR Preview        | Separate console Vercel project previews, deployment protection plus staging Supabase Auth, host-only per-deployment cookies                       | Staging API/Postgres only, fixture adapters; no prod environment inheritance; explicit expected preview host                                                                                 |
| Stable Staging    | `console-staging.lilosgrowth.com`, protected Vercel console; separate `lilos-command-center-staging` Supabase project containing Auth and Postgres | `lilos-command-center-staging-api`, `-worker`, `-scheduler`, `-hermes`; Render Oregon; synthetic orgs, dedicated GitHub test repo, independently authorized live read-only Google properties |
| Production Canary | Production console/auth/API/DB; only verified LILOs Growth org UUID and hard-scoped canary target                                                  | Production canonical provider/gate path, dedicated canary file/URL; no staging tokens/fixtures; reset only separate manual PR harness                                                        |
| Production        | Separate Vercel console from existing web; existing production Supabase                                                                            | Existing API/worker/scheduler/Hermes and provider connections, same canonical authority                                                                                                      |

VERIFIED CURRENT FACT: existing `render.staging.yaml` uses an older
`worker/backend-closure-2026-08-10` branch, Render PostgreSQL 17, API + worker only,
provider writes false. It is **not** the required staging contract. Reconcile it in
Phase 0.5; no second staging database or parallel job framework. Live provisioning
of this Blueprint was not established.

PROPOSED DESIGN: Vercel Node SSR region `pdx1` near declared Render Oregon, rather
than default `iad1`; verify actual API and staging Supabase region/network latency
before fixing final deployment config. This is an inference from repository topology,
not a verified live runtime region. See
[Vercel regions](https://vercel.com/docs/regions). No Edge business runtime.

PROPOSED DESIGN: server-only Supabase URL/publishable key and API base; explicit
environment/release/expected host, CSRF signing material; no browser API secret.
Backend uses separate DB/migration URLs, Supabase issuer/JWKS, encryption key,
OAuth client/redirect, GitHub App installation/private key, Hermes API/tool keys,
inference key and telemetry destination. Separate every staging value. CI startup
checks fail if preview points to a production origin/project/credential identity.

## J. Provider simulation and safety

VERIFIED CURRENT FACT: existing seams are `SearchConsoleAdapter` in
`products/seo/search_console_adapter.py`, `GoogleAnalyticsAdapter` in
`products/analytics/adapter.py`, `GBPAdapter` in `products/gbp/adapter.py`,
`RepositoryPublisher` in `products/content/adapter.py`; concrete GitHub publisher
and httpx client factories already support isolated tests. Review ingestion/replies
consume GBP adapter paths; no separate Reviews adapter module was found. Inject
through these service/handler construction seams, not environment branches in products.

PROPOSED DESIGN: composition-root fixture selection, explicit registered fixture
implementations and deterministic scenario IDs. Production startup refuses fixture
implementations, fixture credential references, `.invalid` provider targets and
fixture modules; CI import-boundary and production-config negative tests enforce it.
Product loaders/adapters may not import UI `src/data/fixtures` or sample-session.

| Fixture scenario                            | Expected contract and recovery                                                                               |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Healthy hospitality, SAB and multi-location | Synthetic exact org/location/website mappings, deterministic observations and periods, least-privilege reads |
| Expired authorization / revoked refresh     | Typed reconnect_required, no automatic success, audited OAuth action needed                                  |
| Rate limited                                | Canonical retryable/provider error with retry timing, durable job retry budget, no tight UI loop             |
| Partial/paginated response                  | Partial quality and source completeness, no assumed zeros or complete aggregate                              |
| Unavailable / timeout                       | Separate provider unavailable from disconnected, bounded timeout and recovery                                |
| Missing mapping                             | No source-specific read/write until confirmed canonical mapping; other products remain usable                |
| Ambiguous write / drift                     | Reconcile exact provider/publication state; never resend create blindly                                      |

PROPOSED DESIGN: shared contract tests run same scenario assertions for fixture
and production adapters (production HTTP mocked using sanitized recorded payloads,
never live writes in CI). Recorded fixtures include real upstream shape/status/header
semantics, pagination, timezone/date normalization and token expiry; strip client
PII, tokens and resource identifiers. A dated recording is not current OAuth acceptance.
Scheduled smoke uses existing scheduler/workflows (`seo.sync_search_console`,
`insights.sync_analytics`, `gbp.sync` if approved), independently authorized
LILOs-owned read-only staging connections, alerts on typed scope/refresh failures.
No copy of production refresh tokens; read POST searchAnalytics/runReport is allowed,
GBP mutation RPCs are denied regardless of HTTP method naming.

VERIFIED CURRENT FACT: global `provider_writes_enabled` exists and gates publishing;
it cannot by itself express Google writes denied while GitHub test writes allowed.
PROPOSED DESIGN: preserve global fail-closed control and add provider-specific
capability evaluation in the shared provider-write boundary: staging Google/GBP
denied, GitHub only owner-approved fixed repository + installation + branch/path
allowlist; validate every token/repo resolution before any branch/PR call. No arbitrary
repo from UI. Tests cover disabled flag, wrong owner/repo/installation/path, forged
IDs, production fixture startup and existing production governed writes.

## K–L. LILOs Growth readiness and canary qualification

VERIFIED CURRENT FACT: public `https://lilosgrowth.com/robots.txt` allows crawl and
points to sitemap-index -> sitemap-0; no canary URL in inspected sitemap. Site source
has ordinary `src/pages/index.astro` metadata with an Astro string binding, but its
deployed description on 2026-09-30 is the global config description rather than that
page's declared description. `Metadata.astro` merges defaults and trims strings;
source edit cannot be presumed to control rendered HTML. There is no dedicated
canary source in the inspected checkout. Ordinary homepage is rejected as test target.

| Evidence              | Production canary readiness item                                         | Result / next evidence                                                                                                                                                        |
| --------------------- | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| NOT YET VERIFIED      | Canonical production organization and website UUID                       | Saved production session in ignored `apps/web/.auth/production-state.json` expired; no valid API session or authoritative IDs verified. Never infer IDs from site name        |
| NOT YET VERIFIED      | Actual crawler discovery                                                 | Public sitemap availability is verified; persisted SEOCrawlRun/SEOPage for a dedicated canary is unverified                                                                   |
| NOT YET VERIFIED      | GitHub App installation and publishing target                            | Source app slug is known; actual org connection/installation/repository/write-enabled target not read live                                                                    |
| NOT YET VERIFIED      | Allowed path and page map                                                | `PublishingTarget.allowed_site_change_prefixes` and `frontmatter_contract.page_map` supported in code; actual LILOs Growth target values unavailable                          |
| VERIFIED CURRENT FACT | Issue -> recommendation -> change -> workflow/publication implementation | `crawl_engine.py`, `service.py`, `decision.py`, `site_change_service.py`, `site_change_handler.py`, routes SEO decision; deterministic detector and exact approval path exist |
| VERIFIED CURRENT FACT | Live verification implementation                                         | `site_change_handler._verify_live`, `verification.py`, shared publication state machine support observed expected fields; not a successful LILOs Growth live run              |
| BLOCKER               | Qualified actual canary                                                  | No dedicated fixed target with all six checks passed; qualification FAIL pending controlled setup and live evidence                                                           |

| Evidence              | Real Google smoke readiness (independent) | Result / owner evidence                                                                                              |
| --------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| NOT YET VERIFIED      | GSC connection + website mapping          | Canonical connection/SEOSearchProperty code exists; live LILOs Growth connection and mapping unverified              |
| NOT YET VERIFIED      | GA4 connection + website mapping          | Canonical AnalyticsProperty website binding exists; live mapping unverified                                          |
| OWNER ACTION REQUIRED | GBP scope                                 | Confirm whether LILOs Growth GBP is included; absence does not block GitHub canary                                   |
| NOT YET VERIFIED      | Token refresh                             | Encrypted secret/OAuth refresh implementation exists; live refresh not performed in Phase 0                          |
| NOT YET VERIFIED      | Scheduled read-only smoke                 | Workflow keys exist; actual smoke schedule, independent staging auth and latest successful observations not verified |

PROPOSED DESIGN: candidate for future dedicated setup is
`LilosG/lilos-growth:src/pages/lilos-canary.astro`, URL `/lilos-canary`, single
`canaryMetaDescription` Astro binding feeding a direct meta tag (avoid global
fallback/clipping). This file does not exist today. Use empty description as fixed
known-bad state; canonical detector `missing_meta_description` in crawl_engine
line 578. Model `SiteChangeItem.current_value` accepts empty text. Resolver
`AstroCodeLocator` matches exactly one binding and edits its span; JSON editor
instead counts repeated serialized values, so multiple empty strings fail safely.
No need to change JSON/model architecture to bypass ambiguity.

PROPOSED DESIGN: qualification checklist before production-canary acceptance:

1. Detector emits persisted Issue from dedicated page (not merely a unit example).
2. Resolver reads unique source binding and applies exact empty -> approved text;
   duplicate binding, changed current value and outside-prefix paths refuse.
3. Issue reaches existing recommendation/revise/AAL2 approve -> `seo.apply_site_change`.
4. Bad deployed HTML has missing/empty description; good HTML expresses exact repair.
5. Production crawler stores the URL/page ID from explicit approved seed/discovery.
6. Fixed reset harness produces reviewed PR with known-bad field and normal CI.

PROPOSED DESIGN: reset harness resides only in site test infrastructure, manual
`workflow_dispatch` with a confirmation string, hard-coded owner/repo/file/URL and
known-bad patch; no repo/path/patch inputs. Check existing known-good field before
patching, refuse unexpected tree/state; create unique branch/PR, never main write or
auto-merge. Record actor, run ID, base/result SHA and PR in audit/run metadata. Scope
token/App to this repository, enforce code-owner CI review; inaccessible from console.
The product repair path never exposes reset. Setup belongs to approved Phase 0.5;
no defect was inserted or production crawl/sync triggered in this packet.

## M. Performance and observability

PROPOSED DESIGN: initial measurable budgets, subject to staging measurement rather
than assumed plan capacity. Use 20 authorized synthetic orgs, 3 concurrent operators,
at least 200 requests per route, warmed and cold samples separated; run 15 minutes
and capture sample size, environment/release, source quality and instrumentation.

| Measure                    | Initial acceptance budget                                                                                      |
| -------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Authenticated SSR page p95 | <=2 s server response, excluding interactive external OAuth; cold start separately reported                    |
| API read p95               | <=500 ms for internal persisted/aggregate reads; provider execution separate job metric                        |
| API accepted mutation p95  | <=1 s enqueue/decision response; no provider completion promise                                                |
| Memory                     | Sustained RSS <70% limit, peaks <85%, no OOM/restart during test                                               |
| CPU                        | Sustained <70%, short peaks <90%; queue latency must not grow unbounded                                        |
| DB pool                    | <70% sustained utilization, p95 acquire wait <100 ms, no pool timeouts; budget across API + worker + scheduler |
| 5xx                        | <0.5% valid requests, zero tenant leak/security failure, intentional fixture fault rates reported separately   |

VERIFIED CURRENT FACT: database pool defaults 2 with configured overflow, lazy
per-process engine (`database/runtime.py`); correlation middleware bounds and echoes
X-Correlation-ID, WorkflowRun and AgentRun persist correlation. Full browser ->
console -> API -> worker -> Hermes -> publication -> GitHub -> verification trace
continuity and causation are not verified. PROPOSED DESIGN: propagate existing
correlation, add missing parent/source references at canonical boundaries and test
the complete journey; never put tokens in trace baggage.

PROPOSED DESIGN: normal SSR 1–3 initial backend reads including context. Portfolio,
Overview, Attention, Opportunities, Reports and multi-location Reviews/GBP would
otherwise multiply product/tenant calls; use backend aggregate read models for
authorized counts and projections. Opportunity detail may justify extra revision/run
reads, recorded with timing; no product logic in Astro or eager loading every dialog.

## N. CI contract

PROPOSED DESIGN: existing `.github/workflows/ci.yml` web checks remain mandatory.
Add console format, ESLint/style boundary, TS, Astro check, adapter/unit tests, SSR
build, Playwright desktop/mobile, axe, generated OpenAPI drift, production-fixture
ban, auth/MFA/concurrent-refresh/cookie tests, CSRF/origin/redirect tests, cross-tenant
HTML/BFF/cache tests, affected backend integration tests, migration expand/check/
rollback/upgrade on disposable PostgreSQL and dependency audits. API DTO changes
trigger console adapter/build checks. Production console deployment is filtered to
console/contracts/shared deployment inputs, not every docs-only push. Existing
web deployment behavior is unchanged by Phase 0.

## O. Recurring staging cost and owner dependencies

PROPOSED DESIGN: dated USD planning estimates, not purchased plans or capacity
acceptance. Current public rates checked on 2026-09-30 at
[Render](https://render.com/pricing), [Supabase](https://supabase.com/pricing) and
[Vercel](https://vercel.com/pricing). Render data required reading the public HTML
because the extracted pricing page omitted compute tables.

| Incremental resource                           | Planning monthly cost / assumption                                                                                                          |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| Render API + worker + scheduler                | 3 x $7 = $21 (512 MB cost floor); 3 x $25 = $75 if measurements require 2 GB. No plan selected                                              |
| Render Hermes private service                  | $25 example at 2 GB, matching declared production memory class as planning scenario; validate actual usage                                  |
| Hermes disk                                    | 5 GB x $0.25 = $1.25                                                                                                                        |
| Supabase staging Auth + Postgres project       | $10 extra Micro on existing paid org, or $25 isolated Pro org including first Micro; owner must confirm existing credits/billing            |
| Vercel console + previews                      | $0 marginal base if existing Pro team covers seat/project, otherwise $20/month Pro seat plus usage; SSR use may incur overage               |
| Render isolated environment workspace features | $0 marginal if existing Pro includes them; otherwise $25/month workspace upgrade (owner billing unverified)                                 |
| Optional Vercel password protection            | $20/project/month if chosen; use existing deployment protection plus Supabase auth when sufficient, do not buy by default                   |
| Model/provider, bandwidth, CI, telemetry usage | Variable, not priced as fixed $0; planning reserve $10–$30/month for bounded staging inference, reconcile actual usage and set spend limits |

PROPOSED DESIGN: base incremental scenario **$57.25–$72.25/month** before variable
usage (API/worker/scheduler floor + Hermes + disk + staging DB, existing paid teams).
With fresh Render Pro/Vercel seat and memory scenario, **up to $171.25/month** before
optional protection/usage. This range is arithmetic, not a measured hosting choice.
Do not run a duplicate Render Postgres beside required Supabase staging Postgres.

| Evidence              | Owner action                                                                                              | Clears / timing                                                                                                                                                               |
| --------------------- | --------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| OWNER ACTION REQUIRED | Authorize staging resource costs and billing scenario                                                     | Paid setup blocked until explicit budget approval; no purchase in Phase 0                                                                                                     |
| OWNER ACTION REQUIRED | Provide/confirm Render workspace, Supabase project/admin access and Vercel protection entitlement         | Verify actual regions, resources and topology; no secret values in PR                                                                                                         |
| OWNER ACTION REQUIRED | Authorize separate staging Google OAuth client/callback and LILOs-owned GSC/GA4 access; confirm GBP scope | Independent scopes/refresh acceptance; no prod token copying                                                                                                                  |
| OWNER ACTION REQUIRED | DNS control for `console-staging.lilosgrowth.com` and expected callback/preview hosts                     | Stable TLS/auth redirect acceptance                                                                                                                                           |
| OWNER ACTION REQUIRED | Dedicated GitHub test repo, scoped App install/private-key secret, allowed paths                          | Test writes isolated before GitHub staging publish                                                                                                                            |
| OWNER ACTION REQUIRED | Valid read-only production API session/approved org scope                                                 | Verify actual LILOs Growth org/site/provider mapping/readiness; expired saved session insufficient                                                                            |
| OWNER ACTION REQUIRED | Approve dedicated canary setup in LILOs Growth repository and source baseline tag publication             | Fixed target/harness qualification and UI reference freeze before import                                                                                                      |
| BLOCKER               | Required staging secrets unavailable/unverified                                                           | New DB URLs, Auth issuer/JWKS/publishable key, encryption/CSRF signing, OAuth secrets, App private key, Hermes/inference/tool keys and telemetry must be environment-specific |

## P. Implementation phase contract and readiness

PROPOSED DESIGN: no extra phases. Refresh merged-main evidence at each phase start.

| Phase              | Coherent scope and exit                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0.5                | Separate Supabase Auth/Postgres; four staging Render services; protected Vercel placeholder/environment configuration (no production screens); hostname/secrets isolation; canonical synthetic seeds; fixture/recorded/shared provider tests; Google read-only smoke; dedicated GitHub test repo/provider-specific safety; approved readiness/canary setup. Exit environment isolation/write-denial and smoke evidence recorded |
| 1                  | Create apps/console, import frozen UI, SSR server-mediated auth/MFA/BFF/CSRF/cache/route guards/contracts/adapters/UUID context and complete Opportunity reference slice through evidence, revise, protected signals, approve, workflow/PR/build/deploy/live verification in staging                                                                                                                                            |
| 2                  | Centralized Integrations + Local Search all tabs/hospitality views, confirmed mapping/reconnect/sync, GBP operations; unsupported rankings/performance explicit unavailable                                                                                                                                                                                                                                                     |
| 3                  | Reviews/risk/response drafts/approval/provider outcome, requests only with authoritative source or explicit unavailable                                                                                                                                                                                                                                                                                                         |
| 4                  | Website & Content pages/technical/content/editor/assets/governed publication/recovery, retain exact target/page mapping                                                                                                                                                                                                                                                                                                         |
| 5                  | Leads/consent/tasks/status/communications and conversion outcomes; distinguish lead result, GA4 event and attribution                                                                                                                                                                                                                                                                                                           |
| 6                  | Canonical Automation & Agents definitions/schedules/runs/recovery/approval/stop/steer; no parallel runtime, missing prototype automation definitions explicit unavailable                                                                                                                                                                                                                                                       |
| 7                  | Reports/readiness/metrics/periods/history/delivery/export only from canonical governed source; explicitly unavailable unsourced reports                                                                                                                                                                                                                                                                                         |
| 8                  | Overview and portfolio aggregates/attention/work/activity; permissions and period/source truth across products, measured fan-out                                                                                                                                                                                                                                                                                                |
| 9                  | Administration/Settings/Users/Onboarding, canonical roles/owner continuity/modes, accessible and scoped actions                                                                                                                                                                                                                                                                                                                 |
| Staging acceptance | All matrix journeys, security/accessibility/provider simulator/contract/performance/release gates, four-service parity and restore evidence                                                                                                                                                                                                                                                                                     |
| Production canary  | Qualified fixed target, normal governed repair, PR/checks/deploy/live crawler proof, trace/audit and safe reset harness                                                                                                                                                                                                                                                                                                         |
| Gradual rollout    | Capacity -> operator -> internal users -> selected clients -> wider cohort -> canonical console; record acceptance per stage                                                                                                                                                                                                                                                                                                    |
| Rollback           | Repoint navigation/domain/project to retained web deployment; stop new console mutations if needed; reconcile in-flight durable jobs rather than delete/replay them; additive API remains compatible                                                                                                                                                                                                                            |
| Cleanup            | Separate PR only after sustained verification; remove web and obsolete adapters/contracts after mixed-version consumers retired                                                                                                                                                                                                                                                                                                 |

BLOCKER: **Phase 0.5 is BLOCKED for execution** by paid resource approval,
environment/account secrets/access and independent OAuth/DNS/App actions.
LILOs Growth scope and live readiness are NOT YET VERIFIED, rather than prerequisites
for defining or beginning unrelated synthetic staging work. The VERIFIED BASELINE ISSUE blocks baseline acceptance
and later import; it does not justify blocking unrelated staging plumbing once
owner prerequisites are supplied. Canary and Google readiness remain separate;
neither is falsely certified by local tests. Phase 0 documentation may be reviewed
and merged while those external requirements are outstanding. Stop after its PR.

## Phase 0 completion scope

VERIFIED CURRENT FACT: only the three requested documentation artifacts are changed.
Application code, migrations, deployment configuration and the release ledger are
unchanged. The latest user scope instruction limits this packet to these documents.
Adjacent API DTO/read projections, unsupported product values, provider-write safety,
callback compatibility, baseline test issues and runtime readiness are recorded here
and in the decision log; none is implemented or debugged in Phase 0.
