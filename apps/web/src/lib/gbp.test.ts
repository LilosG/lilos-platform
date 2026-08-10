import { describe, expect, it } from "vitest";

import { workspaceContextFor, type GBPLocationSummary } from "./gbp";

function location(
  overrides: Partial<GBPLocationSummary> = {},
): GBPLocationSummary {
  return {
    id: "gbp-location-id",
    business_name: "Wheyland Electric",
    mapping_status: "confirmed",
    location_id: "platform-location-id",
    write_enabled: false,
    last_discovered_at: "2026-08-10T18:00:00Z",
    last_synced_at: "2026-08-10T18:00:00Z",
    ...overrides,
  };
}

describe("workspaceContextFor", () => {
  it("keeps provider and platform location identifiers in their governed scopes", () => {
    expect(workspaceContextFor(location())).toEqual({
      platformLocationId: "platform-location-id",
      gbpLocationId: "gbp-location-id",
    });
  });

  it("does not open an unconfirmed or unscoped mapping", () => {
    expect(
      workspaceContextFor(location({ mapping_status: "suggested" })),
    ).toBeNull();
    expect(workspaceContextFor(location({ location_id: null }))).toBeNull();
  });
});
