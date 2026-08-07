import { afterEach, describe, expect, it, vi } from "vitest";

const config = {
  apiBaseUrl: "https://api.lilos.invalid",
  supabaseUrl: "x",
  supabaseAnonKey: "y",
};

vi.mock("./config", () => ({
  readPublicConfig: vi.fn(),
}));
vi.mock("./session", () => ({
  getAccessToken: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

import { readPublicConfig } from "./config";
import { getAccessToken } from "./session";
import {
  fetchLeadAssignees,
  LEAD_STATUS_VALUES,
  LEAD_TRANSITION_TARGET_STATUSES,
  LEAD_URGENCY_VALUES,
  TERMINAL_LEAD_STATUSES,
  formatSpeedToLead,
  isTerminalLeadStatus,
} from "./leads";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchLeadAssignees", () => {
  it("calls the organization-scoped assignees endpoint and returns the typed candidates", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          data: [
            {
              user_profile_id: "11111111-1111-4111-8111-111111111111",
              display_name: "Owner Operator",
              membership_status: "active",
              membership_type: "client",
              role_keys: ["organization_owner"],
            },
            {
              user_profile_id: "22222222-2222-4222-8222-222222222222",
              display_name: null,
              membership_status: "active",
              membership_type: "client",
              role_keys: ["organization_member"],
            },
          ],
        }),
        { status: 200 },
      ),
    );
    const outcome = await fetchLeadAssignees(
      "00000000-0000-4000-8000-000000000001",
    );
    expect(outcome.kind).toBe("ok");
    if (outcome.kind === "ok") {
      expect(outcome.data).toHaveLength(2);
      expect(outcome.data[0].display_name).toBe("Owner Operator");
      expect(outcome.data[1].display_name).toBeNull();
    }
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [url] = fetchSpy.mock.calls[0];
    expect(url).toBe(
      "https://api.lilos.invalid/api/v1/organizations/00000000-0000-4000-8000-000000000001/leads/assignees",
    );
  });

  it("returns forbidden when the caller lacks leads.assign — never fabricates a list", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "FORBIDDEN" } }), {
        status: 403,
      }),
    );
    const outcome = await fetchLeadAssignees(
      "00000000-0000-4000-8000-000000000001",
    );
    expect(outcome.kind).toBe("forbidden");
  });

  it("returns an empty list truthfully when the organization has no assignable members", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [] }), { status: 200 }),
    );
    const outcome = await fetchLeadAssignees(
      "00000000-0000-4000-8000-000000000001",
    );
    expect(outcome.kind).toBe("ok");
    if (outcome.kind === "ok") {
      expect(outcome.data).toEqual([]);
    }
  });
});

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
