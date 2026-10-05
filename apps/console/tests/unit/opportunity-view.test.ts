import { it, expect } from "vitest";
import {
  SITE_CHANGES_NOT_CONFIGURED,
  evidenceHeadline,
  implementationLabel,
  labelField,
  lifecycleLabel,
  metricText,
  revisionLine,
  rowView,
  title,
  whyItMatters,
} from "../../src/lib/opportunity-view";
import { dateText, rangeText } from "../../src/lib/present";
import type { OpportunityView } from "../../src/adapters/opportunities";
const base = {
  id: "seo_opportunity:2",
  source_kind: "seo_opportunity",
  kind: "seo",
  source_id: "2",
  organization_id: "1",
  client: { organization_id: "1", name: "Alpha", slug: "alpha" },
  location_id: null,
  website_id: null,
  page_id: null,
  classification: "Issue",
  source_type: "missing_meta_description",
  status: "identified",
  subject: { query: null, path: null },
  summary: null,
  lifecycle: "open",
  verified_at: null,
  importance_reason: null,
  earlier_observations: [],
  priority: 82,
  evidence: {},
  score_explanation: {},
  observed_at: "2026-09-30T00:00:00Z",
  evidence_context: {
    source: null,
    quality: null,
    freshness_at: null,
    period_start: null,
    period_end: null,
    limitation_code: null,
  },
  priority_band: "high",
  headline: null,
  confidence: null,
  evidence_summary: {
    source: "crawl",
    signal: "missing_meta_description",
    metrics: [{ key: "impressions", value: 1200 }],
    source_count: null,
  },
  next_action: "request_recommendation",
  latest_revision_status: null,
  site_change: "configured",
  site_change_reason: null,
} as OpportunityView;
const now = new Date("2026-10-01T12:00:00Z");
it("builds labels from typed codes, never from API prose", () => {
  const row = rowView(base, now, "portfolio");
  expect(row.title).toBe("Missing meta description");
  expect(row.band).toBe("High");
  expect(row.next).toBe("Ask Hermes for a recommendation");
  expect(row.evidence).toBe("Missing meta description · 1,200 impressions");
  expect(row.href).toBe("/clients/alpha/opportunities/2/?from=portfolio");
  expect(rowView(base, now, "client").href).toBe(
    "/clients/alpha/opportunities/2/",
  );
});
it("shows the typed site-change reason and never hides the row", () => {
  const row = rowView(
    {
      ...base,
      site_change: "not_configured",
      site_change_reason: "SITE_CHANGES_NOT_CONFIGURED",
    },
    now,
    "client",
  );
  expect(row.siteChangeNote).toBe(SITE_CHANGES_NOT_CONFIGURED);
  expect(SITE_CHANGES_NOT_CONFIGURED).toBe(
    "Site changes not configured for this client",
  );
});
it("does not show a missing priority as a number", () => {
  const row = rowView(
    { ...base, priority: null, priority_band: null },
    now,
    "client",
  );
  expect(row.band).toBe("Priority unavailable");
});
it("titles growth plans by objective and counts their sources", () => {
  const growth = {
    ...base,
    kind: "growth",
    headline: "Win brunch searches",
    evidence_summary: {
      source: null,
      signal: "growth_plan",
      metrics: [],
      source_count: 3,
    },
  } as OpportunityView;
  expect(title(growth)).toBe("Win brunch searches");
  expect(evidenceHeadline(growth)).toBe("3 supporting sources");
});
it("formats numbers by key", () => {
  expect(metricText("ctr", 0.034)).toEqual(["3.4%", "CTR"]);
  expect(metricText("position", 4.26)).toEqual(["4.3", "Average position"]);
  expect(metricText("http_status", 404)).toEqual(["404", "HTTP status"]);
});

const subjects = [
  { query: null, path: null },
  { query: "brunch spots san diego", path: null },
  { query: null, path: "/menu" },
  { query: "brunch", path: "/blog/brunch" },
  // A reference that was never resolved must not leak into a title.
  { query: "seo-opportunity:3f2504e0-4f89-41d3-9a0c-0305e82c3301", path: null },
  { query: null, path: "https://example.com/menu" },
  { query: "3f2504e0-4f89-41d3-9a0c-0305e82c3301", path: null },
  { query: "content-brief:abc", path: "http://example.com" },
];
const types = [
  "gsc_low_ctr",
  "gsc_striking_distance",
  "gsc_query_demand",
  "gsc_unmapped_demand",
  "pagespeed_performance_mobile",
  "pagespeed_seo_desktop",
  "missing_meta_description",
  "non_200_status",
  "seo",
  "something_new_and_unknown",
];
it("never builds a title from a UUID, a reference key or an address", () => {
  const forbidden =
    /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-|seo-opportunity:|content-brief:|http/i;
  for (const kind of ["seo", "content", "growth"] as const)
    for (const source_type of types)
      for (const subject of subjects)
        for (const headline of [null, "content-brief:abc", "Win brunch"]) {
          const t = title({
            ...base,
            kind,
            source_type,
            subject,
            headline,
          } as OpportunityView);
          expect(
            t,
            `${kind} ${source_type} ${JSON.stringify(subject)}`,
          ).not.toMatch(forbidden);
          expect(t.length).toBeGreaterThan(0);
        }
});
it("titles each type from its typed subject", () => {
  const t = (source_type: string, subject: OpportunityView["subject"]) =>
    title({ ...base, source_type, subject } as OpportunityView);
  expect(
    t("gsc_low_ctr", { query: "brunch spots san diego", path: null }),
  ).toBe("Low click-through: \u201cbrunch spots san diego\u201d");
  expect(t("gsc_striking_distance", { query: "brunch", path: "/b" })).toBe(
    "Close to page one: \u201cbrunch\u201d",
  );
  expect(
    t("pagespeed_performance_mobile", { query: null, path: "/menu" }),
  ).toBe("Mobile page speed \u00b7 /menu");
  expect(t("pagespeed_seo_desktop", { query: null, path: "/" })).toBe(
    "Desktop page speed \u00b7 Homepage",
  );
  expect(
    title({
      ...base,
      kind: "content",
      source_type: "seo",
      subject: { query: null, path: "/blog/brunch" },
    } as OpportunityView),
  ).toBe("Content opportunity \u00b7 /blog/brunch");
  expect(
    title({ ...base, kind: "content", source_type: "seo" } as OpportunityView),
  ).toBe("Content opportunity");
});
it("formats every date as a readable range or day, never ISO", () => {
  expect(rangeText("2026-09-27", "2026-10-04")).toBe(
    "Sep 27 \u2013 Oct 4, 2026",
  );
  expect(rangeText("2025-12-28", "2026-01-03")).toBe(
    "Dec 28, 2025 \u2013 Jan 3, 2026",
  );
  expect(dateText("2026-10-04T18:00:00Z")).toBe("Oct 4, 2026");
  expect(dateText("2026-09-30T00:00:00Z")).toBe("Sep 29, 2026");
  expect(dateText(null)).toBe("");
});
it("keeps Why it matters out of list rows", () => {
  const row = rowView(
    { ...base, importance_reason: "KEY_EVENTS_INFERRED" },
    new Date("2026-10-05T00:00:00Z"),
    "client",
  );
  expect(row).not.toHaveProperty("why");
});
it("labels fields, reasons, live state and revisions from typed values", () => {
  expect(labelField("seo_title")).toBe("SEO title");
  expect(labelField("meta_description")).toBe("Meta description");
  expect(whyItMatters(base)).toBeNull();
  expect(
    whyItMatters({ ...base, importance_reason: "KEY_EVENTS_INFERRED" }),
  ).toContain("inferred from key events");
  const live = {
    ...base,
    lifecycle: "live",
    verified_at: "2026-10-04T18:00:00Z",
    status: "approved",
  } as OpportunityView;
  expect(lifecycleLabel(live)).toBe("Live \u00b7 verified Oct 4, 2026");
  expect(lifecycleLabel(base)).toBe("Identified");
  expect(
    rowView({ ...live, next_action: "measure_impact" }, now, "client").next,
  ).toBe("Measure impact");
  expect(implementationLabel("pending", "verified")).toBe("Verified live");
  expect(implementationLabel("pending", null)).toBe("Pending");
  expect(
    revisionLine({
      revision_number: 1,
      status: "superseded",
      created_at: "2026-09-27T12:00:00Z",
    }),
  ).toBe("Revision 1 \u00b7 Superseded \u00b7 Sep 27, 2026");
});
