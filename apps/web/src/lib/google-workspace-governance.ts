import type { ApiOutcome } from "./api-client";
import { discoverResources, type DiscoveryResult } from "./gbp-connection";
import {
  confirmLocationMapping,
  removeLocationMapping,
  type GBPMappingMutation,
} from "./gbp";
import type { MappedResource } from "./integrations";

export const ENABLE_PROVIDER_WRITES_CONFIRMATION =
  "Enable provider writes for this Business Profile location? Approved LILOs workflows will be allowed to publish supported changes to Google. Human approval, workflow, audit, and provider verification controls still apply.";

export const DISABLE_PROVIDER_WRITES_CONFIRMATION =
  "Disable provider writes for this Business Profile location? Existing Google data remains unchanged, but new LILOs provider-write operations will be blocked until writes are enabled again.";

export const REMOVE_GBP_MAPPING_CONFIRMATION =
  "Remove this Business Profile mapping from the LILOs location? Provider writes will be disabled and the Google profile will return to the unmapped queue. Nothing is deleted or changed in Google.";

export type GbpWriteGovernance = {
  stateLabel: "Read only" | "Provider writes enabled";
  stateKind: "setup" | "ready";
  actionLabel: "Enable provider writes" | "Disable provider writes" | null;
  confirmationMessage: string | null;
  desiredWriteEnabled: boolean | null;
};

export function gbpWriteGovernanceFor(
  resource: MappedResource,
  canAdminister: boolean,
): GbpWriteGovernance | null {
  if (
    resource.resource_type !== "location" ||
    resource.platform_resource_id === null ||
    resource.gbp_location_id === null ||
    resource.mapping_status !== "confirmed" ||
    resource.write_enabled === null
  ) {
    return null;
  }

  const writeEnabled = resource.write_enabled;
  return {
    stateLabel: writeEnabled ? "Provider writes enabled" : "Read only",
    stateKind: writeEnabled ? "ready" : "setup",
    actionLabel: canAdminister
      ? writeEnabled
        ? "Disable provider writes"
        : "Enable provider writes"
      : null,
    confirmationMessage: canAdminister
      ? writeEnabled
        ? DISABLE_PROVIDER_WRITES_CONFIRMATION
        : ENABLE_PROVIDER_WRITES_CONFIRMATION
      : null,
    desiredWriteEnabled: canAdminister ? !writeEnabled : null,
  };
}

type ConfirmLocationMapping = typeof confirmLocationMapping;
type RemoveLocationMapping = typeof removeLocationMapping;
type DiscoverResources = typeof discoverResources;
type ReconcileWorkspace = () => Promise<void>;

export async function confirmGbpMappingAndReconcile(
  organizationId: string,
  platformLocationId: string,
  gbpLocationId: string,
  writeEnabled: boolean,
  reconcileWorkspace: ReconcileWorkspace,
  confirmMapping: ConfirmLocationMapping = confirmLocationMapping,
): ReturnType<ConfirmLocationMapping> {
  const result = await confirmMapping(
    organizationId,
    platformLocationId,
    gbpLocationId,
    writeEnabled,
  );
  if (result.kind === "ok") {
    await reconcileWorkspace();
  }
  return result;
}

export async function removeGbpMappingAndReconcile(
  organizationId: string,
  platformLocationId: string,
  gbpLocationId: string,
  reconcileWorkspace: ReconcileWorkspace,
  removeMapping: RemoveLocationMapping = removeLocationMapping,
): Promise<ApiOutcome<GBPMappingMutation>> {
  const result = await removeMapping(
    organizationId,
    platformLocationId,
    gbpLocationId,
  );
  if (result.kind === "ok") {
    await reconcileWorkspace();
  }
  return result;
}

export async function discoverGoogleResourcesAndReconcile(
  organizationId: string,
  reconcileWorkspace: ReconcileWorkspace,
  discover: DiscoverResources = discoverResources,
): Promise<ApiOutcome<DiscoveryResult>> {
  const result = await discover(organizationId);
  if (result.kind === "ok") {
    await reconcileWorkspace();
  }
  return result;
}
