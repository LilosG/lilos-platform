import { beforeEach, describe, expect, it, vi } from "vitest";

const apiGet = vi.fn();

vi.mock("./api-client", () => ({
  apiGet: (...args: unknown[]) => apiGet(...args),
  apiRequest: vi.fn(),
}));

import {
  fetchGoogleWorkspace,
  fetchUnmappedResources,
  fetchGitHubWorkspace,
  type MappedResource,
  type ProviderDirectoryEntry,
} from "./integrations";

describe("integrations client — Google workspace", () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiGet.mockResolvedValue({ kind: "ok", data: {} });
  });

  it("fetchGoogleWorkspace GETs the Google router /workspace endpoint", async () => {
    await fetchGoogleWorkspace("org-1");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/google/workspace",
    );
  });

  it("carries canonical GBP identity and governance state on mapped resources", () => {
    const resource: MappedResource = {
      id: "provider-mapping-id",
      external_resource_id: "locations/google-id",
      platform_resource_id: "platform-location-id",
      resource_type: "location",
      status: "active",
      display_name: "Example location",
      last_synced_at: null,
      sync_freshness: "never",
      gbp_location_id: "gbp-location-id",
      mapping_status: "confirmed",
      write_enabled: false,
    };

    expect(resource).toMatchObject({
      gbp_location_id: "gbp-location-id",
      mapping_status: "confirmed",
      write_enabled: false,
    });
  });
});

describe("integrations client — unmapped resources", () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiGet.mockResolvedValue({ kind: "ok", data: [] });
  });

  it("fetchUnmappedResources GETs the Google router /unmapped endpoint", async () => {
    await fetchUnmappedResources("org-1");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/google/unmapped",
    );
  });

  it("fetchUnmappedResources appends search query parameter", async () => {
    await fetchUnmappedResources("org-1", "cafe");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/google/unmapped?search=cafe",
    );
  });

  it("fetchUnmappedResources URL-encodes search value", async () => {
    await fetchUnmappedResources("org-1", "cafe & bar");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/google/unmapped?search=cafe%20%26%20bar",
    );
  });
});

describe("integrations client — GitHub workspace", () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiGet.mockResolvedValue({ kind: "ok", data: {} });
  });

  it("fetchGitHubWorkspace GETs the GitHub router /workspace endpoint", async () => {
    await fetchGitHubWorkspace("org-1");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/github/workspace",
    );
  });
});

describe("integrations client — provider directory types", () => {
  it("ProviderDirectoryEntry type is exported for frontend consumption", () => {
    // Type-level test — verifies the type is importable
    const entry: ProviderDirectoryEntry = {
      provider_key: "google_business_profile",
      provider_name: "Google",
      description: "Test",
      status: "connected",
      status_label: "Connected",
      requires_attention: false,
    };
    expect(entry.provider_key).toBe("google_business_profile");
  });

  it("ProviderDirectoryEntry supports all four status values", () => {
    const statuses: ProviderDirectoryEntry["status"][] = [
      "connected",
      "degraded",
      "not_connected",
      "not_configured",
    ];
    expect(statuses.length).toBe(4);
  });
});
