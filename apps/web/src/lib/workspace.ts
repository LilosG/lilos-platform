import { apiGet, type ApiOutcome } from "./api-client";

export type PrincipalSummary = {
  platform_user_id: string;
  auth_user_id: string;
  user_status: string;
  assurance_level: "aal1" | "aal2";
};

export type MyOrganization = {
  organization_id: string;
  organization_name: string;
  organization_slug: string;
  organization_status: string;
  membership_id: string;
  membership_status: string;
  membership_type: string;
};

export type LocationSummary = {
  id: string;
  name: string;
  status: string;
  is_primary: boolean;
};

export type ReadinessFinding = {
  code: string;
  blocking: boolean;
  resource_key: string | null;
  remediation: string;
};

export type ProductReadiness = {
  ready: boolean;
  readiness_state: "ready" | "blocked" | "not_entitled";
  product_key: string;
  blocking_requirements: ReadinessFinding[];
  warnings: ReadinessFinding[];
};

export const PRODUCT_KEYS = [
  "gbp",
  "reviews",
  "leads",
  "content",
  "seo",
  "insights",
] as const;
export type ProductKey = (typeof PRODUCT_KEYS)[number];

export const PRODUCT_LABELS: Record<ProductKey, string> = {
  gbp: "Business Profile",
  reviews: "Reviews",
  leads: "Leads",
  content: "Content",
  seo: "SEO",
  insights: "Insights",
};

export function fetchPrincipal(): Promise<ApiOutcome<PrincipalSummary>> {
  return apiGet<PrincipalSummary>("/api/v1/me");
}

export function fetchMyOrganizations(): Promise<ApiOutcome<MyOrganization[]>> {
  return apiGet<MyOrganization[]>("/api/v1/me/organizations");
}

export type PlatformAdministratorSelfStatus = {
  is_platform_administrator: boolean;
  meets_required_assurance: boolean;
  required_assurance_level: string;
};

/**
 * Self-scoped only: whether the caller themselves holds a platform-admin
 * grant and whether their current session meets its assurance requirement.
 * Never usable to probe another account — always resolved from the caller's
 * own verified principal server-side.
 */
export function fetchMyPlatformAdministratorStatus(): Promise<
  ApiOutcome<PlatformAdministratorSelfStatus>
> {
  return apiGet<PlatformAdministratorSelfStatus>(
    "/api/v1/me/platform-administrator",
  );
}

export function fetchLocations(
  organizationId: string,
): Promise<ApiOutcome<LocationSummary[]>> {
  return apiGet<LocationSummary[]>(
    `/api/v1/organizations/${organizationId}/locations`,
  );
}

export function fetchProductReadiness(
  organizationId: string,
  productKey: ProductKey,
): Promise<ApiOutcome<ProductReadiness>> {
  return apiGet<ProductReadiness>(
    `/api/v1/organizations/${organizationId}/products/${productKey}/readiness`,
  );
}

export type InsightsSummary = {
  workflow_runs: Record<string, number>;
  gbp: {
    locations: number;
    profile_snapshots: number;
    publications: Record<string, number>;
  };
  reviews: Record<string, number>;
  content_publications: Record<string, number>;
  seo: {
    crawl_runs: Record<string, number>;
    opportunities: Record<string, number>;
  };
  leads: Record<string, number>;
};

export function fetchInsightsSummary(
  organizationId: string,
): Promise<ApiOutcome<InsightsSummary>> {
  return apiGet<InsightsSummary>(
    `/api/v1/organizations/${organizationId}/insights/summary`,
  );
}
