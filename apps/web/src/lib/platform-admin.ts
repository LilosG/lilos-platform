import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type OrganizationType =
  "client" | "internal" | "partner" | "demo" | "test";
export type OrganizationStatus =
  | "prospect"
  | "onboarding"
  | "active"
  | "paused"
  | "suspended"
  | "offboarding"
  | "archived";
export type LocationType = "physical" | "service_area" | "hybrid" | "virtual";
export type LocationStatus =
  | "setup_required"
  | "active"
  | "paused"
  | "closed_temporarily"
  | "closed_permanently"
  | "archived";

export type AdminOrganization = {
  id: string;
  name: string;
  slug: string;
  organization_type: OrganizationType;
  status: OrganizationStatus;
  timezone: string;
  default_currency: string;
  version: number;
};

export type AdminLocation = {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  location_type: LocationType;
  status: LocationStatus;
  timezone: string;
  is_primary: boolean;
  version: number;
};

export type Industry = {
  id: string;
  key: string;
  name: string;
};

export type CreateOrganizationInput = {
  name: string;
  slug: string;
  organization_type: OrganizationType;
  timezone: string;
  default_currency: string;
  industry_id?: string | null;
  website_url?: string | null;
  primary_contact_name?: string | null;
  primary_contact_email?: string | null;
};

export type CreateLocationInput = {
  name: string;
  slug: string;
  location_type: LocationType;
  timezone: string;
  country_code: string;
  address_line_1?: string | null;
  city?: string | null;
  region?: string | null;
  postal_code?: string | null;
  service_area_description?: string | null;
  phone?: string | null;
  website_url?: string | null;
  is_primary?: boolean;
};

export type BootstrapOwnerInput = {
  auth_user_id: string;
  email?: string | null;
  display_name?: string | null;
};

export type BootstrapOwnerResult = {
  user_profile_id: string;
  membership_id: string;
  user_profile_created: boolean;
  membership_created: boolean;
  owner_role_assignment_created: boolean;
};

export type OrganizationProfile = {
  organization_id: string;
  brand_name: string | null;
  business_description: string | null;
  version: number;
};

export type CreateOrganizationProfileInput = {
  brand_name?: string | null;
  brand_summary?: string | null;
  business_description?: string | null;
  value_proposition?: string | null;
  target_customer?: string | null;
  default_call_to_action?: string | null;
};

export type OrganizationDomain = {
  id: string;
  organization_id: string;
  domain: string;
  is_primary: boolean;
  status: "active" | "archived";
  version: number;
};

export type OnboardingStepKey =
  | "organization_profile"
  | "locations"
  | "primary_location"
  | "website_domain"
  | "industry"
  | "services"
  | "users";

export type OnboardingStep = {
  key: OnboardingStepKey;
  label: string;
  state: "complete" | "incomplete" | "optional_incomplete";
  blocking: boolean;
  detail: string;
  next_action: string | null;
};

export type OnboardingProductStatus = {
  product_key: string;
  product_name: string;
  selected: boolean;
  entitlement_status: string | null;
  readiness_state: "ready" | "blocked" | "not_entitled" | null;
  ready: boolean;
  blocking_findings: string[];
  external_integration_pending: boolean;
  next_action: string | null;
};

export type OnboardingState = {
  organization_id: string;
  organization_name: string;
  organization_status: OrganizationStatus;
  organization_version: number;
  steps: OnboardingStep[];
  products: OnboardingProductStatus[];
  blockers: string[];
  warnings: string[];
  progress_percent: number;
  activation_eligible: boolean;
  evaluated_at: string;
};

const base = "/api/v1/platform";

export function fetchIndustries(): Promise<ApiOutcome<Industry[]>> {
  return apiGet<Industry[]>(`${base}/industries`);
}

export function fetchOrganizations(): Promise<ApiOutcome<AdminOrganization[]>> {
  return apiGet<AdminOrganization[]>(`${base}/organizations`);
}

export function fetchOrganization(
  organizationId: string,
): Promise<ApiOutcome<AdminOrganization>> {
  return apiGet<AdminOrganization>(`${base}/organizations/${organizationId}`);
}

export function createOrganization(
  command: CreateOrganizationInput,
): Promise<ApiOutcome<AdminOrganization>> {
  return apiRequest<AdminOrganization>(`${base}/organizations`, {
    method: "POST",
    body: command,
  });
}

export function startOnboarding(
  organizationId: string,
  expectedVersion: number,
): Promise<ApiOutcome<AdminOrganization>> {
  return apiRequest<AdminOrganization>(
    `${base}/organizations/${organizationId}/start-onboarding`,
    { method: "POST", body: { expected_version: expectedVersion } },
  );
}

export function activateOrganization(
  organizationId: string,
  expectedVersion: number,
): Promise<ApiOutcome<AdminOrganization>> {
  return apiRequest<AdminOrganization>(
    `${base}/organizations/${organizationId}/activate`,
    {
      method: "POST",
      body: { expected_version: expectedVersion },
    },
  );
}

export function fetchOrganizationLocations(
  organizationId: string,
): Promise<ApiOutcome<AdminLocation[]>> {
  return apiGet<AdminLocation[]>(
    `${base}/organizations/${organizationId}/locations`,
  );
}

export function createLocation(
  organizationId: string,
  command: CreateLocationInput,
): Promise<ApiOutcome<AdminLocation>> {
  return apiRequest<AdminLocation>(
    `${base}/organizations/${organizationId}/locations`,
    {
      method: "POST",
      body: command,
    },
  );
}

export function activateLocation(
  organizationId: string,
  locationId: string,
  expectedVersion: number,
): Promise<ApiOutcome<AdminLocation>> {
  return apiRequest<AdminLocation>(
    `${base}/organizations/${organizationId}/locations/${locationId}/activate`,
    { method: "POST", body: { expected_version: expectedVersion } },
  );
}

export function bootstrapOwner(
  organizationId: string,
  command: BootstrapOwnerInput,
): Promise<ApiOutcome<BootstrapOwnerResult>> {
  return apiRequest<BootstrapOwnerResult>(
    `${base}/organizations/${organizationId}/owner`,
    {
      method: "POST",
      body: command,
    },
  );
}

export function assignIndustry(
  organizationId: string,
  industryId: string,
  expectedVersion: number,
): Promise<ApiOutcome<AdminOrganization>> {
  return apiRequest<AdminOrganization>(
    `${base}/organizations/${organizationId}/industry`,
    {
      method: "POST",
      body: { industry_id: industryId, expected_version: expectedVersion },
    },
  );
}

export function fetchOrganizationProfile(
  organizationId: string,
): Promise<ApiOutcome<OrganizationProfile | null>> {
  return apiGet<OrganizationProfile | null>(
    `${base}/organizations/${organizationId}/profile`,
  );
}

export function createOrganizationProfile(
  organizationId: string,
  command: CreateOrganizationProfileInput,
): Promise<ApiOutcome<OrganizationProfile>> {
  return apiRequest<OrganizationProfile>(
    `${base}/organizations/${organizationId}/profile`,
    { method: "POST", body: command },
  );
}

export function fetchOrganizationDomains(
  organizationId: string,
): Promise<ApiOutcome<OrganizationDomain[]>> {
  return apiGet<OrganizationDomain[]>(
    `${base}/organizations/${organizationId}/domains`,
  );
}

export function createOrganizationDomain(
  organizationId: string,
  domain: string,
  isPrimary: boolean,
): Promise<ApiOutcome<OrganizationDomain>> {
  return apiRequest<OrganizationDomain>(
    `${base}/organizations/${organizationId}/domains`,
    { method: "POST", body: { domain, is_primary: isPrimary } },
  );
}

export function setPrimaryOrganizationDomain(
  organizationId: string,
  domainId: string,
  expectedVersion: number,
): Promise<ApiOutcome<OrganizationDomain>> {
  return apiRequest<OrganizationDomain>(
    `${base}/organizations/${organizationId}/domains/${domainId}/set-primary`,
    { method: "POST", body: { expected_version: expectedVersion } },
  );
}

export function archiveOrganizationDomain(
  organizationId: string,
  domainId: string,
  expectedVersion: number,
): Promise<ApiOutcome<OrganizationDomain>> {
  return apiRequest<OrganizationDomain>(
    `${base}/organizations/${organizationId}/domains/${domainId}/archive`,
    { method: "POST", body: { expected_version: expectedVersion } },
  );
}

export function fetchOnboardingState(
  organizationId: string,
): Promise<ApiOutcome<OnboardingState>> {
  return apiGet<OnboardingState>(
    `${base}/organizations/${organizationId}/onboarding-state`,
  );
}
