/** Integrations control plane API client — provider workspaces and unmapped queue.
 *
 * These functions call the privileged Integrations control plane endpoints
 * mounted under existing Google and GitHub OAuth routers.  They are NOT
 * consumed by ordinary product pages.
 *
 * Mapping confirmation uses the canonical AAL2 GBP endpoint on the product
 * route, never a duplicate Integrations-owned mutation.
 */
import { apiGet, type ApiOutcome } from "./api-client";

// -- Google workspace ---------------------------------------------------------

export type GoogleCapability = {
  key: string;
  label: string;
  enabled: boolean;
};

export type MappedResource = {
  id: string;
  external_resource_id: string;
  platform_resource_id: string | null;
  resource_type: string;
  status: string;
  display_name: string | null;
  last_synced_at: string | null;
  sync_freshness: "fresh" | "stale" | "never";
  gbp_location_id: string | null;
  mapping_status: string | null;
  write_enabled: boolean | null;
};

export type GoogleWorkspace = {
  connection_status: string;
  connection_id: string | null;
  token_expires_at: string | null;
  last_verified_at: string | null;
  capabilities: GoogleCapability[];
  mapped_resources: MappedResource[];
  unmapped_count: number;
};

function googleBase(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}/integrations/google`;
}

export function fetchGoogleWorkspace(
  organizationId: string,
): Promise<ApiOutcome<GoogleWorkspace>> {
  return apiGet<GoogleWorkspace>(`${googleBase(organizationId)}/workspace`);
}

// -- Unmapped resource queue (privileged) -------------------------------------

export type UnmappedResource = {
  id: string;
  external_location_id: string;
  display_name: string;
  primary_category: string | null;
};

export function fetchUnmappedResources(
  organizationId: string,
  search?: string,
): Promise<ApiOutcome<UnmappedResource[]>> {
  const query = search ? `?search=${encodeURIComponent(search)}` : "";
  return apiGet<UnmappedResource[]>(
    `${googleBase(organizationId)}/unmapped${query}`,
  );
}

// -- GitHub workspace ---------------------------------------------------------

export type GitHubRepository = {
  repository_id: string;
  name: string;
  default_branch: string;
  private: boolean;
};

export type GitHubWorkspace = {
  connection_status: string;
  connection_id: string | null;
  external_account_reference: string | null;
  repositories: GitHubRepository[];
};

function githubBase(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}/integrations/github`;
}

export function fetchGitHubWorkspace(
  organizationId: string,
): Promise<ApiOutcome<GitHubWorkspace>> {
  return apiGet<GitHubWorkspace>(`${githubBase(organizationId)}/workspace`);
}

// -- Provider directory (client-assembled from individual status endpoints) ---

export type ProviderDirectoryEntry = {
  provider_key: string;
  provider_name: string;
  description: string;
  status: "connected" | "degraded" | "not_connected" | "not_configured";
  status_label: string;
  requires_attention: boolean;
};
