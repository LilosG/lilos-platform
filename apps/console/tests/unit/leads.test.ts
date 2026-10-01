import { describe, expect, it, vi } from "vitest";
import fixture from "../fixtures/phase5.json";
import {
  adaptLeads,
  adaptLeadDetail,
  leadMetric,
  outcomeLabel,
} from "../../src/adapters/leads";
import { forward } from "../../src/server/bff";
import { csrfToken } from "../../src/server/security";
const org = fixture.workspace.organization_id,
  id = fixture.detail.lead.id;
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
  correlationId: "leads-test",
  auth: {} as App.Locals["auth"],
};
describe("Leads source and outcome truth", () => {
  it("preserves true zero, unavailable, missing attribution and stale/partial identity", () => {
    const v = adaptLeads(fixture.workspace, org);
    expect(v.recorded_conversions).toBe(0);
    expect(v.sources[0].provider).toBe("synthetic_test_provider");
    expect(v.sources[0].intake_recency).toBe("stale");
    expect(v.sources[0].quality).toBe("partial");
    expect(v.sources[0].connection_status).toBe("reconnect_required");
    expect(leadMetric(null)).toBe("Unavailable");
    expect(leadMetric(0)).toBe("0");
    expect(
      adaptLeads(
        {
          ...fixture.workspace,
          sources: [],
          items: [],
          inventory_count: null,
          recorded_conversions: null,
          quality: "unavailable",
        },
        org,
      ).inventory_count,
    ).toBeNull();
    expect(v.items[0].attribution).toBe(
      "source_identity_only_no_campaign_or_landing_page",
    );
  });
  it("preserves unknown outcome, operator conversion and unconfirmed delivery", () => {
    const v = adaptLeadDetail(fixture.detail, org, id);
    expect(outcomeLabel(v.lead.outcome)).toBe("Unknown outcome");
    expect(v.communications[0].workflow_status).toBe("queued");
    expect(v.communications[0].delivered_at).toBeNull();
    expect(v.downstream_outcomes).toBe(
      "unavailable_no_booking_sales_jobs_or_revenue_source",
    );
    const converted = adaptLeadDetail(
      {
        ...fixture.detail,
        lead: {
          ...fixture.detail.lead,
          outcome: "recorded_conversion",
          converted_at: "2026-10-01T00:00:00Z",
        },
      },
      org,
      id,
    );
    expect(converted.lead.converted_value_cents).toBeNull();
  });
  it("rejects wrong tenant, lead, source, location and fabricated outcome", () => {
    expect(() => adaptLeads(fixture.workspace, id)).toThrow();
    expect(() => adaptLeads(fixture.workspace, org, id)).toThrow();
    expect(() => adaptLeadDetail(fixture.detail, org, org)).toThrow();
    expect(() =>
      adaptLeadDetail(
        { ...fixture.detail, source: { ...fixture.detail.source, id: org } },
        org,
        id,
      ),
    ).toThrow();
    expect(() =>
      adaptLeadDetail(
        {
          ...fixture.detail,
          lead: { ...fixture.detail.lead, outcome: "booked_job" },
        },
        org,
        id,
      ),
    ).toThrow();
  });
});
describe("Leads closed BFF", () => {
  it("rejects open queries, bad scope, unauthenticated access and source secret routes", async () => {
    const path = `organizations/${org}/command-center/leads/`;
    for (const query of [
      "location_id=bad",
      `location_id=${id}&location_id=${id}`,
      "source_id=bad",
      "offset=-1",
      "url=https://evil.test",
    ]) {
      const fetcher = vi.fn<typeof fetch>();
      expect(
        (
          await forward(
            new Request(settings.origin + "/api/" + path + "?" + query),
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
    for (const suffix of ["sources", `sources/${id}/rotate-secret`, "intake"])
      expect(
        (
          await forward(
            new Request(settings.origin),
            `organizations/${org}/leads/${suffix}/`,
            locals,
          )
        ).status,
      ).toBe(404);
  });
  it("forwards only canonical action bodies with bound CSRF, exact origin and private cache", async () => {
    const path = `organizations/${org}/leads/${id}/communications/`;
    const body = {
      channel: "email",
      consent_type: "transactional_email",
      message_reference: "canonical-message",
      idempotency_key: "canonical-key",
    };
    const headers = {
      "Content-Type": "application/json",
      Origin: settings.origin,
      "X-CSRF-Token": csrfToken(
        locals.binding,
        locals.userId,
        settings.csrfSecret,
      ),
    };
    const fetcher = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify({ data: { status: "planned" } }), {
          headers: { "Content-Type": "application/json" },
        }),
    );
    const request = (data: unknown, overrides = {}) =>
      new Request(settings.origin + "/api/" + path, {
        method: "POST",
        headers: { ...headers, ...overrides },
        body: JSON.stringify(data),
      });
    expect(
      (
        await forward(
          request({ ...body, workflow_run_id: org }),
          path,
          locals,
          fetcher,
        )
      ).status,
    ).toBe(400);
    expect(
      (
        await forward(
          request(body, { Origin: "https://evil.test" }),
          path,
          locals,
          fetcher,
        )
      ).status,
    ).toBe(403);
    expect(
      (
        await forward(
          request(body, { "X-CSRF-Token": "forged" }),
          path,
          locals,
          fetcher,
        )
      ).status,
    ).toBe(403);
    expect(fetcher).not.toHaveBeenCalled();
    const result = await forward(request(body), path, locals, fetcher);
    expect(result.status).toBe(200);
    expect(result.headers.get("cache-control")).toBe("private, no-store");
    expect(JSON.parse(fetcher.mock.calls[0][1]!.body as string)).toEqual(body);
  });
});
