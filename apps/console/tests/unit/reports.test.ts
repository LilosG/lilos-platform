import { expect, it, vi } from "vitest";
import fixture from "../fixtures/phase7.json";
import { adaptReports } from "../../src/adapters/reports";
import { forward } from "../../src/server/bff";

const org = fixture.organization_id;
const settings = {
  origin: "https://console.test",
  apiOrigin: "https://api.test",
  supabaseUrl: "https://auth.test",
  supabaseKey: "key",
  csrfSecret: "x".repeat(32),
  local: false,
};
const locals = {
  settings, userId: org, token: "server-only", binding: "binding",
  csrf: "", correlationId: "phase7-test", auth: {} as App.Locals["auth"],
};
const path = `organizations/${org}/command-center/reports/`;

it("preserves backend readiness, quality, generation, blockers and history", () => {
  const view = adaptReports({ data: fixture }, org);
  expect(view.reports.map((r) => r.readiness)).toEqual([
    "ready", "not_ready", "not_ready", "not_ready", "not_ready",
  ]);
  expect(view.reports.map((r) => r.data_state)).toEqual([
    "ready", "missing", "stale", "partial", "unavailable",
  ]);
  expect(view.reports.map((r) => r.generation)).toEqual([
    "sent", "queued", "generating", "failed", "unavailable",
  ]);
  expect(view.reports[0].deliveries[0].status).toBe("sent");
  expect(view.reports[1].blockers[0].code).toBe("DATA_MISSING");
  expect(view.schedule_state).toBe("unavailable_no_canonical_report_schedule");
});

it("rejects wrong tenant and malformed or invented readiness", () => {
  expect(() => adaptReports({ data: fixture }, fixture.reports[0].id)).toThrow();
  expect(() => adaptReports({
    data: { ...fixture, reports: [{ ...fixture.reports[1], readiness: "guessed" }] },
  }, org)).toThrow();
  expect(() => adaptReports({
    data: { ...fixture, reports: [{ ...fixture.reports[1], blockers: [{ code: "FREE_TEXT", metric_id: null }] }] },
  }, org)).toThrow();
});

it("keeps Reports on an exact read-only, authenticated BFF route", async () => {
  const fetcher = vi.fn<typeof fetch>(async () => new Response(JSON.stringify({ data: fixture }), {
    headers: { "content-type": "application/json" },
  }));
  const request = new Request(settings.origin + "/api/" + path);
  const response = await forward(request, path, locals, fetcher);
  expect(response.status).toBe(200);
  expect(response.headers.get("cache-control")).toContain("no-store");
  expect(fetcher).toHaveBeenCalledOnce();
  expect(fetcher.mock.calls[0][0]).toBe(settings.apiOrigin + "/api/v1/" + path.slice(0, -1));
  for (const bad of ["?org=" + fixture.reports[0].id, "?url=https://evil.test"]) {
    expect((await forward(new Request(request.url + bad), path, locals, fetcher)).status).toBe(400);
  }
  expect((await forward(request, path, { ...locals, token: null })).status).toBe(401);
  expect((await forward(new Request(request.url, { method: "POST" }), path, locals)).status).toBe(405);
  expect((await forward(request, path + "generate/", locals)).status).toBe(404);
});
