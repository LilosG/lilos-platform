import { beforeEach, describe, expect, it, vi } from "vitest";

const apiGet = vi.fn();
const apiRequest = vi.fn();

vi.mock("./api-client", () => ({
  apiGet: (...args: unknown[]) => apiGet(...args),
  apiRequest: (...args: unknown[]) => apiRequest(...args),
}));

import {
  decideGrowthInitiative,
  dispatchGrowthInitiative,
  fetchGrowthInitiative,
  fetchGrowthQueue,
  reconcileGrowthInitiative,
} from "./growth";

describe("growth lib routes", () => {
  beforeEach(() => {
    apiGet.mockReset();
    apiRequest.mockReset();
    apiGet.mockResolvedValue({ kind: "ok", data: [] });
    apiRequest.mockResolvedValue({ kind: "ok", data: {} });
  });

  it("loads the organization Growth Queue", async () => {
    await fetchGrowthQueue("org-1");
    expect(apiGet).toHaveBeenCalledWith("/api/v1/organizations/org-1/growth");
  });

  it("loads one initiative", async () => {
    await fetchGrowthInitiative("org-1", "initiative-1");
    expect(apiGet).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/growth/initiative-1",
    );
  });

  it("submits an explicit initiative decision", async () => {
    await decideGrowthInitiative("org-1", "initiative-1", true);
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/growth/initiative-1/decision",
      { method: "POST", body: { approve: true } },
    );
  });

  it("dispatches only through the governed Growth endpoint", async () => {
    await dispatchGrowthInitiative("org-1", "initiative-1");
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/growth/initiative-1/dispatch",
      { method: "POST" },
    );
  });

  it("reconciles downstream workflow state", async () => {
    await reconcileGrowthInitiative("org-1", "initiative-1");
    expect(apiRequest).toHaveBeenCalledWith(
      "/api/v1/organizations/org-1/growth/initiative-1/reconcile",
      { method: "POST" },
    );
  });
});
