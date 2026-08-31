import { describe, expect, it } from "vitest";
import {
  BUSINESS_DAYS,
  buildBusinessHoursValue,
  formatBusinessHoursRows,
  type BusinessHoursDayInput,
} from "./business-hours";

/**
 * business.hours could only be derived from a connected Google Business
 * Profile. Connecting a provider happens after activation and activation waits
 * on the business details, so a client with no GBP connection had a required
 * detail marked Missing and no way in the product to supply it.
 */

function week(
  overrides: Partial<Record<string, Partial<BusinessHoursDayInput>>> = {},
): BusinessHoursDayInput[] {
  return BUSINESS_DAYS.map((day) => ({
    day,
    closed: true,
    open: "09:00",
    close: "17:00",
    ...(overrides[day] ?? {}),
  }));
}

describe("entering hours by hand", () => {
  it("produces the same shape a GBP sync does, so both render identically", () => {
    const { value, errors } = buildBusinessHoursValue(
      week({ MONDAY: { closed: false, open: "09:00", close: "17:00" } }),
    );
    expect(errors).toEqual([]);
    expect(value).toEqual({
      periods: [
        {
          openDay: "MONDAY",
          openTime: "09:00",
          closeDay: "MONDAY",
          closeTime: "17:00",
        },
      ],
    });
    // The proof that the shape is right: the existing formatter reads it.
    expect(formatBusinessHoursRows(value)).not.toBeNull();
  });

  it("rolls a closing time past midnight onto the next day", () => {
    // A beach bar that shuts at 2am is the ordinary case here, not an edge one.
    const { value } = buildBusinessHoursValue(
      week({ FRIDAY: { closed: false, open: "18:00", close: "02:00" } }),
    );
    expect(value?.periods[0]).toEqual({
      openDay: "FRIDAY",
      openTime: "18:00",
      closeDay: "SATURDAY",
      closeTime: "02:00",
    });
  });

  it("wraps Sunday round to Monday rather than falling off the week", () => {
    const { value } = buildBusinessHoursValue(
      week({ SUNDAY: { closed: false, open: "20:00", close: "01:00" } }),
    );
    expect(value?.periods[0].closeDay).toBe("MONDAY");
  });

  it("keeps only the days that are open", () => {
    const { value } = buildBusinessHoursValue(
      week({
        MONDAY: { closed: false },
        WEDNESDAY: { closed: false },
      }),
    );
    expect(value?.periods.map((p) => p.openDay)).toEqual([
      "MONDAY",
      "WEDNESDAY",
    ]);
  });

  it("refuses a time it cannot read instead of guessing at it", () => {
    // A silently wrong opening hour is published to a client's Google profile.
    const { value, errors } = buildBusinessHoursValue(
      week({ TUESDAY: { closed: false, open: "9am", close: "17:00" } }),
    );
    expect(value).toBeNull();
    expect(errors[0]).toContain("Tuesday");
    expect(errors[0]).toContain("HH:MM");
  });

  it.each(["24:00", "09:60", "", "  ", "9:00"])(
    "rejects %s as an opening time",
    (open: string) => {
      const { errors } = buildBusinessHoursValue(
        week({ MONDAY: { closed: false, open, close: "17:00" } }),
      );
      expect(errors.length).toBeGreaterThan(0);
    },
  );

  it("says so when every day was left closed", () => {
    const { value, errors } = buildBusinessHoursValue(week());
    expect(value).toBeNull();
    expect(errors[0]).toContain("at least one day");
  });

  it("reports every unreadable day, not just the first", () => {
    const { errors } = buildBusinessHoursValue(
      week({
        MONDAY: { closed: false, open: "bad" },
        FRIDAY: { closed: false, close: "worse" },
      }),
    );
    expect(errors).toHaveLength(2);
  });

  it("tolerates surrounding whitespace an operator types", () => {
    const { value, errors } = buildBusinessHoursValue(
      week({ MONDAY: { closed: false, open: " 09:00 ", close: " 17:00 " } }),
    );
    expect(errors).toEqual([]);
    expect(value?.periods[0].openTime).toBe("09:00");
  });
});
