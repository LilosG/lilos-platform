import { afterEach, describe, expect, expectTypeOf, it, vi } from "vitest";

vi.mock("./config", () => ({ readPublicConfig: vi.fn() }));
vi.mock("./session", () => ({
  getAccessToken: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

import { readPublicConfig } from "./config";
import { getAccessToken } from "./session";
import type { ApiOutcome } from "./api-client";
import {
  fetchIndustries,
  fetchOrganizationDomains,
  fetchOrganizationLocations,
  fetchOrganizations,
  provisionOrganizationWebsite,
  type AdminOrganization,
  type IndustriesResponse,
  type OrganizationDomain,
  type PaginatedLocations,
  type PaginatedOrganizations,
} from "./platform-admin";

const config = {
  apiBaseUrl: "https://api.lilos.invalid",
  supabaseUrl: "x",
  supabaseAnonKey: "y",
};

afterEach(() => {
  vi.restoreAllMocks();
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200 });
}

// Type-level regression for the configured API payload contract.
//
// The platform-admin list endpoints return `{ data: { items, ... }, meta }`,
// NOT a bare array. The shared client must expose that truthful shape to
// callers. Against the previous broken contract — typed as
// `ApiOutcome<Industry[]>` / `ApiOutcome<AdminOrganization[]>` /
// `ApiOutcome<AdminLocation[]>` — these `expectTypeOf` assertions are
// *compile-time errors*: the very contract mismatch that produced
// `data.map is not a function` on /administration and /onboarding in
// production. Domains remain a bare array (the backend returns `data: [...]`
// for that one endpoint, with no pagination).
expectTypeOf<ReturnType<typeof fetchIndustries>>().toEqualTypeOf<
  Promise<ApiOutcome<IndustriesResponse>>
>();
expectTypeOf<ReturnType<typeof fetchOrganizations>>().toEqualTypeOf<
  Promise<ApiOutcome<PaginatedOrganizations>>
>();
expectTypeOf<ReturnType<typeof fetchOrganizationLocations>>().toEqualTypeOf<
  Promise<ApiOutcome<PaginatedLocations>>
>();
expectTypeOf<ReturnType<typeof fetchOrganizationDomains>>().toEqualTypeOf<
  Promise<ApiOutcome<OrganizationDomain[]>>
>();

describe("platform-admin list endpoints consume the REAL configured API payload shapes", () => {
  it("fetchIndustries exposes {items:[...]} from the real {data:{items}, meta} envelope and supports the corrected consumer pattern (.data.items.map)", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        data: { items: [{ id: "ind-1", key: "hvac", name: "HVAC" }] },
        meta: { correlation_id: "c-1" },
      }),
    );

    const outcome = await fetchIndustries();

    expect(fetchSpy).toHaveBeenCalledWith(
      "https://api.lilos.invalid/api/v1/platform/industries",
      expect.anything(),
    );
    expect(outcome).toEqual({
      kind: "ok",
      data: { items: [{ id: "ind-1", key: "hvac", name: "HVAC" }] },
    });
    // The corrected pattern Administration/Onboarding now use. Against the
    // previous broken contract this threw `data.map is not a function`.
    expect(
      outcome.kind === "ok" && outcome.data.items.map((i) => i.name),
    ).toEqual(["HVAC"]);
  });

  it("fetchOrganizations exposes the paginated {items, limit, offset, next_offset, has_more} shape", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        data: {
          items: [
            {
              id: "org-1",
              name: "Acme",
              slug: "acme",
              organization_type: "client",
              status: "active",
              timezone: "UTC",
              default_currency: "USD",
              version: 1,
            },
          ],
          limit: 50,
          offset: 0,
          next_offset: null,
          has_more: false,
        },
        meta: { correlation_id: "c-2" },
      }),
    );

    const outcome = await fetchOrganizations();

    expect(outcome.kind).toBe("ok");
    if (outcome.kind !== "ok") return;
    expect(outcome.data.items).toHaveLength(1);
    expect(outcome.data.has_more).toBe(false);
    expect(outcome.data.next_offset).toBeNull();
    expect(outcome.data.items.map((o: AdminOrganization) => o.name)).toEqual([
      "Acme",
    ]);
  });

  it("fetchOrganizationLocations exposes the paginated locations shape and targets the org-scoped path", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        data: {
          items: [
            {
              id: "loc-1",
              organization_id: "org-1",
              name: "HQ",
              slug: "hq",
              location_type: "physical",
              status: "active",
              timezone: "UTC",
              is_primary: true,
              version: 1,
            },
          ],
          limit: 50,
          offset: 0,
          next_offset: 50,
          has_more: true,
        },
        meta: { correlation_id: "c-3" },
      }),
    );

    const outcome = await fetchOrganizationLocations("org-1");

    expect(fetchSpy).toHaveBeenCalledWith(
      "https://api.lilos.invalid/api/v1/platform/organizations/org-1/locations",
      expect.anything(),
    );
    expect(outcome.kind).toBe("ok");
    if (outcome.kind !== "ok") return;
    expect(outcome.data.items).toHaveLength(1);
    expect(outcome.data.has_more).toBe(true);
    expect(outcome.data.next_offset).toBe(50);
  });

  it("fetchOrganizationDomains remains a bare array — the backend returns data: [...], not paginated items, so this contract is intentionally NOT changed", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        data: [
          {
            id: "dom-1",
            organization_id: "org-1",
            domain: "example.com",
            is_primary: true,
            status: "active",
            version: 1,
          },
        ],
        meta: { correlation_id: "c-4" },
      }),
    );

    const outcome = await fetchOrganizationDomains("org-1");

    expect(outcome.kind).toBe("ok");
    if (outcome.kind !== "ok") return;
    expect(Array.isArray(outcome.data)).toBe(true);
    expect(outcome.data).toHaveLength(1);
  });
});

describe("website provisioning uses the endpoint the operator's grant satisfies", () => {
  it("posts to the platform route, not the organization route", async () => {
    // The organization route authorizes on org RBAC
    // ("organization.settings.manage"), which an agency operator holding only
    // a platform-administrator grant does not have. Sending this write there
    // would replace a hidden control with a refused one.
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        data: {
          website_id: "web-1",
          canonical_origin: "https://example.com",
          website_created: true,
          crawl_run_id: "crawl-1",
          crawl_enqueued: true,
          skipped_reason: null,
        },
        meta: { correlation_id: "c-1" },
      }),
    );

    const outcome = await provisionOrganizationWebsite("org-1");

    expect(fetchSpy).toHaveBeenCalledWith(
      "https://api.lilos.invalid/api/v1/platform/organizations/org-1/provision-website",
      expect.objectContaining({ method: "POST" }),
    );
    expect(outcome.kind === "ok" && outcome.data.crawl_enqueued).toBe(true);
    expect(outcome.kind === "ok" && outcome.data.canonical_origin).toBe(
      "https://example.com",
    );
  });

  it("surfaces a refusal rather than reporting a silent success", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "NO_PRIMARY_DOMAIN",
            message:
              "This client has no active primary domain, so there is no website to provision. Add the domain and mark it primary first.",
            category: "conflict",
          },
        }),
        { status: 409 },
      ),
    );

    const outcome = await provisionOrganizationWebsite("org-1");
    expect(outcome.kind).not.toBe("ok");
  });
});
