import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type GBPAccountSummary = {
  id: string;
  display_name: string;
  account_type: string | null;
  status: string;
  discovered_at: string;
};

export type GBPLocationSummary = {
  id: string;
  business_name: string;
  mapping_status:
    | "unmapped"
    | "suggested"
    | "confirmed"
    | "conflicted"
    | "disconnected"
    | "archived";
  location_id: string | null;
  write_enabled: boolean;
  last_discovered_at: string;
  last_synced_at: string | null;
};

export function fetchGBPAccounts(
  organizationId: string,
): Promise<ApiOutcome<GBPAccountSummary[]>> {
  return apiGet<GBPAccountSummary[]>(
    `/api/v1/organizations/${organizationId}/gbp/accounts`,
  );
}

export function fetchGBPLocations(
  organizationId: string,
): Promise<ApiOutcome<GBPLocationSummary[]>> {
  return apiGet<GBPLocationSummary[]>(
    `/api/v1/organizations/${organizationId}/gbp/locations`,
  );
}

export type PlatformLocation = {
  id: string;
  name: string;
  status: string;
  is_primary: boolean;
};

export function fetchPlatformLocations(
  organizationId: string,
): Promise<ApiOutcome<PlatformLocation[]>> {
  return apiGet<PlatformLocation[]>(
    `/api/v1/organizations/${organizationId}/locations`,
  );
}

export function confirmLocationMapping(
  organizationId: string,
  platformLocationId: string,
  gbpLocationId: string,
  writeEnabled: boolean,
): Promise<
  ApiOutcome<{ id: string; mapping_status: string; write_enabled: boolean }>
> {
  return apiRequest(
    `/api/v1/organizations/${organizationId}/locations/${platformLocationId}/gbp/locations/${gbpLocationId}/confirm`,
    {
      method: "POST",
      body: { location_id: platformLocationId, write_enabled: writeEnabled },
    },
  );
}
