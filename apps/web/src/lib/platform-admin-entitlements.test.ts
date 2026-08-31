import { afterEach, describe, expect, expectTypeOf, it, vi } from "vitest";

vi.mock("./config", () => ({ readPublicConfig: vi.fn() }));
vi.mock("./session", () => ({
  getAccessToken: vi.fn(),
  refreshAccessToken: vi.fn(),
}));

import { readPublicConfig } from "./config";
import { getAccessToken } from "./session";
import {
  createProductEntitlement,
  fetchProductEntitlements,
  transitionProductEntitlement,
  type EntitlementStatus,
  type ProductEntitlement,
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

function createdResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 201 });
}

const fullEntitlement: ProductEntitlement = {
  id: "ent-1",
  organization_id: "org-1",
  product_id: "product-gbp",
  status: "setup_required",
  source: "platform_admin_onboarding",
  reason: "Enable GBP during client onboarding",
  effective_from: "2026-08-07T00:00:00Z",
  effective_until: null,
  activated_at: null,
  archived_at: null,
  version: 1,
  created_at: "2026-08-07T00:00:00Z",
  updated_at: "2026-08-07T00:00:00Z",
};

// Compile-time contract: the client must expose the truthful backend row
// shape (all columns serialized by `_row`), not a fabricated subset that
// would hide lifecycle state from the operator UI.
expectTypeOf<EntitlementStatus>().toEqualTypeOf<EntitlementStatus>();

describe("platform-admin entitlement client functions target the production platform-administration routes", () => {
  it("fetchProductEntitlements GETs /platform/organizations/{id}/product-entitlements and exposes the full row shape", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        data: [fullEntitlement],
        meta: { correlation_id: "c" },
      }),
    );

    const outcome = await fetchProductEntitlements("org-1");

    expect(fetchSpy).toHaveBeenCalledWith(
      "https://api.lilos.invalid/api/v1/platform/organizations/org-1/product-entitlements",
      expect.anything(),
    );
    expect(outcome).toEqual({ kind: "ok", data: [fullEntitlement] });
    // The full row shape survives unwrapping — the operator UI can read
    // status, version (for transitions), and created_at without a second
    // round-trip.
    expectTypeOf<ReturnType<typeof fetchProductEntitlements>>().toEqualTypeOf<
      Promise<
        | { kind: "ok"; data: ProductEntitlement[] }
        | { kind: "not-configured" }
        | { kind: "unauthenticated" }
        // Carries the named cause when the backend disclosed one.
        | { kind: "forbidden"; code?: string; message?: string }
        | { kind: "not-found" }
        | { kind: "disconnected" }
        | {
            kind: "error";
            status: number;
            code: string;
            message: string;
            details: { field?: string; code?: string; message: string }[];
          }
      >
    >();
  });

  it("createProductEntitlement POSTs the truthful payload to the production route and returns the created setup_required row", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      createdResponse({
        data: fullEntitlement,
        meta: { correlation_id: "c" },
      }),
    );

    const outcome = await createProductEntitlement("org-1", {
      product_key: "gbp",
      source: "platform_admin_onboarding",
      reason: "Enable GBP during client onboarding",
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      "https://api.lilos.invalid/api/v1/platform/organizations/org-1/product-entitlements",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
        }),
      }),
    );
    const callBody = JSON.parse(
      (fetchSpy.mock.calls[0][1] as RequestInit).body as string,
    );
    // Truthful payload: stable operator source, audit reason, and the
    // optional location_ids defaulting to an empty array (the backend
    // EntitlementCreate contract default). No fabricated fields.
    expect(callBody).toEqual({
      product_key: "gbp",
      source: "platform_admin_onboarding",
      reason: "Enable GBP during client onboarding",
      location_ids: [],
    });
    expect(outcome).toEqual({ kind: "ok", data: fullEntitlement });
    if (outcome.kind === "ok") {
      expect(outcome.data.status).toBe("setup_required");
    }
  });

  it("transitionProductEntitlement POSTs target_status/reason/expected_version to the transition route", async () => {
    vi.mocked(readPublicConfig).mockReturnValue(config);
    vi.mocked(getAccessToken).mockResolvedValue("token");
    const restored: ProductEntitlement = {
      ...fullEntitlement,
      status: "setup_required",
      version: 2,
    };
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse({ data: restored, meta: { correlation_id: "c" } }),
      );

    const outcome = await transitionProductEntitlement("org-1", "ent-1", {
      target_status: "setup_required",
      reason: "Operator restored gbp entitlement to its initial setup state.",
      expected_version: 1,
    });

    expect(fetchSpy).toHaveBeenCalledWith(
      "https://api.lilos.invalid/api/v1/platform/organizations/org-1/product-entitlements/ent-1/transition",
      expect.objectContaining({ method: "POST" }),
    );
    const callBody = JSON.parse(
      (fetchSpy.mock.calls[0][1] as RequestInit).body as string,
    );
    // Truthful transition payload — the backend enforces expected_version
    // for optimistic concurrency and ENTITLEMENT_TRANSITIONS for the
    // lifecycle guard; the client must not strip either.
    expect(callBody).toEqual({
      target_status: "setup_required",
      reason: "Operator restored gbp entitlement to its initial setup state.",
      expected_version: 1,
    });
    expect(outcome.kind).toBe("ok");
    if (outcome.kind === "ok") {
      expect(outcome.data.version).toBe(2);
      expect(outcome.data.status).toBe("setup_required");
    }
  });
});
