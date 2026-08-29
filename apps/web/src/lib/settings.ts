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

/**
 * Domain lifecycle. The API has supported replacing a domain since it shipped —
 * create, set-primary and archive all exist — but Settings only ever listed
 * them. A domain entered with a typo during onboarding was therefore permanent:
 * onboarding refuses to add a second primary ("the organization already has an
 * active primary domain") and Settings offered no way to change the first.
 */
export function createOrganizationDomain(
  organizationId: string,
  body: { domain: string; is_primary: boolean },
): Promise<ApiOutcome<OrganizationDomain>> {
  return apiRequest<OrganizationDomain>(`${base(organizationId)}/domains`, {
    method: "POST",
    body,
  });
}

export function setPrimaryOrganizationDomain(
  organizationId: string,
  domainId: string,
  expectedVersion: number,
): Promise<ApiOutcome<OrganizationDomain>> {
  return apiRequest<OrganizationDomain>(
    `${base(organizationId)}/domains/${domainId}/set-primary`,
    { method: "POST", body: { expected_version: expectedVersion } },
  );
}

export function archiveOrganizationDomain(
  organizationId: string,
  domainId: string,
  expectedVersion: number,
): Promise<ApiOutcome<OrganizationDomain>> {
  return apiRequest<OrganizationDomain>(
    `${base(organizationId)}/domains/${domainId}/archive`,
    { method: "POST", body: { expected_version: expectedVersion } },
  );
}
