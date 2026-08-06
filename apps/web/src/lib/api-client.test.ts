import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "./api-client";

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

  it("times out and returns disconnected instead of hanging forever on a stalled request", async () => {
    // Regression: a server that accepts a connection but never responds
    // never rejects fetch() and never resolves it either -- with no
    // timeout, the awaited request (and every page awaiting it, e.g.
    // /onboarding's bootstrap calls) hung on "Loading…" indefinitely.
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
          // Never resolves and never rejects on its own -- simulates a
          // stalled connection with no network error ever raised.
        }),
    );

    const outcomePromise = apiGet("/api/v1/me");
    await vi.advanceTimersByTimeAsync(15_000);
    const outcome = await outcomePromise;

    expect(outcome).toEqual({ kind: "disconnected" });
    vi.useRealTimers();
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
