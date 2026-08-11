import { describe, expect, it } from "vitest";

import {
  MAX_CRAWL_PAGES,
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
  it("matches the API crawl limit", () => {
    expect(MAX_CRAWL_PAGES).toBe(20);
    expect(normalizeCrawlPageLimit(100)).toBe(20);
  });

  it("keeps the operator value within the accepted range", () => {
    expect(normalizeCrawlPageLimit(5)).toBe(5);
    expect(normalizeCrawlPageLimit(0)).toBe(1);
    expect(normalizeCrawlPageLimit(Number.NaN)).toBe(20);
  });
});

describe("describeCrawlResult", () => {
  it("renders the truthful completed crawl result", () => {
    expect(
      describeCrawlResult({
        crawl_run_id: "crawl-1",
        status: "completed",
        safe_result: { pages_crawled: 1, opportunities_found: 2 },
        opportunities_created: [],
      }),
    ).toBe("Status: completed · 1 page crawled · 2 opportunities found");
  });

  it("does not invent result counts that the API omitted", () => {
    expect(
      describeCrawlResult({
        crawl_run_id: "crawl-2",
        status: "partial",
        safe_result: {},
        opportunities_created: [],
      }),
    ).toBe("Status: partial");
  });
});
