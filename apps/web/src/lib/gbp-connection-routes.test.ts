import { beforeEach, describe, expect, it, vi } from "vitest";

const apiRequest = vi.fn();

vi.mock("./api-client", () => ({
  apiGet: vi.fn(),
  apiRequest: (...args: unknown[]) => apiRequest(...args),
}));

import { beginConnection, connectGoogle } from "./gbp-connection";
import { confirmLocationMapping, removeLocationMapping } from "./gbp";

describe("Google connection product route", () => {
  beforeEach(() => {
    apiRequest.mockReset();
    apiRequest.mockResolvedValue({ kind: "ok", data: {} });
  });

  it("posts the requested product scopes to the shared connection endpoint", async () => {
    await connectGoogle("org-1", ["search_console", "analytics"]);
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/google/connect",
      {
        method: "POST",
        body: { products: ["search_console", "analytics"] },
      },
    );
  });

  it("uses the no-body shared connection path for credential reconnect", async () => {
    await beginConnection("org-1");
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/google/connect",
      { method: "POST" },
    );
  });
});

describe("canonical GBP mapping lifecycle route", () => {
  beforeEach(() => {
    apiRequest.mockReset();
    apiRequest.mockResolvedValue({ kind: "ok", data: {} });
  });

  it("confirms a mapping through the governed AAL2 mapping boundary", async () => {
    await confirmLocationMapping(
      "org-1",
      "platform-location-1",
      "gbp-location-1",
      false,
    );

    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/locations/platform-location-1/gbp-mapping/gbp-location-1/confirm",
      {
        method: "POST",
        body: {
          location_id: "platform-location-1",
          write_enabled: false,
        },
      },
    );
  });

  it("removes a mapping without issuing a provider mutation", async () => {
    await removeLocationMapping(
      "org-1",
      "platform-location-1",
      "gbp-location-1",
    );

    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/locations/platform-location-1/gbp-mapping/gbp-location-1",
      { method: "DELETE" },
    );
  });
});
