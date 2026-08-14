import { describe, expect, it } from "vitest";

import {
  deltaClass,
  formatDelta,
  formatPercentDelta,
  metricAwareDeltaClass,
  periodLabelFromDays,
  toTimeSeriesPoints,
} from "./reporting";

describe("formatDelta", () => {
  it("prefixes positive values with +", () => {
    expect(formatDelta(12)).toBe("+12");
  });

  it("keeps negative values with -", () => {
    expect(formatDelta(-5)).toBe("-5");
  });

  it("returns em dash for null", () => {
    expect(formatDelta(null)).toBe("—");
  });
});

describe("formatPercentDelta", () => {
  it("formats positive with + and one decimal", () => {
    expect(formatPercentDelta(12.42)).toBe("+12.4%");
  });

  it("formats negative", () => {
    expect(formatPercentDelta(-3.5)).toBe("-3.5%");
  });

  it("returns null for null", () => {
    expect(formatPercentDelta(null)).toBeNull();
  });

  it("returns null for non-finite", () => {
    expect(formatPercentDelta(Infinity)).toBeNull();
  });
});

describe("deltaClass", () => {
  it("positive delta is positive by default", () => {
    expect(deltaClass(5)).toBe("delta--positive");
  });

  it("negative delta is negative by default", () => {
    expect(deltaClass(-5)).toBe("delta--negative");
  });

  it("zero delta is neutral", () => {
    expect(deltaClass(0)).toBe("delta--neutral");
  });

  it("null delta is neutral", () => {
    expect(deltaClass(null)).toBe("delta--neutral");
  });
});

describe("metricAwareDeltaClass", () => {
  it("position decrease is positive (inverted metric)", () => {
    // Lower average position = better ranking
    expect(metricAwareDeltaClass("position", -0.5)).toBe("delta--positive");
  });

  it("position increase is negative (inverted metric)", () => {
    expect(metricAwareDeltaClass("position", 0.8)).toBe("delta--negative");
  });

  it("clicks increase is positive (normal metric)", () => {
    expect(metricAwareDeltaClass("clicks", 100)).toBe("delta--positive");
  });

  it("clicks decrease is negative (normal metric)", () => {
    expect(metricAwareDeltaClass("clicks", -100)).toBe("delta--negative");
  });

  it("impressions increase is positive", () => {
    expect(metricAwareDeltaClass("impressions", 50)).toBe("delta--positive");
  });

  it("ctr increase is positive", () => {
    expect(metricAwareDeltaClass("ctr", 0.02)).toBe("delta--positive");
  });

  it("null delta is neutral regardless of metric", () => {
    expect(metricAwareDeltaClass("position", null)).toBe("delta--neutral");
  });
});

describe("periodLabelFromDays", () => {
  it("returns the exact day count for all supported periods", () => {
    expect(periodLabelFromDays(7)).toBe("7 days");
    expect(periodLabelFromDays(28)).toBe("28 days");
    expect(periodLabelFromDays(90)).toBe("90 days");
  });
});

describe("toTimeSeriesPoints (missing vs zero)", () => {
  it("preserves real zero as 0", () => {
    const points = toTimeSeriesPoints(
      [{ date: "2026-08-01", metrics: { sessions: 0 } }],
      "sessions",
    );
    expect(points).toEqual([{ date: "2026-08-01", value: 0 }]);
  });

  it("preserves missing metric as null (not zero)", () => {
    const points = toTimeSeriesPoints(
      [{ date: "2026-08-01", metrics: {} }],
      "sessions",
    );
    expect(points).toEqual([{ date: "2026-08-01", value: null }]);
  });

  it("distinguishes zero from missing on the same series", () => {
    const points = toTimeSeriesPoints(
      [
        { date: "2026-08-01", metrics: { sessions: 0 } },
        { date: "2026-08-02", metrics: {} },
        { date: "2026-08-03", metrics: { sessions: 12 } },
      ],
      "sessions",
    );
    expect(points).toEqual([
      { date: "2026-08-01", value: 0 },
      { date: "2026-08-02", value: null },
      { date: "2026-08-03", value: 12 },
    ]);
  });

  it("keeps input chronological order", () => {
    const points = toTimeSeriesPoints(
      [
        { date: "2026-08-03", metrics: { sessions: 3 } },
        { date: "2026-08-01", metrics: { sessions: 1 } },
        { date: "2026-08-02", metrics: { sessions: 2 } },
      ],
      "sessions",
    );
    expect(points.map((p) => p.date)).toEqual([
      "2026-08-03",
      "2026-08-01",
      "2026-08-02",
    ]);
  });
});
