import { beforeEach, describe, expect, it, vi } from "vitest";

const apiGet = vi.fn();
const apiRequest = vi.fn();

vi.mock("./api-client", () => ({
  apiGet: (...args: unknown[]) => apiGet(...args),
  apiRequest: (...args: unknown[]) => apiRequest(...args),
}));

import {
  discoverAnalytics,
  mapAnalytics,
  syncAnalytics,
  fetchAnalyticsSummary,
} from "./analytics";

describe("analytics lib routes", () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiRequest.mockReset();
    apiGet.mockResolvedValue({ kind: "ok", data: {} });
    apiRequest.mockResolvedValue({ kind: "ok", data: {} });
  });

  it("discoverAnalytics POSTs to the discover endpoint with optional website", async () => {
    await discoverAnalytics("org-1", "site-1");
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/insights/analytics/discover",
      { method: "POST", body: { website_id: "site-1" } },
    );
  });

  it("mapAnalytics POSTs the selected property to the map endpoint", async () => {
    await mapAnalytics("org-1", {
      external_property_id: "properties/123",
      property_number: "123",
      display_name: "Wheyland",
    });
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/insights/analytics/map",
      {
        method: "POST",
        body: {
          external_property_id: "properties/123",
          property_number: "123",
          display_name: "Wheyland",
        },
      },
    );
  });

  it("syncAnalytics POSTs to the sync endpoint", async () => {
    await syncAnalytics("org-1", "prop-1", 28);
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/insights/analytics/properties/prop-1/sync",
      { method: "POST", body: { days: 28 } },
    );
  });

  it("fetchAnalyticsSummary GETs the summary endpoint", async () => {
    await fetchAnalyticsSummary("org-1");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/insights/analytics/summary",
    );
  });
});
