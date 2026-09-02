import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet, type ApiRequestOptions } from "./api-client";

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
  refreshAccessToken: vi.fn(),
}));

import { readPublicConfig } from "./config";
import { getAccessToken, refreshAccessToken } from "./session";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("apiGet", () => {
  it("returns not-configured without making a network call", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(null);
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const outcome = await apiGet("/api/v1/me");
    expect(outcome).toEqual({ kind: "not-configured" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("returns unauthenticated when there is no access token", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue(null);
    const outcome = await apiGet("/api/v1/me");
    expect(outcome).toEqual({ kind: "unauthenticated" });
  });

  it("classifies a network failure as disconnected, not a fabricated result", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new TypeError("network error"),
    );
    const outcome = await apiGet("/api/v1/me");
    expect(outcome).toEqual({ kind: "disconnected" });
  });

  it("classifies a stalled request as a timeout error instead of a disconnected API", async () => {
    vi.useFakeTimers();
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_input, init) =>
        new Promise((_resolve, reject) => {
          const signal = (init as RequestInit | undefined)?.signal;
          signal?.addEventListener("abort", () => {
            reject(
              new DOMException("The operation was aborted.", "AbortError"),
            );
          });
        }),
    );

    const outcomePromise = apiGet("/api/v1/me");
    await vi.advanceTimersByTimeAsync(15_000);
    const outcome = await outcomePromise;

    expect(outcome).toEqual({
      kind: "error",
      status: 0,
      code: "REQUEST_TIMEOUT",
      message: "The platform API did not finish within 15 seconds.",
      details: [],
    });
    vi.useRealTimers();
  });

  it("recovers from a stale token by refreshing and retrying once, instead of reporting a real sign-out", async () => {
    // Regression: production logs showed genuine authenticated AAL2
    // sessions getting a 401 on the industries/organizations calls (a
    // locally-held token stale relative to the server, e.g. right after an
    // MFA step-up) that was previously reported straight through as
    // "unauthenticated" -- indistinguishable from an actual sign-out.
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("stale-token");
    vi.mocked(refreshAccessToken).mockResolvedValue("fresh-token");
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation((_input, init) => {
        const headers = new Headers((init as RequestInit).headers);
        if (headers.get("Authorization") === "Bearer stale-token") {
          return Promise.resolve(new Response(null, { status: 401 }));
        }
        return Promise.resolve(
          new Response(JSON.stringify({ data: { ok: true } }), {
            status: 200,
          }),
        );
      });

    const outcome = await apiGet<{ ok: boolean }>(
      "/api/v1/platform/industries",
    );

    expect(outcome).toEqual({ kind: "ok", data: { ok: true } });
    expect(fetchSpy).toHaveBeenCalledTimes(2);
    expect(refreshAccessToken).toHaveBeenCalledTimes(1);
  });

  it("reports unauthenticated (not an infinite retry) when refreshing does not recover a valid session", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("stale-token");
    vi.mocked(refreshAccessToken).mockResolvedValue(null);
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 401 }));

    const outcome = await apiGet("/api/v1/platform/industries");

    expect(outcome).toEqual({ kind: "unauthenticated" });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
  });

  it("classifies 401/403/404 as distinct truthful states", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    for (const [status, kind] of [
      [401, "unauthenticated"],
      [403, "forbidden"],
      [404, "not-found"],
    ] as const) {
      vi.spyOn(globalThis, "fetch").mockResolvedValue(
        new Response(null, { status }),
      );
      const outcome = await apiGet("/api/v1/me");
      expect(outcome).toEqual({ kind });
    }
  });

  it("returns ok with the unwrapped data envelope on success", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: { hello: "world" } }), {
        status: 200,
      }),
    );
    const outcome = await apiGet<{ hello: string }>("/api/v1/me");
    expect(outcome).toEqual({ kind: "ok", data: { hello: "world" } });
  });

  it("surfaces the standard error envelope for other failures", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: { code: "CONFLICT", message: "Stale version." },
        }),
        { status: 409 },
      ),
    );
    const outcome = await apiGet("/api/v1/me");
    expect(outcome).toEqual({
      kind: "error",
      status: 409,
      code: "CONFLICT",
      message: "Stale version.",
      details: [],
    });
  });
});

describe("ApiRequestOptions supports PATCH", () => {
  it("accepts PATCH as a valid HTTP method", () => {
    const opts: ApiRequestOptions = {
      method: "PATCH",
      body: { status: "active" },
    };
    expect(opts.method).toBe("PATCH");
    expect(opts.body).toEqual({ status: "active" });
  });
});

describe("ApiRequestOptions timeoutMs", () => {
  it("allows callers to supply an operation-specific timeout", () => {
    const opts: ApiRequestOptions = {
      method: "POST",
      body: { brief_id: "b1" },
      timeoutMs: 60_000,
    };
    expect(opts.timeoutMs).toBe(60_000);
  });

  it("defaults to undefined so the client fallback applies", () => {
    const opts: ApiRequestOptions = { method: "GET" };
    expect(opts.timeoutMs).toBeUndefined();
  });
});
