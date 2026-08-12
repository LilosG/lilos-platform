# PACKET 1 — Platform Information Architecture

You are the `release-integrator`.

Prerequisite:
Round 0 is accepted and `docs/PLATFORM-OWNERSHIP-MAP.md` plus `docs/PLATFORM-PACKET-PLAN.md` exist.

## Objective

Establish the shared platform information architecture that every specialist branch will consume.

This packet is about boundaries and platform coherence, not broad redesign of every product.

## Required outcomes

- Agency and Client workspace boundaries are explicit in navigation and page ownership.
- Navigation respects role/scope/entitlement using existing authoritative access contracts.
- Integrations has one obvious platform location.
- Automation & Agents has one obvious platform location or scaffold aligned with the release spec.
- Reporting/Insights placement is clear.
- Settings/Administration responsibilities are separated.
- Normal operational product pages do not own broad provider discovery/mapping.
- Client users cannot navigate to agency-only administration.
- No frontend-only authorization workaround.
- Existing product routes are preserved or migrated intentionally with tests; do not break deep links without a deliberate compatibility decision.
- Terminology is operational and consistent.

## Scope discipline

Do not complete all provider integrations, all automation workflows, all product UX, or all reporting in Packet 1.

Create the stable shell/contracts those packets will use.

## Verification

Run focused frontend/API authorization/navigation tests plus the smallest relevant type/lint/build checks.

Use `@release-auditor` after implementation.

Packet 1 is accepted only if the auditor does not find architecture drift, client-scope leakage, or duplicated integration ownership.

After acceptance:
- commit Packet 1;
- update the release ledger;
- freeze shared contracts/file ownership;
- create specialist worktrees from this accepted commit.
