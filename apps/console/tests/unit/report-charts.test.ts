import { describe, expect, it } from "vitest";
import {
  barChart,
  compact,
  horizontalBars,
  niceMaximum,
} from "../../src/lib/report-charts";
const bar = (
  value: number | null,
  group: "compared" | "period",
  partial = false,
) => ({
  label: "Aug",
  year: null,
  value,
  partial,
  group,
});
describe("report charts", () => {
  it("rounds an axis up to a plain number", () => {
    expect(niceMaximum(0)).toBe(4);
    expect(niceMaximum(1464)).toBe(1500);
    expect(niceMaximum(9100)).toBe(10000);
    expect(compact(12400)).toBe("12.4k");
    expect(compact(950)).toBe("950");
  });
  it("draws a month with no data as a gap, never a bar of zero", () => {
    const chart = barChart({
      title: "Views",
      bars: [
        bar(100, "compared"),
        bar(null, "period"),
        bar(300, "period", true),
      ],
      baseline: 100,
      baselineText: "Comparison average: 100 a month",
      format: (n) => String(n),
    });
    const [compared, missing, partial] = chart.bars;
    expect(missing).toMatchObject({
      missing: true,
      height: 0,
      valueLabel: null,
    });
    expect(compared.height).toBeGreaterThan(0);
    expect(partial.valueLabel).toBe("300*");
    expect(chart.divider).not.toBeNull();
    expect(chart.baseline!.y).toBeCloseTo(compared.y, 5);
    expect(chart.description).toContain("Aug not synced");
    expect(chart.description).toContain("Comparison average: 100 a month");
  });
  it("draws no baseline when nothing settled can set one", () => {
    const chart = barChart({
      title: "Views",
      bars: [bar(100, "period")],
      baseline: null,
      baselineText: "",
      format: String,
    });
    expect(chart.baseline).toBeNull();
    expect(chart.divider).toBeNull();
  });
  it("scales horizontal bars to the largest and keeps a real zero as no bar", () => {
    const model = horizontalBars("Stars", [
      { label: "5 stars", value: 260, valueLabel: "260 reviews", share: 76 },
      { label: "1 star", value: 0, valueLabel: "0 reviews", share: 0 },
    ]);
    expect(model.rows[0].barWidth).toBeGreaterThan(model.rows[1].barWidth);
    expect(model.rows[1].barWidth).toBe(0);
    expect(model.description).toContain("5 stars: 260 reviews, 76%");
  });
});
