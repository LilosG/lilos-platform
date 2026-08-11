import { beforeEach, describe, expect, it, vi } from "vitest";

const apiRequest = vi.fn();

vi.mock("./api-client", () => ({
  apiGet: vi.fn(),
  apiRequest: (...args: unknown[]) => apiRequest(...args),
}));

import { beginConnection, connectGoogle } from "./gbp-connection";

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
