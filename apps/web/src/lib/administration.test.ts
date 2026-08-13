import { describe, expect, it } from "vitest";
import {
  businessFactLabel,
  factSourceLabel,
  formatBusinessFactValue,
} from "./administration";

describe("business fact presentation", () => {
  it("uses operator-facing labels for governed fact keys", () => {
    expect(businessFactLabel("business.name")).toBe("Business name");
    expect(businessFactLabel("business.address")).toBe("Business address");
    expect(businessFactLabel("brand.approved_claims")).toBe("Approved claims");
  });

  it("renders structured addresses as a reviewable value", () => {
    expect(
      formatBusinessFactValue({
        address_line_1: "123 Main St",
        address_line_2: null,
        city: "San Diego",
        region: "CA",
        postal_code: "92101",
        country_code: "US",
      }),
    ).toBe("123 Main St · San Diego, CA 92101 · US");
  });

  it("never falls back to the unreadable object string", () => {
    expect(formatBusinessFactValue({ service_area: "North County" })).toBe(
      "Service Area: North County",
    );
    expect(formatBusinessFactValue(["Licensed", "Bonded"])).toBe(
      "Licensed, Bonded",
    );
  });
});

describe("factSourceLabel", () => {
  it("produces friendly labels for known sources", () => {
    expect(factSourceLabel("gbp_profile_snapshot")).toBe(
      "Google Business Profile",
    );
    expect(factSourceLabel("organization_profile")).toBe("Business profile");
    expect(factSourceLabel("location")).toBe("Location record");
    expect(factSourceLabel("organization_domain")).toBe("Domain record");
  });

  it("never leaks raw internal identifiers", () => {
    expect(factSourceLabel("internal_system_x")).toBe("Business data");
    expect(factSourceLabel("some_unknown_source")).toBe("Business data");
  });

  it("handles empty source safely", () => {
    expect(factSourceLabel("")).toBe("Business data");
  });
});
