# Packet 4 — Operational Product Convergence

**Depends on:** Packet 1 (frozen contracts), Packet 3 (integration control plane, merged `5f524e1`)
**Owner:** Product UX specialist
**Branch:** `packet/4-product-convergence`
**Builder:** Codex (design-system consistency across many files)
**Reference:** `docs/PLATFORM-PACKET-PLAN.md` SC4-1 through SC4-7 · `docs/VISUAL-UX-REFERENCE-NOTES.md`

---

## Why this packet exists

The backend is substantially built and the reporting data is now correct. The product still reads as an internal engineering console rather than software an agency operator uses all day and a client trusts.

This is not a theming pass. Do not port the Glass Ops dark palette. The reference is an information-architecture and craft benchmark: subordinate context under every number, the primary chart inside the first viewport, compact tables, deliberate empty states, grouped navigation, status as small consistent indicators rather than large colored blocks.

---

## The structural defect to fix first

**Status leakage.** Product readiness and connection health are currently rendered on Overview, on Insights, *and* on Integrations. Three surfaces answer the same question and none owns it, which is why setup machinery crowds out the actual work on every page.

Assign one owner: **Integrations owns connection and provider health.** Everywhere else gets at most a single compact "Needs attention" entry that links there.

Do this before any visual work. The layout problems downstream are mostly consequences of this.

---

## Scope — surfaces

Overview · Business Profile · Reviews · Leads · Content · SEO · Automations · Insights · Settings · Integrations.

Out of scope: Administration and Client Onboarding (privileged surfaces, different audience) — except where they render raw enums, which is in scope everywhere.

---

## Required outcomes

### 1. Layer model, applied to every workspace surface

| Layer | Content |
|---|---|
| First viewport | Org/location, reporting period, 4–6 KPIs each with subordinate context, Needs attention |
| Primary | Outcomes vs prior period for that product |
| Work | What is waiting on the operator: reviews to respond to, content to approve, opportunities, unconfirmed facts, lead follow-up |
| Results | Recently completed and verified work |
| Health | One compact dependency indicator linking to Integrations |
| Diagnostics | Agency/admin surfaces only |

### 2. Insights — rebuilt as a reporting product

The reporting data layer landed in PR #21/#22 and is correct: 7/28/90-day windows, prior-period comparison, overlap-safe GSC totals, freshness. The presentation is not.

- First viewport: client + location + period selector, then 4–6 KPIs with value, delta, prior-period context, source, freshness. Nothing else above the fold.
- One primary interactive trend chart: real axes, gridlines, hover readout, metric switcher, accessible text summary, truthful gaps for missing days. `timeSeriesChart()` is currently a hand-rolled fixed-height SVG bar renderer with no axes or hover — replace it with a reusable component both Insights and SEO consume.
- Organic search: clicks, impressions, CTR, average position with comparisons and a daily series.
- Top queries and pages: **5 rows with "view all"**, not a 25-row dump that owns the page.
- Performance summary: 2–3 deterministic sentences as prose, inline. Not a card of bullets. No causal claims, no AI interpretation.
- **Remove** "Website readiness", "Cross-product metrics", and "Connection status" blocks. Readiness and connection health move to Integrations; cross-product counts belong on Overview or inside each product.

### 3. Overview — outcomes, not configuration

Current state shows six KPI cards of which four read zero, an oversized "Nothing waiting on you" empty state, a "Latest connected results" block duplicating Insights, and a product status list duplicating Integrations.

- Drop or merge KPIs that have no data rather than rendering zeros. A KPI with no data says so, or is absent.
- Every KPI carries a subordinate context line: `90 reviews · 4.8★ · 2 awaiting response`, not `90`.
- Needs attention is the operational centre of this page, not an afterthought below the fold.
- Remove the duplicated performance block; link to Insights.
- Replace the product status list with a single compact health line linking to Integrations.

### 4. Integrations — a workspace, not a directory

Four status chips in a page of whitespace is not a control plane. Per provider: connection health, connected account, granted capabilities, mapped resources, last sync per capability, sync now, disconnect, and — when broken — the actual error with its remediation. Unmapped/available provider resources stay privileged and collapsed.

### 5. Product pages (SC4-1 through SC4-7)

- **GBP** — operational workspace: profile overview, posts, media, performance, recommendations. No unmapped discovery list.
- **Reviews** — inbox with status, draft/approve/publish workflow, approvals. Note: every review currently displays `Sentiment: unknown`; if classification is absent or unrun, present it honestly rather than showing an empty field.
- **SEO** — crawl status and history, page inventory, issues by category and severity, Search Console reporting reusing the Insights components, opportunities linked to evidence. Clean tabs and hierarchy.
- **Content** — opportunity → brief → draft → approve → publish, each state transition visible and truthful.
- **Leads** — intake, routing, assignment, status, communication history. If no lead source is configured, the product must not say "ready to use"; say setup required.
- **Automations** — catalog, schedules, last/next run, run history, failures with recovery. Client-readable: "Last synced 2 hours ago", never worker/lease internals.
- Each product shows one compact dependency indicator linking to Integrations, and setup blockers render as **one bounded banner with a direct action**, never a full-page setup dump that hides the product.

### 6. Language

No raw enums client-facing: `pending_verification`, `never_synced`, `setup_required`, `mapping_status`, `ownership_status`. Define one vocabulary and use it consistently: Configured · Connected · Mapped · Synced · Ready · Stale · Needs attention · Unavailable.

Buttons name what happens and keep that name through the flow — a button that says Publish produces a toast that says Published. Errors explain what happened and how to fix it. Empty states are invitations to act, not shrugs.

### 7. Craft floor

Every interactive surface: loading, empty, success, validation, permission denied, failure, degraded — each with a recovery action, plus a freshness stamp on provider data. Visible keyboard focus, reduced motion respected, responsive to mobile. Consistent cards, tables, tabs, spacing, and type scale across all surfaces; no visual drift between products.

---

## Constraints

- **Presentation only.** No backend contract changes, no new endpoints, no migrations. If a surface needs data the API does not expose, stop and report it rather than inventing a field.
- **No UI without backend.** If a control implies a capability the backend lacks, remove or disable it with an honest label. Report every instance found.
- **No second design system.** Use existing primitives in `apps/web/src/lib/ui/` and `global.css`. Extend them; do not introduce a parallel component library or CSS framework.
- Extract shared reporting components rather than building inline in `insights.astro` and `seo.astro`. Two inconsistent implementations of the same report is a defect.
- Do not modify files owned by other specialists per `docs/PLATFORM-OWNERSHIP-MAP.md` without reporting it.
- **Targeted edits only. Do not `Write` whole existing files.**
- Do not merge or push.

---

## Acceptance

1. **SC4-STATUS-OWNERSHIP** — connection/provider health renders in exactly one place. Evidence: grep showing readiness/health rendering removed from Overview and Insights.
2. **SC4-INSIGHTS-FIRST-VIEWPORT** — a decision is possible from the first screen at 1440×900. Evidence: screenshot.
3. **SC4-CHART** — one reusable chart component with axes, gridlines, hover, accessible summary, consumed by both Insights and SEO. Evidence: component path and both call sites.
4. **SC4-NO-ZERO-KPIS** — no KPI renders `0` where the true state is "no data". Evidence: the handling rule and a screenshot.
5. **SC4-INTEGRATIONS-DEPTH** — per-provider health, capabilities, mappings, last sync, actions. Evidence: screenshot.
6. **SC4-PRODUCT-PAGES** — each of the seven product surfaces satisfies its SC4 scenario from the packet plan. Evidence: one screenshot each.
7. **SC4-NO-RAW-ENUMS** — zero raw enum strings client-facing. Evidence: grep across `apps/web/src/pages` and `apps/web/src/lib`.
8. **SC4-STATES** — every surface renders all seven states with a recovery action. Evidence: browser tests.
9. **SC4-RESPONSIVE-A11Y** — mobile viewport usable; no critical accessibility violations. Evidence: `npm run check:browser`.
10. **SC4-HONEST-AFFORDANCES** — list every control found implying unimplemented capability and what was done about each.

Screenshots are required evidence, not optional. A packet claiming visual convergence without them is not accepted.

---

## Validation

```
npm run lint && npm run typecheck && npm run test && npm run build
npm run check:browser
uv run pytest
git diff --check
```

---

## Report

Use the `AGENTS.md` packet report format, plus:

- Screenshots for scenarios 2, 4, 5, 6
- The status-ownership grep proving deduplication
- The raw-enum grep result
- Every honest-affordance finding and its disposition
- Ledger row updates using the repository status vocabulary
- Adjacent work found and intentionally not implemented
