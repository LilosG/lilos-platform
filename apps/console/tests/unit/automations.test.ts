import { describe, it, expect, vi } from "vitest";
import fixture from "../fixtures/phase6.json";
import {
  adaptAutomations,
  adaptAutomationDetail,
} from "../../src/adapters/automations";
import { forward } from "../../src/server/bff";
import { csrfToken } from "../../src/server/security";
const org = fixture.workspace.organization_id;
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
  correlationId: "phase6-test",
  auth: {} as App.Locals["auth"],
};
it("preserves schedules, raw run states, partial/unavailable and unconfirmed provider outcomes", () => {
  const v = adaptAutomations(fixture.workspace, org);
  expect(v.runs.map((r) => r.status)).toEqual([
    "failed",
    "queued",
    "running",
    "completed",
    "partially_completed",
    "waiting",
    "running",
  ]);
  expect(v.schedules.map((s) => s.status)).toEqual(["active", "paused"]);
  expect(v.definitions[1].definition_status).toBe("disabled");
  expect(v.outcomes[0].outcome).toBe("recorded_result");
  expect(v.runtime_health).toBe("unavailable_no_scoped_heartbeat");
  expect(
    adaptAutomations(
      {
        ...fixture.workspace,
        schedules: [],
        schedules_state: "unavailable_permission",
      },
      org,
    ).schedules_state,
  ).toBe("unavailable_permission");
  expect(
    adaptAutomationDetail(fixture.detail, org, fixture.detail.run.id).recovery,
  ).toBe("domain_controls_only");
});
it("rejects wrong tenant/run/location/job and fabricated completed outcomes", () => {
  expect(() =>
    adaptAutomations(fixture.workspace, fixture.detail.run.id),
  ).toThrow();
  expect(() => adaptAutomations(fixture.workspace, org, org)).toThrow();
  expect(() =>
    adaptAutomations(
      { ...fixture.workspace, outcomes: [fixture.workspace.runs[1]] },
      org,
    ),
  ).toThrow();
  expect(() => adaptAutomationDetail(fixture.detail, org, org)).toThrow();
  expect(() =>
    adaptAutomationDetail(
      { ...fixture.detail, jobs: [] },
      org,
      fixture.detail.run.id,
    ),
  ).toThrow();
});
describe("Automations closed BFF", () => {
  it("rejects unsupported retries, arbitrary workflow launch, unknown queries, anonymous reads", async () => {
    for (const suffix of [
      "workflows/runs/" + fixture.detail.run.id + "/retry/",
      "workflows/content.publish/runs/",
      "workflows/monthly.report/runs/",
    ]) {
      expect(
        (
          await forward(
            new Request(settings.origin),
            `organizations/${org}/${suffix}`,
            locals,
          )
        ).status,
      ).toBe(404);
    }
    const path = `organizations/${org}/command-center/automations/`;
    for (const q of [
      "location_id=bad",
      "offset=-1",
      "url=https://evil.test",
      "status=completed",
    ]) {
      const fetcher = vi.fn<typeof fetch>();
      expect(
        (
          await forward(
            new Request(settings.origin + "/api/" + path + "?" + q),
            path,
            locals,
            fetcher,
          )
        ).status,
      ).toBe(400);
      expect(fetcher).not.toHaveBeenCalled();
    }
    expect(
      (
        await forward(new Request(settings.origin + "/api/" + path), path, {
          ...locals,
          token: null,
        })
      ).status,
    ).toBe(401);
  });
  it("PATCH requires exact origin, bound CSRF and strict body; server Bearer/correlation/private cache survive", async () => {
    const path = `organizations/${org}/workflows/schedules/${fixture.workspace.schedules[0].id}/`;
    const csrf = csrfToken(locals.binding, locals.userId, settings.csrfSecret);
    const request = (body: unknown, origin = settings.origin, nonce = csrf) =>
      new Request(settings.origin + "/api/" + path, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Origin: origin,
          "X-CSRF-Token": nonce,
        },
        body: JSON.stringify(body),
      });
    for (const req of [
      request({ status: "paused" }, "https://foreign.test"),
      request({ status: "paused" }, settings.origin, "bad"),
      request({ status: "paused", next_run_at: "invented" }),
    ]) {
      const f = vi.fn<typeof fetch>();
      expect(
        (await forward(req, path, locals, f)).status,
      ).toBeGreaterThanOrEqual(400);
      expect(f).not.toHaveBeenCalled();
    }
    const f = vi.fn<typeof fetch>().mockResolvedValue(
      new Response("{}", {
        headers: {
          "Content-Type": "application/json",
          "Set-Cookie": "unsafe=1",
        },
      }),
    );
    const response = await forward(
      request({ status: "paused" }),
      path,
      locals,
      f,
    );
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("private, no-store");
    expect(response.headers.get("set-cookie")).toBeNull();
    expect(f.mock.calls[0][1]?.method).toBe("PATCH");
    expect(f.mock.calls[0][1]?.body).toBe('{"status":"paused"}');
    expect(f.mock.calls[0][1]?.headers).toMatchObject({
      Authorization: "Bearer server-only",
      "X-Correlation-ID": "phase6-test",
    });
  });
  it("permits only exact canonical standalone execution and agent controls", async () => {
    const path = `organizations/${org}/workflows/gbp.sync/runs/`;
    const csrf = csrfToken(locals.binding, locals.userId, settings.csrfSecret);
    const req = (body: unknown) =>
      new Request(settings.origin + "/api/" + path, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Origin: settings.origin,
          "X-CSRF-Token": csrf,
        },
        body: JSON.stringify(body),
      });
    const f = vi.fn<typeof fetch>().mockResolvedValue(
      new Response('{"data":{"status":"queued"}}', {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(
      (
        await forward(
          req({
            execute: true,
            input_document: {},
            idempotency_key: "canonical-key",
          }),
          path,
          locals,
          f,
        )
      ).status,
    ).toBe(201);
    expect(
      (
        await forward(
          req({
            execute: true,
            input_document: { provider_id: "forged" },
            idempotency_key: "canonical-key",
          }),
          path,
          locals,
          f,
        )
      ).status,
    ).toBe(400);
  });
});
