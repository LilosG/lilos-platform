import { describe, expect, it } from "vitest";
import type { SEORecommendation, SEOSiteChangeState } from "../seo";
import {
  describeBlockedCode,
  isSafePullRequestUrl,
  siteChangeView,
} from "./site-change-view";

function recommendation(
  overrides: Partial<SEORecommendation> = {},
): SEORecommendation {
  return {
    id: "rev-1",
    revision_number: 2,
    proposed_action: "Rewrite the title",
    expected_result_hypothesis: "More clicks",
    risk: "low",
    effort: "low",
    status: "approved",
    approved_by_user_id: "user-1",
    evidence_references: [],
    decision_context: null,
    change_set: [
      {
        page_id: "page-1",
        field: "seo_title",
        current_value: "Old title",
        proposed_value: "New title",
        rationale: "Lead with the query",
      },
    ],
    change_set_limitation_code: null,
    site_change: null,
    ...overrides,
  };
}

function state(
  overrides: Partial<SEOSiteChangeState> = {},
): SEOSiteChangeState {
  return {
    mapping_state: "mapped",
    blocked_code: null,
    publication_status: null,
    pull_request_url: null,
    build_gate: null,
    build_state: null,
    verification_state: null,
    live_checks: [],
    ...overrides,
  };
}

describe("siteChangeView", () => {
  it("is null for a recommendation with no site change", () => {
    expect(
      siteChangeView(recommendation({ change_set: [], site_change: null })),
    ).toBeNull();
    expect(siteChangeView(null)).toBeNull();
  });

  it("shows before and after for each approved edit", () => {
    const view = siteChangeView(recommendation({ site_change: state() }))!;
    expect(view.changes).toEqual([
      {
        label: "SEO title",
        before: "Old title",
        after: "New title",
        rationale: "Lead with the query",
      },
    ]);
    expect(view.pullRequest).toBeNull();
    expect(view.blocked).toBeNull();
  });

  it("links to the pull request on the client repo and reports the build gate", () => {
    const view = siteChangeView(
      recommendation({
        site_change: state({
          pull_request_url: "https://github.com/LilosG/coco-maya/pull/42",
          build_gate: "vercel_preview",
          build_state: "pending",
          publication_status: "checks_running",
        }),
      }),
    )!;
    expect(view.pullRequest).toEqual({
      href: "https://github.com/LilosG/coco-maya/pull/42",
      label: "View pull request on GitHub",
    });
    expect(view.stages.map((stage) => [stage.label, stage.tone])).toEqual([
      ["Mapping", "ready"],
      ["Build", "pending"],
      ["Live check", "neutral"],
    ]);
    expect(view.stages[1].text).toBe("Waiting on Vercel preview");
  });

  it("shows the typed code, not a guess, when a page is unmapped", () => {
    const view = siteChangeView(
      recommendation({
        change_set: [],
        change_set_limitation_code: "SITE_MAPPING_REQUIRED",
        site_change: state({
          mapping_state: "required",
          blocked_code: "SITE_MAPPING_REQUIRED",
        }),
      }),
    )!;
    expect(view.blocked?.code).toBe("SITE_MAPPING_REQUIRED");
    expect(view.blocked?.message).toContain("page map");
    expect(view.stages[0]).toMatchObject({ label: "Mapping", tone: "blocked" });
    expect(view.changes).toEqual([]);
  });

  it("uses the limitation code even before any site-change state exists", () => {
    const view = siteChangeView(
      recommendation({
        change_set: [],
        change_set_limitation_code: "SITE_MAPPING_REQUIRED",
        site_change: null,
      }),
    )!;
    expect(view.blocked?.code).toBe("SITE_MAPPING_REQUIRED");
    expect(view.stages).toHaveLength(1);
  });

  it("explains CHECKS_UNAVAILABLE and keeps the pull request link", () => {
    const view = siteChangeView(
      recommendation({
        site_change: state({
          publication_status: "checks_failed",
          blocked_code: "CHECKS_UNAVAILABLE",
          pull_request_url: "https://github.com/LilosG/site/pull/9",
          build_gate: "none",
          build_state: "unavailable",
        }),
      }),
    )!;
    expect(view.blocked?.code).toBe("CHECKS_UNAVAILABLE");
    expect(view.blocked?.message).toContain("not merged");
    expect(view.stages[1]).toMatchObject({ tone: "blocked" });
    expect(view.pullRequest?.href).toContain("/pull/9");
  });

  it("reports the observed value when the live page differs", () => {
    const view = siteChangeView(
      recommendation({
        site_change: state({
          publication_status: "failed",
          blocked_code: "SITE_CHANGE_VERIFICATION_FAILED",
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
      }),
    )!;
    expect(view.stages[2]).toMatchObject({ tone: "blocked" });
    expect(view.liveChecks).toEqual([
      {
        label: "SEO title",
        expected: "New title",
        observed: "Old title",
        matches: false,
      },
    ]);
  });

  it("marks a verified change ready end to end", () => {
    const view = siteChangeView(
      recommendation({
        site_change: state({
          publication_status: "verified",
          build_gate: "repository_ci",
          build_state: "passed",
          verification_state: "verified",
          live_checks: [
            {
              field: "seo_title",
              expected: "New title",
              observed: "New title",
              state: "verified",
            },
            {
              field: "schema",
              expected: "x",
              observed: null,
              state: "not_checked",
            },
          ],
        }),
      }),
    )!;
    expect(view.stages.map((stage) => stage.tone)).toEqual([
      "ready",
      "ready",
      "ready",
    ]);
    // A field the read-back cannot prove is never listed as confirmed.
    expect(view.liveChecks).toHaveLength(1);
    expect(view.blocked).toBeNull();
  });
});

describe("describeBlockedCode", () => {
  it("never renders blank for a code the UI has not learned yet", () => {
    expect(describeBlockedCode("SOMETHING_NEW")).toContain("stopped");
    expect(describeBlockedCode("SITE_CHANGE_FINGERPRINT_MISMATCH")).toContain(
      "approved",
    );
  });
});

describe("isSafePullRequestUrl", () => {
  it("links only to https GitHub", () => {
    expect(isSafePullRequestUrl("https://github.com/o/r/pull/1")).toBe(true);
    expect(isSafePullRequestUrl("http://github.com/o/r/pull/1")).toBe(false);
    expect(isSafePullRequestUrl("https://evil.example/pull/1")).toBe(false);
    expect(isSafePullRequestUrl("javascript:alert(1)")).toBe(false);
    expect(isSafePullRequestUrl("not a url")).toBe(false);
  });
});
