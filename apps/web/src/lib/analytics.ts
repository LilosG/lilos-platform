import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type DiscoveredAnalyticsProperty = {
  external_property_id: string;
  property_number: string;
  display_name: string;
  account_display_name: string;
};

export type AnalyticsDiscovery = {
  properties: DiscoveredAnalyticsProperty[];
  recommended: DiscoveredAnalyticsProperty | null;
};

export type AnalyticsSummary = {
  connected: boolean;
  properties: {
    id: string;
    display_name: string;
    external_property_id: string;
    freshness_status: string;
    last_synced_at: string | null;
  }[];
  metrics: Record<string, number>;
};

export type AnalyticsKPI = {
  label: string;
  current: number | null;
  previous: number | null;
  delta: number | null;
  percent_delta: number | null;
  quality: string;
};

export type AnalyticsPerformanceReport = {
  connected: boolean;
  properties: {
    id: string;
    display_name: string;
    external_property_id: string;
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
  metrics: Record<string, AnalyticsKPI>;
  series: {
    date: string;
    metrics: Record<string, number>;
  }[];
};

function base(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}/insights`;
}

export function analyticsReportHasData(
  report: AnalyticsPerformanceReport,
): boolean {
  return report.range !== null && Object.keys(report.metrics).length > 0;
}

export function discoverAnalytics(
  organizationId: string,
  websiteId?: string,
): Promise<ApiOutcome<AnalyticsDiscovery>> {
  const body = websiteId ? { website_id: websiteId } : {};
  return apiRequest<AnalyticsDiscovery>(
    `${base(organizationId)}/analytics/discover`,
    {
      method: "POST",
      body,
    },
  );
}

export function mapAnalytics(
  organizationId: string,
  selection: {
    external_property_id: string;
    property_number: string;
    display_name: string;
  },
): Promise<ApiOutcome<unknown>> {
  return apiRequest(`${base(organizationId)}/analytics/map`, {
    method: "POST",
    body: selection,
  });
}

export function syncAnalytics(
  organizationId: string,
  analyticsPropertyId: string,
  days = 28,
): Promise<
  ApiOutcome<{ analytics_property_id: string; metrics_synced: number }>
> {
  return apiRequest(
    `${base(organizationId)}/analytics/properties/${analyticsPropertyId}/sync`,
    { method: "POST", body: { days } },
  );
}

export async function fetchAnalyticsPerformance(
  organizationId: string,
  days = 28,
): Promise<ApiOutcome<AnalyticsPerformanceReport>> {
  const outcome = await apiGet<AnalyticsPerformanceReport>(
    `${base(organizationId)}/analytics/performance?days=${days}`,
  );
  if (
    outcome.kind === "ok" &&
    outcome.data.connected &&
    !analyticsReportHasData(outcome.data)
  ) {
    return {
      ...outcome,
      data: { ...outcome.data, connected: false },
    };
  }
  return outcome;
}

export function fetchAnalyticsSummary(
  organizationId: string,
): Promise<ApiOutcome<AnalyticsSummary>> {
  return apiGet<AnalyticsSummary>(`${base(organizationId)}/analytics/summary`);
}
