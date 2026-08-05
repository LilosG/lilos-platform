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
