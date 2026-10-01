import { latestLiveRecommendation, type SEORecommendation } from "./seo";
import { describe, expect, it } from "vitest";

import {
  FALLBACK_MAX_CRAWL_PAGES,
  describeCrawlResult,
  isSEOOpportunityActionable,
  normalizeCrawlPageLimit,
} from "./seo";

describe("SEO opportunity lifecycle", () => {
  it("matches the statuses produced by the recommendation workflow", () => {
    expect(isSEOOpportunityActionable("identified")).toBe(true);
    expect(isSEOOpportunityActionable("recommended")).toBe(true);
    expect(isSEOOpportunityActionable("approved")).toBe(true);
    expect(isSEOOpportunityActionable("rejected")).toBe(false);
  });
});

describe("normalizeCrawlPageLimit", () => {
  it("falls back to the platform default when the API limit is unavailable", () => {
    expect(FALLBACK_MAX_CRAWL_PAGES).toBe(300);
    expect(normalizeCrawlPageLimit(10_000)).toBe(300);
  });

  it("clamps to an API-supplied limit rather than the fallback", () => {
    expect(normalizeCrawlPageLimit(1_000, 500)).toBe(500);
    expect(normalizeCrawlPageLimit(10, 500)).toBe(10);
  });

  it("keeps the operator value within the accepted range", () => {
    expect(normalizeCrawlPageLimit(5)).toBe(5);
    expect(normalizeCrawlPageLimit(0)).toBe(1);
    expect(normalizeCrawlPageLimit(Number.NaN)).toBe(300);
  });
});

describe("describeCrawlResult", () => {
  it("renders the truthful completed crawl result", () => {
    expect(
      describeCrawlResult({
        id: "crawl-1",
        status: "success",
        max_pages: 20,
        stop_reason: "Crawl completed",
        safe_result: { pages_crawled: 1 },
      }),
    ).toBe("Status: Success · 1 page crawled · Crawl completed");
  });

  it("does not invent result counts that the API omitted", () => {
    expect(
      describeCrawlResult({
        id: "crawl-2",
        status: "partial",
        max_pages: 20,
        stop_reason: null,
        safe_result: {},
      }),
    ).toBe("Status: Partial");
  });
});

function revision(revision_number: number, status: string): SEORecommendation {
  return {
    id: `rev-${revision_number}`,
    revision_number,
    proposed_action: "x",
    expected_result_hypothesis: "y",
    risk: "low",
    effort: "low",
    status,
    approved_by_user_id: null,
    evidence_references: [],
    decision_context: null,
    change_set: [],
    change_set_limitation_code: null,
    site_change: null,
  };
}

describe("latestLiveRecommendation", () => {
  it("returns the newest revision that is still in play", () => {
    const live = latestLiveRecommendation([
      revision(3, "awaiting_approval"),
      revision(2, "superseded"),
      revision(1, "superseded"),
    ]);
    expect(live?.id).toBe("rev-3");
  });

  it("never returns a superseded or withdrawn revision, whatever its number", () => {
    const live = latestLiveRecommendation([
      revision(9, "superseded"),
      revision(8, "withdrawn"),
      revision(4, "approved"),
    ]);
    expect(live?.id).toBe("rev-4");
    expect(
      latestLiveRecommendation([
        revision(2, "superseded"),
        revision(1, "withdrawn"),
      ]),
    ).toBeUndefined();
    expect(latestLiveRecommendation([])).toBeUndefined();
  });

  it("keeps a rejected revision visible as the latest decision", () => {
    expect(
      latestLiveRecommendation([
        revision(2, "rejected"),
        revision(1, "superseded"),
      ])?.id,
    ).toBe("rev-2");
  });
});
