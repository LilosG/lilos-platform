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
