import { it, expect } from "vitest";
import {
  SITE_CHANGES_NOT_CONFIGURED,
  evidenceHeadline,
  metricText,
  rowView,
  title,
} from "../../src/lib/opportunity-view";
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
