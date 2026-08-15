import { describe, expect, it } from "vitest";
import { formatMetricDelta, formatMetricValue } from "./data-display";

describe("data display formatting", () => {
  it("formats governed units with consistent precision", () => {
    expect(formatMetricValue(3248, { unit: "count" })).toBe("3,248");
    expect(
      formatMetricValue(0.033, { unit: "percentage", sourceScale: "ratio" }),
    ).toBe("3.3%");
    expect(
      formatMetricValue(0.003, {
        unit: "percentagePoint",
        sourceScale: "ratio",
      }),
    ).toBe("0.3pp");
    expect(formatMetricValue(11.36, { unit: "position" })).toBe("11.4");
    expect(
      formatMetricValue(125.5, { unit: "currency", currency: "USD" }),
    ).toBe("$125.50");
    expect(
      formatMetricValue(183, { unit: "duration", durationUnit: "seconds" }),
    ).toBe("3m 3s");
  });

  it("separates numeric sign from inverted outcome direction", () => {
    expect(
      formatMetricDelta(-5.8, {
        unit: "percentage",
        outcome: "lower-is-better",
      }),
    ).toEqual({
      text: "−5.8%",
      outcome: "positive",
    });
    expect(
      formatMetricDelta(0.003, {
        unit: "percentagePoint",
        sourceScale: "ratio",
        outcome: "higher-is-better",
      }),
    ).toEqual({
      text: "+0.3pp",
      outcome: "positive",
    });
  });
});
