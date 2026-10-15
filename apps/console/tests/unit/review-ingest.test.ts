import { describe, expect, it, vi } from "vitest";
import fixtures from "../fixtures/phase3.json";
import {
  failureMessage,
  importReviews,
  INGEST_WORKING,
} from "../../src/lib/review-actions";
import { forward } from "../../src/server/bff";
import { csrfToken } from "../../src/server/security";
const org = fixtures.workspace.organization_id,
  loc = fixtures.workspace.location_id,
  run = "33333333-3333-4333-8333-333333333333";
const url = `/api/organizations/${org}/locations/${loc}/reviews/ingest/`;
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
/** A fetch that accepts the import, then answers each poll in turn. */
const script = (...polls: (Response | Error)[]) => {
  const fetcher = vi.fn<typeof fetch>(async (input) => {
    if (!String(input).endsWith(`${run}/`))
      return json({ run_id: run, run_status: "queued" }, 202);
    const next = polls.shift() ?? json({ result: null });
    if (next instanceof Error) throw next;
    return next;
  });
  return fetcher;
};
const status = (result: string | null, run_status = "running") =>
  json({ run_id: run, run_status, result });
const go = (fetcher: typeof fetch, extra = {}) =>
  importReviews(
    url,
    { "X-CSRF-Token": "t" },
    { fetcher, wait: async () => {}, key: "import-key-1", ...extra },
  );
describe("manual review import", () => {
  it("tells the person it is working", () =>
    expect(INGEST_WORKING).toBe("Importing reviews. This can take a minute."));
  it("queues with an idempotency key, then keeps polling while it runs", async () => {
    const fetcher = script(status(null), status(null), status("SUCCEEDED"));
    expect(await go(fetcher)).toBe("SUCCEEDED");
    expect(fetcher).toHaveBeenCalledTimes(4);
    const [, init] = fetcher.mock.calls[0];
    expect(init?.method).toBe("POST");
    expect((init?.headers as Record<string, string>)["Idempotency-Key"]).toBe(
      "import-key-1",
    );
    expect(fetcher.mock.calls[1][0]).toBe(`${url}${run}/`);
  });
  it("asks again after a failed poll while the import may still be going", async () => {
    const fetcher = script(
      new Error("network"),
      json({ code: "UPSTREAM_UNAVAILABLE" }, 504),
      status("SUCCEEDED"),
    );
    expect(await go(fetcher)).toBe("SUCCEEDED");
  });
  it("reports a lost Google connection", async () => {
    expect(await go(script(status("RECONNECT_REQUIRED", "failed")))).toBe(
      "RECONNECT_REQUIRED",
    );
    expect(failureMessage("RECONNECT_REQUIRED")).toBe(
      "Google needs to be reconnected for this client. Open Integrations to reconnect.",
    );
  });
  it("reports a failed import with the generic message, never a code", async () => {
    expect(await go(script(status("FAILED", "failed")))).toBe("FAILED");
    expect(failureMessage("FAILED")).toBe(
      "That did not go through. Refresh to see the current state before trying again.",
    );
  });
  it("stops at the time limit with the background message", async () => {
    const fetcher = script();
    const outcome = await go(fetcher, { pollMs: 3000, limitMs: 300000 });
    expect(outcome).toBe("INGEST_STILL_RUNNING");
    expect(fetcher).toHaveBeenCalledTimes(1 + 100);
    expect(failureMessage("INGEST_STILL_RUNNING")).toBe(
      "Still importing in the background. Refresh in a minute.",
    );
  });
  it("returns the failure code when the import cannot be queued", async () => {
    const fetcher = vi.fn<typeof fetch>(async () =>
      json({ error: { code: "AAL2_REQUIRED" } }, 403),
    );
    expect(await go(fetcher)).toEqual({ failure: "AAL2_REQUIRED" });
  });
});
describe("manual review import through the BFF", () => {
  const settings = {
    origin: "https://console.test",
    apiOrigin: "https://api.test",
    supabaseUrl: "https://auth.test",
    supabaseKey: "key",
    csrfSecret: "x".repeat(32),
    local: false,
  };
  const locals = {
    settings,
    userId: org,
    token: "server-only",
    binding: "binding",
    csrf: "",
    correlationId: "ingest-test",
    auth: {} as App.Locals["auth"],
  };
  const path = `organizations/${org}/locations/${loc}/reviews/ingest/`;
  it("forwards the status read to the API", async () => {
    const fetcher = vi.fn<typeof fetch>(async () =>
      json({ run_id: run, run_status: "queued", result: null }),
    );
    const response = await forward(
      new Request(`${settings.origin}/api/${path}${run}/`),
      `${path}${run}/`,
      locals,
      fetcher,
    );
    expect(response.status).toBe(200);
    expect(String(fetcher.mock.calls[0][0])).toBe(
      `https://api.test/api/v1/organizations/${org}/locations/${loc}/reviews/ingest/${run}`,
    );
  });
  it("forwards the Idempotency-Key on the POST and refuses a missing one", async () => {
    const csrf = csrfToken(locals.binding, locals.userId, settings.csrfSecret);
    const post = (headers: Record<string, string>) =>
      new Request(`${settings.origin}/api/${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: settings.origin,
          "X-CSRF-Token": csrf,
          ...headers,
        },
        body: "{}",
      });
    const fetcher = vi.fn<typeof fetch>(async () =>
      json({ run_id: run, run_status: "queued" }, 202),
    );
    const sent = await forward(
      post({ "Idempotency-Key": "import-key-1" }),
      path,
      locals,
      fetcher,
    );
    expect(sent.status).toBe(202);
    expect(
      (fetcher.mock.calls[0][1]?.headers as Record<string, string>)[
        "Idempotency-Key"
      ],
    ).toBe("import-key-1");
    expect((await forward(post({}), path, locals, fetcher)).status).toBe(400);
  });
});
