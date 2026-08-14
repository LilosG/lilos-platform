# AGENTS.md — LILOs Platform

Every coding agent session in this repository loads this file first. It overrides model defaults and habits. Where it conflicts with a packet instruction, the packet wins; where it conflicts with your inclination, this file wins.

## Authority order

1. `/docs/LILOS-MASTER-SPEC.md` — required behavior and acceptance
2. `/docs/LILOS-BUILD-ROADMAP.md` — sequence and exit criteria
3. `/docs/LILOS-MASTER-BUILD-PROMPT.md` — engineering standard
4. `/docs/LILOS-CAPABILITY-TRUTH.md` — what is actually implemented right now
5. The assigned packet
6. Existing code — evidence of current state, not authority

When documents conflict, do not silently pick one. Preserve the more restrictive behavior and report the conflict.

## The rule that exists because it was broken

**No UI without backend.** If a control, field, or status implies a capability the backend does not have, you either implement the capability or remove the control in the same change. A disabled control labeled "Not available yet" is acceptable. A live control that silently does less than it says is a defect of the same severity as a data leak.

This rule exists because the SEO crawl UI shipped a "Max pages" field on a backend that fetches exactly one URL and never discovers a link.

## Completion

You may write `COMPLETE` only when every item in the packet's acceptance list has been demonstrated with the evidence the packet names. Tests passing is necessary and never sufficient.

Use exactly one status: `COMPLETE` · `PARTIALLY COMPLETE` · `BLOCKED`.

Forbidden phrasings, because they have all been used to disguise unfinished work: "substantially complete", "functionally complete", "should now work", "the implementation is in place", "ready pending verification".

If you cannot demonstrate it, say `PARTIALLY COMPLETE` and name what is missing. That answer is always accepted. A false `COMPLETE` is not.

## Root cause before code

For every defect:

1. Reproduce the user action
2. Capture: HTTP status, safe error code, correlation ID, failing endpoint, frontend call site, backend service path
3. Name the owning service
4. State the root cause as a fact you can point at in source
5. Smallest architecture-correct fix
6. Focused regression test
7. Repeat the original user action

Never write a fix from a hypothesis. If you find yourself writing "this is likely caused by", stop and go get the evidence.

## Scope

Implement only the assigned packet. Classify everything else you find as: blocks this packet (fix minimally) · related follow-up (record in the packet report) · future scope (record). Do not refactor unrelated code because it could be better.

Do not pull a later packet's work forward. Do not begin a redesign when a targeted change satisfies the packet.

## Architecture — non-negotiable

- Modular monolith. Products consume shared platform services; they do not reimplement auth, authorization, orgs, locations, entitlements, config, workflows, approvals, notifications, integrations, AI routing, audit, or reporting.
- Products never call provider APIs directly. All provider traffic goes through registered connectors and the Integration Framework.
- AI is requested by task type through the AI Gateway. No hardcoded model or provider calls in product code.
- Tenant, organization, and location scope explicit at every boundary. Never infer tenant from client input.
- Authentication, membership, permission, entitlement, readiness, and approval are six distinct checks.
- Deterministic software controls permissions, consent, state transitions, publication eligibility, external actions, and retention. AI does not.
- Long-running work runs in durable background workflows, not HTTP requests.
- External writes require idempotency, verification, reconciliation, audit, and approval where defined.
- Approved and published revisions are immutable; changes create versions.
- Secrets stay server-side, redacted from logs, excluded from frontend responses and AI context.

## Prohibited

- Direct production database edits. Schema changes go through migrations, always.
- Manufacturing provider state — inserting integration connections, entitlements, or resource mappings by hand. This was done in an earlier session with invented Google resource IDs and it cost days.
- Reconciling a historical provider mapping because a row says "confirmed". Reconcile only after the same canonical external resource is re-verified through live provider discovery.
- Fabricated data anywhere. Missing is missing; zero is a measurement. No invented metrics, trends, comparisons, resource IDs, repositories, or business facts.
- Raw enum strings in client-facing UI (`pending_verification`, `never_synced`, `setup_required`).
- Weakening, skipping, or deleting a test to make acceptance pass.
- Claiming a test ran when it did not.
- Merging to main, enabling provider writes, or publishing to a client's live site without explicit owner approval.
- Changing Google Cloud OAuth configuration, scopes, or verification state. That is owner territory. If the app asks for consent on a healthy fully-scoped credential, the defect is in our lifecycle code.

## Stop conditions

Stop and ask only for: a secret you cannot obtain · a customer-visible provider write · a business fact only the owner knows · a billing decision · an external account permission · a genuine specification conflict.

Everything else is an engineering decision. Make it, record it, continue. Do not stop after each fix to ask whether to proceed.

## Validation

During iteration, run focused tests for what changed. At the end of the packet, run the full suite once:

```
npm run test:web && npm run typecheck:web && npm run build:web && npm run check:browser
uv run pytest
uv run ruff check .
npm run check
git diff --check
```

Record exact commands and exact results. If a check could not run, say so and do not report COMPLETE.

## Report format

```
PACKET <id> — <name>
Branch / HEAD SHA
Acceptance (one line per item): item → EVIDENCE → PASS/FAIL
Capability audit rows changed: <surface> HOLLOW→REAL
Implemented
Root causes fixed: symptom → evidence → cause → fix
Live demonstration: what, against what data, result
Tests: exact commands, exact results
Files changed
Remaining gaps
Status: COMPLETE | PARTIALLY COMPLETE | BLOCKED
```

No architecture narration. No re-planning. No summarizing the request back.
