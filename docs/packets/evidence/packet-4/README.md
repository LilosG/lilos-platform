# Packet 4 screenshot evidence

All screenshots in this directory are fixture-rendered acceptance evidence,
not live data. Each image includes that caption visibly in the viewport.

The fixtures are existing-contract-shaped constants in
`apps/web/tests/fixtures/packet-4/responses.ts`. The local evidence proxy is
`apps/web/tests/fixtures/packet-4/evidence-server.mjs`; it exits unless
`LILOS_PACKET4_FIXTURES=1`, binds only to `127.0.0.1`, and is never imported by
an application module or included in an Astro deployed build. It performs no
database or provider writes.

The proxy's `full` mode renders the populated Overview from
`insightsSummary`; its `no-data` mode returns the contract-shaped
`emptyInsightsSummary` so the empty layout is exercised without simulating an
API failure.

Capture timestamps below are filesystem modification times recorded in
America/Los_Angeles immediately after browser capture.

| Acceptance coverage | Evidence | Viewport | Captured |
| --- | --- | --- | --- |
| SC4-INSIGHTS-FIRST-VIEWPORT / SC4-PRODUCT-PAGES — Insights | `sc4-insights-first-viewport-fixture.png` | 1440×900 | 2026-08-14 22:09:08 PDT |
| SC4-CHART — hover tooltip | `sc4-insights-trend-fixture.png` | 1440×900 | 2026-08-14 22:09:08 PDT |
| SC4-NO-ZERO-KPIS — empty Overview | `sc4-no-zero-kpis-fixture.png` | 1440×900 | 2026-08-14 22:09:09 PDT |
| SC4-OVERVIEW-POPULATED | `sc4-overview-populated-fixture.png` | 1440×900 | 2026-08-14 22:09:10 PDT |
| SC4-INTEGRATIONS-DEPTH — provider detail | `sc4-integrations-depth-fixture.png` | 1440×900 | 2026-08-14 22:09:10 PDT |
| SC4-INTEGRATIONS-DEPTH — expanded mappings | `sc4-integrations-mappings-fixture.png` | 1440×900 | 2026-08-14 22:09:53 PDT |
| SC4-PRODUCT-PAGES — GBP | `sc4-product-gbp-fixture.png` | 1440×900 | 2026-08-14 22:09:11 PDT |
| SC4-PRODUCT-PAGES — Reviews | `sc4-product-reviews-fixture.png` | 1440×900 | 2026-08-14 22:09:12 PDT |
| SC4-PRODUCT-PAGES — SEO / shared Chart.js renderer | `sc4-product-seo-fixture.png` | 1440×900 | 2026-08-14 22:09:13 PDT |
| SC4-PRODUCT-PAGES — Content | `sc4-product-content-fixture.png` | 1440×900 | 2026-08-14 22:09:14 PDT |
| SC4-PRODUCT-PAGES — Leads | `sc4-product-leads-fixture.png` | 1440×900 | 2026-08-14 22:09:14 PDT |
| SC4-PRODUCT-PAGES — Automations | `sc4-product-automations-fixture.png` | 1440×900 | 2026-08-14 22:09:15 PDT |
| Bounded product setup blocker | `sc4-setup-blocker-fixture.png` | 1440×900 | 2026-08-14 22:09:16 PDT |
| SC4-RESPONSIVE-A11Y | `sc4-responsive-mobile-fixture.png` | 390×844 | 2026-08-14 22:09:16 PDT |

SC4-NO-RAW-ENUMS remains documented in `SC4-NO-RAW-ENUMS.md`.

Playwright reported the mobile document width as 390 CSS pixels at a 390 CSS
pixel viewport, so the captured page had no horizontal document overflow.
