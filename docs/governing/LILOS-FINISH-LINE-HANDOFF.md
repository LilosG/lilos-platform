# LILOs Platform — Finish-Line Handoff

**Prepared:** August 11, 2026 (Pacific Time)  
**Purpose:** Give one principal coding agent a compact, current, authoritative release-closure brief so the project can reach a controlled client pilot without repeating prior speculative debugging, architecture drift, direct-database shortcuts, or endless full-suite cycles.

---

## 1. Executive decision

LILOs does **not** need another rebuild, architecture rewrite, or open-ended “finish the platform” pass.

The shared platform and most product foundations are substantially implemented. The remaining work is concentrated in:

1. deployment parity,
2. client/agency scoping and product-readiness correctness,
3. live integration acceptance,
4. one complete real-client operator journey,
5. controlled provider-write acceptance,
6. dashboard / workflow UX convergence,
7. truthful classification of anything still not live-accepted,
8. one final release gate.

The correct target for today is a **Controlled Client Pilot**. Formal Production GA should only be claimed if the Master Specification's operational/recovery evidence is actually complete.

---

## 2. Authority hierarchy

The coding agent must use this order of authority:

1. `/docs/LILOS-MASTER-SPEC.md`
2. `/docs/LILOS-BUILD-ROADMAP.md`
3. `/docs/LILOS-MASTER-BUILD-PROMPT.md` (or the current equivalent build prompt path)
4. current `main` repository state and current production evidence
5. ADRs / current implementation documentation
6. this handoff as an execution brief
7. historical chats only as forensic context — never as implementation authority

If current code and an old chat disagree, inspect the current repository and live system. Do not rebuild behavior merely because an old chat says it was missing at that time.

---

## 3. Permanent engineering guardrails

These are non-negotiable:

- No direct production SQL as a normal administrative or repair path.
- No fabricated provider IDs, mappings, resources, metrics, users, locations, or integration records.
- No OAuth bypass.
- No manual insertion of entitlements, provider connections, GBP resources, or mappings to make a UI unblock.
- No duplicate product/integration/auth/workflow subsystem.
- No one-off Wheyland-specific application logic.
- No broad refactor unless evidence proves the owning architecture is the root cause.
- No coding from a guessed root cause.
- No provider write without confirmed tenant, permission, entitlement/readiness, mapping, credential, idempotency, runtime gate, verification, reconciliation, and audit context.
- No treating provider acceptance as proof of completion.
- No missing data represented as zero.
- No production secrets in frontend variables, prompts, logs, screenshots, or docs.
- No repeated full repository test suite after every small correction.
- No claim of completion without live acceptance evidence for the behavior being claimed.

For every defect use this sequence:

**Reproduce → capture operator action → network/API status → safe error + correlation ID → owning service → provider evidence if applicable → actual root cause → smallest architecture-correct fix → focused regression test → repeat the original operator action.**

If evidence does not support a root cause, do not code it.

---

## 4. What went wrong in the prior AI-assisted work

The earlier sessions are useful because they show exactly what must not happen again.

### 4.1 Oversized “finish everything” prompts

These caused context loss, unreviewable scope, repeated refactors, and implementation state being confused with operator usability. The correct pattern is a finite acceptance queue with coherent work packets.

### 4.2 Speculative diagnosis

A prior onboarding failure was confidently attributed to a post-MFA/AAL2 token race. Later production evidence showed the actual defect was an API contract mismatch: frontend callers expected arrays while backend list endpoints returned paginated `data.items`, producing `data.map is not a function`.

Permanent lesson: **never implement a hypothesized root cause before reproducing and tracing the failure.**

### 4.3 Gemini guardrail violations

The Gemini session repeatedly proposed or instructed direct Supabase changes for entitlements, connections, GBP records, mappings, and other platform state. It also proposed bypassing OAuth and used invented Google resource identifiers.

Do **not** blindly delete historical rows because of that history. Instead:

**fresh provider discovery → compare provider truth to persisted state → reconcile through current owning services → preserve history/audit.**

### 4.4 Google OAuth confusion

Google Cloud application verification, OAuth scopes configured for the app, and a particular user's granted scopes were repeatedly conflated.

The intended lifecycle is now straightforward:

- A verified OAuth application can still require one incremental user grant when genuinely new product scopes are introduced.
- Once the required GBP + GSC + GA4 scopes are granted and the credential is healthy, ordinary use must not repeatedly send the operator through consent.
- Reauthorization should occur only for a real scope upgrade, revoked/expired/invalid credential, or deliberate reconnect.
- Do not change the Google Cloud project or verification state merely because a product page is blocked. First inspect the actual connection health and granted scopes.

---

## 5. Current repository truth (checked after the historical chats)

Repository: `LilosG/lilos-platform`  
Default branch: `main`

### Current `main`

`65c51f4dfd0a3d9a7642a68814a58c21679038eb`

Commit title:

`feat(handlers): add GBP media upload, leads communication, and scheduled sync handlers (#15)`

There were no open pull requests at the time of this handoff check.

### Recent merged release sequence

#### PR #10 — Google reauthorization lifecycle

The implementation fixed the incorrect reconnect/missing-product logic, preserves already granted GBP/GSC/GA4 scopes, keeps incremental authorization separate, avoids unnecessary OAuth actions for healthy fully scoped connections, and improves encrypted credential replacement lifecycle.

**Important:** the code fix does not substitute for live acceptance. Prove the healthy fully scoped connection no longer prompts again in normal navigation/reloads.

#### PR #11 — Review provider reply reconciliation

Review reconciliation behavior was hardened. Recent release evidence reports Wheyland's 90 reviews reconciled/responded.

#### PR #12 — GBP sync semantics

Successful unchanged GBP profile syncs advance current sync freshness rather than appearing stale merely because provider content did not change.

#### PR #13 — Product operations UX

Large frontend pass (agency operating dashboard, workspace scoping, content/SEO/Insights/product status components). This is merged.

#### PR #14 — Final closure release

Release evidence reported:

- backend tests passing,
- release gate/hardening passing,
- Render API live at the release commit,
- worker/scheduler heartbeats,
- GitHub App installed for Wheyland,
- publishing target configured as `LilosG/wheylandelectric-final-2.0`,
- 90 reviews reconciled,
- provider writes intentionally disabled by default.

PR #14's Vercel deployment completed successfully.

#### PR #15 — Current main

Adds the missing GBP media workflow, migration `20260811_0002`, provider verification/reconciliation behavior, leads communication workflow orchestration, and scheduled GBP/reviews handlers.

**Deployment caveat:** Vercel status for current `main` is currently **failure: deployment rate limited, retry in 24 hours**. Therefore exact current-main frontend deployment parity is not established. The prior PR #14 Vercel deployment is green.

Do not waste model tokens treating the Vercel rate limit as a code defect. If same-day deployment is mandatory, resolve the Vercel account/build-limit issue first through the supported account/plan path rather than creating an architectural hosting workaround.

---

## 6. Current product standing

Use the following statuses as a starting hypothesis, then verify live before changing code.

| Capability | Current standing | Required closure |
|---|---|---|
| Supabase/database foundation | Built | Verify migration/deployment parity; no rebuild |
| Auth/MFA/AAL2 | Built | Browser acceptance for operator and real client role |
| Organizations/locations | Built | Repeatable client setup; correct read models |
| Onboarding | Built | Make resumable flow operationally clean; remove contradictory blockers |
| Google OAuth | Built; lifecycle repaired in PR #10 | Prove real current grants/health and no repeated consent |
| GBP account discovery | Built/live exercised | Restrict discovery presentation to privileged setup context |
| GBP location mapping | Built; Wheyland managed/synced | Verify confirmed mapping and tenant/client presentation |
| GBP profile sync | Built/live exercised | Reconfirm current sync/freshness after deployment |
| GBP Reviews | Strong live evidence: 90 reconciled/responded | Controlled write only if a legitimate unanswered review exists |
| GBP Local Posts | Built with verification/reconciliation | Legitimate controlled write acceptance |
| GBP Media | Built in current PR #15 | Deploy migration/backend and run legitimate controlled acceptance |
| Search Console | Built | Real property discovery → mapping → sync → SEO use |
| GA4 | Built; current Insights screenshot shows live metrics | Verify property mapping/source/freshness and date semantics |
| SEO | Built | Fix readiness/scoping if blocked; prove GSC-backed workflow and crawl output |
| Content | Built; GitHub App reported installed | Resolve one business-fact blocker through UI; draft → approve → controlled PR publication |
| Insights | Real aggregation + GA4 data | Correct source/readiness semantics; reporting period/trends/freshness; no raw provider-resource counting |
| Leads core | Built | Real intake/routing/assignment/state acceptance |
| Email/SMS speed-to-lead | Not yet proven production-complete | Validate consent/suppression/provider dispatch/delivery reconciliation before claiming live |
| AI/task foundation | Exists | Product-specific AI can operate; generic autonomous-agent expansion must not block pilot |
| UX | Large redesign merged and deployed at PR #14 | Current screenshots still fail final acceptance; bounded convergence required |
| Formal production ops | Partial | Backup/restore, recovery, observability and formal acceptance evidence before GA claim |

---

## 7. Critical findings from the current LILOs screenshots

These current screenshots are more important than a PR title that says “complete.” They are live acceptance evidence.

### 7.1 Insights screen

Current visible state:

- Organization: Wheyland Electric
- UI labels the scope as `Client workspace`
- GA4 KPIs display Sessions 764, Users 576, Page Views 1201, Conversions 58
- Google Analytics shows connected / one mapped property
- Business Profile says blocked: `Create the location profile.`
- Reviews says blocked: `Create the location profile.`
- Leads says operational
- Content says blocked by one business detail needing confirmation
- SEO says blocked: `Create the location profile.`
- Cross-product cards simultaneously show Business Profile Locations 17 / Profile Snapshots 17, Reviews Responded 90, SEO Crawls Completed 2

This creates multiple acceptance problems:

1. **Contradictory state.** Business Profile and Reviews cannot simultaneously look blocked for lack of a location profile while the product surfaces show synced GBP data and 90 reviews.
2. **Metric semantics are unclear.** `Locations 17` in a Wheyland client workspace requires immediate verification. If it represents all provider-discovered resources visible to the Google credential instead of confirmed Wheyland managed locations, the Insights read model/label is wrong.
3. **The KPI row is not yet spec-grade.** It lacks a clear reporting period, comparison/trend, source/direction presentation, and strong first-viewport action context.
4. **The first viewport is setup/readiness-heavy**, making the application feel like an implementation console instead of daily operating software.

Do not fix these with frontend text overrides. Trace the owning readiness and metric aggregation contracts.

### 7.2 Business Profile screen

The current Wheyland `Client workspace` page shows one managed Wheyland Electric location as synced, then a very large `Setup — discovered locations not yet managed` section containing numerous other businesses accessible through the Google credential (restaurants and other agency clients/businesses).

This is the most important UX/scoping issue currently visible.

The correct distinction is:

- a provider connection may discover multiple resources accessible to the authorizing Google user,
- the platform must explicitly map resources to LILOs organizations/locations,
- a client product workspace should operate on its confirmed mapped resources,
- broad provider discovery/mapping belongs in a privileged Integrations/onboarding administration workflow.

**P0 acceptance test:** log in with an actual Wheyland client-role account. If that role can see names/resources belonging to other businesses, treat it as a release-blocking cross-client information exposure. If only the agency operator can see it, it is still a severe information-architecture problem because the screen is labeled `Client workspace` and the resource-discovery queue dominates normal GBP operations.

Do not assume the other discovered businesses are fake. They may be real resources accessible to the agency Google account. The problem is their scope/presentation/mapping semantics.

### 7.3 Navigation

The current LILOs client workspace shell visibly exposes admin-oriented navigation such as Administration and Client Onboarding. Backend authorization still needs to remain authoritative, but client presentation should be capability/scope aware. A client should not discover forbidden tools by clicking them and receiving a 403.

### 7.4 Glass Ops benchmark

Do not copy the dark navy color system or field-service domain.

Copy these qualities:

- immediate information hierarchy,
- first-viewport KPIs,
- obvious action queues,
- focused product workspaces,
- consistent card/table/tab patterns,
- intentional empty/loading/error states,
- concise integration directory with provider drill-down,
- clear settings organization,
- high information density without visual clutter.

LILOs should feel like a professional growth-operations platform, not a setup/control panel.

---

## 8. Required UX target

### 8.1 Agency Overview

First viewport should answer within seconds:

- Which client/location am I operating?
- What changed?
- What requires action?
- What is scheduled today?
- Are data sources healthy/fresh?

Recommended structure:

**Header / scope bar**
- organization
- optional location
- reporting period
- last data refresh / source health summary

**4–6 outcome KPI cards**
Examples, based only on enabled sources:
- Organic Search Clicks — current period + comparison
- GBP Interactions — calls/directions/website where available
- Reviews — rating, new reviews, waiting for response
- Leads — new/qualified leads + median response time
- Conversions — defined GA4 conversion metric + comparison
- Completed Growth Work — published/verified items for current period

Each metric must carry period, source/freshness, and comparison where valid.

**Requires Attention**
- failed connection/sync
- pending approvals
- data-quality issues
- unresolved business facts
- publication/reconciliation failures

**Today's Work**
- posts due
- content approvals
- review responses
- lead follow-up SLA issues
- reports due

**Below first viewport**
- trends / performance visualization
- recent completed work / activity
- product health and source freshness
- operational diagnostics only as drill-down

Setup/readiness appears prominently only when it actually blocks a requested capability.

### 8.2 Client Home

Much simpler:

- Account status
- 3–5 outcome KPIs
- What changed this period
- Requires your attention (approvals, connection, missing info)
- Work completed
- Upcoming work
- data-as-of/freshness

Do not expose agency portfolio diagnostics, raw integration discovery, internal costs, provider IDs, or admin tools.

### 8.3 Integrations

Use a directory → focused provider-workspace pattern.

**Directory**
- Google
- GitHub
- email provider
- SMS provider when enabled
- future integrations

Each provider card: connected/degraded/action-required, enabled capabilities, last successful sync.

**Google workspace**
- Credential health
- Granted capabilities/scopes: GBP / Search Console / GA4
- Provider account
- Confirmed mappings
- Last sync and freshness per capability
- Missing capability action only when genuinely missing
- Explicit reconnect only when credential health requires it
- Admin-only `Unmapped resources` queue, searchable/collapsible

**Mapping queue**
- provider resource
- provider account
- suggested LILOs organization/location
- matching evidence
- mapping status
- explicit confirm/reject

Never force the normal client GBP workspace to render the entire provider discovery set.

### 8.4 GBP Product

Normal product workspace should be operational, not an integration setup dump.

Suggested navigation:
- Overview
- Profile
- Posts
- Media
- Reviews (or cross-link to Reviews product)
- Performance
- Recommendations / Changes
- Activity / Audit as appropriate

If setup is incomplete, show one bounded blocking banner with a direct action to Integrations/Mapping.

### 8.5 Insights

Move from “totals + readiness” to decision support:

- period selector
- current vs comparison
- source/freshness
- trends
- drill-down
- data-quality/partial-period states
- cross-product results
- explicit unavailable/not-connected/stale states

Do not treat missing as zero and do not count unmapped provider resources as client business locations.

---

## 9. Today’s finite closure queue

The principal agent should continue through this queue without stopping after every minor fix. Stop only for a genuine user-only external action, an irreversible/high-risk provider decision, or an evidence-backed architecture decision.

### Packet 0 — Freeze and establish deployment parity

1. Confirm local/current branch starts from `main` at or after `65c51f4dfd0a3d9a7642a68814a58c21679038eb`.
2. Record exact current frontend/backend/worker/scheduler commit identities.
3. Confirm Supabase/Alembic migration head includes `20260811_0002` before exercising GBP media.
4. Confirm Render API/worker/scheduler deployment parity with current intended release.
5. Record the Vercel rate-limit blocker separately. Do not write code to “fix” it.
6. Do not touch production Google configuration in this packet.

Exit: one current release ledger with deployed component versions and blockers.

### Packet 1 — P0 client-scope and readiness correctness

1. Exercise Wheyland as an agency operator and as a real client-role user.
2. Verify client navigation hides unauthorized admin/onboarding items.
3. Verify the client GBP page cannot expose unrelated provider resources.
4. Move broad provider-resource discovery into privileged Integrations/Google mapping UI if needed.
5. Verify Insights `Locations 17` semantics.
6. Verify all client/Insights metrics only use governed org/location/resource mappings.
7. Trace and repair the contradictory `Create the location profile` readiness state through its owning service/read model.
8. Add focused regression tests for scope/readiness behavior.

Exit: Wheyland client role sees only authorized client scope; agency mapping remains usable; readiness reflects actual managed state.

### Packet 2 — Google lifecycle + GSC/GA4 acceptance

1. Read current connection health and recorded grants.
2. If GBP/GSC/GA4 are already granted and healthy, do not start OAuth.
3. If a capability is genuinely missing, perform only the required incremental authorization.
4. After successful grant, prove reload/navigation does not prompt again.
5. Discover/map/sync Search Console property through governed mapping.
6. Verify GA4 mapped property and current metrics/date range/freshness.
7. Verify Google provider IDs never become LILOs tenant scope by themselves.
8. No Google Cloud console edits unless a real provider response identifies a configuration defect.

Exit: Google is connected once, normal navigation is stable, GBP/GSC/GA4 are truthfully mapped/synced or a specific external blocker is documented.

### Packet 3 — Complete Wheyland operator journey

Run exactly:

**Settings / business facts → Integrations → GBP → Reviews → SEO → Content → Insights → Leads**

For each screen verify:
- truthful status
- correct organization/location
- no unrelated data
- useful next action
- empty/degraded/error state
- successful normal workflow

Specific items:
- resolve the one Content business-detail confirmation through the platform UI,
- verify SEO GSC/crawl data and recommendation lifecycle,
- verify Reviews remain reconciled and deduplicated,
- verify Leads intake/routing/assignment/status and consent/suppression state.

Exit: one real client can be operated without direct database manipulation.

### Packet 4 — UX convergence

Do this only after the data/readiness contracts above are correct.

1. Recompose Agency Overview around KPIs + Requires Attention + Today’s Work.
2. Create/verify simplified Client Home.
3. Refine Integrations directory/provider drill-down.
4. Make GBP an operational product screen rather than discovery dump.
5. Improve Insights period/comparison/trend/source/freshness presentation.
6. Normalize tabs, cards, tables, empty states, spacing, type scale, button hierarchy.
7. Preserve current LILOs brand; use Glass Ops as hierarchy/quality reference, not a theme to clone.
8. Desktop first but verify mobile critical paths required by spec.

Exit: a new operator understands status and next actions in seconds; client workspace feels intentionally client-facing.

### Packet 5 — Controlled live write acceptance

Keep the global provider-write kill switch fail-closed by default.

Only enable a bounded write window for legitimate test actions.

Recommended order:

1. **GitHub Content PR publication** — safest/reversible, does not have to merge/publicly deploy content.
2. **GBP Local Post** — only a real approved post.
3. **GBP Media** — only a real approved image/media asset and after PR #15 deployment/migration parity.
4. **Review reply** — only if a real unanswered review exists.
5. **Profile write** — only if a real, approved correction exists.

For every live write prove:

approval → reservation/idempotency → provider write → provider re-read verification → canonical state update → reconciliation behavior → audit → no duplicate on replay.

Disable the broad write switch again after the test window unless the release policy explicitly approves ongoing writes.

### Packet 6 — Speed-to-lead truth test

Current main now contains a `leads.send_communication` workflow handler. The current implementation creates notification intent/delivery records and describes actual email/SMS dispatch as the responsibility of durable notification delivery jobs.

Do **not** equate workflow orchestration with a delivered message.

Verify separately:

**Email**
- actual provider connector
- template/rendering
- consent eligibility where applicable
- destination validation
- suppression
- durable dispatch job
- provider acceptance ID
- delivery/failure state
- retries/idempotency
- reconciliation/webhook if supported
- lead communication status semantics

**SMS**
- actual provider connector
- explicit consent basis
- suppression/STOP handling
- destination validation
- durable dispatch
- provider acceptance/delivery state
- retries/idempotency
- reconciliation

Critical semantic check: `LeadCommunication.status = sent` / `sent_at` must not falsely mean provider-dispatched if only a notification delivery has been queued. If the platform distinguishes queued/accepted/delivered elsewhere, ensure the UI/metrics use the correct milestone. If it does not, fix the owning domain contract rather than masking it in UI.

If either channel cannot be proven today, leave it visibly pilot-disabled and classify it as `IMPLEMENTED_NOT_LIVE_ACCEPTED` or `CONFIRMED_GAP`. It must not block the rest of the client pilot.

### Packet 7 — One final release gate

During implementation use focused tests only.

At the end run the complete applicable gate once:
- backend unit/integration tests
- PostgreSQL integration tests that were previously skipped locally
- migration forward check
- tenant/auth/permission regressions
- connector contract tests
- frontend unit/type/lint/build
- browser critical journeys
- accessibility critical workflow check
- secrets scan
- release/preflight scripts
- Render API/worker/scheduler smoke
- Vercel route/auth smoke once deployment is available

Produce a final release ledger with each capability classified:
- `LIVE_ACCEPTED`
- `IMPLEMENTED_NOT_LIVE_ACCEPTED`
- `EXTERNAL_BLOCKER`
- `PILOT_DISABLED`
- `NOT_IN_PILOT_SCOPE`

No generic “done” claim.

---

## 10. Controlled Client Pilot acceptance gate

Do not issue a client login until all of these are true:

- correct organization/client role authenticates,
- client cannot see unrelated business names/resources/data,
- client navigation is permission-aware,
- Wheyland managed location is correctly mapped and not contradicted by readiness banners,
- Google connection does not repeatedly demand consent in ordinary use,
- current client-visible data is truthful and freshness is shown,
- critical pages do not require direct database operations,
- error/empty/degraded states have valid next actions,
- no fake dashboard metrics,
- agency can complete routine workflows through the app,
- deployed frontend/backend versions are known,
- known pilot-disabled capabilities are explicitly labeled and do not masquerade as complete.

---

## 11. Formal Production GA is a separate claim

The Master Specification and roadmap require more than a green Vercel build for formal GA. Formal GA requires the defined production operational package, including monitoring/alerts, backup and restore evidence, recovery/rollback, critical workflow evidence, accessibility/security acceptance, and other Section 26/27 requirements.

Do not let that distinction derail today's controlled client pilot. Also do not erase it by falsely calling the entire formal spec certified.

---

## 12. AI / agent scope for the pilot

The platform vision explicitly treats AI as an enhancement to governed software.

For the pilot, prioritize concrete product tasks:

- review classification/drafting,
- content drafting/validation,
- SEO clustering/recommendation assistance,
- lead classification/summary/drafting,
- insight narrative over validated metrics.

Do not create a generic autonomous-agent layer merely to satisfy the word “agents.” Scheduled syncs, durable workflows, approvals, and product-specific AI tasks are the correct production primitives. Expand autonomous behavior only after the core operating loop is stable and measurable.

---

# 13. Exact principal-agent prompt

Paste the following into the principal coding agent from the repository root.

```text
You are the principal release-closure engineer for the LILOs platform.

THIS IS NOT A REBUILD OR AN ARCHITECTURE EXERCISE.
Your job is to take the CURRENT repository and CURRENT deployed system through a finite production-acceptance queue and make it ready for a controlled real-client pilot today.

Before editing anything, read completely and obey:
1. /docs/LILOS-MASTER-SPEC.md
2. /docs/LILOS-BUILD-ROADMAP.md
3. the current Master Build Prompt in /docs
4. applicable ADRs
5. LILOS-FINISH-LINE-HANDOFF-2026-08-11.md

Then inspect CURRENT main, git history, migrations, tests, deployment config, and current runtime evidence. Historical chats are forensic context only and are NOT implementation authority.

CURRENT REPOSITORY BASELINE TO VERIFY:
main was last observed at:
65c51f4dfd0a3d9a7642a68814a58c21679038eb
feat(handlers): add GBP media upload, leads communication, and scheduled sync handlers (#15)

Do not assume this SHA is still current: verify it before editing and use the newer repository truth if main has moved.

NON-NEGOTIABLE RULES:
- no direct production SQL repair
- no fabricated provider IDs, mappings, records, metrics, or resources
- no OAuth bypass
- no one-off Wheyland logic
- no duplicate subsystem
- no broad refactor without an evidence-backed root cause
- no coding from hypotheses
- no weakening tenant/auth/permission/entitlement/readiness/approval controls
- no provider write without mapping + approval + idempotency + verification + reconciliation + audit
- no secrets in frontend/logs/docs/prompts
- no missing data represented as zero
- no repeated full-suite execution after every small fix
- no claim of completion without live acceptance evidence

DEFECT LOOP — REQUIRED:
For every failure:
1. reproduce the exact operator action
2. capture endpoint, HTTP status, safe error/body, correlation ID, frontend caller
3. inspect owning backend service and provider evidence when applicable
4. determine the ACTUAL root cause
5. implement the smallest architecture-correct repair
6. add focused regression coverage
7. run focused validation
8. repeat the original operator action
9. continue automatically to the next acceptance scenario

Do not stop after every small defect. Batch related fixes into coherent, reviewable commit packets. Stop only for a genuinely user-only external action, an irreversible/high-risk provider choice, or a real architecture decision that cannot be resolved from the governing documents.

CURRENT HIGH-PRIORITY LIVE EVIDENCE:
- PR #14 UX is deployed successfully.
- current main/PR #15 Vercel deployment was last observed rate-limited; treat deployment parity as an operational blocker, not a code defect.
- Wheyland Business Profile shows one managed synced location BUT also a huge list of other Google-discovered businesses under a page labeled Client workspace.
- Wheyland Insights simultaneously says Business Profile/Reviews/SEO are blocked by “Create the location profile” while also showing GBP location/snapshot counts and 90 responded reviews.
- GA4 metrics are visibly present: sessions/users/pageviews/conversions.
- Content is blocked by one business fact needing confirmation.
- Google OAuth lifecycle was repaired in PR #10. Do NOT blindly reauthorize or touch Google Cloud. First inspect actual current connection health and granted capabilities.
- provider writes are intentionally fail-closed by default.

EXECUTION QUEUE — COMPLETE IN ORDER:

PACKET 0 — BASELINE + DEPLOYMENT PARITY
- verify current main/branch/clean tree
- record frontend/API/worker/scheduler deployed SHAs
- verify Supabase/Alembic migration head, including 20260811_0002 if current code requires it
- verify Render API/worker/scheduler health/heartbeats
- record Vercel rate-limit/deployment state
- do not alter Google/provider configuration

PACKET 1 — CLIENT SCOPE + READINESS P0
- test Wheyland as agency operator and real client role
- client navigation must hide unauthorized Administration/Client Onboarding
- client GBP/product pages must not expose unrelated provider resources
- broad Google resource discovery belongs in privileged Integrations/Google mapping workflow
- verify what Insights “Locations 17” actually counts
- ensure client metrics use confirmed governed org/location/resource mappings only
- trace and repair contradictory “Create the location profile” readiness through the owning service/read model
- add regressions and retest

If a real client role can see names/resources belonging to other organizations, this is a RELEASE BLOCKER. Fix it before any client login is issued.

PACKET 2 — GOOGLE / GSC / GA4
- inspect connection health + recorded grants
- healthy fully scoped connection must not launch OAuth
- only perform incremental authorization if a required capability is genuinely absent
- after any legitimate grant prove reload/navigation does not prompt again
- discover/map/sync Search Console through governed mapping
- verify GA4 property mapping, date semantics, source and freshness
- no Google Cloud console changes unless an actual provider error proves configuration is missing

PACKET 3 — ONE REAL WHEYLAND OPERATOR JOURNEY
Run:
Settings/business facts -> Integrations -> GBP -> Reviews -> SEO -> Content -> Insights -> Leads

For every surface verify correct scope, truthful state, usable action, and degraded/error behavior.
Resolve the one Content business-fact blocker through the normal UI.
Do not use SQL to get past setup.

PACKET 4 — UX CONVERGENCE
Use the supplied Glass Ops screenshots as QUALITY / INFORMATION-ARCHITECTURE references, not as a theme to clone.

Agency Overview first viewport:
- org/location/period context
- 4-6 meaningful KPIs with source/freshness/comparison where valid
- Requires Attention
- Today's Work
Then trends, recent completed work/activity, product/source health.

Client Home:
- simpler outcome KPIs
- what changed
- requires your attention
- completed work
- upcoming work
- freshness
No agency diagnostics or admin tools.

Integrations:
- provider directory -> focused provider workspace
- Google workspace: credential health, GBP/GSC/GA4 capabilities, account, mappings, sync/freshness
- unmapped resources: admin-only searchable/collapsible mapping queue

GBP:
- normal operational workspace for mapped location(s)
- setup only as a bounded blocker banner
- profile/posts/media/reviews/performance/recommendations/activity as appropriate

Insights:
- reporting period
- comparison/trend
- source + freshness
- data-quality/partial/unavailable states
- no contradictory readiness
- no raw provider-resource counts presented as client locations

Do not hardcode UI state to hide backend/read-model defects.

PACKET 5 — CONTROLLED LIVE WRITES
Keep global provider writes false by default.
Use the smallest legitimate write window and only real content/data.
Preferred order:
1. GitHub content PR publication
2. real GBP Local Post
3. real GBP media after current deployment/migration parity
4. review reply only if a real unanswered review exists
5. profile write only if a real approved correction exists

For each prove:
approval -> idempotent reservation -> write -> provider re-read -> verified canonical state -> reconciliation -> audit -> duplicate-safe replay.

PACKET 6 — SPEED-TO-LEAD TRUTH TEST
Current main contains leads.send_communication orchestration that creates notification intent/delivery; actual provider dispatch is delegated to durable notification delivery jobs.
Do NOT call email/SMS live merely because the orchestration exists.

Verify actual provider dispatch, consent, suppression, destination validation, idempotency, provider acceptance, delivery/failure reconciliation, and status semantics for email and SMS separately.
Check that LeadCommunication “sent” / sent_at cannot falsely mean provider-dispatched if the platform only queued a NotificationDelivery.
If not provable today, leave the capability pilot-disabled and label it accurately. Do not let it block the rest of the pilot.

PACKET 7 — FINAL RELEASE GATE ONCE
During fixes run focused tests.
At the end run the complete applicable test/migration/security/browser/accessibility/build/preflight/smoke gate once.
Include PostgreSQL integration tests that had previously been skipped when a test DB was unavailable.

FINAL OUTPUT REQUIRED:
1. exact current/deployed SHAs
2. changed files + commits/PR
3. root causes fixed
4. tests/checks actually run
5. live acceptance evidence by product
6. release matrix with ONLY these labels:
   LIVE_ACCEPTED
   IMPLEMENTED_NOT_LIVE_ACCEPTED
   EXTERNAL_BLOCKER
   PILOT_DISABLED
   NOT_IN_PILOT_SCOPE
7. known limitations
8. Controlled Client Pilot: GO or NO-GO with exact reason
9. Formal Production GA: separate GO/NO-GO classification based only on actual Master Spec evidence

Do not spend time rewriting the Master Spec, inventing another roadmap, or polishing architecture that is already functioning. The goal is to FINISH, PROVE, POLISH, AND RELEASE the current platform through the normal product paths.
```

---

## 14. Model choice / cost-control execution notes

For this closure run, the model should receive:

- this handoff,
- the three governing project documents,
- direct access to the current repository,
- current screenshots / browser access,
- current runtime/deployment evidence.

Do **not** preload the entire old chat history as prompt context unless investigating one specific historical defect. That history is large, contradictory, and includes obsolete implementation state.

Use one principal agent. Avoid a crowd of agents repeatedly auditing the same code. If parallel work is used, keep it to clearly independent, bounded checks and converge immediately into one release ledger.

Use focused tests while iterating and the full gate once at the end.

---

## 15. Final definition of success for today

Today is successful when:

- Wheyland can be operated end-to-end from the platform UI,
- Google connection is stable without recurring unnecessary consent,
- GBP/GSC/GA4/GitHub data/mapping is governed and scoped,
- client login cannot expose other agency resources,
- GBP/Reviews/SEO/Content/Insights readiness is truthful,
- the agency dashboard is a daily operating surface instead of a setup board,
- the client dashboard is intentionally client-facing,
- legitimate provider-write vertical slices are verified where possible,
- anything unproven is explicitly disabled/labeled instead of faked,
- one final release gate passes for the controlled pilot,
- the exact deployed versions and acceptance evidence are recorded.

That is the finish line. Do not replace it with another architecture phase.
