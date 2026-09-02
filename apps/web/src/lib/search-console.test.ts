import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock the api-client so we can assert the Search Console lib wires the real
// operator-path routes with the expected bodies, without any network access.
const apiGet = vi.fn();
const apiRequest = vi.fn();

vi.mock("./api-client", () => ({
  apiGet: (...args: unknown[]) => apiGet(...args),
  apiRequest: (...args: unknown[]) => apiRequest(...args),
}));

import {
  discoverSearchConsole,
  mapSearchConsole,
  syncSearchConsole,
  fetchSearchConsoleSummary,
} from "./search-console";

describe("search-console lib routes", () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiRequest.mockReset();
    apiGet.mockResolvedValue({ kind: "ok", data: {} });
    apiRequest.mockResolvedValue({ kind: "ok", data: {} });
  });

  it("discoverSearchConsole GETs the discover endpoint", async () => {
    await discoverSearchConsole("org-1", "site-1");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/seo/websites/site-1/search-console/discover",
    );
  });

  it("mapSearchConsole POSTs the selected property to the map endpoint", async () => {
    await mapSearchConsole("org-1", "site-1", {
      external_property_id: "sc-domain:example.com",
      property_type: "domain",
    });
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/seo/websites/site-1/search-console/map",
      {
        method: "POST",
        body: {
          external_property_id: "sc-domain:example.com",
          property_type: "domain",
        },
      },
    );
  });

  it("syncSearchConsole POSTs to the sync endpoint with the window", async () => {
    await syncSearchConsole("org-1", "site-1", "prop-1", 90);
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/seo/websites/site-1/search-properties/prop-1/sync",
      { method: "POST", body: { days: 90 }, timeoutMs: 90_000 },
    );
  });

  it("fetchSearchConsoleSummary GETs the summary endpoint", async () => {
    await fetchSearchConsoleSummary("org-1", "site-1");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/seo/websites/site-1/search-console/summary",
    );
  });
});
