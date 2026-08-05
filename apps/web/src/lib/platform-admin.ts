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

const base = "/api/v1/platform";

export function fetchIndustries(): Promise<ApiOutcome<Industry[]>> {
  return apiGet<Industry[]>(`${base}/industries`);
}

export function fetchOrganizations(): Promise<ApiOutcome<AdminOrganization[]>> {
  return apiGet<AdminOrganization[]>(`${base}/organizations`);
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
