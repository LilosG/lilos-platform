import { apiGet, type ApiOutcome } from "./api-client";

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
