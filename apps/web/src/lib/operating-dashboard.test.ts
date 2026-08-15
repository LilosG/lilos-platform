import { describe, expect, it } from "vitest";

import {
  dashboardMetrics,
  hasRecordedActivity,
  requiresAttention,
  todaysWork,
  totalStatuses,
} from "./operating-dashboard";
import type { InsightsSummary } from "./workspace";

const summary: InsightsSummary = {
  workflow_runs: { completed: 4, failed: 1 },
  gbp: {
    locations: 2,
    profile_snapshots: 3,
    publications: { verified: 2, reconciliation_required: 1 },
  },
  reviews: { responded: 5, new: 2, publication_failed: 1 },
  content_publications: { deployed: 1, failed: 1, reserved: 2 },
  seo: {
    crawl_runs: { completed: 2 },
    opportunities: { identified: 3, rejected: 1 },
  },
  leads: { new: 2, assigned: 3, converted: 1, lost: 1 },
};

describe("operating dashboard", () => {
  it("derives truthful operational metrics from status counts", () => {
    const metrics = dashboardMetrics(summary);
    expect(metrics.find((item) => item.key === "reviews")?.value).toBe(8);
    expect(metrics.find((item) => item.key === "review-work")?.value).toBe(3);
    expect(metrics.find((item) => item.key === "leads")?.value).toBe(5);
    expect(metrics.find((item) => item.key === "content")?.value).toBe(1);
  });

  it("does not turn missing summary data into fabricated zeroes", () => {
    expect(dashboardMetrics(null)).toEqual([]);
  });

  it("does not treat a mapped location without product activity as an outcome", () => {
    const thinSummary: InsightsSummary = {
      workflow_runs: {},
      gbp: { locations: 1, profile_snapshots: 0, publications: {} },
      reviews: {},
      content_publications: {},
      seo: { crawl_runs: {}, opportunities: {} },
      leads: {},
    };
    expect(dashboardMetrics(thinSummary)).toEqual([]);
    expect(hasRecordedActivity(thinSummary)).toBe(false);
  });

  it("separates failures from routine work", () => {
    expect(requiresAttention(summary).map((item) => item.key)).toEqual([
      "workflows",
      "reviews",
      "gbp",
      "content",
    ]);
    expect(todaysWork(summary).map((item) => item.key)).toEqual([
      "review-work",
      "lead-work",
      "content-work",
      "seo-work",
    ]);
  });

  it("sums only the supplied provider-observed statuses", () => {
    expect(totalStatuses({ new: 2, responded: 7 })).toBe(9);
  });
});
