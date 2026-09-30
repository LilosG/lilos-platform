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
