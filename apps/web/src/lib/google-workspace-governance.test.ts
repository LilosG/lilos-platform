import { describe, expect, it, vi } from "vitest";

import {
  confirmGbpMappingAndReconcile,
  discoverGoogleResourcesAndReconcile,
  gbpWriteGovernanceFor,
} from "./google-workspace-governance";
import type { MappedResource } from "./integrations";

function mappedResource(
  overrides: Partial<MappedResource> = {},
): MappedResource {
  return {
    id: "provider-mapping-id",
    external_resource_id: "locations/google-id",
    platform_resource_id: "platform-location-id",
    resource_type: "location",
    status: "active",
    display_name: "Example location",
    last_synced_at: "2026-08-24T12:00:00Z",
    sync_freshness: "fresh",
    gbp_location_id: "gbp-location-id",
    mapping_status: "confirmed",
    write_enabled: false,
    ...overrides,
  };
}

describe("mapped GBP write-governance presentation", () => {
  it("offers enable for an administrator when backend truth is read-only", () => {
    expect(gbpWriteGovernanceFor(mappedResource(), true)).toMatchObject({
      stateLabel: "Read only",
      actionLabel: "Enable provider writes",
      desiredWriteEnabled: true,
    });
  });

  it("offers disable for an administrator when backend truth enables writes", () => {
    expect(
      gbpWriteGovernanceFor(mappedResource({ write_enabled: true }), true),
    ).toMatchObject({
      stateLabel: "Provider writes enabled",
      actionLabel: "Disable provider writes",
      desiredWriteEnabled: false,
    });
  });

  it("shows truthful state without a privileged action to an ordinary user", () => {
    expect(gbpWriteGovernanceFor(mappedResource(), false)).toMatchObject({
      stateLabel: "Read only",
      actionLabel: null,
      confirmationMessage: null,
      desiredWriteEnabled: null,
    });
  });

  it("returns no governance control for an unresolved or unconfirmed mapping", () => {
    expect(
      gbpWriteGovernanceFor(mappedResource({ gbp_location_id: null }), true),
    ).toBeNull();
    expect(
      gbpWriteGovernanceFor(
        mappedResource({ mapping_status: "suggested" }),
        true,
      ),
    ).toBeNull();
  });
});

describe("Google workspace mutation reconciliation", () => {
  it("uses the canonical GBP confirm mutation and reconciles only after success", async () => {
    const reconcile = vi.fn(async () => undefined);
    const confirm = vi.fn(async () => ({
      kind: "ok" as const,
      data: {
        id: "gbp-location-id",
        mapping_status: "confirmed",
        write_enabled: true,
      },
    }));

    await confirmGbpMappingAndReconcile(
      "organization-id",
      "platform-location-id",
      "gbp-location-id",
      true,
      reconcile,
      confirm,
    );

    expect(confirm).toHaveBeenCalledWith(
      "organization-id",
      "platform-location-id",
      "gbp-location-id",
      true,
    );
    expect(reconcile).toHaveBeenCalledOnce();
  });

  it("does not reconcile or invent write state when confirmation fails", async () => {
    const reconcile = vi.fn(async () => undefined);
    const confirm = vi.fn(async () => ({ kind: "forbidden" as const }));

    const result = await confirmGbpMappingAndReconcile(
      "organization-id",
      "platform-location-id",
      "gbp-location-id",
      false,
      reconcile,
      confirm,
    );

    expect(result.kind).toBe("forbidden");
    expect(reconcile).not.toHaveBeenCalled();
  });

  it("re-fetches and re-renders workspace truth after successful discovery", async () => {
    const reconcile = vi.fn(async () => undefined);
    const discover = vi.fn(async () => ({
      kind: "ok" as const,
      data: {
        accounts_discovered: 1,
        locations_discovered: 2,
        profiles_synced: 2,
      },
    }));

    await discoverGoogleResourcesAndReconcile(
      "organization-id",
      reconcile,
      discover,
    );

    expect(discover).toHaveBeenCalledWith("organization-id");
    expect(reconcile).toHaveBeenCalledOnce();
  });
});
