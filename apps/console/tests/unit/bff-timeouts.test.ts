import { describe, it, expect, vi, afterEach } from "vitest";
import { forward, routes } from "../../src/server/bff";
import { DRAFT_NARRATIVE_TIMEOUT_MS } from "../../src/server/report-routes";
import { csrfToken } from "../../src/server/security";

const settings = {
  origin: "https://console.test",
  apiOrigin: "https://api.test",
  supabaseUrl: "https://auth.test",
  supabaseKey: "key",
  csrfSecret: "x".repeat(32),
  local: false,
};
const userId = "11111111-1111-4111-8111-111111111111";
const org = "22222222-2222-4222-8222-222222222222";
const locals = (): App.Locals => ({
  settings,
  userId,
  token: "server-only-token",
  binding: "session-1",
  csrf: "",
  correlationId: "journey-1",
  auth: {} as App.Locals["auth"],
});
const reply = () =>
  new Response('{"data":{}}', {
    headers: { "Content-Type": "application/json" },
  });

afterEach(() => vi.restoreAllMocks());

describe("BFF request timeouts", () => {
  it("gives only the draft-narrative route a longer timeout", () => {
    const longer = routes.filter((route) => "timeoutMs" in route);
    expect(longer).toHaveLength(1);
    expect(
      longer[0].pattern.test(
        `organizations/${org}/command-center/reports/2026-09/previous/1/draft-narrative/`,
      ),
    ).toBe(true);
    expect((longer[0] as { timeoutMs: number }).timeoutMs).toBe(
      DRAFT_NARRATIVE_TIMEOUT_MS,
    );
    expect(DRAFT_NARRATIVE_TIMEOUT_MS).toBe(200_000);
  });

  it("applies it to the draft POST and keeps 10 s and 30 s for the rest", async () => {
    const timeout = vi.spyOn(AbortSignal, "timeout");
    const base = `organizations/${org}/command-center/reports`;
    const post = () =>
      new Request("https://console.test/api/action/", {
        method: "POST",
        headers: {
          origin: "https://console.test",
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken("session-1", userId, settings.csrfSecret),
        },
        body: "{}",
      });
    const run = async (request: Request, path: string) => {
      timeout.mockClear();
      const fetcher = vi.fn(async (_i: unknown, _init: RequestInit = {}) =>
        reply(),
      );
      expect((await forward(request, path, locals(), fetcher)).status).toBe(
        200,
      );
      return timeout.mock.calls[0][0];
    };
    expect(
      await run(post(), `${base}/2026-09/previous/1/draft-narrative/`),
    ).toBe(200_000);
    expect(await run(post(), `${base}/2026-09/previous/1/approve/`)).toBe(
      30_000,
    );
    expect(
      await run(new Request("https://console.test/api/action/"), `${base}/`),
    ).toBe(10_000);
  });
});
