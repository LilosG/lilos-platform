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

export type SearchConsoleKPI = {
  current: number | null;
  previous: number | null;
  delta: number | null;
  percent_delta: number | null;
  quality: string;
};

export type SearchConsolePerformanceReport = {
  connected: boolean;
  properties: {
    id: string;
    external_property_id: string;
    property_type: string;
    freshness_status: string;
    last_synced_at: string | null;
  }[];
  range: {
    start: string;
    end: string;
    days: number;
  } | null;
  comparison_range: {
    start: string;
    end: string;
    days: number;
  } | null;
  freshness: {
    last_synced_at: string | null;
    status: string;
  };
  metrics: Record<string, SearchConsoleKPI>;
  series: {
    date: string;
    clicks: number;
    impressions: number;
    ctr: number;
    position: number;
  }[];
  top_queries: {
    query: string;
    clicks: number;
    impressions: number;
    ctr: number;
    position: number;
  }[];
  top_pages: {
    page: string;
    clicks: number;
    impressions: number;
    ctr: number;
    position: number;
  }[];
};

function seoBase(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}/seo`;
}

export function searchConsoleReportHasData(
  report: SearchConsolePerformanceReport,
): boolean {
  return report.range !== null && Object.keys(report.metrics).length > 0;
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

export async function fetchSearchConsolePerformance(
  organizationId: string,
  websiteId: string,
  days = 28,
): Promise<ApiOutcome<SearchConsolePerformanceReport>> {
  const outcome = await apiGet<SearchConsolePerformanceReport>(
    `${seoBase(organizationId)}/websites/${websiteId}/search-console/performance?days=${days}`,
  );
  if (
    outcome.kind === "ok" &&
    outcome.data.connected &&
    !searchConsoleReportHasData(outcome.data)
  ) {
    return {
      ...outcome,
      data: { ...outcome.data, connected: false },
    };
  }
  return outcome;
}

export function fetchSearchConsoleSummary(
  organizationId: string,
  websiteId: string,
): Promise<ApiOutcome<SearchConsoleSummary>> {
  return apiGet<SearchConsoleSummary>(
    `${seoBase(organizationId)}/websites/${websiteId}/search-console/summary`,
  );
}
