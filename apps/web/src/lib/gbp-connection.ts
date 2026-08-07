import { apiGet, apiRequest, type ApiOutcome } from "./api-client";

export type GBPConnectionStatus = {
  status:
    | "pending"
    | "connected"
    | "degraded"
    | "reconnect_required"
    | "disconnected";
  token_expires_at: string | null;
  last_verified_at: string | null;
} | null;

function base(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}/integrations/google`;
}

/**
 * Specific, actionable description of a GBP connect attempt failure, used
 * by the /gbp page instead of the generic
 * "The request conflicts with the current resource state." that the
 * backend `PRODUCT_NOT_READY` 409 carries as its `public_message`.
 *
 * The backend rule that Google OAuth requires an effective entitlement
 * (`apps.api.app.routes.integrations._require_effective_entitlement`) is
 * NOT weakened: a missing or non-effective entitlement still fails closed
 * here. This pure classifier only decides how the UI describes that
 * failure to the operator, so it can be unit-tested without a browser.
 */
export type GBPConnectFailureDescription = {
  kind: "product_not_ready" | "generic";
  message: string;
  onboardingHref: string | null;
};

export function describeGbpConnectFailure(
  outcome: ApiOutcome<unknown>,
  organizationId: string,
): GBPConnectFailureDescription {
  if (outcome.kind === "error" && outcome.code === "PRODUCT_NOT_READY") {
    return {
      kind: "product_not_ready",
      message:
        "Google Business Profile is not enabled for this client. Enable it in Client Onboarding before connecting Google.",
      onboardingHref: `/onboarding?org=${encodeURIComponent(organizationId)}`,
    };
  }
  return {
    kind: "generic",
    message: describeConnectFailureGeneric(outcome),
    onboardingHref: null,
  };
}

function describeConnectFailureGeneric(outcome: ApiOutcome<unknown>): string {
  switch (outcome.kind) {
    case "forbidden":
      return "You do not have permission to manage the Google connection for this organization.";
    case "not-found":
      return "The requested resource could not be found.";
    case "disconnected":
      return "Could not reach the platform API.";
    case "unauthenticated":
      return "Your session has expired. Sign in again.";
    case "not-configured":
      return "This deployment is not configured.";
    case "error":
      return outcome.message;
    case "ok":
      return "";
  }
}

export function fetchConnectionStatus(
  organizationId: string,
): Promise<ApiOutcome<GBPConnectionStatus>> {
  return apiGet<GBPConnectionStatus>(`${base(organizationId)}/status`);
}

export function beginConnection(
  organizationId: string,
): Promise<ApiOutcome<{ authorization_url: string }>> {
  return apiRequest<{ authorization_url: string }>(
    `${base(organizationId)}/connect`,
    { method: "POST" },
  );
}

export function disconnectConnection(
  organizationId: string,
): Promise<ApiOutcome<{ status: string }>> {
  return apiRequest<{ status: string }>(`${base(organizationId)}/disconnect`, {
    method: "POST",
  });
}

export type DiscoveryResult = {
  accounts_discovered: number;
  locations_discovered: number;
  profiles_synced: number;
};

export function discoverResources(
  organizationId: string,
): Promise<ApiOutcome<DiscoveryResult>> {
  return apiRequest<DiscoveryResult>(`${base(organizationId)}/discover`, {
    method: "POST",
  });
}

export function syncProfile(
  organizationId: string,
  gbpLocationId: string,
): Promise<
  ApiOutcome<{ snapshot_id: string; content_hash: string; observed_at: string }>
> {
  return apiRequest(`${base(organizationId)}/locations/${gbpLocationId}/sync`, {
    method: "POST",
  });
}
