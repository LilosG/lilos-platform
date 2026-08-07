import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type OrganizationProfile = {
  id: string;
  organization_id: string;
  brand_name: string | null;
  brand_summary: string | null;
  business_description: string | null;
  value_proposition: string | null;
  target_customer: string | null;
  primary_services: string[] | null;
  approved_claims: string[] | null;
  prohibited_claims: string[] | null;
  tone_guidelines: string[] | null;
  legal_disclaimers: string[] | null;
  default_call_to_action: string | null;
  version: number;
};

export type OrganizationDomain = {
  id: string;
  organization_id: string;
  domain: string;
  is_primary: boolean;
  status: string;
  version: number;
};

function base(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}`;
}

export function fetchOrganizationProfile(
  organizationId: string,
): Promise<ApiOutcome<OrganizationProfile>> {
  return apiGet<OrganizationProfile>(`${base(organizationId)}/profile`);
}

export function replaceOrganizationProfile(
  organizationId: string,
  profile: Omit<OrganizationProfile, "id" | "organization_id" | "version"> & {
    expected_version: number;
  },
): Promise<ApiOutcome<OrganizationProfile>> {
  return apiRequest<OrganizationProfile>(`${base(organizationId)}/profile`, {
    method: "PUT",
    body: profile,
  });
}

export function fetchOrganizationDomains(
  organizationId: string,
): Promise<ApiOutcome<OrganizationDomain[]>> {
  return apiGet<OrganizationDomain[]>(`${base(organizationId)}/domains`);
}
