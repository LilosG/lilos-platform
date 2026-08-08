import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type AdministeredProduct = {
  /**
   * Product catalog row id (UUID). The backend `GET /products` route serializes
   * the full `Product` row, including `id`; entitlement rows reference this
   * same `id` via `product_id`, so the operator UI needs it to associate
   * entitlements with product keys.
   */
  id: string;
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
  version: number;
};

export type ServiceAssignment = {
  id: string;
  organization_id: string;
  service_id: string;
  scope_type: "organization" | "location";
  location_id: string | null;
  status: "active" | "removed";
  version: number;
};

export type BusinessFactRevision = {
  id: string;
  organization_id: string;
  location_id: string | null;
  fact_identity: string;
  fact_key: string;
  value_type: string;
  value: unknown;
  status: string;
  revision: number;
  authority: string;
};

export type FactResolution = {
  state: "resolved" | "missing" | "ambiguous";
  fact_key: string;
  selected_revision_id: string | null;
  value: unknown;
};

export type ProductEntitlement = {
  id: string;
  organization_id: string;
  product_id: string;
  status: string;
  source: string;
  reason: string;
  version: number;
};

export type PolicyRevision = {
  id: string;
  organization_id: string;
  policy_identity: string;
  policy_key: string;
  category: "general" | "approval" | "notification";
  status: string;
  revision: number;
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

export function createService(
  organizationId: string,
  key: string,
  name: string,
  description?: string,
): Promise<ApiOutcome<OrganizationService>> {
  return apiRequest<OrganizationService>(`${base(organizationId)}/services`, {
    method: "POST",
    body: { key, name, description },
  });
}

export function fetchEffectiveServices(
  organizationId: string,
): Promise<ApiOutcome<ServiceAssignment[]>> {
  return apiGet<ServiceAssignment[]>(
    `${base(organizationId)}/services/effective`,
  );
}

export function assignService(
  organizationId: string,
  serviceId: string,
  scopeType: "organization" | "location",
  locationId?: string,
): Promise<ApiOutcome<ServiceAssignment>> {
  return apiRequest<ServiceAssignment>(
    `${base(organizationId)}/service-assignments`,
    {
      method: "POST",
      body: {
        service_id: serviceId,
        scope_type: scopeType,
        location_id: locationId ?? null,
      },
    },
  );
}

export function removeServiceAssignment(
  organizationId: string,
  assignmentId: string,
  expectedVersion: number,
): Promise<ApiOutcome<ServiceAssignment>> {
  return apiRequest<ServiceAssignment>(
    `${base(organizationId)}/service-assignments/${assignmentId}/remove`,
    { method: "POST", body: { expected_version: expectedVersion } },
  );
}

export function resolveBusinessFact(
  organizationId: string,
  factKey: string,
  locationId?: string,
): Promise<ApiOutcome<FactResolution>> {
  const query = locationId
    ? `?location_id=${encodeURIComponent(locationId)}`
    : "";
  return apiGet<FactResolution>(
    `${base(organizationId)}/business-facts/resolve/${encodeURIComponent(factKey)}${query}`,
  );
}

export function proposeBusinessFact(
  organizationId: string,
  factKey: string,
  valueType: string,
  value: unknown,
  changeReason: string,
  locationId?: string,
): Promise<ApiOutcome<BusinessFactRevision>> {
  return apiRequest<BusinessFactRevision>(
    `${base(organizationId)}/business-facts`,
    {
      method: "POST",
      body: {
        fact_key: factKey,
        value_type: valueType,
        value,
        change_reason: changeReason,
        location_id: locationId ?? null,
        source: "operator_entered",
        authority: "operator_verified",
      },
    },
  );
}

export function decideBusinessFact(
  organizationId: string,
  revisionId: string,
  decision: "approve" | "reject",
): Promise<ApiOutcome<BusinessFactRevision>> {
  return apiRequest<BusinessFactRevision>(
    `${base(organizationId)}/business-facts/${revisionId}/decision`,
    { method: "POST", body: { decision } },
  );
}

export type BusinessFactReconcileResult = {
  proposed: {
    fact_key: string;
    revision_id: string;
    location_id: string | null;
  }[];
  unresolved: string[];
};

export function reconcileBusinessFacts(
  organizationId: string,
): Promise<ApiOutcome<BusinessFactReconcileResult>> {
  return apiRequest<BusinessFactReconcileResult>(
    `${base(organizationId)}/business-facts/reconcile`,
    { method: "POST", body: {} },
  );
}

export function fetchBusinessFactCandidates(
  organizationId: string,
): Promise<ApiOutcome<BusinessFactRevision[]>> {
  return apiGet<BusinessFactRevision[]>(
    `${base(organizationId)}/business-facts/candidates`,
  );
}

export function reconcileDefaultPolicy(
  organizationId: string,
): Promise<ApiOutcome<{ approval_policy_provisioned: boolean }>> {
  return apiRequest<{ approval_policy_provisioned: boolean }>(
    `/api/v1/platform/organizations/${organizationId}/reconcile-defaults`,
    { method: "POST", body: {} },
  );
}

export function fetchProductReadinessDetail(
  organizationId: string,
  productKey: string,
): Promise<ApiOutcome<unknown>> {
  return apiGet<unknown>(
    `${base(organizationId)}/products/${encodeURIComponent(productKey)}/readiness`,
  );
}

export function createEntitlement(
  organizationId: string,
  productKey: string,
  reason: string,
  locationIds: string[] = [],
): Promise<ApiOutcome<ProductEntitlement>> {
  return apiRequest<ProductEntitlement>(
    `${base(organizationId)}/product-entitlements`,
    {
      method: "POST",
      body: {
        product_key: productKey,
        source: "onboarding",
        reason,
        location_ids: locationIds,
      },
    },
  );
}

export function transitionEntitlement(
  organizationId: string,
  entitlementId: string,
  targetStatus: string,
  reason: string,
  expectedVersion: number,
): Promise<ApiOutcome<ProductEntitlement>> {
  return apiRequest<ProductEntitlement>(
    `${base(organizationId)}/product-entitlements/${entitlementId}/transition`,
    {
      method: "POST",
      body: {
        target_status: targetStatus,
        reason,
        expected_version: expectedVersion,
      },
    },
  );
}

export function fetchEffectivePolicies(
  organizationId: string,
  category: "general" | "approval" | "notification",
): Promise<ApiOutcome<PolicyRevision[]>> {
  return apiGet<PolicyRevision[]>(
    `${base(organizationId)}/policies/effective/${category}`,
  );
}

export function createPolicy(
  organizationId: string,
  policyKey: string,
  category: "general" | "approval" | "notification",
  scopeType: "organization" | "location" | "product",
  document: Record<string, unknown>,
  changeReason: string,
): Promise<ApiOutcome<PolicyRevision>> {
  return apiRequest<PolicyRevision>(`${base(organizationId)}/policies`, {
    method: "POST",
    body: {
      policy_key: policyKey,
      category,
      schema_version: 1,
      scope_type: scopeType,
      document,
      change_reason: changeReason,
    },
  });
}

export function approvePolicy(
  organizationId: string,
  revisionId: string,
): Promise<ApiOutcome<PolicyRevision>> {
  return apiRequest<PolicyRevision>(
    `${base(organizationId)}/policies/${revisionId}/approve`,
    { method: "POST" },
  );
}

export type Membership = {
  id: string;
  organization_id: string;
  user_profile_id: string;
  membership_type: "client" | "internal" | "partner";
  status: "invited" | "active" | "suspended" | "revoked" | "expired";
  version: number;
};

export type Invitation = {
  id: string;
  organization_id: string;
  membership_id: string;
  normalized_email: string;
  status: "pending" | "accepted" | "cancelled" | "expired";
  expires_at: string;
  version: number;
};

export type Role = {
  id: string;
  key: string;
  name: string;
  description: string;
};

export function addExistingUser(
  organizationId: string,
  email: string,
  membershipType: "client" | "internal" | "partner" = "client",
): Promise<ApiOutcome<Membership>> {
  return apiRequest<Membership>(`${base(organizationId)}/memberships`, {
    method: "POST",
    body: { email, membership_type: membershipType },
  });
}

export function fetchMemberships(
  organizationId: string,
): Promise<ApiOutcome<Membership[]>> {
  return apiGet<Membership[]>(`${base(organizationId)}/memberships`);
}

export function inviteUser(
  organizationId: string,
  email: string,
  membershipType: "client" | "internal" | "partner" = "client",
): Promise<ApiOutcome<Invitation>> {
  return apiRequest<Invitation>(`${base(organizationId)}/invitations`, {
    method: "POST",
    body: { email, membership_type: membershipType },
  });
}

export function fetchInvitations(
  organizationId: string,
): Promise<ApiOutcome<Invitation[]>> {
  return apiGet<Invitation[]>(`${base(organizationId)}/invitations`);
}

export function fetchRoles(
  organizationId: string,
): Promise<ApiOutcome<Role[]>> {
  return apiGet<Role[]>(`${base(organizationId)}/access/roles`);
}

export function assignRole(
  organizationId: string,
  membershipId: string,
  roleId: string,
  scopeType: "organization" | "location" = "organization",
  locationId?: string,
): Promise<ApiOutcome<unknown>> {
  return apiRequest<unknown>(
    `${base(organizationId)}/memberships/${membershipId}/role-assignments`,
    {
      method: "POST",
      body: {
        role_id: roleId,
        scope_type: scopeType,
        location_id: locationId ?? null,
      },
    },
  );
}
