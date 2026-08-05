import { apiGet, type ApiOutcome } from "./api-client";

export type AdministeredProduct = {
  key: string;
  name: string;
  description: string;
  status: string;
  owning_module: string;
};

export type OrganizationService = {
  id: string;
  key: string;
  name: string;
  status: string;
};

function base(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}`;
}

export function fetchProducts(
  organizationId: string,
): Promise<ApiOutcome<AdministeredProduct[]>> {
  return apiGet<AdministeredProduct[]>(`${base(organizationId)}/products`);
}

export function fetchServices(
  organizationId: string,
): Promise<ApiOutcome<OrganizationService[]>> {
  return apiGet<OrganizationService[]>(`${base(organizationId)}/services`);
}
