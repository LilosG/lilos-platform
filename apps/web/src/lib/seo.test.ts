import { describe, expect, it } from "vitest";

import { MAX_CRAWL_PAGES, normalizeCrawlPageLimit } from "./seo";

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
