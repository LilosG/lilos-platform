# RR-4 — Deterministic Leads Intake/Routing

## Goal
Close the Leads routing implementation gap without touching workflow execution or outbound-provider dispatch while PR47 is in progress.

## Baseline
Branch from PR46 accepted commit `a91e64367810d7d45524b472a3007a6ba9fe1cb5`.

## Confirmed root cause
Lead intake is secure, tenant-scoped, idempotent and normalized, but routing is not implemented. Caller-provided location/service identifiers may be labeled as matched without a governed deterministic routing decision. There is no central rule model for location/service matching, ambiguity, business-hours behavior, spam decision, or automatic assignment. Outbound communication currently stops at queued; provider dispatch is explicitly excluded from RR-4.

## Ownership
- `apps/api/app/products/leads/contracts.py`
- `apps/api/app/products/leads/models.py`
- `apps/api/app/products/leads/service.py`
- `apps/api/app/routes/leads.py`
- `apps/web/src/lib/leads.ts`
- `apps/web/src/pages/leads.astro`
- Leads-only migration if required
- `tests/python/leads/**`
- Leads-specific web tests
- release-ledger evidence for this packet only

## Exclusions
Do not modify:
- `apps/api/app/execution/**`
- workflow handlers/registry/scheduler
- notifications provider dispatch
- Integrations
- Hermes/AI/agent tools
- PR47-owned shared UI
- email/SMS provider implementation

## Design rules
1. Routing must be deterministic and auditable. An agent/LLM must not decide canonical lead routing.
2. Provider/caller input is evidence, not authority. Never mark a supplied location/service as matched unless validated against configured tenant-owned routing data.
3. Route outcomes must distinguish matched, ambiguous, unmatched, suppressed/spam and configuration-required states rather than fabricating an assignment.
4. Rules must be organization-scoped and location/service references must belong to that tenant.
5. Define explicit precedence when multiple rules match. Tie/ambiguity must fail safely rather than choose arbitrarily.
6. Support configured service/location matching and assignment semantics using existing organization/location/user models where possible; do not create shadow identities.
7. If business-hours behavior is implemented, timezone and fallback semantics must be explicit and deterministic.
8. Intake idempotency must remain unchanged; replay must not create a second routing/assignment result.
9. Routing decisions and manual overrides must be auditable without logging lead PII beyond existing safe metadata conventions.
10. No outbound message may be sent by this packet.

## Required product behavior
The Leads UI should truthfully show routing state, matched location/service/assignee where established, and requires-attention state for ambiguity/unmatched/configuration gaps. Do not label queued communication as sent.

## Acceptance matrix
At minimum prove:
- exact configured location+service match routes deterministically;
- service-only or location-only fallback behaves according to configured precedence;
- two equal-priority matches => ambiguous/requires attention, no arbitrary assignee;
- caller-supplied foreign/cross-tenant IDs are rejected/ignored safely;
- unknown service/location remains unmatched, not falsely matched;
- configured assignee belongs to correct tenant;
- paused/disabled routing rules do not match;
- intake replay returns same lead/routing result without duplicate assignment;
- manual correction/assignment is auditable if existing product supports it;
- no workflow/provider dispatch is invoked;
- cross-tenant retrieval remains denied.

## Validation
Run Leads-focused database/API/web tests first, including migration upgrade/downgrade if schema changes. Run Ruff/mypy/ESLint/Astro for touched surfaces. Then one integrated repository validation. Stop and report unrelated failures; do not change shared execution/PR47 code.

## Completion
Commit/push only when repository acceptance is green. Do not merge. Return routing model/precedence, changed files, validation totals, commit SHA, and the remaining post-PR47 outbound messaging acceptance dependency.