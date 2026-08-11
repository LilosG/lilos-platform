import { describe, expect, it } from "vitest";
import {
  describeGbpConnectFailure,
  googleAuthorizationAction,
  missingGoogleProducts,
} from "./gbp-connection";
import type { ApiOutcome } from "./api-client";

const genericError: ApiOutcome<unknown> = {
  kind: "error",
  status: 409,
  code: "RESOURCE_CONFLICT",
  message: "The request conflicts with the current resource state.",
  details: [],
};

const productNotReady: ApiOutcome<unknown> = {
  kind: "error",
  status: 409,
  code: "PRODUCT_NOT_READY",
  message: "The request conflicts with the current resource state.",
  details: [],
};

describe("describeGbpConnectFailure — /gbp actionable error regression", () => {
  it("converts the PRODUCT_NOT_READY 409 into the specific actionable message, not the generic resource-conflict string", () => {
    const description = describeGbpConnectFailure(productNotReady, "org-123");
    expect(description.kind).toBe("product_not_ready");
    expect(description.message).toBe(
      "Google Business Profile is not enabled for this client. Enable it in Client Onboarding before connecting Google.",
    );
    // The actionable link points at the onboarding surface for the SAME
    // organization, so an operator can resolve it without a shell or a
    // manually-entered id.
    expect(description.onboardingHref).toBe("/onboarding?org=org-123");
  });

  it("escapes the organization id into the onboarding href", () => {
    const description = describeGbpConnectFailure(
      productNotReady,
      "org/with spaces",
    );
    expect(description.onboardingHref).toBe(
      "/onboarding?org=org%2Fwith%20spaces",
    );
  });

  it("falls back to a generic, truthful message for other 409 conflict codes (does not pretend PRODUCT_NOT_READY)", () => {
    const description = describeGbpConnectFailure(genericError, "org-1");
    expect(description.kind).toBe("generic");
    expect(description.onboardingHref).toBeNull();
    // The generic message must not be the actionable PRODUCT_NOT_READY one.
    expect(description.message).not.toContain("Client Onboarding");
  });

  it("classifies disconnected/not-configured/unauthenticated truthfully, not as PRODUCT_NOT_READY", () => {
    expect(
      describeGbpConnectFailure({ kind: "disconnected" }, "org-1").kind,
    ).toBe("generic");
    expect(
      describeGbpConnectFailure({ kind: "not-configured" }, "org-1").kind,
    ).toBe("generic");
    expect(
      describeGbpConnectFailure({ kind: "unauthenticated" }, "org-1").kind,
    ).toBe("generic");
    expect(describeGbpConnectFailure({ kind: "forbidden" }, "org-1").kind).toBe(
      "generic",
    );
  });

  it("never fabricates a success state from a failure outcome", () => {
    // A non-ok outcome must never be classified as actionable-ready; the
    // backend OAuth-requires-an-effective-entitlement rule is not weakened
    // by the frontend classifier.
    const ok: ApiOutcome<unknown> = {
      kind: "ok",
      data: { authorization_url: "x" },
    };
    expect(describeGbpConnectFailure(ok, "org-1").kind).toBe("generic");
    expect(describeGbpConnectFailure(ok, "org-1").message).toBe("");
  });
});

describe("Google product authorization", () => {
  it("identifies only the services not present on an existing connection", () => {
    expect(
      missingGoogleProducts({
        gbp: true,
        search_console: false,
        analytics: false,
      }),
    ).toEqual(["search_console", "analytics"]);
  });

  it("identifies no missing products for a fully-scoped connection", () => {
    expect(
      missingGoogleProducts({
        gbp: true,
        search_console: true,
        analytics: true,
      }),
    ).toEqual([]);
  });

  it("requests all approved services for a new connection", () => {
    expect(missingGoogleProducts(undefined)).toEqual([
      "gbp",
      "search_console",
      "analytics",
    ]);
  });

  it("uses credential reconnect even when the connection is fully scoped", () => {
    expect(
      googleAuthorizationAction({
        status: "reconnect_required",
        token_expires_at: null,
        last_verified_at: null,
        services: { gbp: true, search_console: true, analytics: true },
      }),
    ).toEqual({ kind: "reconnect" });
  });

  it("offers no OAuth action for a healthy fully-scoped connection", () => {
    expect(
      googleAuthorizationAction({
        status: "connected",
        token_expires_at: null,
        last_verified_at: null,
        services: { gbp: true, search_console: true, analytics: true },
      }),
    ).toEqual({ kind: "none" });
  });

  it("offers only genuinely missing services for incremental authorization", () => {
    expect(
      googleAuthorizationAction({
        status: "connected",
        token_expires_at: null,
        last_verified_at: null,
        services: { gbp: true, search_console: false, analytics: true },
      }),
    ).toEqual({
      kind: "authorize_missing",
      products: ["search_console"],
    });
  });
});
