import { beforeEach, describe, expect, it, vi } from "vitest";

const apiGet = vi.fn();
const apiRequest = vi.fn();
const apiBase = "https://api.example.com";
const callbackBase = `${apiBase}/api/v1/integrations/github/callback`;

vi.mock("./api-client", () => ({
  apiGet: (...args: unknown[]) => apiGet(...args),
  apiRequest: (...args: unknown[]) => apiRequest(...args),
}));

import {
  beginGitHubInstall,
  disconnectGitHub,
  fetchGitHubRepositories,
  githubInstallCallbackUrl,
} from "./github-app";

describe("github-app lib routes", () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiRequest.mockReset();
    apiGet.mockResolvedValue({ kind: "ok", data: [] });
    apiRequest.mockResolvedValue({ kind: "ok", data: {} });
  });

  it("beginGitHubInstall POSTs to the install endpoint", async () => {
    await beginGitHubInstall("org-1");
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/github/install",
      { method: "POST" },
    );
  });

  it("fetchGitHubRepositories GETs the repositories endpoint", async () => {
    await fetchGitHubRepositories("org-1");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/github/repositories",
    );
  });

  it("disconnectGitHub POSTs to the local installation binding endpoint", async () => {
    await disconnectGitHub("org-1");
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/integrations/github/disconnect",
      { method: "POST" },
    );
  });

  it("forwards a GitHub App installation return to the canonical API callback", () => {
    const search =
      "?state=tenant-state&installation_id=12345&setup_action=install";
    const expected =
      `${callbackBase}?state=tenant-state` +
      "&installation_id=12345&setup_action=install";

    expect(githubInstallCallbackUrl(search, `${apiBase}/`)).toBe(expected);
  });

  it("forwards provider errors so the backend can fail the one-time intent", () => {
    const search = "?state=tenant-state&error=access_denied";
    const expected = `${callbackBase}?state=tenant-state&error=access_denied`;

    expect(githubInstallCallbackUrl(search, apiBase)).toBe(expected);
  });

  it("ignores ordinary Integrations navigation and incomplete provider returns", () => {
    expect(githubInstallCallbackUrl("?installed=1", apiBase)).toBeNull();
    expect(githubInstallCallbackUrl("?installation_id=12345", apiBase)).toBeNull();
    expect(githubInstallCallbackUrl("?state=tenant-state", apiBase)).toBeNull();
  });
});
