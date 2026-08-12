import { describe, expect, it } from "vitest";
import {
  NOT_EFFECTIVE_ENTITLEMENT_STATUSES,
  OPERATOR_ENTITLEMENT_SOURCE,
  RE_ENABLE_STATUSES,
  SELECTED_ENTITLEMENT_STATUSES,
  describeEntitlementRow,
  entitlementBadgeKind,
  isEffectiveEntitlement,
  isSelectedEntitlement,
} from "./product-entitlements";
import type { ProductEntitlement } from "./platform-admin";

function entitlement(
  overrides: Partial<ProductEntitlement> = {},
): ProductEntitlement {
  return {
    id: "ent-1",
    organization_id: "org-1",
    product_id: "product-gbp",
    status: "setup_required",
    source: OPERATOR_ENTITLEMENT_SOURCE,
    reason: "test",
    effective_from: null,
    effective_until: null,
    activated_at: null,
    archived_at: null,
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("entitlement effectiveness mirrors the backend OAuth gate", () => {
  it("treats setup_required as effective — a setup_required entitlement permits the GBP OAuth connection", () => {
    expect(isEffectiveEntitlement("setup_required")).toBe(true);
    expect(isSelectedEntitlement("setup_required")).toBe(true);
  });

  it("treats not_enabled / archived / suspended as not effective (the backend NOT_EFFECTIVE_ENTITLEMENT_STATUSES frozenset)", () => {
    expect(NOT_EFFECTIVE_ENTITLEMENT_STATUSES.has("not_enabled")).toBe(true);
    expect(NOT_EFFECTIVE_ENTITLEMENT_STATUSES.has("archived")).toBe(true);
    expect(NOT_EFFECTIVE_ENTITLEMENT_STATUSES.has("suspended")).toBe(true);
    expect(isEffectiveEntitlement("not_enabled")).toBe(false);
    expect(isEffectiveEntitlement("archived")).toBe(false);
    expect(isEffectiveEntitlement("suspended")).toBe(false);
    // suspended IS selected (the entitlement row exists; the product is in
    // the portfolio but operationally paused). It is selected AND not effective.
    expect(isSelectedEntitlement("suspended")).toBe(true);
  });

  it("does not invent client-side effective statuses the backend does not recognize", () => {
    // The onboarding read model counts a product as "selected" for every
    // status except not_enabled/archived. SELECTED_ENTILEMENT_STATUSES must
    // mirror that exactly so the UI never claims a product is selected when
    // the backend would say it is not.
    expect(SELECTED_ENTITLEMENT_STATUSES.has("setup_required")).toBe(true);
    expect(SELECTED_ENTITLEMENT_STATUSES.has("configuration_required")).toBe(
      true,
    );
    expect(SELECTED_ENTITLEMENT_STATUSES.has("connection_required")).toBe(true);
    expect(SELECTED_ENTITLEMENT_STATUSES.has("ready")).toBe(true);
    expect(SELECTED_ENTITLEMENT_STATUSES.has("active")).toBe(true);
    expect(SELECTED_ENTITLEMENT_STATUSES.has("paused")).toBe(true);
    expect(SELECTED_ENTITLEMENT_STATUSES.has("degraded")).toBe(true);
    expect(SELECTED_ENTITLEMENT_STATUSES.has("suspended")).toBe(true);
    expect(SELECTED_ENTITLEMENT_STATUSES.has("not_enabled")).toBe(false);
    expect(SELECTED_ENTITLEMENT_STATUSES.has("archived")).toBe(false);
  });
});

describe("describeEntitlementRow", () => {
  it("offers an Enable control only when no entitlement row exists", () => {
    const row = describeEntitlementRow("gbp", null);
    expect(row.canEnable).toBe(true);
    expect(row.canReEnable).toBe(false);
    expect(row.effective).toBe(false);
    expect(row.selected).toBe(false);
    expect(row.entitlement).toBeNull();
    expect(row.productKey).toBe("gbp");
  });

  it("never offers Enable once an entitlement exists — recreation is the backend's job to reject, the UI's job to never attempt", () => {
    for (const status of [
      "setup_required",
      "configuration_required",
      "connection_required",
      "ready",
      "active",
      "paused",
      "degraded",
      "not_enabled",
      "suspended",
      "archived",
    ] as const) {
      const row = describeEntitlementRow("gbp", entitlement({ status }));
      expect(row.canEnable, `status=${status}`).toBe(false);
    }
  });

  it("offers Restore only for not_enabled/suspended — archived is terminal and must not be silently reactivated", () => {
    expect(RE_ENABLE_STATUSES.has("not_enabled")).toBe(true);
    expect(RE_ENABLE_STATUSES.has("suspended")).toBe(true);
    expect(RE_ENABLE_STATUSES.has("archived")).toBe(false);
    expect(RE_ENABLE_STATUSES.has("setup_required")).toBe(false);

    expect(
      describeEntitlementRow("gbp", entitlement({ status: "not_enabled" }))
        .canReEnable,
    ).toBe(true);
    expect(
      describeEntitlementRow("gbp", entitlement({ status: "suspended" }))
        .canReEnable,
    ).toBe(true);
    expect(
      describeEntitlementRow("gbp", entitlement({ status: "archived" }))
        .canReEnable,
    ).toBe(false);
    expect(
      describeEntitlementRow("gbp", entitlement({ status: "setup_required" }))
        .canReEnable,
    ).toBe(false);
  });

  it("reports an existing setup_required entitlement as selected and effective", () => {
    const row = describeEntitlementRow(
      "gbp",
      entitlement({ status: "setup_required" }),
    );
    expect(row.selected).toBe(true);
    expect(row.effective).toBe(true);
  });
});

describe("entitlementBadgeKind", () => {
  it("maps lifecycle states to truthful badge kinds, never inventing 'ready' for setup_required", () => {
    expect(entitlementBadgeKind("active")).toBe("ready");
    expect(entitlementBadgeKind("ready")).toBe("ready");
    expect(entitlementBadgeKind("paused")).toBe("degraded");
    expect(entitlementBadgeKind("degraded")).toBe("degraded");
    expect(entitlementBadgeKind("not_enabled")).toBe("blocked");
    expect(entitlementBadgeKind("archived")).toBe("blocked");
    expect(entitlementBadgeKind("suspended")).toBe("blocked");
    expect(entitlementBadgeKind("setup_required")).toBe("setup");
    expect(entitlementBadgeKind("configuration_required")).toBe("setup");
    expect(entitlementBadgeKind("connection_required")).toBe("setup");
  });
});
