# PACKET 00 — Capability Truth Audit

**Builder model:** DeepSeek V4 Pro or GLM 5.2 (needs whole-repo context)
**Branch:** `audit/capability-truth-v1`
**Type:** Read and document. **No production code changes in this packet.**

---

## Load first

`/AGENTS.md`, then `/docs/LILOS-MASTER-SPEC.md`, `/docs/LILOS-BUILD-ROADMAP.md`, `/docs/LILOS-MASTER-BUILD-PROMPT.md`. Then read the current `main` HEAD and reconcile: prior session transcripts are not authority, and several describe defects that are already fixed.

---

## Why this packet exists

Four prior review sessions concluded the platform was "80–90% built, only release closure remains." That was wrong, and the proof is the SEO crawler: the UI presents a "Max pages" field, the frontend sends `seedPaths: ["/"]`, the backend never discovers a link from a fetched page, and the run reports `pages_crawled = len(targets)`. It crawls one page and always will. A complete UI sits on a capability that does not exist.

No schedule for this project is real until we know how many more of those exist.

---

## Task

For every user-facing affordance in the client workspace — every control, input, button, tab, status badge, metric, and empty state — determine **from source** what actually happens when a user uses it. Trace: frontend call site → API route → service → repository or connector → provider. Do not infer from names, tests, or documentation.

Write the result to `/docs/LILOS-CAPABILITY-TRUTH.md`.

### Verdicts

Exactly one per row:

- `REAL` — implemented, exercised against live data, and it does what the UI implies
- `REAL_UNPROVEN` — implemented and plausible, never run against live production data
- `HOLLOW` — the UI implies a capability the backend does not have, or has only partially
- `ABSENT` — the Master Spec requires it for the initial release and nothing exists

`HOLLOW` is the verdict that matters. Apply it whenever a user would reasonably expect more than the code does. When torn between `REAL_UNPROVEN` and `HOLLOW`, choose `HOLLOW` and explain.

### Row format

```
| Surface | Affordance | Frontend call | Backend path | What it actually does | Verdict | Note |
```

The "what it actually does" cell must be a factual statement traceable to a file and function, not a summary of intent.

---

## Surfaces to cover — all of them

Overview · Business Profile · Reviews · Leads · Content · SEO (Overview, Crawl, Search Console, Opportunities) · Automations · Insights · Settings (including Website & Domain) · Integrations · Administration · Client Onboarding.

---

## Specific questions that must be answered by name

Each of these gets its own subsection in the output document with a direct answer and file references.

1. **SEO opportunity detection.** Does any code detect high-impression/low-CTR, near-page-one, performance decline, content gap, or technical issue (Spec 13.114)? Name the detectors that exist. If "Open SEO opportunities: 0" reflects a table nothing writes to, say so.

2. **Content pipeline.** Trace the full chain: opportunity → brief → AI draft → business-fact grounding → validation → editorial approval → client approval → GitHub PR → build verification → deploy verification → publication verified. State which links exist, which are stubs, which are absent. Name the first broken link.

3. **Astro publishing adapter.** Does the GitHub publisher write a correctly-shaped Astro content-collection entry — frontmatter matching the target repository's collection schema, correct directory, slug, date, description, image references — or does it write a generic markdown file and hope the build passes? Quote the code that constructs the file.

4. **Automations.** Is there one workflow template a user can select, configure, schedule, run, pause, and view history for? Name it. If the control plane exists with no runnable template, verdict is `HOLLOW` and say what is missing.

5. **Reviews classification.** Spec 15 requires sentiment, topic, risk flags, and priority scoring. Every review currently displays "Sentiment: unknown." Determine which: classifier absent, classifier present but never run on the 90 imported reviews, or classified but not surfaced by the read model.

6. **Leads outbound.** `LeadCommunication` is marked sent with `sent_at` populated when a notification is queued, while `NotificationDelivery` is still pending. Determine whether a real Resend or SMS dispatch path exists, and whether consent enforcement, suppression enforcement, delivery reconciliation, and failure handling exist. Speed-to-lead timing that measures queueing rather than delivery is a reporting defect — say so if that is what it does.

7. **AI Gateway.** List every registered AI task type with its prompt version, validators, routing policy, and fallback. Then list every place product code calls a model outside the gateway. The second list should be empty; report it either way.

8. **GBP write paths.** For posts, media, review replies, and profile fields: is each implemented with kill switch, confirmed mapping, credential resolution, provider call, provider re-read, reconciliation, and audit? Which have ever executed against production?

9. **Insights and SEO reporting read layer.** The reporting math was corrected recently (7/28/90-day windows, prior-period comparison, overlap-safe GSC totals). Confirm that on current `main` and identify what the read layer still discards from stored observations.

10. **Website readiness.** `seo.astro` renders `website.status` directly into a user-facing badge, which is why `pending_verification` is visible. Identify every surface that renders a raw backend enum to a client-facing user. List them all.

---

## Also produce

**A. Hollow inventory.** Every `HOLLOW` and `ABSENT` row, ordered by how visible it is to a paying client, each with a one-line estimate of what closing it requires: `mechanical` (hours) · `feature` (days) · `subsystem` (a real build).

**B. Duplication map.** Where the same information is computed or displayed in more than one place — product readiness and connection health currently appear on Overview, Insights, and Integrations. List every duplication with the surface that should own it.

**C. Dead surface list.** Any page, tab, control, or empty state that no code path can currently populate.

---

## Constraints

- Read only. No production code changes. Adding the documentation file and a branch is the entire diff.
- No fixes, even obvious one-line ones. Record them; a later packet closes them.
- Do not rely on prior session transcripts, PR descriptions, or `LILOS-IMPLEMENTATION-STATUS.md` for any verdict. Those describe intent. Read the code.
- Where you cannot determine behavior without running it, mark `REAL_UNPROVEN` and state precisely what execution would settle it.
- Completeness beats speed. A missed `HOLLOW` row costs a day later.

---

## Acceptance

1. `/docs/LILOS-CAPABILITY-TRUTH.md` exists on branch `audit/capability-truth-v1`
2. Every surface in the list above appears, with no surface represented by fewer than three rows unless it genuinely has fewer affordances
3. All ten named questions answered directly, with file and function references
4. Hollow inventory, duplication map, and dead surface list present
5. Every `HOLLOW` and `ABSENT` verdict cites the specific code that falls short
6. Diff contains no production code changes — verify with `git diff --stat` and include the output

---

## Report

```
PACKET 00 — Capability Truth Audit
Branch / HEAD SHA
git diff --stat output
Counts: REAL / REAL_UNPROVEN / HOLLOW / ABSENT
Top 10 hollow items by client visibility, with sizing
Answers to the 10 named questions (one paragraph each, with file references)
Anything you could not determine, and what would settle it
Status: COMPLETE | PARTIALLY COMPLETE | BLOCKED
```

Return the completed `LILOS-CAPABILITY-TRUTH.md` in full along with the report.
