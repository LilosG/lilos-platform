import { describe, expect, it } from "vitest";
import {
  LEAD_STATUS_VALUES,
  LEAD_TRANSITION_TARGET_STATUSES,
  LEAD_URGENCY_VALUES,
  TERMINAL_LEAD_STATUSES,
  formatSpeedToLead,
  isTerminalLeadStatus,
} from "./leads";

describe("LEAD_STATUS_VALUES", () => {
  it("contains every status the API contract permits so the filter can locate any lead", () => {
    // Mirrors the Lead.status check constraint in the backend model.
    const expected = [
      "new",
      "validating",
      "unassigned",
      "assigned",
      "acknowledged",
      "contact_attempted",
      "contacted",
      "qualifying",
      "qualified",
      "appointment_requested",
      "appointment_scheduled",
      "converted",
      "nurture",
      "unresponsive",
      "disqualified",
      "lost",
      "spam",
      "duplicate",
      "archived",
    ];
    expect(LEAD_STATUS_VALUES).toEqual(expected);
  });

  it("has no duplicate values", () => {
    expect(new Set(LEAD_STATUS_VALUES).size).toBe(LEAD_STATUS_VALUES.length);
  });
});

describe("LEAD_URGENCY_VALUES", () => {
  it("includes the `unknown` default set at intake so newly intaken leads are filterable", () => {
    expect([...LEAD_URGENCY_VALUES]).toEqual([
      "routine",
      "same_day",
      "urgent",
      "emergency",
      "unknown",
    ]);
  });
});

describe("LEAD_TRANSITION_TARGET_STATUSES", () => {
  it("excludes conversion/loss/duplicate terminals, which are only reachable via dedicated endpoints", () => {
    // Mirrors the LeadStatusTransition.to_status literal.
    for (const terminal of [
      "converted",
      "disqualified",
      "lost",
      "spam",
      "cancelled",
      "duplicate",
    ]) {
      expect(LEAD_TRANSITION_TARGET_STATUSES).not.toContain(terminal);
    }
    expect(LEAD_TRANSITION_TARGET_STATUSES).toContain("archived");
  });
});

describe("isTerminalLeadStatus", () => {
  it("flags every status from which no further transition is possible", () => {
    for (const status of TERMINAL_LEAD_STATUSES) {
      expect(isTerminalLeadStatus(status)).toBe(true);
    }
  });

  it("does not flag active lifecycle states as terminal", () => {
    for (const status of [
      "new",
      "assigned",
      "contact_attempted",
      "contacted",
      "qualified",
      "nurture",
      "unresponsive",
    ]) {
      expect(isTerminalLeadStatus(status)).toBe(false);
    }
  });
});

describe("formatSpeedToLead", () => {
  it("returns Not available when no lead has reached first human contact (null average)", () => {
    expect(formatSpeedToLead(null)).toBe("Not available");
  });

  it("returns Not available for a non-numeric value rather than inventing a number", () => {
    expect(formatSpeedToLead(Number.NaN)).toBe("Not available");
  });

  it("shows seconds for sub-minute averages instead of rounding down to 0 min", () => {
    // Regression: a real 30-second average previously displayed as "0 min".
    expect(formatSpeedToLead(30)).toBe("30 sec");
    expect(formatSpeedToLead(59.4)).toBe("59 sec");
  });

  it("shows rounded minutes for averages of a minute or more", () => {
    expect(formatSpeedToLead(60)).toBe("1 min");
    expect(formatSpeedToLead(90)).toBe("2 min");
    expect(formatSpeedToLead(3600)).toBe("60 min");
  });
});
