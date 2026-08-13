import { describe, expect, it } from "vitest";
import { formatBusinessHours } from "./business-hours";

describe("formatBusinessHours", () => {
  it("returns em dash for null / undefined / non-object", () => {
    expect(formatBusinessHours(null)).toBe("\u2014");
    expect(formatBusinessHours(undefined)).toBe("\u2014");
    expect(formatBusinessHours("")).toBe("\u2014");
    expect(formatBusinessHours(42)).toBe("\u2014");
  });

  it("returns em dash for object without valid periods", () => {
    expect(formatBusinessHours({})).toBe("\u2014");
    expect(formatBusinessHours({ periods: null })).toBe("\u2014");
    expect(formatBusinessHours({ periods: [] })).toBe("\u2014");
  });

  it("formats standard Mon-Fri 9-5 with weekends closed", () => {
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: "09:00",
          closeTime: "17:00",
        },
        {
          openDay: "TUESDAY",
          closeDay: "TUESDAY",
          openTime: "09:00",
          closeTime: "17:00",
        },
        {
          openDay: "WEDNESDAY",
          closeDay: "WEDNESDAY",
          openTime: "09:00",
          closeTime: "17:00",
        },
        {
          openDay: "THURSDAY",
          closeDay: "THURSDAY",
          openTime: "09:00",
          closeTime: "17:00",
        },
        {
          openDay: "FRIDAY",
          closeDay: "FRIDAY",
          openTime: "09:00",
          closeTime: "17:00",
        },
      ],
    };
    const result = formatBusinessHours(hours);
    expect(result).toContain("Mon\u2013Fri");
    expect(result).toContain("9:00 AM\u20135:00 PM");
    expect(result).toContain("Sat\u2013Sun");
    expect(result).toContain("Closed");
  });

  it("includes minutes when non-zero", () => {
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: "08:30",
          closeTime: "17:30",
        },
      ],
    };
    const result = formatBusinessHours(hours);
    expect(result).toContain("8:30 AM");
    expect(result).toContain("5:30 PM");
  });

  it("handles split hours on a single day", () => {
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: "09:00",
          closeTime: "12:00",
        },
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: "13:00",
          closeTime: "17:00",
        },
      ],
    };
    const result = formatBusinessHours(hours);
    expect(result).toContain("9:00 AM\u201312:00 PM");
    expect(result).toContain("1:00 PM\u20135:00 PM");
  });

  it("handles overnight intervals", () => {
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: "22:00",
          closeTime: "02:00",
        },
      ],
    };
    const result = formatBusinessHours(hours);
    // Should not crash; overnight interval produces meaningful output
    expect(result).not.toBe("\u2014");
    expect(result.length).toBeGreaterThan(0);
  });

  it("falls back to em dash for unrecognized day names", () => {
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "RABBITDAY",
          openTime: "09:00",
          closeTime: "17:00",
        },
      ],
    };
    expect(formatBusinessHours(hours)).toBe("\u2014");
  });
});
