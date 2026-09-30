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
    governed_eligibility: {
      eligible: true,
      limitation: null,
      limitation_code: null,
    },
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
              change_set: [],
              change_set_limitation_code: null,
              site_change: null,
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
      limitation_code: "SOURCE_RECORD_NOT_FOUND",
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
      "Check its mapping in Integrations and refresh evidence",
    );
    [...panel.querySelectorAll("button")]
      .find((button) => button.textContent === "Review")
      ?.click();
    expect(panel.textContent).toContain(
      "Check its mapping in Integrations and refresh evidence",
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
    delete growth.opportunity.evidence.page_mapping_state;
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
      change_set: [],
      change_set_limitation_code: null,
      site_change: null,
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
    expect(panel.textContent).toContain("Target resolution required");
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

  function approvedSiteChange(
    siteChange: NonNullable<
      SearchIntelligenceItem["recommendation"]
    >["site_change"],
  ): SearchIntelligenceItem {
    const growth = item("growth_change");
    growth.recommendation = {
      id: "revision-site",
      revision_number: 2,
      proposed_action: "Rewrite the title",
      expected_result_hypothesis: "More clicks",
      risk: "low",
      effort: "low",
      status: "approved",
      approved_by_user_id: "operator",
      evidence_references: [],
      decision_context: null,
      change_set: [
        {
          page_id: "page",
          field: "seo_title",
          current_value: "Old title",
          proposed_value: "New title",
          rationale: "Lead with the query",
        },
      ],
      change_set_limitation_code: null,
      site_change: siteChange,
    };
    return growth;
  }

  function openDetail(growth: SearchIntelligenceItem): HTMLElement {
    const panel = document.createElement("div");
    document.body.append(panel);
    renderSearchIntelligenceWorkspace(
      panel,
      workspace([growth]),
      "organization",
      () => undefined,
    );
    [...panel.querySelectorAll("button")]
      .find((button) => button.textContent === "Review")
      ?.click();
    return panel;
  }

  it("links an approved change to its pull request with mapping, build and live state", () => {
    const panel = openDetail(
      approvedSiteChange({
        mapping_state: "mapped",
        blocked_code: null,
        publication_status: "checks_running",
        pull_request_url: "https://github.com/LilosG/coco-maya/pull/42",
        build_gate: "vercel_preview",
        build_state: "pending",
        verification_state: null,
        live_checks: [],
      }),
    );
    const link = [...panel.querySelectorAll("a")].find(
      (anchor) => anchor.textContent === "View pull request on GitHub",
    );
    expect(link?.getAttribute("href")).toBe(
      "https://github.com/LilosG/coco-maya/pull/42",
    );
    expect(link?.getAttribute("rel")).toContain("noopener");
    expect(panel.textContent).toContain("Old title");
    expect(panel.textContent).toContain("New title");
    expect(panel.textContent).toContain("Mapping: Page mapped to its file");
    expect(panel.textContent).toContain("Build: Waiting on Vercel preview");
    panel.remove();
  });

  it("shows the typed code when a change is blocked and never links an unsafe URL", () => {
    const panel = openDetail(
      approvedSiteChange({
        mapping_state: "mapped",
        blocked_code: "CHECKS_UNAVAILABLE",
        publication_status: "checks_failed",
        pull_request_url: "https://evil.example/pull/1",
        build_gate: "none",
        build_state: "unavailable",
        verification_state: null,
        live_checks: [],
      }),
    );
    const alert = panel.querySelector<HTMLElement>("[data-blocked-code]");
    expect(alert?.dataset.blockedCode).toBe("CHECKS_UNAVAILABLE");
    expect(alert?.textContent).toContain("CHECKS_UNAVAILABLE");
    expect(alert?.textContent).toContain("not merged");
    expect(
      [...panel.querySelectorAll("a")].some((anchor) =>
        anchor.textContent?.includes("pull request"),
      ),
    ).toBe(false);
    panel.remove();
  });

  it("reports the observed live value when verification failed", () => {
    const panel = openDetail(
      approvedSiteChange({
        mapping_state: "mapped",
        blocked_code: "SITE_CHANGE_VERIFICATION_FAILED",
        publication_status: "failed",
        pull_request_url: "https://github.com/LilosG/coco-maya/pull/42",
        build_gate: "repository_ci",
        build_state: "passed",
        verification_state: "failed",
        live_checks: [
          {
            field: "seo_title",
            expected: "New title",
            observed: "Old title",
            state: "mismatch",
          },
        ],
      }),
    );
    expect(panel.textContent).toContain("SITE_CHANGE_VERIFICATION_FAILED");
    expect(panel.textContent).toContain(
      "Expected “New title”, observed “Old title”",
    );
    panel.remove();
  });
});
