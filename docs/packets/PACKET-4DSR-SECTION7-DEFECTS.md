# Packet 4-DS-R — Section 7 Defect Remediation

**Branch:** `packet/4-product-convergence` (continue on the existing working tree)
**Builder:** Codex
**Type:** Presentation only. No backend contracts, endpoints, migrations, or provider state.

Owner review of the fourteen Section 7 screenshots. Items 1–3 are systemic — they come from the primitives and affect most surfaces, so fix them in the primitives, not per page.

**Iteration gate:** `npm run typecheck && npm run build`, then recapture. Full gate once at the end.
**Editing constraint:** targeted edits only.

---

## A. Systemic — fix in the primitives

### A1. Section headers render twice, transposed

Insights shows `ANALYTICS / Website performance` immediately followed by `WEBSITE PERFORMANCE / Analytics` — the same two words swapped and stacked. Present on desktop and mobile.

A PageSection eyebrow and a nested section header are both rendering. Determine which component owns the eyebrow, make it own it exclusively, and audit every surface for the same duplication.

### A2. Info banners collide with the following section

On Automations, Content, Leads, Reviews, and SEO the banner's bottom edge butts directly against the next eyebrow (`HEALTH`, `PERFORMANCE`, `WORKFLOW`) with no spacing; on Automations it visually overlaps.

Fix the spacing contract between the banner primitive and a following PageSection so it holds everywhere, rather than adding a margin per page.

### A3. Badges render as full-width bars

The Integrations "Connected" badge and the SEO "Ready" badge each span the full card width. A badge is an inline pill sized to its content. Fix in the Badge primitive and verify no surface stretches one.

---

## B. Layout and composition

### B1. Overview orphan is worse than before
Five KPI cards in a row, then `OPEN SEO OPPORTUNITIES` alone in a full-width card. Previously 4+2; now 5+1 stretched across the page, which reads as a rendering error. Apply one grid rule: cards flow to fill, or the count matches the columns. Apply it on every surface with a KPI row.

### B2. Overview empty state is unchanged
Still three stacked rows repeating the same sentence with "Open Business Profile" three times, and the three buttons sit at different widths and x positions, leaving a ragged right edge. Section 6 of the parent packet required consolidating this: one empty state, explained once, one next action.

### B3. Content has two competing navigation rows
Stage filter chips sit directly above Pipeline / Opportunities / Publishing tabs, with no hierarchy between them. Establish one primary navigation for this page and make the other subordinate or remove it.

### B4. Disabled Open button is ambiguous
On the setup blocker, the disabled "Open" renders as a muted green that still reads as available. Make the disabled state unmistakably inert.

---

## C. Consistency

### C1. Leads inbox does not use the Table primitive
Leads rows are plain stacked text — no dividers, no columns, no alignment — while Automations in the same build uses a proper table. Both are operational lists and must use the same primitive. If the row needs more than a table row affords, define a list-row primitive and use it in both places.

### C2. Mobile header composition
Mobile carries the A1 duplication plus a full-width "Manage data sources" button stranded below the period selector. Compose the mobile header deliberately.

---

## D. Content and copy

### D1. Leads copy leaks implementation language

Client-facing text currently reads:
- "Source not exposed by the lead response contract"
- "Service reference service-emergency"
- "Rows use authorized detail data for contact identity; unavailable source and service names are stated explicitly"

Being honest about the gap is right; this phrasing is not. Rewrite in the interface's voice, naming things by what the user recognizes rather than how the system is built — for example "Source unavailable" and the service shown by its name, or omitted if only an identifier exists. The third line is a note to a reviewer, not to a user; remove it.

Audit every surface for the same class of leak.

---

## E. Contract-gap surfaces

### E1. Business Profile still shows no data
The three cards read as descriptions of what they would contain — "Mapping and sync — Confirmed provider mapping, write authority, discovery time, and last successful sync." No values are shown. The page is still empty, better dressed.

Your Section 7 report stated GBP lacks read models for current core profile values, address, and regular weekly hours. Given that, show what *is* retrievable — confirmed mapping, write authority, discovery time, last successful sync, posts, media, special hours — as actual values rather than descriptions of fields.

For anything genuinely unavailable, do not render a card describing it. Cut it, and cut the matching promise from the page subtitle. Report the precise list of what you rendered and what you removed.

---

## F. Decision required

### F1. Positive deltas render blue
`+388 +13.6%` renders in `delta-positive` blue. This follows the token system as designed, and the reasoning — that metric movement is not a status — is sound. But on a client-facing report, a positive delta in blue rather than green will read as wrong to anyone accustomed to analytics tooling.

Do not change it yet. Produce a short recommendation with one alternative that keeps status and delta distinct while letting positive movement read as positive — for example delta-positive as a green clearly separated from both the forest action color and the teal success color. Include the hex values and the contrast check.

---

## Acceptance

Recapture all fourteen screenshots at 1440×900 (mobile 390×844). For each item, state what changed and cite the image showing it.

Full gate once at the end: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`, `npm run check:browser`, `uv run pytest`, `git diff --check`. Update the visual regression baselines.

Do not commit, merge, or push.
