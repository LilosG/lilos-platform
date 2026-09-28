import { describe, expect, it } from "vitest";
import type {
  SearchIntelligenceItem,
  SearchIntelligenceWorkspace,
} from "../seo";
import {
  renderSearchIntelligenceWorkspace,
  searchIntelligenceSections,
} from "./search-intelligence";

function item(
  classification: "growth_change" | "technical_regression",
): SearchIntelligenceItem {
  return {
    opportunity: {
      id: classification,
      website_id: "site",
      page_id: null,
      opportunity_type:
        classification === "growth_change"
          ? "gsc_query_demand"
          : "missing_title",
      recommendation_class: classification,
      priority_score: 42,
      score_explanation: {},
      evidence: { query: "local services", page_mapping_state: "unknown" },
      status: "identified",
    },
    website: {
      id: "site",
      location_id: "location",
      key: "site",
      name: "Example",
      canonical_origin: "https://example.test",
      status: "active",
      ownership_status: "verified",
      verified_at: null,
    },
    page: null,
    recommendation: null,
    task: null,
    outcome: null,
    measurement: null,
    active_change: null,
    latest_measured: null,
  };
}

function workspace(
  items: SearchIntelligenceItem[],
): SearchIntelligenceWorkspace {
  return {
    items,
    readiness: [
      {
        website_id: "site",
        website_name: "Example",
        location_id: "location",
        gsc: "fresh",
        ga4: "unavailable",
        page_inventory: "unavailable",
      },
    ],
    readiness_has_more: false,
    history_truncated: false,
    pagination: { limit: 50, offset: 0, next_offset: null, has_more: false },
  };
}

describe("Search Intelligence workspace", () => {
  it("uses deterministic classification and leaves query demand without a page", () => {
    const data = workspace([
      item("growth_change"),
      item("technical_regression"),
    ]);
    const sections = searchIntelligenceSections(data);
    expect(sections.growth).toHaveLength(1);
    expect(sections.technical).toHaveLength(1);
    expect(sections.measuring).toHaveLength(0);

    const panel = document.createElement("div");
    renderSearchIntelligenceWorkspace(
      panel,
      data,
      "organization",
      () => undefined,
    );
    expect(panel.textContent).toContain("Unattributed query");
    expect(panel.textContent).not.toContain("SEO Health");
    expect(panel.textContent).not.toContain("caused");
  });

  it("does not turn a verified change into an observed outcome", () => {
    const growth = item("growth_change");
    growth.task = {
      id: "task",
      recommendation_revision_id: "revision",
      workflow_run_id: "run",
      target_type: "page",
      target_reference: "seo-page:page",
      status: "verified",
      verified_at: "2026-09-01T00:00:00Z",
      verification_evidence: { result: "verified" },
    };
    growth.measurement = {
      metric: "gsc_clicks",
      maturity: "pending",
      limitation: null,
    };
    const sections = searchIntelligenceSections(workspace([growth]));
    expect(sections.measuring).toEqual([growth]);
    expect(sections.learned).toHaveLength(0);
  });
});
