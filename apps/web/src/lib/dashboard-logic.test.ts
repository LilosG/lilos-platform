import { describe, expect, it } from "vitest";
import {
  selectDefaultOrganization,
  summarizeReadiness,
} from "./dashboard-logic";
import type { MyOrganization, ProductReadiness } from "./workspace";

const organization = (
  overrides: Partial<MyOrganization> = {},
): MyOrganization => ({
  organization_id: "org-1",
  organization_name: "Example Org",
  organization_slug: "example-org",
  organization_status: "active",
  membership_id: "membership-1",
  membership_status: "active",
  membership_type: "client",
  ...overrides,
});

describe("selectDefaultOrganization", () => {
  it("returns null for an empty list rather than a fabricated organization", () => {
    expect(selectDefaultOrganization([])).toBeNull();
  });

  it("prefers an active membership over an earlier non-active one", () => {
    const invited = organization({
      organization_id: "org-invited",
      membership_status: "invited",
    });
    const active = organization({
      organization_id: "org-active",
      membership_status: "active",
    });
    expect(selectDefaultOrganization([invited, active])?.organization_id).toBe(
      "org-active",
    );
  });

  it("falls back to the first membership when none are active", () => {
    const suspended = organization({ membership_status: "suspended" });
    expect(selectDefaultOrganization([suspended])).toEqual(suspended);
  });
});

const readiness = (
  overrides: Partial<ProductReadiness> = {},
): ProductReadiness => ({
  ready: true,
  readiness_state: "ready",
  product_key: "seo",
  blocking_requirements: [],
  warnings: [],
  ...overrides,
});

describe("summarizeReadiness", () => {
  it("reports ready with no blocking requirement", () => {
    expect(summarizeReadiness({ kind: "ok", data: readiness() })).toEqual({
      status: "ready",
      detail: "Ready.",
    });
  });

  it("maps not_entitled to setup and surfaces the first blocking remediation", () => {
    const outcome = summarizeReadiness({
      kind: "ok",
      data: readiness({
        readiness_state: "not_entitled",
        blocking_requirements: [
          {
            code: "ENTITLEMENT_NOT_EFFECTIVE",
            blocking: true,
            resource_key: "seo",
            remediation: "Create an entitlement.",
          },
        ],
      }),
    });
    expect(outcome).toEqual({
      status: "setup",
      detail: "Create an entitlement.",
    });
  });

  it("never fabricates a ready/blocked state for non-ok outcomes", () => {
    expect(summarizeReadiness({ kind: "forbidden" }).status).toBe("missing");
    expect(summarizeReadiness({ kind: "not-found" }).status).toBe("missing");
    expect(summarizeReadiness({ kind: "disconnected" }).status).toBe("missing");
    expect(summarizeReadiness({ kind: "unauthenticated" }).status).toBe(
      "missing",
    );
    expect(summarizeReadiness({ kind: "not-configured" }).status).toBe(
      "missing",
    );
    expect(
      summarizeReadiness({
        kind: "error",
        status: 500,
        code: "X",
        message: "Server error.",
      }),
    ).toEqual({ status: "missing", detail: "Server error." });
  });
});
