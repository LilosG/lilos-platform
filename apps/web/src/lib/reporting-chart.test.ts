import { describe, expect, it } from "vitest";

import { trendChartModel, trendSummary } from "./reporting-chart";

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
