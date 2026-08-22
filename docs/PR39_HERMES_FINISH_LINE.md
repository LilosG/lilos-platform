# PR #39 — Hermes First-Class Runtime / Operations Finish Line

## Purpose

This document is the execution contract for PR #39. It exists to prevent another one-error-at-a-time or architecture-drift loop.

PR #39 supersedes PR #38 and preserves its pushed work. The target is one coherent controlled-pilot release in which Hermes is a first-class LILOs agent runtime, not a developer-only sidecar.

## Architecture decision

Hermes is the primary production **agent execution runtime** behind the existing LILOs AI Gateway and durable workflow system.

LILOs remains authoritative for:

- organization/location scope and tenant isolation;
- approved business facts and grounding;
- entitlements and permissions;
- workflow state and idempotency;
- cost/latency/task limits;
- human approvals;
- audit and diagnostics;
- external provider-write authorization;
- verification and reconciliation.

Hermes owns agent execution, model/tool orchestration, memory/skills/subagent behavior, and agent runtime lifecycle. Hermes may call only sanctioned LILOs/provider tools with bounded credentials and policy. It may not bypass LILOs state, approvals, tenant scope, or audit.

The current branch already adds:

- `HermesAgentProvider` behind `AIGateway`;
- typed Hermes runtime settings;
- Render private `lilos-hermes` service and private API wiring;
- Hermes provider unit tests;
- `LILOS_AI_PROVIDER=hermes` for production;
- `.env.example` Hermes settings;
- initial cleanup of inherited PageSpeed/Drive typing defects.

## Current branch / PR

- Repository: `LilosG/lilos-platform`
- PR: `#39`
- Branch: `fix/hermes-first-class-orchestration-2026-08-21`
- Base: `main`
- PR #38 is closed and preserved as superseded history.

Do not reset, rebase away, or discard current branch work.

---

## Gate 1 — Clear the exact current Python type failures

Latest clean formatting + Ruff CI reaches mypy and reports exactly these seven errors:

1. `apps/api/app/integrations/directory_service.py:306`
   - Python boolean combined with SQLAlchemy `ColumnElement` via `&`.
   - Fix the query semantics, not the type checker. Branch based on whether `mapping.platform_resource_id` exists or build SQL expressions only from SQL expressions.

2. `apps/api/app/products/seo/orchestration.py:138`
   - nullable `SEOPage | None` assigned to a variable inferred as `SEOPage`.
   - Give the lookup result correct optional typing / avoid variable reuse.

3. `apps/api/app/products/seo/orchestration.py:364`
   - JSON-column assignment typing for `score_explanation`.

4. `apps/api/app/products/seo/orchestration.py:365`
   - JSON-column assignment typing for `source_versions`.
   - Use explicit platform/domain-compatible value types; do not `type: ignore` a real contract mismatch.

5. `apps/api/app/products/seo/orchestration.py:417`
   - recommendation `effort` generic `str` vs `Literal['low','medium','high']`.
   - Make `_recommendation_text` return the actual literal type.

6. `apps/api/app/products/gbp/post_generation.py:106`
   - `_topic_hint` expects `list[dict[str, object]]` but receives `list[GovernedFact]`.
   - Use the real `GovernedFact` contract; do not convert business-fact objects into an ad-hoc duplicate representation unless the canonical API requires serialization.

7. `apps/api/app/products/gbp/post_generation.py:199`
   - `asset` redefined from line 66.
   - Rename/scope variables according to actual meaning.

Also fix the already-proven SEO scoring contract:

- `tests/python/seo/test_opportunity_scoring_contract.py` expects `explanation['final_score'] == score`.
- `opportunity_score()` must include `final_score` in its explanation. Fix implementation, not the test.

After these edits run locally before continuing:

```bash
uv run ruff format apps tests scripts migrations
uv run ruff format --check apps tests scripts migrations
uv run ruff check apps tests scripts migrations
uv run mypy apps tests scripts migrations
```

No push until those four are green.

---

## Gate 2 — Correct the orchestration architecture before declaring CI-ready

### 2.1 One canonical GBP post publication path

Current PR inheritance contains a canonical `_handle_gbp_publish_post` in `execution/handlers.py` and a second `_handle_gbp_publish_post_with_media` in `execution/operational_extensions.py` that registers the same `gbp.publish_post` key.

This registry overwrite/import-order behavior is prohibited.

Required state:

- exactly one canonical `gbp.publish_post` workflow handler;
- optional approved media integrated through that canonical product/publication path;
- no private import-order override;
- existing idempotency, provider kill-switch, approval, location mapping, verification and reconciliation behavior retained.

Add a regression test that fails if duplicate workflow keys are registered/overwritten silently.

### 2.2 External provider calls must not live inside long-held DB locks/transactions

The GBP publish path currently obtains a locked publication row and then can resolve OAuth and call Google before completing.

Follow the platform contract:

1. validate and reserve/mark pending;
2. persist/commit durable state;
3. perform provider I/O without a long-held row lock;
4. record success/failure in a new transaction;
5. verify or enter reconciliation.

Do not weaken idempotency to achieve this.

### 2.3 SEO evidence must represent the latest valid period

`SEOOrchestrationService` currently loads many GSC observations newest-first and can later process older observations for the same opportunity key, allowing older evidence to overwrite newer evidence.

Required:

- deterministic latest/current-period evidence selection;
- no overlapping-window double counting or older-window overwrite;
- preserve explicit provider date windows and provenance;
- update an existing active opportunity only from evidence that is newer/canonical for that detector;
- tests with at least two date windows proving older evidence cannot replace current evidence.

### 2.4 SEO → Content routing must be semantic

Do not mirror every SEO opportunity into Content.

Content-addressable examples include:

- striking-distance/on-page improvement;
- low-CTR snippet/content work;
- validated unmapped demand/content gap.

Pure crawl/indexability/PageSpeed/performance/accessibility technical work remains SEO/implementation work unless it contains a legitimate content action.

Add a test proving a technical PageSpeed/crawl opportunity is not automatically created as a Content opportunity.

### 2.5 Content opportunity dedupe must not depend on first 100 rows

Replace `list_opportunities(limit=100)` Python-side source-reference scanning with a direct repository/database lookup for the canonical source/dedupe reference. Add coverage with >100 existing records.

### 2.6 Operator execution must be proven end-to-end

The `execute=true` request-field unit test is not sufficient.

Test the real flow:

operator-authorized request → workflow definition → durable run → enqueued job → worker claim → handler → terminal result/recovery → history/audit.

Retain `execute=false` reservation semantics for product mutation workflows that must attach an authoritative resource before queueing.

---

## Gate 3 — Hermes is not considered integrated until the platform proves its runtime contract

### Required now

1. `resolve_ai_provider()` selects Hermes in production and fails closed if Hermes configuration is missing.
2. Content/GBP/Reviews AI tasks continue through the existing `AIGateway` grounding/secret/cost/latency controls and therefore execute via Hermes.
3. Hermes API key remains server-side only.
4. Hermes runs over Render private networking.
5. Hermes service has persistent data storage.
6. Provider unavailable/timeout/invalid-output behavior becomes a safe failed AI execution, never an unauthorized provider write.
7. Human review remains required for generated drafts.
8. Render blueprint validates.
9. A mocked provider contract test proves no secret appears in request body or user-visible output.

### Immediately after this PR is green/deployed

The next controlled-pilot runtime slice must expose Hermes agent lifecycle in LILOs Automations using its run/events/stop/steer/approval primitives. Do this through a supported LILOs adapter/service, not direct browser shell access or direct production DB access.

Then add LILOs-specific Hermes skills/tools for sanctioned operations such as:

- read current tenant-scoped business facts;
- read GBP/GSC/GA4/crawl evidence;
- propose SEO/content/GBP work;
- initiate allowed LILOs workflows;
- inspect workflow/run status;
- submit work to existing approval queues.

Provider mutations remain in existing product workflows, never direct Hermes calls.

---

## Gate 4 — Full repository validation

Read `.github/workflows/ci.yml` and reproduce all locally reproducible gates. At minimum:

```bash
uv run ruff format --check apps tests scripts migrations
uv run ruff check apps tests scripts migrations
uv run mypy apps tests scripts migrations
uv run pytest -q
npm run format:check
npm run lint:web
npm run typecheck:web
npm run test:web
npm run build:web
npm run check:browser
npm run check

git diff --check
```

Also run the repository's exact Render blueprint, migration, synthetic restore, environment-example, dependency/security and release-acceptance validation commands from CI.

Do not push because a subset is green.

---

## Gate 5 — Adversarial release audit

After builder gates are green, run the existing read-only `release-auditor` over the complete PR #39 diff.

It must explicitly check:

- duplicate implementations/workflow keys;
- tenant/location leakage;
- provider-write bypasses;
- missing approval/audit/reconciliation paths;
- stale/overlapping SEO evidence semantics;
- technical SEO incorrectly entering Content;
- Hermes secrets/config exposure;
- Render service/config parity;
- UI claims inconsistent with durable state;
- hidden manual production steps.

Resolve every legitimate blocker before making PR #39 non-draft.

---

## Gate 6 — Controlled pilot acceptance after merge/deploy

One Wheyland Electric journey must prove, with no SQL/manual database intervention:

1. correct organization/location selected;
2. Google/GBP/GSC/GA4 connection truth and freshness;
3. GBP discovery/sync refresh completes;
4. SEO crawl + analysis completes and produces explainable useful opportunities when evidence warrants them;
5. appropriate SEO work routes into Content, while technical-only work does not;
6. Hermes generates a grounded Content or GBP draft from approved client facts;
7. human review/approval remains explicit;
8. GitHub publishing target is correct for Wheyland;
9. one legitimate controlled provider/publication action is verified/reconciled;
10. Automations shows the actual durable execution and recovery state;
11. Overview/Insights/Content/SEO/Automations agree about current health and do not present contradictory status;
12. client-role user sees only client-appropriate resources and controls.

Only then classify the controlled client pilot as ready.

## Stop conditions

Stop and report instead of guessing if:

- a required production secret/provider resource is genuinely unavailable;
- a provider capability cannot be verified safely;
- fixing a defect requires bypassing an approval/tenant/audit boundary;
- branch state differs unexpectedly from PR #39;
- a test would require destructive or fake client data in production.

Otherwise continue through the gates without asking for approval after every small fix.
