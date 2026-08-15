# Packet 4-DS — Design System Foundation

**Branch:** `packet/4-product-convergence` (continue on the existing working tree)
**Builder:** Codex
**Type:** Presentation only. No backend contracts, endpoints, migrations, or provider state.

---

## Why this packet exists

Packet 4 built surfaces without a design system beneath them. Every defect found in owner review is a symptom of that: a hand-built chart, left-aligned numeric columns, orphaned KPI rows, unstyled native selects, an input narrower than its own placeholder, a raw `▼` character used as an icon, three different empty-state treatments, chart cards that don't fill their containers.

Those are not ten separate bugs. They are one missing foundation, showing up ten times.

This packet builds the foundation and then rebuilds every surface on top of it. It is not a patch pass. Do not fix defects individually — build the system, then compose the surfaces from it, and the defects disappear as a class.

**Work in this order. Do not start section 7 until sections 1–6 exist.**

---

## Standard

This is client-facing software sold to paying customers. Anything a customer sees is held to the standard of a mature commercial SaaS product.

Where a mature library exists for a UI problem, use it. Do not hand-roll charts, date pickers, virtualized tables, comboboxes, or dropdown menus. "Lightweight" is not a justification for output that looks amateur. State every library you add and why.

---

## 1. Design tokens

Define one token layer in CSS custom properties. Every value below is defined once here and referenced everywhere. No component defines its own raw values.

**Color** — a neutral ramp of 9–11 steps, a brand ramp derived from the existing LILOs dark green and lime, and semantic roles mapped onto those ramps: surface, surface-raised, surface-sunken, border-subtle, border-strong, text-primary, text-secondary, text-tertiary, and success / warning / danger / info each with a foreground, background, and border variant. Preserve the existing LILOs identity — this is a refinement of the current palette, not a rebrand, and not a dark theme.

**Type** — one scale with defined size, line height, weight, and letter spacing per step: display, h1, h2, h3, body-lg, body, body-sm, caption, overline. Add a `tabular` treatment using `font-variant-numeric: tabular-nums` for all numeric data. Choose the typeface deliberately and state the choice; system-ui by default is a decision you must justify rather than inherit.

**Spacing** — a scale on a 4px base: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64. Every margin, padding, and gap uses a step. No arbitrary pixel values anywhere.

**Radius, border, elevation, motion** — a small named set each. Elevation as a defined shadow ramp, not per-component box-shadow. Motion as two or three durations and one easing curve, with `prefers-reduced-motion` respected.

Audit `global.css` and every `.astro` page for raw hex values, arbitrary pixel spacing, and one-off shadows. Replace them all. Report the count found and replaced.

---

## 2. Primitives

One implementation of each, in `apps/web/src/lib/ui/`, built entirely from tokens. Every primitive defines every state: default, hover, focus-visible, active, disabled, loading, error.

Button (primary, secondary, ghost, danger; sm/md/lg; icon-only) · Input · Select · Textarea · Checkbox · Radio · Badge · Card · Table · Tabs · Dropdown menu · Tooltip · Modal · Toast · Empty state · Skeleton · Icon.

**Select and dropdown must not be raw native `<select>` styled with a background-image arrow.** The Integrations mapping section currently shows an unstyled native select next to a cramped button — that is the failure this replaces. Use a headless accessible component library (Radix primitives or equivalent) or a properly built custom control with full keyboard support.

**Icons come from an icon library.** No text characters used as icons — the raw `▼` disclosure triangle in Integrations must go.

No page composes bespoke markup once these exist.

---

## 3. Data display rules

Written into the Table primitive so they cannot be got wrong per-page:

- **Numeric columns right-aligned**, with tabular figures. Currently every numeric column across Insights, SEO, Content, Reviews, and Leads is left-aligned. This is the single loudest amateur tell in the product.
- Decimals aligned; consistent precision per metric type.
- Column widths sized to content, not evenly distributed. The QUERY column currently takes ~40% for text needing half that.
- Row hover state. Sticky header on long tables.
- Table footer actions inside the table's own frame and aligned to its padding. "View all 6 queries" currently renders as a detached box hanging off the table edge.
- Defined empty, loading, and error states for the table itself.

**Units and precision, defined once and applied everywhere:** counts with thousands separators; percentages to one decimal; percentage-point deltas as `pp`; position to one decimal, inverted for outcome color; currency and duration formats defined. Every metric declares its type and gets its formatting from that.

---

## 4. Chart theme

Configure Chart.js defaults **once**, globally: fonts from the type tokens, grid and axis colors from the neutral ramp, tooltip styled to match the design system rather than the library default, point and line weights, and a deliberate series palette with a real gradient fill — the current fill is a flat desaturated grey-green produced by applying opacity to the line color, and it looks it.

Axis behavior: round-number ticks, a headroom rule so the series does not float in a mostly empty plot (data currently peaks near 52 against a ceiling of 60), and no dead band between the last gridline and the axis labels.

No chart is styled at its call site after this.

---

## 5. Layout system

Page shell with defined max width, gutters, and section rhythm. A grid where card rows flow to fill — Overview currently orphans 2 cards in a 4-column row, Reviews and Leads orphan 1 each. Responsive breakpoints designed deliberately, not desktop reflow: the mobile Insights header currently crams source metadata beside the heading and strands "Manage data sources" on its own line.

---

## 6. Content standards

One vocabulary document, applied everywhere: status terms, button labels, empty-state structure, error-message structure.

Empty states explain the situation once and offer one next action. Overview's empty state currently repeats the same sentence and the same button three times.

Errors state what happened and how to fix it. No filler: Automations currently repeats "Runs with validation, permissions, audit, and recovery controls." verbatim on all three rows, which tells an operator nothing.

Buttons keep their name through the flow — Publish produces "Published."

---

## 7. Rebuild every surface on the system

Only after 1–6 exist. Overview, Business Profile, Reviews, Leads, Content, SEO, Automations, Insights, Settings, Integrations.

Each page composed entirely from primitives. No bespoke markup, no page-level CSS beyond layout composition.

Carry these specific defects into the rebuild:

- **Business Profile** promises "location data, hours, posts, and media" and renders one row plus 400px of white space. Build it around what the API actually exposes, and cut any promise the contracts cannot keep. Report exactly what is and is not available.
- **Setup blocker** shows "Google is not connected" directly above a location badged **Synced** with a timestamp. Resolve to one coherent state. Do not fix it by hiding one side.
- **Automations** rows must carry schedule, last run with result, next run, and failure count.
- **Leads** rows must identify the lead — name, contact, service, source — with urgency as a badge, not the title. Fix the fixture if it lacks representative data.
- **Content and Reviews** stage strips must show real per-stage counts and filter the list below, or be removed. Decoration that looks like a control is worse than no control.
- **Content** KPI reads "PUBLISHED 11 · All time" beside a table of 3. Make the scope of each number explicit.
- **Workspace label** reads "Agency workspace" everywhere; production showed "Client workspace." Confirm it derives from membership and scope, and report which.

---

## 8. Enforcement

So this cannot regress:

- Stylelint or equivalent rejecting raw hex values and arbitrary pixel spacing outside the token file.
- ESLint rule against inline style attributes carrying design values.
- Playwright visual regression snapshots for each surface.

---

## Working method

**Do not begin coding at section 7.** Sections 1–6 first, in order.

**Before writing code, produce the token plan and show it to the owner**: the palette as named hex values, the type scale, the spacing scale, and the chart theme direction. Get confirmation before building on it. This is the one checkpoint in the packet — everything after it follows the confirmed plan.

**Iteration gate:** `npm run typecheck && npm run build`, then recapture. Do not run the full test/pytest/browser suite between visual revisions. Full gate once at the end.

**Targeted edits only.** Do not rewrite whole files.

**Critique your own output.** Screenshot each surface as you finish it and review it against this document before moving on. Anything you would not put in front of a paying customer is not done.

---

## Acceptance

1. Token file exists; zero raw hex or arbitrary spacing outside it, with the audit count reported.
2. Every primitive in section 2 exists with all states, built from tokens.
3. Every numeric column right-aligned with tabular figures, across all surfaces.
4. Chart theme configured globally; no chart styled at its call site.
5. No native unstyled selects; no text characters used as icons.
6. No orphaned card rows on any surface.
7. Every surface in section 7 rebuilt from primitives, each defect above resolved or reported as a contract gap.
8. Lint rules and visual regression tests in place and passing.
9. Full gate: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`, `npm run check:browser`, `uv run pytest`, `git diff --check`.
10. All fourteen screenshots recaptured at 1440×900 (mobile 390×844).

Where a defect cannot be fixed because the API does not expose the data, say so and name the missing contract. Do not fabricate data. Do not leave copy promising a capability the page does not deliver.

Do not commit, merge, or push.
