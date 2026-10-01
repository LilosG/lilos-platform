import { describe, it, expect, vi } from "vitest";
import {
  assertMutation,
  csrfToken,
  safeReturn,
  boundedBody,
} from "../../src/server/security";
import { acceptedWrites, validCookieHeader } from "../../src/server/session";
import { config } from "../../src/server/config";
import { forward } from "../../src/server/bff";
import { resolveSlug } from "../../src/server/context";
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
const rev = "33333333-3333-4333-8333-333333333333";
function locals(): App.Locals {
  return {
    settings,
    userId,
    token: "server-only-token",
    binding: "session-1",
    csrf: "",
    correlationId: "journey-1",
    auth: {} as App.Locals["auth"],
  };
}
function post(
  origin = "https://console.test",
  csrf = csrfToken("session-1", userId, settings.csrfSecret),
  body: unknown = { approve: true },
) {
  return new Request("https://console.test/api/action/", {
    method: "POST",
    headers: {
      origin,
      "Content-Type": "application/json",
      "X-CSRF-Token": csrf,
    },
    body: JSON.stringify(body),
  });
}
describe("CSRF/host/returns", () => {
  it("binds a nonce to exact origin, session and actor", () => {
    const nonce = csrfToken("binding", userId, settings.csrfSecret);
    const request = new Request(settings.origin + "/action/", {
      headers: { Origin: settings.origin },
    });
    expect(() =>
      assertMutation(request, nonce, "binding", userId, settings),
    ).not.toThrow();
    for (const origin of ["null", "https://evil.test", ""])
      expect(() =>
        assertMutation(
          new Request(settings.origin, { headers: { Origin: origin } }),
          nonce,
          "binding",
          userId,
          settings,
        ),
      ).toThrow();
    expect(() =>
      assertMutation(request, nonce, "different", userId, settings),
    ).toThrow();
    expect(() =>
      assertMutation(request, nonce, "binding", "other-user", settings),
    ).toThrow();
    expect(() =>
      assertMutation(
        new Request("https://evil.vercel.app/", {
          headers: { Origin: settings.origin },
        }),
        nonce,
        "binding",
        userId,
        settings,
      ),
    ).toThrow();
  });
  it.each([
    "//evil.test",
    "https://evil.test",
    "/%5cevil.test",
    "/%2f%2fevil.test",
    "/auth/sign-in/",
    "/%00oops",
  ])("rejects unsafe return %s", (value) =>
    expect(safeReturn(value)).toBe("/"),
  );
  it("preserves protected context", () =>
    expect(safeReturn("/clients/synthetic/opportunities/?offset=50")).toBe(
      "/clients/synthetic/opportunities/?offset=50",
    ));
  it("bounds streamed bodies", async () =>
    expect(
      boundedBody(
        new Request(settings.origin, { method: "POST", body: "x".repeat(10) }),
        5,
      ),
    ).rejects.toThrow("BODY_TOO_LARGE"));
  it("rejects preview host or production auth identity mismatch", () => {
    const env = {
      CONSOLE_ENV: "staging",
      VERCEL_ENV: "preview",
      VERCEL_URL: "approved.vercel.app",
      CONSOLE_ORIGIN: "https://evil.vercel.app",
      CONSOLE_EXPECTED_HOST: "evil.vercel.app",
      CONSOLE_API_ORIGIN: "https://api.test",
      CONSOLE_SUPABASE_URL: "https://stage.supabase.co",
      CONSOLE_SUPABASE_KEY: "key",
      CONSOLE_CSRF_SECRET: "x".repeat(32),
    };
    expect(() => config(env)).toThrow();
  });
});
describe("concurrent refresh and chunk cleanup", () => {
  it.each([true, false])(
    "stale failure cannot clear a successful rotation in completion order %s",
    (successFirst) => {
      const rotated = [
        { name: "__Host-lilos-session.0", value: "rotated", options: {} },
        { name: "__Host-lilos-session.1", value: "", options: { maxAge: 0 } },
      ];
      const failed = [
        { name: "__Host-lilos-session.0", value: "", options: { maxAge: 0 } },
      ];
      const responses = successFirst
        ? [acceptedWrites(rotated, true), acceptedWrites(failed, false)]
        : [acceptedWrites(failed, false), acceptedWrites(rotated, true)];
      const jar = new Map<string, string>();
      for (const response of responses)
        for (const cookie of response) {
          if (cookie.value) jar.set(cookie.name, cookie.value);
          else jar.delete(cookie.name);
        }
      expect(jar.get("__Host-lilos-session.0")).toBe("rotated");
      expect(jar.has("__Host-lilos-session.1")).toBe(false);
    },
  );
  it("refuses oversized, duplicate and gapped session cookies", () => {
    expect(() => validCookieHeader("x".repeat(16385), "session")).toThrow(
      "COOKIE_TOO_LARGE",
    );
    expect(validCookieHeader("session.0=x; session.2=y", "session")).toBe(
      false,
    );
    expect(validCookieHeader("session=x; session=x", "session")).toBe(false);
    expect(validCookieHeader("session.0=x; session.1=y", "session")).toBe(true);
    expect(() =>
      validCookieHeader(
        Array.from({ length: 9 }, (_, i) => `session.${i}=x`).join(";"),
        "session",
      ),
    ).toThrow();
  });
});
describe("explicit BFF", () => {
  it("only attaches server bearer and approved correlation headers", async () => {
    const fetcher = vi.fn(
      async (_input: unknown, _init: RequestInit = {}) =>
        new Response('{"data":{}}', {
          headers: {
            "Content-Type": "application/json",
            "Set-Cookie": "unsafe=1",
            Connection: "close",
          },
        }),
    );
    const result = await forward(
      post(),
      `organizations/${org}/seo/recommendations/${rev}/decision/`,
      locals(),
      fetcher,
    );
    expect(result.status).toBe(200);
    expect(result.headers.get("set-cookie")).toBeNull();
    expect(result.headers.get("connection")).toBeNull();
    expect(result.headers.get("cache-control")).toBe("private, no-store");
    expect(fetcher.mock.calls[0][0]).toBe(
      `https://api.test/api/v1/organizations/${org}/seo/recommendations/${rev}/decision`,
    );
    const init = fetcher.mock.calls[0][1]!;
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Bearer server-only-token",
    );
    expect(init.redirect).toBe("manual");
    expect(
      (init.headers as Record<string, string>)["Idempotency-Key"],
    ).toBeUndefined();
  });
  it.each([
    "proxy/?url=https://evil.test",
    `organizations/not-uuid/command-center/opportunities/`,
    "me/?url=x",
  ])("denies arbitrary paths %s", async (path) => {
    const fetcher = vi.fn();
    expect((await forward(post(), path, locals(), fetcher)).status).toBe(404);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("denies foreign origin, invalid body, query and method before upstream", async () => {
    const path = `organizations/${org}/seo/recommendations/${rev}/decision/`;
    const fetcher = vi.fn();
    expect(
      (await forward(post("https://evil.test"), path, locals(), fetcher))
        .status,
    ).toBe(403);
    expect(
      (
        await forward(
          post(undefined, undefined, { approve: true, revision_id: "other" }),
          path,
          locals(),
          fetcher,
        )
      ).status,
    ).toBe(400);
    expect(
      (
        await forward(
          new Request(settings.origin + "/?url=evil"),
          "me/",
          locals(),
          fetcher,
        )
      ).status,
    ).toBe(400);
    expect(
      (
        await forward(
          new Request(settings.origin, { method: "DELETE" }),
          path,
          locals(),
          fetcher,
        )
      ).status,
    ).toBe(405);
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("refuses redirects and secret-bearing upstream responses", async () => {
    for (const result of [
      new Response(null, {
        status: 302,
        headers: { Location: "https://evil.test" },
      }),
      new Response('{"access_token":"unsafe"}', {
        headers: { "Content-Type": "application/json" },
      }),
    ])
      expect(
        (
          await forward(
            new Request(settings.origin),
            "me/",
            locals(),
            async () => result,
          )
        ).status,
      ).toBe(502);
  });
  it("does not automatically replay uncertain mutations", async () => {
    const fetcher = vi.fn(async () => {
      throw new Error("timeout");
    });
    const response = await forward(
      post(),
      `organizations/${org}/seo/recommendations/${rev}/decision/`,
      locals(),
      fetcher,
    );
    expect(response.status).toBe(504);
    expect(await response.json()).toMatchObject({
      code: "MUTATION_OUTCOME_UNCERTAIN",
    });
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
  it("never shares tenant request state or upstream cache headers", async () => {
    const a = locals(),
      b = { ...locals(), userId: "other", token: "tenant-b" };
    const fetcher = vi.fn(
      async (_input: unknown, init: RequestInit = {}) =>
        new Response(JSON.stringify({ data: init.headers }), {
          headers: {
            "Content-Type": "application/json",
            "Cache-Control": "public,max-age=3600",
          },
        }),
    );
    const responses = await Promise.all(
      [a, b].map((local) =>
        forward(new Request(settings.origin), "me/", local, fetcher),
      ),
    );
    expect(await responses[1].text()).not.toContain(a.token!);
    expect(
      responses.every(
        (r) => r.headers.get("cache-control") === "private, no-store",
      ),
    ).toBe(true);
  });
  it("resolves only an authorized canonical slug once", () => {
    expect(() => resolveSlug([], "synthetic-client")).toThrow(
      "CLIENT_NOT_FOUND",
    );
  });
});
