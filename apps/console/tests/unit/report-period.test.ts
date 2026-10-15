import { describe, expect, it } from "vitest";
import {
  PREVIOUS,
  addMonths,
  baselineError,
  comparisonBody,
  comparisonFromQuery,
  comparisonSlug,
  monthsOf,
  periodError,
  periodFromSlug,
  periodSlug,
  presetPeriods,
  reportHref,
  selectableMonths,
  span,
} from "../../src/lib/report-period";
const sept = { start: "2026-09-01", end: "2026-09-01" };
describe("report periods", () => {
  it("round-trips an address and refuses what is not 1 to 12 whole months", () => {
    for (const slug of ["2026-09", "2026-05_2026-09", "2025-10_2026-09"])
      expect(periodSlug(periodFromSlug(slug)!)).toBe(slug);
    for (const slug of [
      "2026-9",
      "2026-13",
      "2026-09_",
      "2026-09_2026-08",
      "2025-09_2026-09",
      "2026-05_2026-06_2026-07",
      "x",
    ])
      expect(periodFromSlug(slug)).toBeNull();
  });
  it("counts months across a year end", () => {
    const period = periodFromSlug("2025-11_2026-02")!;
    expect(span(period)).toBe(4);
    expect(monthsOf(period)).toEqual([
      "2025-11-01",
      "2025-12-01",
      "2026-01-01",
      "2026-02-01",
    ]);
    expect(addMonths("2026-01-01", -1)).toBe("2025-12-01");
    expect(addMonths("2026-11-01", 3)).toBe("2027-02-01");
  });
  it("names the comparison in an address and in the request", () => {
    expect(comparisonSlug(PREVIOUS)).toBe("previous");
    expect(comparisonSlug({ kind: "year-ago" })).toBe("year-ago");
    expect(
      comparisonSlug({
        kind: "baseline",
        start: "2026-01-01",
        end: "2026-03-01",
      }),
    ).toBe("vs-2026-01_2026-03");
    expect(comparisonFromQuery(null)).toEqual(PREVIOUS);
    expect(comparisonFromQuery("year-ago")).toEqual({ kind: "year-ago" });
    expect(comparisonFromQuery("2026-01_2026-03")).toEqual({
      kind: "baseline",
      start: "2026-01-01",
      end: "2026-03-01",
    });
    expect(comparisonFromQuery("nonsense")).toBeNull();
    expect(comparisonBody({ kind: "year-ago" })).toEqual({
      basis: "same_period_last_year",
    });
    expect(
      comparisonBody({
        kind: "baseline",
        start: "2026-01-01",
        end: "2026-03-01",
      }),
    ).toEqual({
      basis: "custom_baseline",
      baseline_start: "2026-01-01",
      baseline_end: "2026-03-01",
    });
  });
  it("builds the address of a report and of its document", () => {
    expect(reportHref("coco", sept)).toBe("/clients/coco/reports/2026-09/");
    expect(
      reportHref(
        "coco",
        { start: "2026-05-01", end: "2026-09-01" },
        { kind: "year-ago" },
        {
          revision: 2,
          document: true,
        },
      ),
    ).toBe(
      "/clients/coco/reports/2026-05_2026-09/document/?vs=year-ago&revision=2",
    );
  });
});
describe("period validation", () => {
  it("refuses a month that has not ended, an inverted range and one that is too long", () => {
    expect(periodError(sept, "2026-09-01")).toBeNull();
    expect(
      periodError({ start: "2026-09-01", end: "2026-10-01" }, "2026-09-01"),
    ).toBe("REPORT_MONTH_NOT_ENDED");
    expect(
      periodError({ start: "2026-09-01", end: "2026-08-01" }, "2026-09-01"),
    ).toBe("REPORT_PERIOD_ORDER");
    expect(
      periodError({ start: "2025-09-01", end: "2026-09-01" }, "2026-09-01"),
    ).toBe("REPORT_PERIOD_TOO_LONG");
    expect(
      periodError({ start: "2025-10-01", end: "2026-09-01" }, "2026-09-01"),
    ).toBeNull();
  });
  it("refuses a baseline that overlaps, runs backwards or is too long", () => {
    const period = { start: "2026-05-01", end: "2026-09-01" };
    expect(
      baselineError({ start: "2026-01-01", end: "2026-04-01" }, period),
    ).toBeNull();
    expect(
      baselineError({ start: "2026-03-01", end: "2026-05-01" }, period),
    ).toBe("REPORT_BASELINE_OVERLAPS");
    expect(
      baselineError({ start: "2026-03-01", end: "2026-02-01" }, period),
    ).toBe("REPORT_PERIOD_ORDER");
    expect(
      baselineError({ start: "2024-01-01", end: "2025-06-01" }, period),
    ).toBe("REPORT_PERIOD_TOO_LONG");
  });
});
describe("choices", () => {
  it("offers only months that have ended, newest first", () => {
    const months = selectableMonths("2026-09-01", 4);
    expect(months).toEqual([
      "2026-09-01",
      "2026-08-01",
      "2026-07-01",
      "2026-06-01",
    ]);
    expect(months).not.toContain("2026-10-01");
  });
  it("builds the four presets from the last ended month", () => {
    const presets = presetPeriods("2026-09-01");
    expect(presets["last-month"]).toEqual(sept);
    expect(presets["last-3"]).toEqual({
      start: "2026-07-01",
      end: "2026-09-01",
    });
    expect(presets["last-6"]).toEqual({
      start: "2026-04-01",
      end: "2026-09-01",
    });
    expect(presets["year-to-date"]).toEqual({
      start: "2026-01-01",
      end: "2026-09-01",
    });
    // In January the last ended month is December: the year so far is that whole year.
    expect(presetPeriods("2026-12-01")["year-to-date"]).toEqual({
      start: "2026-01-01",
      end: "2026-12-01",
    });
  });
});
