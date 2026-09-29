import { describe, expect, it, vi } from "vitest";
import * as seo from "../seo";
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
    governed_eligibility: { eligible: true, limitation: null },
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
  it.each(["queued", "running", "completed", "failed"])(
    "shows the persisted Hermes %s state for the selected opportunity",
    async (state) => {
      if (state === "completed")
        vi.spyOn(seo, "fetchRecommendations").mockResolvedValue({
          kind: "ok",
          data: [
            {
              id: "revision",
              revision_number: 1,
              proposed_action: "Investigate demand",
              expected_result_hypothesis: "Clarify attribution",
              risk: "low",
              effort: "medium",
              status: "awaiting_approval",
              approved_by_user_id: null,
              evidence_references: [],
              decision_context: null,
            },
          ],
        });
      vi.spyOn(seo, "fetchOpportunityHermesRun").mockResolvedValue({
        kind: "ok",
        data: {
          workflow_run_id: "workflow",
          agent_run_id: "agent",
          status: state,
          safe_error_code:
            state === "failed" ? "HERMES_EXECUTION_FAILED" : null,
          proposal_references:
            state === "completed" ? ["seo-recommendation:revision"] : [],
        },
      });
      const panel = document.createElement("div");
      document.body.append(panel);
      renderSearchIntelligenceWorkspace(
        panel,
        workspace([item("growth_change")]),
        "organization",
        () => undefined,
      );
      const review = [...panel.querySelectorAll("button")].find(
        (button) => button.textContent === "Review",
      );
      review?.click();
      await vi.waitFor(() => {
        if (state === "completed")
          expect(panel.textContent).toContain("Investigate demand");
        else
          expect(panel.textContent?.toLowerCase()).toContain(
            state.replace("_", " "),
          );
      });
      const ask = [...panel.querySelectorAll("button")].find((button) =>
        button.textContent?.startsWith("Ask Hermes"),
      );
      expect(ask?.disabled).toBe(["queued", "running"].includes(state));
      panel.remove();
      vi.restoreAllMocks();
    },
  );

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

  it("keeps unresolved evidence visible without offering Ask Hermes", () => {
    const invalid = item("growth_change");
    invalid.governed_eligibility = {
      eligible: false,
      limitation: "The source observation does not resolve in this scope",
    };
    const data = workspace([invalid]);
    const sections = searchIntelligenceSections(data);
    expect(sections.attention).toEqual([invalid]);
    expect(sections.growth).toEqual([]);
    const panel = document.createElement("div");
    document.body.append(panel);
    renderSearchIntelligenceWorkspace(
      panel,
      data,
      "organization",
      () => undefined,
    );
    expect(panel.textContent).toContain(
      invalid.governed_eligibility.limitation,
    );
    [...panel.querySelectorAll("button")]
      .find((button) => button.textContent === "Review")
      ?.click();
    expect(panel.textContent).toContain(
      invalid.governed_eligibility.limitation,
    );
    expect(
      [...panel.querySelectorAll("button")].some((button) =>
        button.textContent?.startsWith("Ask Hermes"),
      ),
    ).toBe(false);
    panel.remove();
  });

  it("shows the exact next action for an approved unattributed change", () => {
    const growth = item("growth_change");
    growth.recommendation = {
      id: "revision-two",
      revision_number: 2,
      proposed_action: "Revise title and meta description",
      expected_result_hypothesis: "Improve CTR at stable rank",
      risk: "low",
      effort: "low",
      status: "approved",
      approved_by_user_id: "operator",
      evidence_references: [],
      decision_context: null,
    };
    growth.task = {
      id: "task",
      recommendation_revision_id: "revision-two",
      workflow_run_id: "run",
      target_type: "opportunity",
      target_reference: "seo-opportunity:source",
      status: "verification_pending",
      verified_at: null,
      verification_evidence: { result: "unavailable" },
    };
    const data = workspace([growth]);
    expect(searchIntelligenceSections(data).attention).toEqual([growth]);
    const panel = document.createElement("div");
    document.body.append(panel);
    renderSearchIntelligenceWorkspace(
      panel,
      data,
      "organization",
      () => undefined,
    );
    expect(panel.textContent).toContain("Implementation evidence is pending");
    [...panel.querySelectorAll("button")]
      .find((button) => button.textContent === "Review")
      ?.click();
    expect(panel.textContent).toContain("Target resolution required");
    expect(panel.textContent).toContain("not a page URL");
    expect(panel.textContent).not.toContain("Implementation completed");
    panel.remove();
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
