import { describe, expect, it } from "vitest";

import {
  overlayChartModel,
  trendChartModel,
  trendSummary,
  type TrendMetric,
} from "./reporting-chart";

describe("shared reporting trend chart", () => {
  it("passes missing days to Chart.js as truthful null gaps", () => {
    const model = trendChartModel({
      key: "clicks",
      label: "Clicks",
      points: [
        { date: "2026-08-10", value: 4 },
        { date: "2026-08-11", value: null },
        { date: "2026-08-12", value: 7 },
      ],
    });

    expect(model.labels).toEqual(["2026-08-10", "2026-08-11", "2026-08-12"]);
    expect(model.values).toEqual([4, null, 7]);
  });

  it("provides an accessible summary including missing observations", () => {
    expect(
      trendSummary({
        key: "clicks",
        label: "Clicks",
        points: [
          { date: "2026-08-10", value: 4 },
          { date: "2026-08-11", value: null },
          { date: "2026-08-12", value: 7 },
        ],
      }),
    ).toBe(
      "Clicks ranged from 4 to 7 across 2 reported days, with 1 day missing.",
    );
  });

  it("uses round-number y-axis steps and bounds", () => {
    const model = trendChartModel({
      key: "sessions",
      label: "Sessions",
      points: [
        { date: "2026-08-10", value: 47 },
        { date: "2026-08-11", value: 142 },
        { date: "2026-08-12", value: 181 },
      ],
    });

    expect(model.stepSize).toBe(20);
    expect(model.minimum).toBe(40);
    expect(model.maximum).toBe(200);
  });

  it("anchors below the observed minimum without forcing a zero baseline", () => {
    const model = trendChartModel({
      key: "sessions",
      label: "Sessions",
      points: [
        { date: "2026-08-10", value: 88 },
        { date: "2026-08-11", value: 142 },
        { date: "2026-08-12", value: 190 },
      ],
    });

    expect(model).toMatchObject({ minimum: 80, stepSize: 20, maximum: 200 });
  });
});

function overlayMetric(
  key: string,
  points: Array<[string, number | null]>,
): TrendMetric {
  return {
    key,
    label: key,
    points: points.map(([date, value]) => ({ date, value })),
  };
}

describe("dual-metric overlay model", () => {
  it("gives each series its own scale so the smaller one is not flattened", () => {
    const model = overlayChartModel(
      overlayMetric("impressions", [
        ["2026-08-01", 4200],
        ["2026-08-02", 5100],
      ]),
      overlayMetric("clicks", [
        ["2026-08-01", 61],
        ["2026-08-02", 74],
      ]),
    );

    // On a shared axis, clicks in the tens against impressions in the thousands
    // would be painted flat along the baseline.
    expect(model.primary.axis.maximum).toBeGreaterThan(4200);
    expect(model.secondary.axis.maximum).toBeLessThan(1000);
  });

  it("aligns both series onto the union of their dates", () => {
    const model = overlayChartModel(
      overlayMetric("impressions", [
        ["2026-08-01", 100],
        ["2026-08-03", 300],
      ]),
      overlayMetric("clicks", [
        ["2026-08-02", 20],
        ["2026-08-03", 30],
      ]),
    );

    expect(model.labels).toEqual(["2026-08-01", "2026-08-02", "2026-08-03"]);
    expect(model.primary.values).toEqual([100, null, 300]);
    expect(model.secondary.values).toEqual([null, 20, 30]);
  });

  it("orders labels chronologically regardless of input order", () => {
    const model = overlayChartModel(
      overlayMetric("impressions", [
        ["2026-08-05", 10],
        ["2026-08-01", 20],
      ]),
      overlayMetric("clicks", [["2026-08-03", 5]]),
    );

    expect(model.labels).toEqual(["2026-08-01", "2026-08-03", "2026-08-05"]);
  });

  it("keeps a missing day as a gap rather than reporting it as zero", () => {
    const model = overlayChartModel(
      overlayMetric("impressions", [
        ["2026-08-01", 100],
        ["2026-08-02", null],
      ]),
      overlayMetric("clicks", [
        ["2026-08-01", 4],
        ["2026-08-02", 0],
      ]),
    );

    // A day with no observation and a day with zero clicks are different facts.
    expect(model.primary.values[1]).toBeNull();
    expect(model.secondary.values[1]).toBe(0);
  });

  it("produces a usable axis when a series has no observations at all", () => {
    const model = overlayChartModel(
      overlayMetric("impressions", [["2026-08-01", 100]]),
      overlayMetric("clicks", [["2026-08-01", null]]),
    );

    expect(Number.isFinite(model.secondary.axis.minimum)).toBe(true);
    expect(model.secondary.axis.maximum).toBeGreaterThan(
      model.secondary.axis.minimum,
    );
  });
});
