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
