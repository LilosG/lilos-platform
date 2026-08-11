import { describe, expect, it } from "vitest";
import { businessFactLabel, formatBusinessFactValue } from "./administration";

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
