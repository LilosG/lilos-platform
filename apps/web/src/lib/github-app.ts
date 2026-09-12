import { apiGet, apiRequest, type ApiOutcome } from "./api-client";
import { readPublicConfig } from "./config";

export type GitHubRepository = {
  repository_id: string;
  name: string;
  default_branch: string;
  private: boolean;
};

function base(organizationId: string): string {
  return `/api/v1/organizations/${organizationId}/integrations/github`;
}

/**
 * Build the canonical backend callback URL when GitHub returns an App
 * installation to the web Integrations surface.
 *
 * GitHub App Setup URLs are configured at the App level, so an existing App
 * can legitimately return to the frontend instead of the API callback. Keep
 * the backend as the single place that validates the one-time state, verifies
 * the installation with the App JWT, persists the tenant binding, and
 * reconciles repositories/publishing targets by forwarding only GitHub's
 * documented setup parameters.
 */
export function githubInstallCallbackUrl(
  search: string,
  apiBaseUrl: string,
): string | null {
  const params = new URLSearchParams(search);
  const state = params.get("state");
  const installationId = params.get("installation_id");
  const setupAction = params.get("setup_action");
  const error = params.get("error");

  if (!state || (!installationId && !error)) {
    return null;
  }

  const callback = new URLSearchParams({ state });
  if (installationId) callback.set("installation_id", installationId);
  if (setupAction) callback.set("setup_action", setupAction);
  if (error) callback.set("error", error);

  return `${apiBaseUrl.replace(/\/+$/, "")}/api/v1/integrations/github/callback?${callback.toString()}`;
}

function forwardGitHubSetupReturn(): void {
  if (typeof window === "undefined") return;
  if (!/^\/integrations\/?$/.test(window.location.pathname)) return;

  const config = readPublicConfig();
  if (!config) return;

  const callbackUrl = githubInstallCallbackUrl(
    window.location.search,
    config.apiBaseUrl,
  );
  if (callbackUrl) {
    window.location.replace(callbackUrl);
  }
}

// The GitHub integration module is loaded only on product surfaces that use
// GitHub. If GitHub's configured Setup URL returns to /integrations, complete
// the existing canonical backend callback before normal workspace boot runs.
forwardGitHubSetupReturn();

export function beginGitHubInstall(
  organizationId: string,
): Promise<ApiOutcome<{ authorization_url: string }>> {
  return apiRequest<{ authorization_url: string }>(
    `${base(organizationId)}/install`,
    { method: "POST" },
  );
}

export function fetchGitHubRepositories(
  organizationId: string,
): Promise<ApiOutcome<GitHubRepository[]>> {
  return apiGet<GitHubRepository[]>(`${base(organizationId)}/repositories`);
}

export function disconnectGitHub(
  organizationId: string,
): Promise<ApiOutcome<{ status: string }>> {
  return apiRequest<{ status: string }>(`${base(organizationId)}/disconnect`, {
    method: "POST",
  });
}
