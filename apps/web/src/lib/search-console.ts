import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type DiscoveredSearchProperty = {
  external_property_id: string;
  property_type: "domain" | "url_prefix";
  permission_level: string;
};

export type SearchConsoleDiscovery = {
  properties: DiscoveredSearchProperty[];
  recommended: DiscoveredSearchProperty | null;
};

export type SearchConsoleSummary = {
  connected: boolean;
  total_clicks: number;
  total_impressions: number;
  properties: {
    id: string;
    external_property_id: string;
    property_type: string;
    freshness_status: string;
    last_synced_at: string | null;
  }[];
};

function seoBase(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}/seo`;
}

export function discoverSearchConsole(
  organizationId: string,
  websiteId: string,
): Promise<ApiOutcome<SearchConsoleDiscovery>> {
  return apiGet<SearchConsoleDiscovery>(
    `${seoBase(organizationId)}/websites/${websiteId}/search-console/discover`,
  );
}

export function mapSearchConsole(
  organizationId: string,
  websiteId: string,
  selection: {
    external_property_id: string;
    property_type: "domain" | "url_prefix";
  },
): Promise<ApiOutcome<unknown>> {
  return apiRequest(
    `${seoBase(organizationId)}/websites/${websiteId}/search-console/map`,
    { method: "POST", body: selection },
  );
}

export function syncSearchConsole(
  organizationId: string,
  websiteId: string,
  searchPropertyId: string,
  days = 28,
): Promise<ApiOutcome<{ search_property_id: string; rows_synced: number }>> {
  return apiRequest(
    `${seoBase(organizationId)}/websites/${websiteId}/search-properties/${searchPropertyId}/sync`,
    { method: "POST", body: { days } },
  );
}

export function fetchSearchConsoleSummary(
  organizationId: string,
  websiteId: string,
): Promise<ApiOutcome<SearchConsoleSummary>> {
  return apiGet<SearchConsoleSummary>(
    `${seoBase(organizationId)}/websites/${websiteId}/search-console/summary`,
  );
}
