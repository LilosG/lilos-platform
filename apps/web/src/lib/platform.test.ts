import { describe, expect, it } from "vitest";
import {
  productState,
  requiresStepUp,
  visibleNavigation,
  type WorkspaceState,
} from "./platform";

const state = (overrides: Partial<WorkspaceState> = {}): WorkspaceState => ({
  organizationName: "Test",
  organizationStatus: "active",
  assurance: "aal1",
  permissions: new Set(["organization.read", "seo.read"]),
  entitlements: new Set(["seo"]),
  readyProducts: new Set(["seo"]),
  runtimeBlocks: new Set(),
  ...overrides,
});

describe("authorization-aware workspace", () => {
  it("shows only server-authorized entitled navigation", () =>
    expect(visibleNavigation(state()).map((item) => item.key)).toEqual([
      "overview",
      "seo",
    ]));
  it("does not use entitlement as authorization", () =>
    expect(
      visibleNavigation(
        state({ permissions: new Set(["organization.read"]) }),
      ).map((item) => item.key),
    ).toEqual(["overview"]));
  it("reflects readiness and restrictive runtime controls", () => {
    expect(productState(state(), "seo")).toBe("ready");
    expect(
      productState(state({ runtimeBlocks: new Set(["seo"]) }), "seo"),
    ).toBe("blocked");
    expect(productState(state({ readyProducts: new Set() }), "seo")).toBe(
      "setup",
    );
  });
  it("requires verified aal2 for step-up actions", () => {
    expect(requiresStepUp(state(), "aal2")).toBe(true);
    expect(requiresStepUp(state({ assurance: "aal2" }), "aal2")).toBe(false);
  });
});
