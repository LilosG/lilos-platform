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
  // The editable detail. Present on every location response; previously
  // omitted from this type because nothing could edit a location, so the
  // fields had nowhere to go.
  address_line_1?: string | null;
  address_line_2?: string | null;
  city?: string | null;
  region?: string | null;
  postal_code?: string | null;
  country_code?: string | null;
  service_area_description?: string | null;
  phone?: string | null;
  email?: string | null;
  website_url?: string | null;
};

/**
 * A correction to an existing location.
 *
 * Only the keys present are sent, and the backend writes only what it is
 * given, so editing the address cannot blank the phone number. `slug` is
 * absent on purpose: it is routing identity, not a detail.
 */
export type UpdateLocationInput = {
  expected_version: number;
  name?: string;
  location_type?: LocationType;
  timezone?: string;
  address_line_1?: string | null;
  address_line_2?: string | null;
  city?: string | null;
  region?: string | null;
  postal_code?: string | null;
  country_code?: string;
  service_area_description?: string | null;
  phone?: string | null;
  email?: string | null;
  website_url?: string | null;
};

export type Industry = {
  id: string;
  key: string;
  name: string;
};

/**
 * Real response shape of `GET /api/v1/platform/industries`:
 * `{ data: { items: [...] }, meta: ... }`. The shared client unwraps the
 * outer `data` envelope, so callers receive `{ items: Industry[] }`.
 */
export type IndustriesResponse = {
  items: Industry[];
};

/**
 * Real paginated response shape used by `GET /api/v1/platform/organizations`
 * and `GET /api/v1/platform/organizations/{id}/locations`:
 * `{ data: { items, limit, offset, next_offset, has_more }, meta }`.
 * `next_offset` is `null` when there is no further page.
 */
export type Paginated<T> = {
  items: T[];
  limit: number;
  offset: number;
  next_offset: number | null;
  has_more: boolean;
};

export type PaginatedOrganizations = Paginated<AdminOrganization>;
export type PaginatedLocations = Paginated<AdminLocation>;

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
  onboarding_mode?: OnboardingResponsibilityMode | null;
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

export type OnboardingResponsibilityMode =
  "managed" | "co_managed" | "self_service";

/**
 * Where a blocker or step is resolved.
 *
 * Blockers used to reach the frontend as bare sentences, so the UI could only
 * print them and the operator had to work out where the control lived. The
 * backend now names the route, the control within it, and the permission that
 * clears it — see `apps/api/app/administration/readiness_codes.py`.
 */
export type BlockerResolution = {
  step_key: OnboardingStepKey | null;
  route: string;
  /** Stable id of the control to scroll to and focus on arrival. */
  control: string;
  permission: string | null;
  label: string;
};

export type OnboardingStep = {
  key: OnboardingStepKey;
  label: string;
  state: "complete" | "incomplete" | "optional_incomplete";
  blocking: boolean;
  detail: string;
  next_action: string | null;
  resolution?: BlockerResolution | null;
};

export type OnboardingBlocker = {
  message: string;
  resolution: BlockerResolution;
  product_name: string | null;
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
  responsibility_mode: OnboardingResponsibilityMode | null;
  steps: OnboardingStep[];
  products: OnboardingProductStatus[];
  /**
   * The blocker sentences. Retained so this client keeps rendering against an
   * API that predates `blocker_details` during a deploy skew; prefer
   * `blocker_details`, which carries where each one is resolved.
   */
  blockers: string[];
  blocker_details?: OnboardingBlocker[];
  warnings: string[];
  progress_percent: number;
  activation_eligible: boolean;
  evaluated_at: string;
};

/**
 * Truthful lifecycle states of a `ProductEntitlement`, mirroring the backend
 * `EntitlementStatus` enum (`apps.api.app.administration.enums`). These are
 * the only values the backend ever writes to `status`; the frontend must
 * render them truthfully rather than inventing its own.
 */
export type EntitlementStatus =
  | "not_enabled"
  | "setup_required"
  | "configuration_required"
  | "connection_required"
  | "ready"
  | "active"
  | "paused"
  | "degraded"
  | "suspended"
  | "archived";

/**
 * Real row shape returned by the platform-administration entitlement routes.
 * The backend `list_product_entitlements`/`create_product_entitlement`/
 * `transition_product_entitlement` handlers serialize the `ProductEntitlement`
 * row's columns verbatim (see `_row` in `routes/platform_administration.py`),
 * so this contract must match those columns exactly — no client-side
 * fabrication.
 */
export type ProductEntitlement = {
  id: string;
  organization_id: string;
  product_id: string;
  status: EntitlementStatus;
  source: string;
  reason: string;
  effective_from: string | null;
  effective_until: string | null;
  activated_at: string | null;
  archived_at: string | null;
  version: number;
  created_at: string;
  updated_at: string;
};

/**
 * Entitlement statuses that the OAuth connect route's
 * `_require_effective_entitlement` treats as *not* effective (a connection
 * attempt fails closed with `PRODUCT_NOT_READY`). Mirrors the backend
 * `NOT_EFFECTIVE_ENTITLEMENT_STATUSES` frozenset exactly. Kept in sync here
 * so the operator UI can render the truthful "not effective" state without
 * a second round-trip.
 */
export const NOT_EFFECTIVE_ENTITLEMENT_STATUSES: ReadonlySet<EntitlementStatus> =
  new Set<EntitlementStatus>(["not_enabled", "archived", "suspended"]);

/**
 * Entitlement statuses the onboarding read model counts as "selected" — i.e.
 * the product is enabled for this client, even if not yet ready. Mirrors the
 * backend `_NOT_SELECTED_ENTITLEMENT_STATUSES` inverse (the onboarding
 * service treats only `not_enabled`/`archived` as not selected). A
 * `setup_required` entitlement therefore counts as selected/effective for
 * the purpose of permitting the GBP OAuth connection.
 */
export const SELECTED_ENTITLEMENT_STATUSES: ReadonlySet<EntitlementStatus> =
  new Set<EntitlementStatus>([
    "setup_required",
    "configuration_required",
    "connection_required",
    "ready",
    "active",
    "paused",
    "degraded",
    "suspended",
  ]);

export type CreateProductEntitlementInput = {
  product_key: string;
  /** Stable operator/onboarding source attribution (audit). */
  source: string;
  /** Truthful audit reason recorded on the entitlement row. */
  reason: string;
  location_ids?: string[];
};

export type TransitionProductEntitlementInput = {
  target_status: EntitlementStatus;
  reason: string;
  expected_version: number;
};

const base = "/api/v1/platform";

export function fetchIndustries(): Promise<ApiOutcome<IndustriesResponse>> {
  return apiGet<IndustriesResponse>(`${base}/industries`);
}

export function fetchOrganizations(): Promise<
  ApiOutcome<PaginatedOrganizations>
> {
  return apiGet<PaginatedOrganizations>(`${base}/organizations`);
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

/**
 * Begin retiring a client — the first of two deliberate steps.
 *
 * The lifecycle engine always supported retirement, but neither transition was
 * exposed, so a client created by mistake (or one that has left) stayed in
 * every switcher and client list permanently.
 */
export function startOffboardingOrganization(
  organizationId: string,
  expectedVersion: number,
): Promise<ApiOutcome<AdminOrganization>> {
  return apiRequest<AdminOrganization>(
    `${base}/organizations/${organizationId}/start-offboarding`,
    { method: "POST", body: { expected_version: expectedVersion } },
  );
}

/**
 * Retire an offboarding client. Archived is terminal — nothing leads out of it
 * through this API — so the caller must confirm before this is reached.
 */
export function archiveOrganization(
  organizationId: string,
  expectedVersion: number,
): Promise<ApiOutcome<AdminOrganization>> {
  return apiRequest<AdminOrganization>(
    `${base}/organizations/${organizationId}/archive`,
    { method: "POST", body: { expected_version: expectedVersion } },
  );
}

export function fetchOrganizationLocations(
  organizationId: string,
): Promise<ApiOutcome<PaginatedLocations>> {
  return apiGet<PaginatedLocations>(
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

/**
 * Correct an existing location's details.
 *
 * A location could be created and retired but never edited, so a typo in the
 * name or a wrong address was permanent and the only way round it was a second
 * location — which then blocked activation, because product readiness
 * evaluates every non-archived location.
 */
export function updateLocation(
  organizationId: string,
  locationId: string,
  command: UpdateLocationInput,
): Promise<ApiOutcome<AdminLocation>> {
  return apiRequest<AdminLocation>(
    `${base}/organizations/${organizationId}/locations/${locationId}`,
    { method: "PATCH", body: command },
  );
}

/**
 * Move the primary designation to this location.
 *
 * The primary location is what GBP mapping and product readiness resolve
 * against, and it could only be chosen at creation time.
 */
export function setPrimaryLocation(
  organizationId: string,
  locationId: string,
  expectedVersion: number,
): Promise<ApiOutcome<AdminLocation>> {
  return apiRequest<AdminLocation>(
    `${base}/organizations/${organizationId}/locations/${locationId}/set-primary`,
    { method: "POST", body: { expected_version: expectedVersion } },
  );
}

/**
 * Retire a location that should not have been created.
 *
 * This is the escape from the two-location trap: readiness evaluates every
 * location that is not archived or closed-permanently, so an unwanted spare
 * blocks activation until it is archived.
 */
export function archiveLocation(
  organizationId: string,
  locationId: string,
  expectedVersion: number,
): Promise<ApiOutcome<AdminLocation>> {
  return apiRequest<AdminLocation>(
    `${base}/organizations/${organizationId}/locations/${locationId}/archive`,
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

export type WebsiteProvisioning = {
  website_id: string | null;
  canonical_origin: string | null;
  website_created: boolean;
  crawl_run_id: string | null;
  crawl_enqueued: boolean;
  skipped_reason: string | null;
};

/**
 * Provision the SEO website implied by the organization's primary domain and
 * queue its first crawl.
 *
 * Activation does this for organizations activated from now on. This is the
 * path for the ones activated before that existed — a configured primary
 * domain and no website — and the recovery path when a crawl never started.
 * Idempotent: safe to press twice.
 */
export function provisionOrganizationWebsite(
  organizationId: string,
): Promise<ApiOutcome<WebsiteProvisioning>> {
  return apiRequest<WebsiteProvisioning>(
    `${base}/organizations/${organizationId}/provision-website`,
    { method: "POST" },
  );
}

export function fetchOnboardingState(
  organizationId: string,
): Promise<ApiOutcome<OnboardingState>> {
  return apiGet<OnboardingState>(
    `${base}/organizations/${organizationId}/onboarding-state`,
  );
}

/**
 * List product entitlements for an organization through the production
 * platform-administration API. The backend serializes each row verbatim
 * (see `ProductEntitlement`); the returned array is the truthful lifecycle
 * state — never fabricated, never a readiness badge that hides an absent
 * entitlement.
 */
export function fetchProductEntitlements(
  organizationId: string,
): Promise<ApiOutcome<ProductEntitlement[]>> {
  return apiGet<ProductEntitlement[]>(
    `${base}/organizations/${organizationId}/product-entitlements`,
  );
}

/**
 * Create a product entitlement for an organization through the production
 * platform-administration API — the same governed
 * `AdministrationService.create_entitlement` service the per-organization
 * route uses, attributed to the authenticated platform administrator. This
 * is the normal-application-flow replacement for the deprecated
 * `scripts/provision_gbp_entitlement.py` script; the resulting
 * `setup_required` entitlement is effective enough to permit the GBP OAuth
 * connection. Does not use the deprecated DB provisioning script.
 */
export function createProductEntitlement(
  organizationId: string,
  command: CreateProductEntitlementInput,
): Promise<ApiOutcome<ProductEntitlement>> {
  return apiRequest<ProductEntitlement>(
    `${base}/organizations/${organizationId}/product-entitlements`,
    {
      method: "POST",
      body: {
        product_key: command.product_key,
        source: command.source,
        reason: command.reason,
        location_ids: command.location_ids ?? [],
      },
    },
  );
}

/**
 * Transition a product entitlement's lifecycle state through the production
 * platform-administration API. The backend enforces the same
 * `ENTITLEMENT_TRANSITIONS` lifecycle guards as the per-organization route:
 * an invalid transition is rejected with `TRANSITION_NOT_ALLOWED` (409)
 * rather than silently applied. Callers must pass the row's current
 * `version` for optimistic-concurrency control. Does not weaken lifecycle
 * guards.
 */
export function transitionProductEntitlement(
  organizationId: string,
  entitlementId: string,
  command: TransitionProductEntitlementInput,
): Promise<ApiOutcome<ProductEntitlement>> {
  return apiRequest<ProductEntitlement>(
    `${base}/organizations/${organizationId}/product-entitlements/${entitlementId}/transition`,
    {
      method: "POST",
      body: {
        target_status: command.target_status,
        reason: command.reason,
        expected_version: command.expected_version,
      },
    },
  );
}

export type SetOnboardingModeInput = {
  mode: OnboardingResponsibilityMode;
  expected_version: number;
};

export function setOnboardingMode(
  organizationId: string,
  command: SetOnboardingModeInput,
): Promise<ApiOutcome<AdminOrganization>> {
  return apiRequest<AdminOrganization>(
    `${base}/organizations/${organizationId}/onboarding-mode`,
    { method: "POST", body: command },
  );
}

export type StepAssignmentInput = {
  step_key: string;
  assigned_to: "agency" | "client";
};

export type StepAssignment = {
  step_key: string;
  assigned_to: string;
  assigned_at?: string;
};

export function assignOnboardingStep(
  organizationId: string,
  command: StepAssignmentInput,
): Promise<ApiOutcome<StepAssignment>> {
  return apiRequest<StepAssignment>(
    `${base}/organizations/${organizationId}/onboarding-assign`,
    { method: "POST", body: command },
  );
}

export function fetchStepAssignments(
  organizationId: string,
): Promise<ApiOutcome<StepAssignment[]>> {
  return apiGet<StepAssignment[]>(
    `${base}/organizations/${organizationId}/onboarding-assign`,
  );
}
