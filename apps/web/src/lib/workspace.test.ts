import { afterEach, describe, expect, it, vi } from "vitest";

const config = {
  apiBaseUrl: "https://api.lilos.invalid",
  supabaseUrl: "x",
  supabaseAnonKey: "y",
};

vi.mock("./config", () => ({
  readPublicConfig: vi.fn(),
}));
vi.mock("./session", () => ({
  getAccessToken: vi.fn(),
}));

import { readPublicConfig } from "./config";
import { getAccessToken } from "./session";
import { fetchMyPlatformAdministratorStatus } from "./workspace";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("fetchMyPlatformAdministratorStatus", () => {
  it("calls the self-scoped endpoint only — never a path that could target another account", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            is_platform_administrator: true,
            meets_required_assurance: false,
            required_assurance_level: "aal2",
          },
        }),
        { status: 200 },
      ),
    );
    const outcome = await fetchMyPlatformAdministratorStatus();
    expect(fetchSpy).toHaveBeenCalledWith(
      "https://api.lilos.invalid/api/v1/me/platform-administrator",
      expect.anything(),
    );
    expect(outcome).toEqual({
      kind: "ok",
      data: {
        is_platform_administrator: true,
        meets_required_assurance: false,
        required_assurance_level: "aal2",
      },
    });
  });
});
