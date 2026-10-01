# Command Center decision log

Date: 2026-09-30. Phase 0 only. Evidence labels have the meanings defined in
`PHASE_00_INTEGRATION_CONTRACT.md`. Designs below are implementation contracts,
not completed runtime features.

| ID  | Evidence                                        | Decision / rationale / owning phase                                                                                                                                                                                                                                        |
| --- | ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D01 | VERIFIED CURRENT FACT                           | Platform baseline `0d505db70233f54f69729a85979a9c2d093fdee2`; UI baseline `d097c5255995b010f45b67a8ace90a80d00f090b`; retained requested branch and clean initial state                                                                                                    |
| D02 | PROPOSED DESIGN                                 | Preserve approved UI structure, create separate apps/console in Phase 1, retain apps/web through reversible rollout; no import or console creation in Phase 0                                                                                                              |
| D03 | OWNER ACTION REQUIRED                           | Publish permanent annotated UI baseline tag `command-center-ui-baseline-2026-09-30`, pinned to D01 UI SHA; annotate failed browser journey, never retag to hide evidence                                                                                                   |
| D04 | VERIFIED CURRENT FACT — VERIFIED BASELINE ISSUE | Approved UI validation is incomplete: 46 browser tests pass, Opportunity pointer-entry test fails; focused repeat also fails with session-closure diagnostic. No root-cause assertion or source change authorized by this discovery packet                                 |
| D05 | PROPOSED DESIGN                                 | Backend owns domain writes, permissions, approved revisions, idempotency, providers and durable runtime. Hermes reasons/drafts; console presents. Reuse canonical execution instead of introducing another agent framework                                                 |
| D06 | PROPOSED DESIGN                                 | OpportunityView is namespaced source-ID read projection; AttentionView is separate operational projection. Underlying SEO/Growth/Content/Review/GBP/Lead/workflow/publication records remain first-class; no universal write table                                         |
| D07 | PROPOSED DESIGN                                 | Unsupported rank-grid, GBP performance, review campaigns, named conversion events and persisted report/history/delivery values render explicit unavailable states. Missing metrics never zero; UI sample dates/multipliers/status writes retired                           |
| D08 | PROPOSED DESIGN                                 | Astro SSR Vercel Node adapter; proposed pdx1 near declared Render Oregon, subject to actual region/latency verification. Existing web stays static and operational                                                                                                         |
| D09 | PROPOSED DESIGN                                 | Supabase SSR request-scoped server client; host-only Secure HttpOnly SameSite=Lax cookies, server-mediated login/MFA/refresh, verified user then current Bearer to FastAPI. No browser session token exposure                                                              |
| D10 | PROPOSED DESIGN                                 | Refresh coordination is request-local plus Supabase rotation semantics; no assumption a process-local lock spans Vercel instances. Opposite-order concurrent refresh responses and stale-cookie cleanup are required Phase 1 tests                                         |
| D11 | PROPOSED DESIGN                                 | Explicit method/route BFF allowlist, one configured upstream, bounded bodies/timeouts, no upstream redirect following, CSRF nonce and exact Origin/host validation, private no-store on every authenticated response                                                       |
| D12 | PROPOSED DESIGN                                 | FastAPI OpenAPI -> committed openapi-typescript transport -> tested adapters -> product view models. Generic response dictionaries need additive Pydantic DTOs; generation alone cannot infer nested contracts                                                             |
| D13 | VERIFIED CURRENT FACT                           | Organization slugs are globally unique, normalized and immutable in current contracts. This satisfies active uniqueness; archived reservations stay reserved. No slug change/alias architecture needed for initial import                                                  |
| D14 | PROPOSED DESIGN                                 | UUID authority after authenticated active-slug resolution. If slug changes become required, audited canonical alias migration; duplicate/dead-org cleanup is separate data hygiene                                                                                         |
| D15 | PROPOSED DESIGN                                 | Additive dual-client API window and expand/migrate/contract DB. Security/correctness exceptions fix unsafe behavior with documented adapters and coordinated deployment, never preserve leakage for compatibility                                                          |
| D16 | VERIFIED CURRENT FACT                           | Existing staging Blueprint is older branch + Render DB + API/worker only. It must be reconciled in Phase 0.5 with separate Supabase Auth/Postgres and API/worker/scheduler/Hermes. No database architecture change in this packet                                          |
| D17 | PROPOSED DESIGN                                 | Provider fixtures injected at existing protocols/client factories. Production fails startup with fixtures; no environment switches inside product services. Shared recorded-response contract tests plus separate live read-only smoke                                     |
| D18 | PROPOSED DESIGN                                 | Provider-specific staging safety retains global fail-closed control: Google/GBP writes denied, GitHub only dedicated installation/repository/path allowlist. A global boolean alone cannot safely express the required exception                                           |
| D19 | NOT YET VERIFIED                                | Live tenant/provider readiness cannot be certified: saved production session expired, Render workspace selection unavailable, Vercel project-detail connector rejected arguments. Vercel project list/deployment readiness and repository topology are verified separately |
| D20 | VERIFIED CURRENT FACT                           | LILOs Growth source `fc8f63c6faaa55b98908b644cbf8db4694f80a3d`; public robots/sitemap readable. No dedicated canary in source/sitemap. Homepage declared and deployed description differ; ordinary homepage rejected as disposable canary                                  |
| D21 | PROPOSED DESIGN                                 | Future fixed `/lilos-canary` source with unique Astro binding controlling direct meta description, deterministic missing_meta_description detector and exact SiteChangeSet repair. All six qualification checks must pass before canary acceptance                         |
| D22 | PROPOSED DESIGN                                 | Manual fixed-repo/file/patch confirmation-only reset harness creates PR with normal CI and actor/run/SHA evidence; no arbitrary input, direct main reset, auto-merge or console entry point                                                                                |
| D23 | VERIFIED CURRENT FACT                           | Empty current_value supported by model; source resolver still checks exact binding/value. JSON repeated empty literals fail safe; do not weaken source editing to force a canary                                                                                           |
| D24 | PROPOSED DESIGN                                 | Normal initial SSR fan-out 1–3 reads; justify aggregate portfolio/overview/attention/opportunity/report reads. Budgets measure p95, CPU, RSS, DB pool and 5xx before plan choices                                                                                          |
| D25 | OWNER ACTION REQUIRED                           | Approve costs/access/secrets and independent OAuth/DNS/GitHub App actions. Planning base $57.25–$72.25/month incremental, expanded scenario up to $171.25 plus usage/optional protection; no paid resources provisioned                                                    |
| D26 | PROPOSED DESIGN                                 | Existing web gates remain. Add console contract/security/fixture/accessibility gates in implementation; no docs-only production console deploy                                                                                                                             |
| D27 | BLOCKER                                         | Phase 0.5 execution BLOCKED by external paid/account/secret prerequisites. Failed UI baseline acceptance and unqualified canary are distinct later acceptance blockers; unrelated environment preparation can proceed once its actual dependencies are supplied            |
| D28 | PROPOSED DESIGN                                 | Stop at one Phase 0 PR against main; no merge. Rollout stays staging -> qualified canary/capacity -> operators/internal users -> cohorts -> canonical console -> sustained verification -> separate cleanup                                                                |

## Discrepancies intentionally preserved as evidence

VERIFIED CURRENT FACT: CLAUDE's historical-document wording differs from AGENTS'
governing authority order; this packet follows AGENTS and the explicitly assigned
integration documents. Hermes remains optional to deterministic operations under
the Master Spec even though the current production Blueprint selects it for AI.

NOT YET VERIFIED: scoped live acceptance cannot be substituted with existing historical
ledger entries about other client organizations. No provider IDs, mappings,
installation state, active schedule or release parity was invented.

PROPOSED DESIGN: the old integration callback targets old web. Add a validated
console return target while preserving old web compatibility; do not silently
replace authentication deployment settings.

PROPOSED DESIGN: adjacent unsupported product contracts and baseline browser
diagnostics are recorded in these three Phase 0 artifacts; the release ledger is unchanged
under the latest user scope instruction. They are not Phase 0 implementation
tasks, and no extra phase or parallel architecture is introduced to solve them.

## Phase 0.5 — safe environment implementation

The replacement `PHASE_00_5_PROMPT.md` governs this execution. D27's blanket
external block is superseded for repository-side work; paid provisioning,
account/OAuth/DNS authorization and unavailable secrets remain individual owner
steps. Phase 0 discovery and the approved architecture were not reopened.

- D29 — IMPLEMENTED_NOT_ACCEPTED: four-service isolated manual staging Blueprint
  uses reviewed main and separate Supabase, with independent identity/secret checks;
  no Render Postgres or external resource purchase.
- D30 — IMPLEMENTED_NOT_ACCEPTED: fixtures compose at canonical provider factories,
  sharing real parsers and deterministic sanitized-response contracts. Partial GA4
  parser evidence fails closed so missing requested metrics cannot aggregate as zero.
- D31 — IMPLEMENTED_NOT_ACCEPTED: preserve global write switch, deny staging Google,
  allow only the fixed GitHub installation/repo/branch/path and checked PR file set.
  Token minting is repository scoped; production governance is preserved.
- D32 — IMPLEMENTED_NOT_ACCEPTED: staging-only canonical seed, protected console
  prerequisite configuration and existing daily GSC/GA4 read-smoke schedules/handlers.
  No copied client data/tokens, fabricated live installation or parallel scheduler.
- D33 — OWNER ACTION REQUIRED: consolidated remaining actions and exact validation
  evidence are in `PHASE_00_5_ACCEPTANCE.md`; actual recurring cost introduced is $0.
  Phase 1 is READY WITH OWNER ACTIONS BEFORE LIVE STAGING. Stop after the Phase 0.5
  PR; no automatic merge, console import, live client write or production canary.

## Phase 1 — console foundation and canonical reference slice

- D34 — IMPLEMENTED_NOT_ACCEPTED: immutable UI `d097c5255995b010f45b67a8ace90a80d00f090b`
  imported in the separate console workspace; original source isolated under reference,
  approved shell/styles/dialog adapted to SSR, old web retained. Missing remote tag
  does not block the replacement Phase 1 prompt's SHA-authoritative import.
- D35 — IMPLEMENTED_NOT_ACCEPTED: request-scoped server-only Supabase SSR/MFA,
  buffered verified cookie writes, opposite-order stale-refresh refusal, same-origin
  recovery, bound CSRF, exact host/preview isolation and private/no-store responses.
- D36 — IMPLEMENTED_NOT_ACCEPTED: closed BFF method/path/body registry forwards
  only current server Bearer and correlation; canonical revise/decision remain the
  sole audited write gates. No unsupported idempotency forwarding or automatic replay.
- D37 — IMPLEMENTED_NOT_ACCEPTED: additive typed SEO Opportunity/Attention/detail
  projections reuse canonical evidence, quality, revisions, authorization, tasks,
  runs and publication state; no universal write model, migration or duplicate engine.
- D38 — IMPLEMENTED_NOT_ACCEPTED: deterministic OpenAPI/TS exports, byte drift CI,
  adapter/source-scope tests and production fixture boundaries. Reference fixtures are
  test-only; no unsourced metrics or sample-state fallback reaches production.
- D39 — OWNER ACTION REQUIRED: live staging's eight scenarios remain pending the
  consolidated checklist in `PHASE_01_ACCEPTANCE.md`. Repository acceptance does not
  certify a live provider or production rollout. Stop at one PR; do not begin Phase 2.

## Phase 2 implementation decisions

- D40 — IMPLEMENTED_NOT_ACCEPTED: bounded typed Integrations/Local Search/Page Intelligence/GBP projections consume existing canonical services and scoped persisted sources. Astro never computes provider metrics or selects mapping authority.
- D41 — IMPLEMENTED_NOT_ACCEPTED: atomic website-check and exact-approved-post dispatch endpoints reuse ExecutionService and canonical crawl/publication enqueue, idempotency, audits and reconciliation; closed BFF exposes no arbitrary workflow launch.
- D42 — IMPLEMENTED_NOT_ACCEPTED: console OAuth return uses a configured bare HTTPS origin and a marker bound into persisted OAuth state before hashing. Existing callers retain their web return. No provider redirect registration changed.
- D43 — VERIFIED CURRENT FACT: no persisted geographic rank-grid/scan or GBP performance source exists. Explicit unavailable states remain; crawler indexability is not Google confirmed indexation. GA4 overview is organization-wide/all channels, with page organic evidence only from canonical Page Intelligence.
- D44 — OWNER ACTION REQUIRED: repository/synthetic evidence does not establish live provider acceptance. Phase 2 acceptance carries forward Phase 0.5/1 owner prerequisites and adds backend console origin plus deployed Integrations/Local Search/OAuth source-state journeys. Phase 3 requires review/merge; no Phase 3 work performed.

## Phase 3 — Reviews implementation decisions

- D45 — IMPLEMENTED_NOT_ACCEPTED: additive scoped Reviews workspace/detail projections consume canonical inventory, revisions, Google connection/mapping, import audit freshness, facts, workflows and permission-gated histories. Persisted metrics never claim provider-wide coverage; missing evidence remains null.
- D46 — VERIFIED CURRENT FACT: canonical local drafts require exact approval and AAL2 publication; no implemented client/industry approval-free local override exists. Provider-imported observations require no local approval. Backend per-response policy codes expose this distinction without prototype preference authority.
- D47 — IMPLEMENTED_NOT_ACCEPTED: Reviews BFF and SSR inbox/dialog use canonical draft/AI/approve/reserve/import actions only. Reservation replay is idempotent; stale review revisions and invalid grounding fail in the canonical service. Existing worker/provider/write-once/read-back/retry boundaries remain authoritative.
- D48 — VERIFIED CURRENT FACT: no canonical review-request campaign source, provider-wide coverage/trend metrics, approval-free local policy or manual response retry/rejection/delete API exists. Explicit unavailable states retained; no duplicate workflow or policy system.
- D49 — OWNER ACTION REQUIRED: Phase 3 repository/synthetic acceptance is separate from live staging. Consolidated inherited/deployed Reviews owner actions are in PHASE_03_ACCEPTANCE.md. Real provider writes require separate explicit authorization; stop at the Phase 3 PR, do not merge or start Phase 4.
