import { beforeEach, describe, expect, it, vi } from "vitest";

const apiGet = vi.fn();
const apiRequest = vi.fn();

vi.mock("./api-client", () => ({
  apiGet: (...args: unknown[]) => apiGet(...args),
  apiRequest: (...args: unknown[]) => apiRequest(...args),
}));

import { beginGitHubInstall, fetchGitHubRepositories } from "./github-app";

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
});
