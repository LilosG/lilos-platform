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
  syncSearchConsoleToCompletion,
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

  it("mapSearchConsole POSTs the selected property and website to the Integrations map endpoint", async () => {
    await mapSearchConsole("org-1", "site-1", {
      external_property_id: "sc-domain:example.com",
      property_type: "domain",
    });
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/google/search-console/properties/map",
      {
        method: "POST",
        body: {
          website_id: "site-1",
          external_property_id: "sc-domain:example.com",
          property_type: "domain",
        },
      },
    );
  });

  it("syncSearchConsole queues the sync and returns without a long timeout", async () => {
    await syncSearchConsole("org-1", "site-1", "prop-1", 90);
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/seo/websites/site-1/search-properties/prop-1/sync",
      { method: "POST", body: { days: 90 } },
    );
  });

  it("syncSearchConsoleToCompletion polls the queued run, not the request", async () => {
    apiRequest
      .mockResolvedValueOnce({
        kind: "ok",
        data: {
          workflow_run_id: "run-1",
          workflow_key: "seo.sync_search_console",
          status: "queued",
        },
      })
      .mockResolvedValueOnce({
        kind: "ok",
        data: { id: "run-1", status: "completed", failure_code: null },
      });
    const outcome = await syncSearchConsoleToCompletion(
      "org-1",
      "site-1",
      "prop-1",
    );
    expect(outcome.kind).toBe("ok");
    expect(apiRequest).toHaveBeenLastCalledWith(
      "/api/v1/organizations/org-1/workflows/runs/run-1",
      { method: "GET" },
    );
  });

  it("fetchSearchConsoleSummary GETs the summary endpoint", async () => {
    await fetchSearchConsoleSummary("org-1", "site-1");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/seo/websites/site-1/search-console/summary",
    );
  });
});
