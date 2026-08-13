import { describe, expect, it } from "vitest";
import {
  formatBusinessHours,
  formatBusinessHoursRows,
  type BusinessHoursRow,
} from "./business-hours";

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

  it("formats production-style Mon-Fri 8-7 with Sat-Sun Closed (object TimeOfDay)", () => {
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "TUESDAY",
          closeDay: "TUESDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "WEDNESDAY",
          closeDay: "WEDNESDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "THURSDAY",
          closeDay: "THURSDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "FRIDAY",
          closeDay: "FRIDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
      ],
    };
    const result = formatBusinessHours(hours);
    expect(result).toContain("Mon\u2013Fri");
    expect(result).toContain("8:00 AM\u20137:00 PM");
    expect(result).toContain("Sat\u2013Sun");
    expect(result).toContain("Closed");
  });

  it("formats string form Mon-Fri 9-5 with weekends closed", () => {
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

  it("handles object TimeOfDay with full fields (hours, minutes, seconds, nanos)", () => {
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: { hours: 8, minutes: 30, seconds: 0, nanos: 0 },
          closeTime: { hours: 17, minutes: 30, seconds: 0, nanos: 0 },
        },
      ],
    };
    const result = formatBusinessHours(hours);
    expect(result).toContain("8:30 AM");
    expect(result).toContain("5:30 PM");
  });

  it("includes minutes when non-zero (string form)", () => {
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

  it("handles overnight intervals with exact output", () => {
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
    expect(result).not.toBe("\u2014");
    expect(result.length).toBeGreaterThan(0);
    expect(result).toContain("10:00 PM\u2013");
    expect(result).toContain("\u20132:00 AM");
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

  it("falls back to em dash for invalid hour values (> 23 or < 0)", () => {
    expect(
      formatBusinessHours({
        periods: [
          {
            openDay: "MONDAY",
            closeDay: "MONDAY",
            openTime: "25:00",
            closeTime: "17:00",
          },
        ],
      }),
    ).toBe("\u2014");
    expect(
      formatBusinessHours({
        periods: [
          {
            openDay: "MONDAY",
            closeDay: "MONDAY",
            openTime: { hours: -1 },
            closeTime: { hours: 17 },
          },
        ],
      }),
    ).toBe("\u2014");
  });

  it("rejects null hours in object form instead of converting to 00:00", () => {
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: { hours: null },
          closeTime: { hours: 17 },
        },
      ],
    };
    expect(formatBusinessHours(hours)).toBe("\u2014");
  });
});

describe("formatBusinessHoursRows", () => {
  it("returns null for invalid input", () => {
    expect(formatBusinessHoursRows(null)).toBeNull();
    expect(formatBusinessHoursRows(undefined)).toBeNull();
    expect(formatBusinessHoursRows({})).toBeNull();
  });

  it("returns structured rows for production-style hours", () => {
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "TUESDAY",
          closeDay: "TUESDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "WEDNESDAY",
          closeDay: "WEDNESDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "THURSDAY",
          closeDay: "THURSDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "FRIDAY",
          closeDay: "FRIDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
      ],
    };

    const rows = formatBusinessHoursRows(hours) as BusinessHoursRow[];
    expect(rows).not.toBeNull();
    expect(rows!.length).toBe(2);
    expect(rows![0]).toEqual({
      dayLabel: "Mon\u2013Fri",
      timeLabel: "8:00 AM\u20137:00 PM",
    });
    expect(rows![1]).toEqual({
      dayLabel: "Sat\u2013Sun",
      timeLabel: "Closed",
    });
  });
});

describe("formatAmPm midnight handling", () => {
  it("does not produce 12:00 PM for midnight boundary", () => {
    // Regression: formatAmPm(1440) must not produce "12:00 PM"
    // 24 * 60 = 1440 minutes = midnight end-of-day
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: "00:00",
          closeTime: "00:00",
        },
      ],
    };
    // closeTime == openTime should be treated as overnight (close <= open)
    // 00:00 should not produce "12:00 PM"
    const result = formatBusinessHours(hours);
    // Either it renders something or it falls back — but it must NOT contain "12:00 PM"
    expect(result).not.toContain("12:00 PM");
  });
});

describe("formatBusinessHoursRows for pending candidates", () => {
  it("returns structured rows for production-style hours, never raw schema keys", () => {
    const hours = {
      periods: [
        {
          openDay: "MONDAY",
          closeDay: "MONDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "TUESDAY",
          closeDay: "TUESDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "WEDNESDAY",
          closeDay: "WEDNESDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "THURSDAY",
          closeDay: "THURSDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
        {
          openDay: "FRIDAY",
          closeDay: "FRIDAY",
          openTime: { hours: 8 },
          closeTime: { hours: 19 },
        },
      ],
    };

    const rows = formatBusinessHoursRows(hours);
    expect(rows).not.toBeNull();
    expect(rows!.length).toBe(2);

    const text = JSON.stringify(rows);
    expect(text).not.toContain("OpenDay");
    expect(text).not.toContain("CloseDay");
    expect(text).not.toContain("OpenTime");
    expect(text).not.toContain("CloseTime");
    expect(text).not.toContain("Hours");
    expect(text).not.toContain("Periods");
    expect(text).not.toContain("MONDAY");
    expect(text).not.toContain("TUESDAY");
    expect(text).not.toContain("WEDNESDAY");
    expect(text).not.toContain("THURSDAY");
    expect(text).not.toContain("FRIDAY");

    expect(rows![0]).toEqual({
      dayLabel: "Mon\u2013Fri",
      timeLabel: "8:00 AM\u20137:00 PM",
    });
    expect(rows![1]).toEqual({
      dayLabel: "Sat\u2013Sun",
      timeLabel: "Closed",
    });
  });
});

describe("strict malformed time rejection", () => {
  it("rejects string times with non-numeric characters", () => {
    expect(
      formatBusinessHours({
        periods: [
          {
            openDay: "MONDAY",
            closeDay: "MONDAY",
            openTime: "08x:00",
            closeTime: "17:00",
          },
        ],
      }),
    ).toBe("\u2014");
  });

  it("rejects string times with trailing junk", () => {
    expect(
      formatBusinessHours({
        periods: [
          {
            openDay: "MONDAY",
            closeDay: "MONDAY",
            openTime: "8:30junk",
            closeTime: "17:00",
          },
        ],
      }),
    ).toBe("\u2014");
  });

  it("rejects overly large nanos values", () => {
    expect(
      formatBusinessHours({
        periods: [
          {
            openDay: "MONDAY",
            closeDay: "MONDAY",
            openTime: { hours: 9, nanos: 1_000_000_000 },
            closeTime: { hours: 17 },
          },
        ],
      }),
    ).toBe("\u2014");
  });

  it("rejects negative nanos values", () => {
    expect(
      formatBusinessHours({
        periods: [
          {
            openDay: "MONDAY",
            closeDay: "MONDAY",
            openTime: { hours: 9, nanos: -1 },
            closeTime: { hours: 17 },
          },
        ],
      }),
    ).toBe("\u2014");
  });
});
